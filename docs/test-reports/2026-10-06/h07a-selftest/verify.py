"""Source-bound offline author checks. No archive reads, provider, or live client."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import types

BASE = "110bd7594e095c3ea0e1940ab2fc4bec5f4d7a77"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("source")
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)

    def save(name, data):
        with (out / name).open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    def git(*argv):
        return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *argv])

    def entries(commit):
        result = {}
        for row in git("ls-tree", "-rz", commit).split(b"\0"):
            if row:
                metadata, path = row.split(b"\t")
                result[path.decode()] = metadata.decode()
        return result

    code = git("rev-parse", "HEAD").decode().strip()
    tree = git("rev-parse", "HEAD^{tree}").decode().strip()
    assert code == args.source
    assert not git("diff", "--name-only", "HEAD")
    before, current = entries(BASE), entries(code)
    changed = [name for name in sorted(set(before) | set(current)) if before.get(name) != current.get(name)]
    protected = {name: row for name, row in before.items() if name.startswith((
        "packages/qa-agent/", "packages/sanmou-common/", ".github/", "scripts/"))
        or name.endswith((".tar", ".tar.gz", ".tgz", ".zip"))}
    assert all(current.get(name) == row for name, row in protected.items())
    # Inspect only source/config/test input bytes. Archive protection above is Git metadata only.
    records = {}
    for name, row in current.items():
        if not name.startswith("packages/") or Path(name).suffix not in {".py", ".json", ".yaml", ".yml"}:
            continue
        raw = (root / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        assert blob == row.split()[2], name
        records[name] = {"git_blob": blob, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    save("source.json", {"source": code, "tree": tree, "baseline": BASE, "changed": changed,
        "protected_entries": protected, "source_input_bytes": records, "archive_content_reads": 0})
    save("runtime.json", {"executable": sys.executable, "python": sys.version, "platform": platform.platform(),
        "native": args.native, "model_calls": 0, "live_calls": 0})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    paths = [root / "packages/pioneer-agent/src", root / "packages/qa-agent/src",
             root / "packages/sanmou-common/src", root / "packages/pioneer-agent/tests"]
    env["PYTHONPATH"] = os.pathsep.join(map(str, paths)) + ("" if args.native else os.pathsep + DEPS)
    failures = []

    def run(name, argv, cwd):
        start = time.time()
        with (out / (name + ".log")).open("xb") as handle:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
        row = {"source": code, "tree": tree, "argv": argv, "cwd": str(cwd), "PYTHONPATH": env["PYTHONPATH"],
               "exit": result.returncode, "seconds": time.time() - start}
        save(name + ".command.json", row)
        print(json.dumps({"name": name, **row}), flush=True)
        if result.returncode:
            failures.append(name)

    if args.native:
        run("native-lock", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
            "-p", "test_checkpoint_lock_native.py", "-v"], root / "packages/pioneer-agent")
    else:
        pioneer = root / "packages/pioneer-agent"
        run("focused", [sys.executable, "-B", "-m", "unittest", "test_task_approval", "test_task_runner",
            "test_task_contracts", "test_task_cli", "test_checkpoint_ownership", "test_task_cr_regressions", "-v"], pioneer)
        for package in ("pioneer-agent", "qa-agent", "sanmou-common"):
            run(package + "-full", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
                "-p", "test_*.py", "-v"], root / "packages" / package)
        run("h09-cli", [sys.executable, "-B", "-m", "pioneer_agent.app.task_eval", "--output", str(out / "h09-cli")], root)
        run("qa-v3", [sys.executable, "-B", "-m", "qa_agent.quality_eval.runner", "--baseline", "v3",
            "--output", str(out / "qa-v3.json")], root / "packages/qa-agent")
        sys.path[:0] = [str(path) for path in paths] + [DEPS]
        from test_task_approval import make_runner
        from pioneer_agent.agent_harness.task_contracts import CheckpointEnvelope
        state = asyncio.run(make_runner().run())
        v2 = CheckpointEnvelope(storage_version=2, revision=1, owner_id="synthetic", state=state).model_dump_json()
        old_contracts = types.ModuleType("h07a_actual_old_contracts")
        sys.modules[old_contracts.__name__] = old_contracts
        contract_path = "packages/pioneer-agent/src/pioneer_agent/agent_harness/task_contracts.py"
        old_bytes = git("show", BASE + ":" + contract_path)
        exec(compile(old_bytes, BASE + ":" + contract_path, "exec"), old_contracts.__dict__)
        key = "pioneer_agent.agent_harness.task_contracts"
        current_contracts = sys.modules[key]
        sys.modules[key] = old_contracts
        try:
            old_store = types.ModuleType("h07a_actual_old_store")
            sys.modules[old_store.__name__] = old_store
            store_path = "packages/pioneer-agent/src/pioneer_agent/agent_harness/run_store.py"
            store_bytes = git("show", BASE + ":" + store_path)
            exec(compile(store_bytes, BASE + ":" + store_path, "exec"), old_store.__dict__)
            fixture = root / "packages/pioneer-agent/tests/fixtures/agent_harness/h07a_v1_compat.json"
            legacy = json.loads(fixture.read_text())
            assert old_contracts.RunState.model_validate(legacy).model_dump(mode="json") == legacy
            path = out / "synthetic-v2-checkpoint.json"
            path.write_text(v2, encoding="utf-8")
            try:
                old_store.JsonRunStore(path).load()
            except ValueError as exc:
                rejected = type(exc).__name__
            else:
                raise AssertionError("actual baseline reader accepted v2")
            assert path.read_text() == v2
            save("old-reader.json", {"source": BASE, "contracts_sha256": hashlib.sha256(old_bytes).hexdigest(),
                "store_sha256": hashlib.sha256(store_bytes).hexdigest(), "v1_exact_roundtrip": True,
                "v2_rejected": rejected, "load_unchanged": True})
        finally:
            sys.modules[key] = current_contracts
    assert git("rev-parse", "HEAD").decode().strip() == code
    assert not git("diff", "--name-only", "HEAD")
    hashes = {}
    for path in sorted(out.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            assert len(raw) <= 8 * 1024 * 1024
            hashes[str(path.relative_to(out))] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    save("manifest.json", {"source": code, "tree": tree, "failures": failures, "files": hashes})
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
