"""Local-process Git byte and loaded-module binding, not a hostile-loader sandbox."""
from __future__ import annotations

import subprocess
import sys
import stat
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
PACKAGING_METADATA_ROOTS = frozenset({
    "packages/pioneer-agent/src/pioneer_agent.egg-info",
    "packages/sanmou-common/src/sanmou_common.egg-info",
})
PACKAGING_METADATA_FILES = frozenset({
    "PKG-INFO", "SOURCES.txt", "dependency_links.txt", "requires.txt", "top_level.txt",
})


class SourceBinding:
    def __init__(self, root: Path):
        self.root = root.absolute()
        self.commit = self.git("rev-parse", "HEAD").decode().strip()
        self.tree = self.git("rev-parse", "HEAD^{tree}").decode().strip()
        self.manifest = {}
        self.modules = {}
        self._blobs = {}
        self.packaging_metadata = None
        self.verify_bytes()
        self.verify_imports()
        self.launcher = self._launcher_info()

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
        packaging_metadata = {}
        for relative in SOURCE_DIRS:
            directory = self.root / relative
            if directory.exists():
                for path in directory.rglob("*"):
                    name = path.relative_to(self.root).as_posix()
                    info = path.lstat()
                    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                        raise InputError("linked_source")
                    if name in PACKAGING_METADATA_ROOTS:
                        if not stat.S_ISDIR(info.st_mode):
                            raise InputError("invalid_packaging_metadata_root:" + name)
                        continue
                    if any(name.startswith(root + "/") for root in PACKAGING_METADATA_ROOTS):
                        parent = path.parent.relative_to(self.root).as_posix()
                        if (parent not in PACKAGING_METADATA_ROOTS or path.name not in PACKAGING_METADATA_FILES
                                or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                                or info.st_mode & 0o111 or info.st_size > 1_000_000):
                            raise InputError("unexpected_packaging_metadata:" + name)
                        raw = safe_path(self.root, name).read_bytes()
                        try:
                            raw.decode("utf-8")
                        except UnicodeDecodeError:
                            raise InputError("nontext_packaging_metadata:" + name) from None
                        if b"\0" in raw or len(raw) > 1_000_000:
                            raise InputError("nontext_packaging_metadata:" + name)
                        packaging_metadata[name] = {"sha256": digest(raw), "bytes": len(raw)}
                        continue
                    if any(part.endswith(".egg-info") for part in path.relative_to(self.root).parts):
                        raise InputError("untracked_source:" + name)
                    if "__pycache__" in path.parts:
                        continue
                    if path.is_file() and name not in manifest:
                        raise InputError("untracked_source:" + name)
        if self.manifest and manifest != self.manifest:
            raise InputError("source_manifest_changed")
        self.manifest = manifest
        if getattr(self, "packaging_metadata", None) is not None and self.packaging_metadata != packaging_metadata:
            raise InputError("packaging_metadata_changed")
        self.packaging_metadata = packaging_metadata

    def verify_imports(self):
        if hasattr(self, "launcher") and self._launcher_info() != self.launcher:
            raise InputError("entrypoint_changed")
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

    def _launcher_info(self):
        main = sys.modules.get("__main__")
        file = getattr(main, "__file__", None)
        spec = getattr(main, "__spec__", None)
        origin = getattr(spec, "origin", None)
        name = getattr(spec, "name", None)
        relative = "packages/pioneer-agent/src/pioneer_agent/app/task_eval.py"
        expected = self.root / relative
        paths_match = bool(file) and Path(file).absolute() == expected
        if spec is not None:
            paths_match = paths_match and bool(origin) and Path(origin).absolute() == expected and name == "pioneer_agent.app.task_eval"
        bound = paths_match and relative in self.manifest
        actual_sha = None
        if bound:
            actual_sha = digest(safe_path(self.root, relative).read_bytes())
            bound = actual_sha == self.manifest[relative]["sha256"]
        return {"bound": bound, "file": file, "spec_origin": origin, "spec_name": name,
                "raw_sha256": actual_sha,
                "mode": ("module" if spec is not None else "direct_script") if bound else "unbound_library_diagnostic"}

    def report(self):
        self.verify_bytes()
        self.verify_imports()
        return {"source_verified": self.launcher["bound"], "module_source_verified": True,
                "launcher": self.launcher, "commit": self.commit, "tree": self.tree,
                "root": str(self.root), "raw_byte_manifest": self.manifest,
                "loaded_modules": self.modules,
                "non_source_metadata": {"kind": "setuptools_egg_info", "git_bound": False,
                    "interpreted_by_evaluator": False, "files": self.packaging_metadata},
                "threat_model": "trusted local process; not hostile monkeypatch/loader proof"}
