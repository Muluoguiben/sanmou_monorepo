"""Local-process Git byte and loaded-module binding, not a hostile-loader sandbox."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ._task_eval_inputs import InputError, digest, safe_path


SOURCE_DIRS = (
    "packages/pioneer-agent/src", "packages/pioneer-agent/config",
    "packages/sanmou-common/src", "packages/sanmou-common/configs",
)
PACKAGE_ROOTS = {
    "pioneer_agent": "packages/pioneer-agent/src/pioneer_agent",
    "sanmou_common": "packages/sanmou-common/src/sanmou_common",
}


class SourceBinding:
    def __init__(self, root: Path):
        self.root = root.absolute()
        self.commit = self.git("rev-parse", "HEAD").decode().strip()
        self.tree = self.git("rev-parse", "HEAD^{tree}").decode().strip()
        self.manifest = {}
        self.modules = {}
        self._blobs = {}
        self.verify_bytes()
        self.verify_imports()

    def git(self, *args) -> bytes:
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True).stdout

    def verify_bytes(self):
        if self.git("rev-parse", "HEAD").decode().strip() != self.commit:
            raise InputError("source_head_changed")
        rows = self.git("ls-tree", "-r", "-z", "HEAD", "--", *SOURCE_DIRS).split(b"\0")
        if not getattr(self, "_blobs", None):
            ids = list(dict.fromkeys(row.split(b"\t", 1)[0].split()[2] for row in rows if row))
            batch = subprocess.run(["git", "-C", str(self.root), "cat-file", "--batch"],
                input=b"\n".join(ids) + b"\n", capture_output=True, check=True).stdout
            self._blobs = {}
            offset = 0
            for blob_id in ids:
                end = batch.index(b"\n", offset)
                sha, kind, size = batch[offset:end].split()
                if sha != blob_id or kind != b"blob":
                    raise InputError("invalid_git_blob")
                offset = end + 1
                self._blobs[sha.decode()] = batch[offset:offset + int(size)]
                offset += int(size) + 1
        manifest = {}
        for row in rows:
            if not row:
                continue
            meta, name = row.split(b"\t", 1)
            mode, kind, blob = meta.decode().split()
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise InputError("nonregular_source")
            relative = name.decode()
            raw = safe_path(self.root, relative).read_bytes()
            committed = self._blobs[blob]
            if raw != committed:
                raise InputError("source_byte_drift:" + relative)
            manifest[relative] = {"blob": blob, "sha256": digest(raw), "bytes": len(raw)}
        if not manifest:
            raise InputError("empty_source_manifest")
        for relative in SOURCE_DIRS:
            directory = self.root / relative
            if directory.exists():
                for path in directory.rglob("*"):
                    if "__pycache__" in path.parts:
                        continue
                    name = path.relative_to(self.root).as_posix()
                    if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
                        raise InputError("linked_source")
                    if path.is_file() and name not in manifest:
                        raise InputError("untracked_source:" + name)
        if self.manifest and manifest != self.manifest:
            raise InputError("source_manifest_changed")
        self.manifest = manifest

    def verify_imports(self):
        observed = {}
        for name, module in list(sys.modules.items()):
            package = name.split(".")[0]
            if package not in PACKAGE_ROOTS or module is None:
                continue
            expected_root = (self.root / PACKAGE_ROOTS[package]).resolve()
            locations = {"file": getattr(module, "__file__", None),
                         "origin": getattr(getattr(module, "__spec__", None), "origin", None)}
            for field, value in locations.items():
                if not value:
                    raise InputError("missing_module_origin:" + name)
                path = Path(value).absolute()
                if not path.resolve().is_relative_to(expected_root):
                    raise InputError("shadow_import:" + name + ":" + field)
                relative = path.relative_to(self.root).as_posix()
                if relative not in self.manifest or digest(safe_path(self.root, relative).read_bytes()) != self.manifest[relative]["sha256"]:
                    raise InputError("module_byte_drift:" + name)
            paths = list(getattr(module, "__path__", []))
            for value in paths:
                path = Path(value).absolute()
                if not path.resolve().is_relative_to(expected_root) or path.is_symlink():
                    raise InputError("shadow_package_path:" + name)
            observed[name] = {**locations, "package_paths": paths}
        if "pioneer_agent.agent_harness.task_runner" not in observed:
            raise InputError("runtime_not_loaded")
        self.modules = observed

    def report(self):
        self.verify_bytes()
        self.verify_imports()
        return {"source_verified": True, "commit": self.commit, "tree": self.tree,
                "root": str(self.root), "raw_byte_manifest": self.manifest,
                "loaded_modules": self.modules,
                "threat_model": "trusted local process; not hostile monkeypatch/loader proof"}
