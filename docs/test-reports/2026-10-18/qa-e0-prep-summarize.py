"""Create-only index of Q-E0 preparation review evidence, including original red."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "qa-e0-prep-independent-results"
FIXED = "b8595f5b24309f9ee67dc27b3dd085adab6db078"
def sha(raw):
    return hashlib.sha256(raw).hexdigest()

records = []
by_tag = {}
for path in sorted(OUT.glob("*.json")):
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or "command" not in record:
        continue
    raw = (OUT / record["log"]).read_bytes()
    assert len(raw) == record["bytes"] and sha(raw) == record["sha256"]
    result = {key: record[key] for key in ("product_source", "review_source", "review_tree",
        "packages_tree", "exit", "timed_out", "tests", "bytes", "sha256", "log")}
    for key in ("errors", "failures", "skipped"):
        found = re.findall((key + r"=(\d+)").encode(), raw)
        result[key] = int(found[-1]) if found else 0
    result["tag"] = path.stem
    records.append(result)
    by_tag[path.stem] = result

expected_counts = {"dedicated-b859": 23, "independent-b859": 9,
    "git-context-b859": 3, "supplemental-b859": 8, "qa-full-b859": 463, "nonutf-b859": 23}
for tag, count in expected_counts.items():
    result = by_tag[tag]
    assert result["product_source"] == FIXED and result["tests"] == count
    assert (result["exit"], result["failures"], result["errors"], result["skipped"]) == (0, 0, 0, 0)
for version in ("v1", "v2", "v3"):
    tag = "qa-" + version + "-b859"
    assert by_tag[tag]["exit"] == 1
    assert b"frozen KB/production source drift" in (OUT / by_tag[tag]["log"]).read_bytes()
assert by_tag["git-context-81c4-original-red"]["failures"] == 3

tree = ast.parse((ROOT / "packages/qa-agent/tests/test_prepare_e0_review.py").read_text(encoding="utf-8"))
inventory = sorted("test_prepare_e0_review." + cls.name + "." + method.name
    for cls in tree.body if isinstance(cls, ast.ClassDef)
    for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith("test_"))
assert len(inventory) == 23
def new_names(log):
    return sorted(re.findall(r"^test_\w+ \((test_prepare_e0_review\.\w+\.test_\w+)\)",
        (OUT / log).read_text(encoding="utf-8"), flags=re.M))
assert new_names("dedicated-b859.log") == inventory
assert new_names("qa-full-b859.log") == inventory
full_names = re.findall(r"^test_\w+ \(([^)]+)\)",
    (OUT / "qa-full-b859.log").read_text(encoding="utf-8"), flags=re.M)
assert len(full_names) == 463 and len(full_names) - len(inventory) == 440

hashes = {"v4": sha((OUT / "qa-v4-b859-output.json").read_bytes()),
    "q04": sha((OUT / "q04-b859-output.json").read_bytes())}
assert hashes == {"v4": "c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c",
    "q04": "b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6"}
verified = json.loads((OUT / "verify-b859.log").read_text(encoding="utf-8"))
frozen = json.loads((ROOT / "packages/qa-agent/tests/fixtures/quality_eval/e0_review_prep_v1/freeze.json").read_text(encoding="utf-8"))
assert verified == frozen
script = (ROOT / "packages/qa-agent/scripts/prepare_e0_review.py").read_text(encoding="utf-8-sig").replace("\r\n", "\n")
assert sha(script.encode("utf-8")) == verified["script_sha256"]
assert verified["provider_calls"] == verified["human_reviewed_labels"] == 0
assert verified["human_gold"] is False and verified["independent_holdout"] is False
assert verified["execution_authority"] == "none" and verified["executable"] is False
assert verified["quality_threshold"] is None
locale = json.loads((OUT / "nonutf-b859.log").read_text(encoding="utf-8").splitlines()[0])
assert locale["default_text_encoding"] == "ANSI_X3.4-1968" and locale["filesystem_encoding"] == "utf-8"
assert locale["utf8_mode"] == 0
summary = dict(decision="APPROVE preparation tool only", product_source=FIXED,
    review_source=by_tag["qa-full-b859"]["review_source"], packages_tree=by_tag["qa-full-b859"]["packages_tree"],
    prior_p2="fixed; original three assertions unchanged and reverified",
    qa_full=dict(total=463, unchanged_existing=440, new_module=23, skipped=0),
    independent_probes=dict(frozen=9, git_context_regression=3, supplemental=8, total=20),
    new_test_inventory=inventory, original_report_sha256=hashes, verify_report_matches_frozen_manifest=True,
    script_sha256=verified["script_sha256"], text_locale=locale, commands=records,
    real_fifty_task_package_generated_by_reviewer=False, user_review_completed=False,
    human_gold=False, independent_holdout=False, q07_quality_gate="open", quality_threshold=None,
    provider_calls=0, execution_authority="none", executable=False, pushes=0)
with (HERE / "qa-e0-prep-independent-summary.json").open("x", encoding="utf-8") as stream:
    json.dump(summary, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps(summary, ensure_ascii=True, indent=2))
