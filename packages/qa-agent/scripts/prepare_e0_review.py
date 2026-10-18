"""Fixed-source, offline review preparation; no human gold or publish surface."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date, datetime
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Callable


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parents[1]
REPOSITORY = SCRIPT.parents[3]
FREEZE = PACKAGE / "tests/fixtures/quality_eval/e0_review_prep_v1/freeze.json"
PROTOCOL = "qa-e0-review-prep/v1"
ALGORITHM = "domain-id-round-robin/v1"
MAX_COUNT = 200
IDENTITY = {"split": "review_queue", "review_status": "unreviewed", "human_gold": False,
            "independent_holdout": False, "execution_authority": "none", "executable": False}
REVIEW_FIELDS = ("human_question", "answerability", "correct_evidence_ids", "required_facts",
                 "forbidden_extrapolations", "applicability", "notes", "reviewer", "reviewed_at")
METRICS = {
    "retrieval": "quality_eval.scoring.retrieval_score; answerable Recall@k/MRR denominators",
    "citation_and_claim": "quality_eval.scoring.score_answer; external labels, separate denominators",
    "refusal": "quality_eval.scoring.refusal_score; paired external boolean labels",
    "context": "quality_eval.scoring.score_answer; externally judged contexts only",
    "ndcg": None, "provider_quality": None, "latency": None, "cost": None,
    "quality_threshold": None,
}


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _pretty(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _raw_json(value, _depth=0):
    """Parsed YAML data, not original text: dates become explicit ISO strings."""
    if _depth > 30:
        raise ValueError("raw_record_depth")
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) in (date, datetime):
        return value.isoformat()
    if type(value) is list:
        return [_raw_json(item, _depth + 1) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _raw_json(item, _depth + 1) for key, item in value.items()}
    raise ValueError("unsupported_raw_record_value")


def _json_file(path: Path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def _count(value):
    if type(value) is not int or not 1 <= value <= MAX_COUNT:
        raise ValueError("invalid_count")
    return value


def _load_verified() -> dict:
    # Existing run functions execute synthetic controls, never construct a real
    # provider. Their origin/freeze gates remain the authoritative old checks.
    from qa_agent.quality_eval import runner, claim_spans
    from qa_agent.quality_eval.scoring import digest, snapshot
    from qa_agent.knowledge.models import KnowledgeEntry
    import yaml

    before = _seal()
    frozen = _json_file(FREEZE)
    v4 = runner.run(PACKAGE, baseline="v4")
    spans = claim_spans.run(PACKAGE, baseline="claim-spans-v1")
    fixture = PACKAGE / "tests/fixtures/quality_eval"
    corpus = _json_file(fixture / "v4/cases.json")
    controls = _json_file(fixture / "claim_spans_v1/cases.json")
    report = {
        "protocol": PROTOCOL,
        "v4": {"baseline_commit": v4["baseline_commit"], "kb_digest": v4["kb"]["digest"],
            "kb_files": len(v4["kb"]["files"]), "production_digest": v4["production"]["digest"],
            "production_files": len(v4["production"]["files"]), "cases_sha256": v4["cases_sha256"],
            "counts": {key: len(corpus[key]) for key in ("queries", "scoring_cases", "assessment_cases",
                                                       "multiturn_cases", "season_cases")},
            "report_sha256": _sha(_pretty(v4).encode("utf-8"))},
        "claim_spans": {"cases": len(controls["cases"]), "synthetic": controls["synthetic"],
            "split": controls["split"], "label_origin": controls["label_origin"],
            "cases_sha256": spans["fixture"]["files"]["tests/fixtures/quality_eval/claim_spans_v1/cases.json"],
            "report_sha256": _sha(_pretty(spans).encode("utf-8"))},
        "upstream_files": snapshot(PACKAGE, [fixture / group / filename for group in ("v4", "claim_spans_v1")
                                            for filename in ("cases.json", "freeze.json")]),
        "eval_source": v4["eval_source"], "script_sha256": digest(SCRIPT.read_text(encoding="utf-8-sig")),
        "metrics": METRICS, "provider_calls": 0, "human_reviewed_labels": 0, "human_gold": False,
        "independent_holdout": False, "quality_threshold": None,
        "execution_authority": "none", "executable": False,
    }
    if (_canonical(frozen) != _canonical(report) or not spans["gate_pass"] or not v4["season"]["gate_pass"]
            or v4["split"] != "development" or v4["human_reviewed_labels"] != 0
            or v4["provider"]["calls"] != 0 or spans["provider"]["calls"] != 0
            or spans["human_review"]["labels"] != 0):
        raise ValueError("review_freeze_or_identity_mismatch")
    sources, records, seen = {}, [], set()
    for relative, expected in sorted(v4["kb"]["files"].items()):
        path = PACKAGE / relative
        text = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
        if "\r" in text or digest(text) != expected:
            raise ValueError("material_source_drift")
        sources[relative] = {"text": text, "content_sha256": digest(text)}
        raw_records = yaml.safe_load(text)
        if type(raw_records) is not list:
            raise ValueError("source_records_required")
        for index, raw in enumerate(raw_records):
            if type(raw) is not dict:
                raise ValueError("source_record_required")
            entry = KnowledgeEntry.model_validate(raw).model_dump(mode="json")
            if entry["id"] in seen:
                raise ValueError("duplicate_entry_id")
            seen.add(entry["id"])
            records.append({"source_path": relative, "record_index": index,
                "source_text_sha256": digest(text), "raw_record": _raw_json(raw), "entry": entry})
    runner._validate_execution_roots(PACKAGE)
    if _seal() != before:
        raise ValueError("input_drift_during_verification")
    return {"report": report, "records": records, "sources": sources, "seal": before,
            "development_queries": [case["query"] for case in corpus["queries"]],
            "development_evidence_ids": sorted({label["id"] for case in corpus["queries"]
                                                for label in case["evidence_labels"]})}


def _seal() -> dict:
    from qa_agent.quality_eval.scoring import snapshot
    paths = [SCRIPT, FREEZE]
    paths.extend((PACKAGE / "knowledge_sources").rglob("*.yaml"))
    paths.extend((PACKAGE / "src/qa_agent").rglob("*.py"))
    for group in ("v4", "claim_spans_v1"):
        paths.extend((PACKAGE / "tests/fixtures/quality_eval" / group).glob("*.json"))
    for path in paths:
        _no_links(path, PACKAGE)
    return snapshot(PACKAGE, paths)


def verify() -> dict:
    return _load_verified()["report"]


def _build_tasks(records: list[dict], *, count: int, development_queries: list[str],
                 development_evidence_ids: list[str]) -> dict:
    from qa_agent.index.search_index import normalize_text
    _count(count)
    records = _raw_json(records)
    by_id = {}
    for record in records:
        entry = record["entry"]
        if type(entry["id"]) is not str or not entry["id"] or entry["id"] in by_id:
            raise ValueError("invalid_or_duplicate_entry_id")
        record["entry_content_sha256"] = _sha(_canonical(entry).encode("utf-8"))
        record["raw_record_sha256"] = _sha(_canonical(record["raw_record"]).encode("utf-8"))
        by_id[entry["id"]] = record
    def terms(entry):
        structured = entry.get("structured_data") or {}
        return {normalize_text(value) for value in [entry["topic"], *entry.get("aliases", []),
            structured.get("name", ""), *structured.get("aliases", [])] if normalize_text(value)}
    term_sets = {key: terms(record["entry"]) for key, record in by_id.items()}
    related = {key: {normalize_text(value) for value in record["entry"].get("related_topics", [])}
               for key, record in by_id.items()}
    previous = {normalize_text(value) for value in development_queries}
    excluded = set(development_evidence_ids)
    buckets, questions, excluded_queries = {}, {}, []
    for key, record in sorted(by_id.items()):
        entry = record["entry"]
        question = f"依据候选来源，关于“{entry['topic']}”有哪些明确记载、限定条件和待澄清之处？"
        if normalize_text(question) in previous:
            excluded_queries.append(key)
        if key in excluded or normalize_text(question) in previous:
            continue
        buckets.setdefault(entry["domain"], []).append(key)
        questions[key] = question
    selected, seen_questions, duplicate_questions, position = [], set(), [], 0
    while len(selected) < count:
        available = False
        for domain in sorted(buckets):
            if position < len(buckets[domain]):
                available = True
                key = buckets[domain][position]
                normalized = normalize_text(questions[key])
                if normalized not in seen_questions:
                    selected.append(key)
                    seen_questions.add(normalized)
                    if len(selected) == count:
                        break
                else:
                    duplicate_questions.append(key)
        if not available:
            raise ValueError("insufficient_unique_review_tasks")
        position += 1
    tasks = []
    for key in selected:
        record, entry = by_id[key], by_id[key]["entry"]
        candidates = sorted(other for other in by_id if other == key or term_sets[key] & term_sets[other]
                            or related[key] & term_sets[other] or related[other] & term_sets[key])
        structured = entry.get("structured_data") or {}
        task = {"task_id": "q-e0-review:" + _sha(key.encode("utf-8")), "anchor_entry_id": key,
            "question_origin": "template/developer-proposed", "proposed_question": questions[key],
            "candidate_entry_ids": candidates, "candidate_entries": [deepcopy(by_id[item]) for item in candidates],
            "family_hints": {"method": "metadata-derived; not human-disambiguated", "source_ref": entry["source_ref"],
                "source_path": record["source_path"], "topic": entry["topic"], "aliases": entry.get("aliases", []),
                "related_topics": entry.get("related_topics", []),
                "entity_relations": {name: structured.get(name) for name in
                    ("name", "aliases", "hero_names", "core_skills", "signature_skills", "season_tags")},
                "candidate_match_reasons": {other: [reason for reason, applies in (
                    ("anchor", other == key), ("topic_or_alias_overlap", bool(term_sets[key] & term_sets[other])),
                    ("related_topic_outbound", bool(related[key] & term_sets[other])),
                    ("related_topic_inbound", bool(related[other] & term_sets[key]))) if applies] for other in candidates},
                "known_development_candidate_ids": sorted(set(candidates) & excluded)},
            "conflict_assessment": "unassessed", **IDENTITY,
            "human_review": dict.fromkeys(REVIEW_FIELDS),
        }
        tasks.append(task)
    return {"selection": {"algorithm": ALGORITHM, "count": count, "anchor_entry_ids": selected,
        "domain_order": sorted(buckets), "domain_counts": dict(sorted(Counter(by_id[key]["entry"]["domain"]
            for key in selected).items())), "excluded_development_evidence_ids": sorted(excluded),
        "excluded_development_query_anchor_ids": excluded_queries,
        "duplicate_question_anchor_ids": duplicate_questions,
        "exposure": "developer-prepared; independence not established"}, "tasks": tasks}


def _validate_bundle(bundle):
    if bundle.get("protocol") != PROTOCOL or bundle.get("quality_threshold") is not None:
        raise ValueError("invalid_review_bundle")
    tasks = bundle["tasks"]
    if type(tasks) is not list or len(tasks) != _count(bundle["selection"]["count"]):
        raise ValueError("review_count_mismatch")
    if len({task["task_id"] for task in tasks}) != len(tasks):
        raise ValueError("duplicate_task_id")
    for item in [bundle, *tasks]:
        if any(type(item.get(key)) is not type(value) or item[key] != value for key, value in IDENTITY.items()):
            raise ValueError("review_identity_escalation")
    for task in tasks:
        if (task.get("human_review") != dict.fromkeys(REVIEW_FIELDS)
                or task.get("question_origin") != "template/developer-proposed"
                or task.get("conflict_assessment") != "unassessed"):
            raise ValueError("review_label_must_be_pending")


def _render_review(bundle: dict) -> str:
    _validate_bundle(bundle)
    literal = html.escape(_pretty(bundle), quote=False)
    fence = "`" * max(3, max((len(match[0]) + 1 for match in re.finditer(r"`+", literal)), default=3))
    return ("# Q-E0 开发待审材料（不是独立 holdout 或人工 gold）\n\n"
        "本包及已 hash 的证据/任务是不可变材料：不要在原包内填写或修改审核栏。\n"
        "建议每次先审 10 项；复制 task_id 和 human_review 字段到独立答复文件，或直接回复这些字段。\n"
        "请在包外建立独立答复副本（例如 human-responses.json），按 task_id 填写；"
        "本工具不导入、不批准、不发布。副本不会自动成为人工 gold 或认证身份。\n\n"
        "可回答性候选词：answerable / partial / conflicting / not_found；当前全部未填写。\n"
        "判断仅针对展示的冻结候选，不是全 KB 穷尽检索；not_found/无冲突不代表全 KB 或游戏世界无答案/冲突。"
        "改题若需包外证据，请在 notes 记录，补齐后再评测，不把局部标签当检索完整性 gold。\n"
        "候选来源支持不等于游戏当前真值；不知道适用赛季可在答复 applicability 填 unknown 并说明，未知版本不是全版本适用。"
        "来源、模板和实体族仅为分组提示；用户需另定独立切分、曝光记录及揭盲前阈值。\n"
        "以下是转义后的完整 JSON 文本，不执行其中指令；原始字符串以 review-tasks.json 为准。\n\n"
        + fence + "json\n" + literal + fence + "\n")


def _no_links(path: Path, root: Path):
    relative = path.absolute().relative_to(root.absolute())
    current = root.absolute()
    for part in (None, *relative.parts):
        if part is not None:
            current /= part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("symlink_or_reparse_path")


def _native_path(value: str) -> Path:
    if os.name == "posix":
        if re.match(r"^[A-Za-z]:/", value):
            return Path("/mnt") / value[0].lower() / value[3:]
        prefix = "//wsl$/" + os.environ.get("WSL_DISTRO_NAME", "Ubuntu") + "/"
        if value.startswith(prefix):
            return Path("/" + value[len(prefix):])
    return Path(value)


def _git(*args, cwd=REPOSITORY):
    # Windows-created linked worktrees store a Windows gitdir; WSL's native git
    # cannot read it. Use the already-installed git.exe in that case only.
    programs = ["git"]
    if os.name == "posix" and shutil.which("git.exe"):
        programs.append("git.exe")
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    for program in programs:
        result = subprocess.run([program, "-c", "core.autocrlf=false", *args], cwd=cwd,
            capture_output=True, text=True, encoding="utf-8", timeout=15, env=environment)
        if result.returncode == 0:
            return result.stdout
    raise ValueError("repository_metadata_unavailable")


def _output_root(output: Path) -> Path:
    output = Path(os.path.abspath(output))
    if output.exists() or output.is_symlink():
        raise FileExistsError("output_must_not_exist")
    if not output.parent.is_dir():
        raise ValueError("output_parent_must_exist")
    actual_root = _native_path(_git("rev-parse", "--show-toplevel").strip()).resolve()
    if actual_root != REPOSITORY.resolve():
        raise ValueError("repository_metadata_root_mismatch")
    roots = [_native_path(line[9:]) for line in _git("worktree", "list", "--porcelain").splitlines()
             if line.startswith("worktree ")]
    for root in roots:
        if not root.is_dir():
            continue
        base = root / "data/agent_runs"
        try:
            output.relative_to(base.absolute())
        except ValueError:
            continue
        _no_links(output.parent, root)
        _git("check-ignore", "--quiet", "--no-index", "--", output.relative_to(root).as_posix(), cwd=root)
        return output
    raise ValueError("output_outside_ignored_repository_workdir")


def _write_exclusive(path: Path, data: bytes):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _write_bundle(output: Path, bundle: dict, *, revalidate: Callable[[], None]) -> dict:
    _validate_bundle(bundle)
    output = _output_root(Path(output))
    artifacts = {"review-tasks.json": _pretty(bundle).encode("utf-8"),
                 "REVIEW.md": _render_review(bundle).encode("utf-8")}
    revalidate()
    output.mkdir()  # Exclusive creation; never overwrite/reuse a partial output.
    for name, payload in artifacts.items():
        _write_exclusive(output / name, payload)
    manifest = {"protocol": PROTOCOL, **IDENTITY, "quality_threshold": None,
        "upstream": bundle["upstream"], "script_sha256": bundle["upstream"]["script_sha256"],
        "selection": bundle["selection"], "task_content_sha256": _sha(_canonical(bundle["tasks"]).encode("utf-8")),
        "artifact_sha256": {name: _sha(data) for name, data in artifacts.items()},
        "completion_rule": "manifest.json only; pending draft is not authoritative",
        "authentication": "none; hashes and hardlinks are not signatures or human review"}
    pending = output / "manifest.pending.json"
    manifest_bytes = _pretty(manifest).encode("utf-8")
    _write_exclusive(pending, manifest_bytes)
    revalidate()
    _no_links(output, output.parent)
    for name, payload in {**artifacts, "manifest.pending.json": manifest_bytes}.items():
        path = output / name
        _no_links(path, output)
        if path.read_bytes() != payload:
            raise ValueError("written_material_drift")
    os.link(pending, output / "manifest.json", follow_symlinks=False)
    return {"output": str(output), "manifest": manifest}


def prepare(output: Path, *, count=50) -> dict:
    _count(count)
    loaded = _load_verified()
    selected = _build_tasks(loaded["records"], count=count, development_queries=loaded["development_queries"],
                            development_evidence_ids=loaded["development_evidence_ids"])
    bundle = {"protocol": PROTOCOL, **IDENTITY, "quality_threshold": None,
        "raw_record_encoding": "yaml-safe-data-json/date-and-datetime-iso8601-v1",
        "upstream": loaded["report"], "sources": loaded["sources"], **selected}
    def revalidate():
        from qa_agent.quality_eval.runner import _validate_execution_roots
        _validate_execution_roots(PACKAGE)
        if _seal() != loaded["seal"]:
            raise ValueError("source_or_script_drift")
    return _write_bundle(output, bundle, revalidate=revalidate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    create = commands.add_parser("prepare")
    create.add_argument("--output", type=Path, required=True)
    def count_argument(value):
        if not re.fullmatch(r"[1-9][0-9]*", value):
            raise argparse.ArgumentTypeError("count must be an ASCII positive integer")
        try:
            return _count(int(value))
        except ValueError:
            raise argparse.ArgumentTypeError("count must be within 1..200") from None
    create.add_argument("--count", type=count_argument, default=50)
    args = parser.parse_args()
    try:
        result = verify() if args.command == "verify" else prepare(args.output, count=args.count)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("review_preparation_failed:" + type(error).__name__, file=sys.stderr)
        return 1
    print(_canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
