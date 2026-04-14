"""Tiny eval harness for ImageExtractor over real sgmdtx hero CDN images.

Runs one image at a time through ImageExtractor, resolves the top hero
candidate against the KB, and records hit / miss / unresolved. Used to
measure vision-layer accuracy before and after prompt hardening + fuzzy
resolve tweaks.

Usage:
    PYTHONPATH=src python3 scripts/vision_eval.py
    PYTHONPATH=src python3 scripts/vision_eval.py --out eval_before.json

Writes a JSON report to stdout (or --out). Exit code = number of misses.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PKG_SRC = SCRIPT_DIR.parent / "src"
sys.path.insert(0, str(PKG_SRC))

from qa_agent.knowledge.models import Domain  # noqa: E402
from qa_agent.retrieval.retriever import Retriever  # noqa: E402
from qa_agent.vision.extractor import ImageExtractor  # noqa: E402

KNOWLEDGE_DIR = SCRIPT_DIR.parent / "knowledge_sources"

# (expected canonical name, CDN URL)
FIXTURE: list[tuple[str, str]] = [
    ("诸葛亮", "https://cdn.sgmdtx.com/img/zhu_ge_liang.png"),
    ("关羽", "https://cdn.sgmdtx.com/img/guan_yu.png"),
    ("张飞", "https://cdn.sgmdtx.com/img/zhang_fei.png"),
    ("周瑜", "https://cdn.sgmdtx.com/img/zhou_yu.png"),
    ("吕布", "https://cdn.sgmdtx.com/img/lv_bu.png"),
    ("曹操", "https://cdn.sgmdtx.com/img/cao_cao.png"),
    ("司马懿", "https://cdn.sgmdtx.com/img/si_ma_yi.png"),
    ("姜维", "https://cdn.sgmdtx.com/img/jiang_wei.png"),
    ("孙策", "https://cdn.sgmdtx.com/img/sun_ce.png"),
    ("荀彧", "https://cdn.sgmdtx.com/img/xun_yu.png"),
    ("张辽", "https://cdn.sgmdtx.com/img/zhang_liao.png"),
    ("郝昭", "https://cdn.sgmdtx.com/img/hao_zhao.png"),  # known failure pre-harden
    ("王双", "https://cdn.sgmdtx.com/img/wang_shuang.png"),  # newly ingested
]


@dataclass
class Outcome:
    expected: str
    url: str
    raw_candidates: list[str]
    resolved_topic: str | None
    status: str  # "hit" | "miss" | "unresolved" | "empty"


def _resolve(retriever: Retriever, name: str | None) -> str | None:
    if not name:
        return None
    matches = retriever.index.resolve_term(name, domain=Domain.HERO)
    return matches[0].topic if matches else None


def run_eval(*, baseline: bool) -> list[Outcome]:
    retriever = Retriever.from_knowledge_dir(KNOWLEDGE_DIR)
    if baseline:
        # No whitelist = exactly the pre-harden behavior of the first
        # vision merge. Used to measure the uplift of this PR.
        extractor = ImageExtractor()
    else:
        extractor = ImageExtractor(retriever=retriever)
    outcomes: list[Outcome] = []
    for expected, url in FIXTURE:
        print(f"[eval] {expected} ← {url}", file=sys.stderr)
        result = extractor.extract([url])
        candidates = [h.name for h in result.heroes]
        top = candidates[0] if candidates else None
        resolved = _resolve(retriever, top)
        if not candidates:
            status = "empty"
        elif resolved == expected:
            status = "hit"
        elif resolved is None:
            status = "unresolved"
        else:
            status = "miss"
        outcomes.append(Outcome(expected, url, candidates, resolved, status))
        print(
            f"    → candidates={candidates} resolved={resolved} status={status}",
            file=sys.stderr,
        )
    return outcomes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, help="Write JSON report here")
    ap.add_argument(
        "--baseline",
        action="store_true",
        help="Run without KB whitelist (measures pre-harden accuracy).",
    )
    args = ap.parse_args()

    outcomes = run_eval(baseline=args.baseline)
    hits = sum(1 for o in outcomes if o.status == "hit")
    total = len(outcomes)
    summary = {
        "total": total,
        "hits": hits,
        "accuracy": round(hits / total, 3) if total else 0.0,
        "per_status": {
            s: sum(1 for o in outcomes if o.status == s)
            for s in ("hit", "miss", "unresolved", "empty")
        },
        "outcomes": [asdict(o) for o in outcomes],
    }
    body = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(body, encoding="utf-8")
    else:
        print(body)
    print(
        f"\n[eval] {hits}/{total} hits ({summary['accuracy']*100:.1f}%)",
        file=sys.stderr,
    )
    misses = total - hits
    sys.exit(misses)


if __name__ == "__main__":
    main()
