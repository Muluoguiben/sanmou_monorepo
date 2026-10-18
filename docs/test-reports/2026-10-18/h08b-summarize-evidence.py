"""Bounded final index over this review's plain evidence; no original log edits."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
OUT = HERE / "h08b-independent-results"
H09 = Path("/home/lan/projects/sanmou_monorepo/data/agent_runs/h08b-20261018/reviewer-tmp/h09-lf-20261018-independent-r4/report.json")
def digest(raw):
    return hashlib.sha256(raw).hexdigest()

records = []
for path in sorted(OUT.glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "command" not in data:
        continue
    raw = (OUT / data["log"]).read_bytes()
    assert digest(raw) == data["sha256"] and len(raw) == data["bytes"], path.name
    counts = {}
    for key in ("errors", "failures", "skipped"):
        matches = re.findall((key + r"=(\d+)").encode(), raw)
        counts[key] = int(matches[-1]) if matches else 0
    records.append(dict(tag=path.stem, exit=data["exit"], tests=data["tests"],
        **counts, log=data["log"], bytes=len(raw), sha256=digest(raw)))

hashes = {name: digest((OUT / filename).read_bytes()) for name, filename in
    (("qa_v4", "lf-v4-output.json"), ("q04", "lf-q04-output.json"))}
assert hashes == {"qa_v4": "c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c",
    "q04": "b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6"}
audit = json.loads((OUT / "lf-source-audit.log").read_text(encoding="utf-8"))
new_names = sorted(re.findall(r"^test_\w+ \((test_skill_trace_binding\.\w+\.test_\w+)\)",
    (OUT / "lf-dedicated.log").read_text(encoding="utf-8"), flags=re.M))
assert new_names == audit["new_test_inventory"]
if H09.is_file():
    report = json.loads(H09.read_text(encoding="utf-8"))
else:
    timeout = json.loads((OUT / "lf-h09-cli-r4.json").read_text(encoding="utf-8"))
    assert timeout["timed_out"] and timeout["exit"] == 124
    report = dict(complete=False, gate_pass=False, source_verified=False, cases=[],
        outer_collector_timeout=True)
source = report.get("source", {})
if report["gate_pass"]:
    assert source["commit"] == audit["review_head"]
    assert source["tree"] == json.loads((OUT / "lf-h09-cli-r4.json").read_text(encoding="utf-8"))["tree"]
    assert report["complete"] and report["source_verified"] and report["valid_suite"]
    assert source["source_verified"] and source["module_source_verified"] and source["launcher"]["bound"]
    assert len(report["cases"]) == 8 and not report["infra_errors"] and not report["artifact_errors"]
    assert len(report["artifacts"]) == 25
    for relative, expected in report["artifacts"].items():
        target = H09.parent / relative
        assert not Path(relative).is_absolute() and ".." not in Path(relative).parts
        assert target.resolve().is_relative_to(H09.parent.resolve()) and not target.is_symlink()
        assert digest(target.read_bytes()) == expected, relative
    phase_count, state_count = 0, 0
    for case in report["cases"]:
        assert case["score"]["control_pass"] and all(case["score"]["assertions"].values())
        assert not case["score"]["infra_error"] and not case["score"]["safety_violations"]
        assert not case["actual"]["infra_errors"]
        states = [case["actual"]["checkpoint"]["state"]]
        for phase in case["actual"]["phases"]:
            phase_count += 1
            assert phase["budget"]["counts"]["model"] == 0
            assert all(item["request"]["kind"] != "model" for item in phase["budget_snapshot"]["reservations"].values())
            states.append(phase["state"])
        for state in states:
            state_count += 1
            assert state["execution_authority"] == "none" and state["executable"] is False
            assert state["task"]["execution_authority"] == "none" and state["task"]["executable"] is False
paired = {item["log"] for item in records}
unpaired = [dict(log=path.name, bytes=path.stat().st_size, sha256=digest(path.read_bytes()))
    for path in sorted(OUT.glob("*.log")) if path.name not in paired]
summary = dict(product_source=audit["source"], review_source=audit["review_head"],
    packages_tree=audit["packages_tree"], exact_text_files=audit["checked_exact_text_files"],
    workflow_inverse_bytes_and_yaml=audit["workflow_inverse_bytes_and_yaml"],
    new_31_names_exact=True, commands=records, retained_unpaired_logs=unpaired,
    retained_timeout_transcription="h08b-independent-results/lf-h09-cli-r3-outer-timeout.txt",
    whole_output_sha256=hashes,
    h09=dict(path=str(H09), sha256=digest(H09.read_bytes()) if H09.is_file() else None, complete=report["complete"],
        gate_pass=report["gate_pass"], source_verified=report["source_verified"],
        source_commit=source.get("commit"), source_tree=source.get("tree"),
        cases=len(report.get("cases", [])), totals=report.get("totals"),
        artifact_hashes_verified=len(report.get("artifacts", {})),
        read_only_states_verified=state_count if report["gate_pass"] else 0,
        zero_model_phases_verified=phase_count if report["gate_pass"] else 0),
    final_native_ci="pending; this local review is not native acceptance",
    product_edits_by_reviewer=0, provider_calls=0, live_game_or_bridge_actions=0,
    protected_q06_archive_body_reads=0, dependency_installs=0, pushes=0)
with (HERE / "h08b-independent-summary-v2.json").open("x", encoding="utf-8") as stream:
    json.dump(summary, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps(summary, ensure_ascii=True, indent=2))
