"""Model-comparison eval for the task #11 v2 lineup frame extractor.

Runs a fixed representative frame set through {classify → column-crop →
per-column dense vision} for each candidate model and reports the metrics
@muluo-lan / @Spark asked for, with 误填率 (mis-fill rate) as the top-priority
signal:

- frame_kind accuracy (vs hand-labeled expected_kind)
- 误填率: fraction of recognized hero/skill names that DON'T resolve to a KB
  canonical (after subtitle_normalizer) — i.e. hallucination / OCR garbage
- 拒填率: fraction of table columns yielding zero names
- cost: prompt+output tokens per frame
- latency: seconds per frame

Frame set is a JSON list of {path, expected_kind, n_cols}. gpt-5.5 is added
automatically once the gateway serves it (currently 503).

Usage:
    python -m qa_agent.app.eval_lineup_vision \
        --frameset packages/qa-agent/tests/fixtures/lineup_eval_frames.json \
        --models gpt-5.4-mini,gpt-5.4 \
        --out /tmp/lineup_eval_report.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from qa_agent.video.lineup_frame_extractor import (
    TABLE_FRAME_KINDS,
    classify_frame_kind,
    crop_into_columns,
)
from qa_agent.video.subtitle_normalizer import (
    build_dictionary_from_profiles,
    default_homophones_path,
    default_knowledge_sources_dir,
)

# Bump when the classify/extract prompts or crop params change, so eval runs
# (esp. once gpt-5.5 is online) stay comparable. temperature is fixed 0.0.
PROMPT_VERSION = "v2-2026-05-17.1"
CLASSIFY_PROMPT = "只读出这张图最上方的大标题文字，不要识别武将战法。"
COLUMN_PROMPT = "这是单支三国谋定天下队伍配置列，列出该队武将名与战法名。"
CROP_PARAMS = {"overlap_frac": 0.05, "upscale": 3, "top_crop_frac": 0.06}
COLUMN_VISION_PARAMS = {
    "image_detail": "original",
    "reasoning_effort": "high",
    "verbosity": "high",
    "max_tokens": 1200,
}


def _kb_canon_set_and_map(package_root: Path):
    d = build_dictionary_from_profiles(
        knowledge_sources_dir=default_knowledge_sources_dir(package_root),
        homophones_path=default_homophones_path(package_root),
    )
    exact = {r.source: r.canonical for r in d.exact_rules}
    canon = set(d.canonical_terms) | set(exact.values())
    return canon, exact


def _is_misfill(name: str, canon: set[str], exact: dict[str, str]) -> bool:
    n = (name or "").strip()
    if not n:
        return True
    resolved = exact.get(n, n)
    return resolved not in canon


def _classify(extractor, image_inputs) -> str:
    """Cheap low-cost classify pass: just read the title band → kind."""
    r = extractor.extract(
        image_inputs,
        question=CLASSIFY_PROMPT,
        image_detail="low",
        reasoning_effort="low",
        max_tokens=128,
    )
    return classify_frame_kind(list(r.text_snippets) + [r.raw_text or ""])


def main() -> None:
    ap = argparse.ArgumentParser(description="Eval lineup vision models.")
    ap.add_argument("--frameset", required=True)
    ap.add_argument("--models", default="gpt-5.4-mini,gpt-5.4")
    ap.add_argument("--out", default="/tmp/lineup_eval_report.json")
    ap.add_argument("--crop-dir", default="/tmp/bili-chencang-frames/_eval_cols")
    ap.add_argument("--package-root", default=None)
    args = ap.parse_args()

    package_root = (
        Path(args.package_root).resolve()
        if args.package_root
        else Path(__file__).resolve().parents[3]
    )
    frames = json.loads(Path(args.frameset).read_text(encoding="utf-8"))
    canon, exact = _kb_canon_set_and_map(package_root)

    from qa_agent.vision.extractor import ImageExtractor
    from qa_agent.vision.image_loader import prepare_image_inputs

    report: dict = {
        "models": {},
        "frameset": args.frameset,
        "repro": {
            "prompt_version": PROMPT_VERSION,
            "classify_prompt": CLASSIFY_PROMPT,
            "column_prompt": COLUMN_PROMPT,
            "crop_params": CROP_PARAMS,
            "column_vision_params": COLUMN_VISION_PARAMS,
            "temperature": 0.0,
            "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    }
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        try:
            extractor = ImageExtractor(client=_client_for(model))
        except Exception as exc:  # noqa: BLE001
            report["models"][model] = {"available": False, "error": str(exc)[:160]}
            continue
        agg = {
            "available": True,
            "frames": 0,
            "kind_correct": 0,
            "names_total": 0,
            "names_misfill": 0,
            "columns_total": 0,
            "columns_empty": 0,
            "gt_hero_total": 0,
            "gt_hero_hit": 0,
            "gt_skill_total": 0,
            "gt_skill_hit": 0,
            "tokens": 0,
            "latency_s": 0.0,
            "per_frame": [],
        }
        for spec in frames:
            path = spec["path"]
            if not Path(path).exists():
                continue
            agg["frames"] += 1
            t0 = time.monotonic()
            try:
                imgs = prepare_image_inputs([path])
                kind = _classify(extractor, imgs)
            except Exception as exc:  # noqa: BLE001
                agg["per_frame"].append({"path": path, "error": str(exc)[:120]})
                continue
            kind_ok = kind == spec.get("expected_kind")
            agg["kind_correct"] += int(kind_ok)
            frame_rec = {"path": Path(path).name, "kind": kind,
                         "kind_ok": kind_ok, "columns": []}
            if kind in TABLE_FRAME_KINDS:
                n_cols = int(spec.get("n_cols", 3))
                cols = crop_into_columns(
                    path, n_cols, args.crop_dir, **CROP_PARAMS
                )
                for ci, cpath in enumerate(cols):
                    agg["columns_total"] += 1
                    try:
                        cimgs = prepare_image_inputs([cpath])
                        r = extractor.extract(
                            cimgs, question=COLUMN_PROMPT, **COLUMN_VISION_PARAMS
                        )
                    except Exception as exc:  # noqa: BLE001
                        agg["columns_empty"] += 1
                        frame_rec["columns"].append({"col": ci + 1, "error": str(exc)[:100]})
                        continue
                    got_h = [exact.get(e.name, e.name) for e in r.heroes]
                    got_s = [exact.get(e.name, e.name) for e in r.skills]
                    names = [e.name for e in r.heroes] + [e.name for e in r.skills]
                    if not names:
                        agg["columns_empty"] += 1
                    mis = sum(_is_misfill(n, canon, exact) for n in names)
                    agg["names_total"] += len(names)
                    agg["names_misfill"] += mis
                    agg["tokens"] += (r.prompt_tokens or 0) + (r.output_tokens or 0)
                    col_rec = {
                        "col": ci + 1,
                        "heroes": [e.name for e in r.heroes],
                        "skills": [e.name for e in r.skills],
                        "misfill": mis,
                    }
                    # GT accuracy (the metric that actually matters: right
                    # name for THIS team, not just a valid KB name).
                    gt_cols = spec.get("columns_gt")
                    if gt_cols and ci < len(gt_cols):
                        gt_h = set(gt_cols[ci].get("heroes", []))
                        gt_s = set(gt_cols[ci].get("skills", []))
                        if gt_h:
                            hit = len(gt_h & set(got_h))
                            agg["gt_hero_total"] += len(gt_h)
                            agg["gt_hero_hit"] += hit
                            col_rec["hero_recall"] = round(hit / len(gt_h), 2)
                        if gt_s:
                            hit_s = len(gt_s & set(got_s))
                            agg["gt_skill_total"] += len(gt_s)
                            agg["gt_skill_hit"] += hit_s
                            col_rec["skill_recall"] = round(hit_s / len(gt_s), 2)
                    frame_rec["columns"].append(col_rec)
            agg["latency_s"] += time.monotonic() - t0
            agg["per_frame"].append(frame_rec)
        # derived rates
        agg["kind_accuracy"] = round(agg["kind_correct"] / max(1, agg["frames"]), 3)
        agg["misfill_rate"] = round(
            agg["names_misfill"] / max(1, agg["names_total"]), 3
        )
        agg["empty_col_rate"] = round(
            agg["columns_empty"] / max(1, agg["columns_total"]), 3
        )
        agg["avg_latency_s"] = round(agg["latency_s"] / max(1, agg["frames"]), 1)
        agg["gt_hero_recall"] = round(
            agg["gt_hero_hit"] / max(1, agg["gt_hero_total"]), 3
        )
        agg["gt_skill_recall"] = round(
            agg["gt_skill_hit"] / max(1, agg["gt_skill_total"]), 3
        )
        report["models"][model] = agg

    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # compact summary table
    print("model | avail | kind_acc | misfill | hero_recall | skill_recall | empty_col | tokens | avg_lat")
    for m, a in report["models"].items():
        if not a.get("available"):
            print(f"{m} | NO ({a.get('error','')[:40]})")
            continue
        print(
            f"{m} | yes | {a['kind_accuracy']} | {a['misfill_rate']} | "
            f"{a['gt_hero_recall']} | {a['gt_skill_recall']} | "
            f"{a['empty_col_rate']} | {a['tokens']} | {a['avg_latency_s']}s"
        )
    print(f"\nfull report: {args.out}")


def _client_for(model: str):
    """Route each model to its provider. gpt-5.5 lives on the freemodel.dev
    gateway (EVAL_GPT55_*); gpt-5.4* on the default sub2api (OPENAI_*).
    """
    import os

    from qa_agent.chat.openai_client import OpenAIChatClient

    if model.startswith("gpt-5.5"):
        key = os.environ.get("EVAL_GPT55_API_KEY")
        base = os.environ.get("EVAL_GPT55_BASE_URL")
        if not key or not base:
            raise RuntimeError("EVAL_GPT55_API_KEY/BASE_URL not set in .env")
        return OpenAIChatClient(model=model, api_key=key, base_url=base)
    return OpenAIChatClient(model=model)


if __name__ == "__main__":
    main()
