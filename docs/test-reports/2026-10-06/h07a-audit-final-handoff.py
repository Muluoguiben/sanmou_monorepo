"""Read only new, explicitly scoped plain-text author evidence from fixed Git blobs."""
import hashlib
import json
from pathlib import Path
import subprocess

HANDOFF = "f04646cc72cc92f8ea928942dd287b88667fe749"
SOURCE = "b3efd271c79908241b0c7e1acabafbd81c683051"
TREE = "7b81ac676314fce3423e07979849b676758aa87c"
PREFIX = "docs/test-reports/2026-10-06/h07a-selftest/"
OWN = Path("/tmp/h07a-cr-b3-20261006-results")


def blob(path):
    assert path.startswith(PREFIX)
    assert Path(path).suffix in {".json", ".log", ".lock"}
    return subprocess.check_output(["git", "-C", "/home/lan/projects/sanmou_monorepo",
                                    "show", HANDOFF + ":" + path])


def read(path):
    return json.loads(blob(path))


checked = {}
for lane in ("linux-b3efd271", "native-b3efd271"):
    root = PREFIX + lane + "/"
    manifest_bytes = blob(root + "manifest.json")
    manifest = json.loads(manifest_bytes)
    assert (manifest["source"], manifest["tree"], manifest["failures"]) == (SOURCE, TREE, [])
    exits = {}
    for name, expected in manifest["files"].items():
        raw = blob(root + name)
        assert len(raw) == expected["bytes"]
        assert hashlib.sha256(raw).hexdigest() == expected["sha256"], name
        if name.endswith(".command.json"):
            command = json.loads(raw)
            wanted = 1 if name == "independent-original.command.json" else 0
            assert (command["source"], command["tree"], command["exit"], command["expected_exit"]) == (SOURCE, TREE, wanted, wanted)
            exits[name] = command["exit"]
    source = read(root + "source.json")
    own_source = json.loads((OWN / "source.json").read_text())
    assert source["source_input_bytes"] == own_source["source_input_bytes"]
    assert source["protected_entries"] == own_source["protected_entries"]
    checked[lane] = {"verified_files": len(manifest["files"]), "exits": exits,
                     "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest()}

root = PREFIX + "linux-b3efd271/"
assert blob(root + "qa-v3.json") == (OWN / "qa-v3.json").read_bytes()
assert read(root + "h09-cli/report.json")["stable_projection"] == json.loads((OWN / "h09-cli/report.json").read_text())["stable_projection"]
assert read(root + "old-reader.json") == json.loads((OWN / "old-reader.json").read_text())
assert read(root + "independent-probes.json") == json.loads((OWN / "independent-probes.json").read_text())
print(json.dumps({"handoff": HANDOFF, "source": SOURCE, "tree": TREE, "checked": checked,
    "source_byte_binding_equal": True, "qa_v3_bytes_equal": True, "h09_stable_equal": True,
    "actual_old_reader_equal": True, "frozen_probe_hashes_equal": True,
    "archive_member_reads": 0}, indent=2))
