from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.client_package_manifest.v1"

DEFAULT_EXCLUDED_DIRS = {
    "LocalPersistentData",
    "LauncherLog",
    "__pycache__",
}

DEFAULT_EXCLUDED_SUFFIXES = {
    ".db",
    ".log",
}

KNOWLEDGE_SOURCE_FILE_NAMES = {
    "manifest.json",
    "app.info",
    "pc_package_info.txt",
    "boot.config",
    "ScriptingAssemblies.json",
    "RuntimeInitializeOnLoads.json",
    "global-metadata.dat",
}


class ClientPackageFile(BaseModel):
    relative_path: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    modified_at: datetime
    sha256: str = Field(min_length=64, max_length=64)
    extension: str
    head_hex: str
    head_ascii: str
    detected_type: str
    knowledge_value: str
    source_ref: str
    reasons: list[str] = Field(default_factory=list)


class ClientPackageManifest(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_type: str = "nslg_client_install"
    root_name: str
    root_path: str | None = None
    scanned_at: datetime
    scan_policy: dict[str, Any]
    version_info: dict[str, Any] = Field(default_factory=dict)
    total_files_seen: int = Field(ge=0)
    included_files: int = Field(ge=0)
    skipped_files: int = Field(ge=0)
    files: list[ClientPackageFile] = Field(default_factory=list)

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.model_dump(mode="json"), allow_unicode=True, sort_keys=False)


def scan_client_package(
    root: Path,
    *,
    include_absolute_paths: bool = False,
    include_runtime_files: bool = False,
) -> ClientPackageManifest:
    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise NotADirectoryError(root)

    excluded_dirs = set() if include_runtime_files else set(DEFAULT_EXCLUDED_DIRS)
    excluded_suffixes = set() if include_runtime_files else set(DEFAULT_EXCLUDED_SUFFIXES)
    files: list[ClientPackageFile] = []
    total_files_seen = 0
    skipped_files = 0

    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        total_files_seen += 1
        rel = path.relative_to(root).as_posix()
        if _should_skip(path, root, excluded_dirs, excluded_suffixes):
            skipped_files += 1
            continue
        files.append(_scan_file(path, rel))

    version_info = _read_version_info(root)
    root_path = str(root) if include_absolute_paths else None
    return ClientPackageManifest(
        root_name=root.name,
        root_path=root_path,
        scanned_at=datetime.now(timezone.utc),
        scan_policy={
            "include_absolute_paths": include_absolute_paths,
            "include_runtime_files": include_runtime_files,
            "excluded_dirs": sorted(excluded_dirs),
            "excluded_suffixes": sorted(excluded_suffixes),
            "notes": [
                "Default scan skips local persistent data, launcher logs, .db, and .log files.",
                "Manifest is an evidence inventory only; it does not promote client data into knowledge_sources.",
            ],
        },
        version_info=version_info,
        total_files_seen=total_files_seen,
        included_files=len(files),
        skipped_files=skipped_files,
        files=files,
    )


def write_client_package_manifest(manifest: ClientPackageManifest, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(manifest.to_yaml(), encoding="utf-8")


def _should_skip(path: Path, root: Path, excluded_dirs: set[str], excluded_suffixes: set[str]) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(part in excluded_dirs for part in rel_parts[:-1]):
        return True
    return path.suffix.lower() in excluded_suffixes


def _scan_file(path: Path, rel: str) -> ClientPackageFile:
    head = _read_head(path)
    sha256 = _sha256(path)
    detected_type, reasons = _classify_file(path, rel, head)
    knowledge_value = _knowledge_value(path, rel, detected_type, reasons)
    return ClientPackageFile(
        relative_path=rel,
        size_bytes=path.stat().st_size,
        modified_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
        sha256=sha256,
        extension=path.suffix.lower(),
        head_hex=" ".join(f"{b:02X}" for b in head),
        head_ascii="".join(chr(b) if 32 <= b <= 126 else "." for b in head),
        detected_type=detected_type,
        knowledge_value=knowledge_value,
        source_ref=f"NSLG_CLIENT:{rel}#sha256={sha256[:16]}",
        reasons=reasons,
    )


def _read_head(path: Path, limit: int = 64) -> bytes:
    with path.open("rb") as fh:
        return fh.read(limit)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _classify_file(path: Path, rel: str, head: bytes) -> tuple[str, list[str]]:
    name = path.name
    suffix = path.suffix.lower()
    reasons: list[str] = []

    if head.startswith(b"UnityFS") or head.startswith(b"UnityWeb") or head.startswith(b"UnityRaw"):
        reasons.append("Unity asset bundle magic")
        return "unity_asset_bundle", reasons
    if name == "global-metadata.dat":
        reasons.append("IL2CPP metadata filename")
        return "il2cpp_global_metadata", reasons
    if head[:4] == bytes.fromhex("FA B1 1B AF"):
        reasons.append("IL2CPP metadata magic")
        return "il2cpp_global_metadata", reasons
    if name == "manifest.json":
        reasons.append("StreamingAssets version manifest")
        return "nslg_version_manifest", reasons
    if name in {"ScriptingAssemblies.json", "RuntimeInitializeOnLoads.json"}:
        reasons.append("Unity runtime JSON metadata")
        return "unity_runtime_manifest", reasons
    if name in {"app.info", "pc_package_info.txt", "boot.config"}:
        reasons.append("client version/config text")
        return "client_runtime_config", reasons
    if suffix == ".bnk" or head.startswith(b"BKHD"):
        reasons.append("Wwise soundbank")
        return "wwise_soundbank", reasons
    if suffix == ".pak" and "BLWebbrowser" in rel:
        reasons.append("CEF browser language/resource pack")
        return "third_party_cef_pack", reasons
    if suffix in {".dll", ".exe"}:
        reasons.append("native binary")
        return "native_binary", reasons
    if suffix in {".json", ".txt", ".ini", ".config", ".xml"}:
        reasons.append("text/config candidate")
        return "text_config", reasons
    return "unknown_binary", reasons


def _knowledge_value(path: Path, rel: str, detected_type: str, reasons: list[str]) -> str:
    name = path.name
    if name in KNOWLEDGE_SOURCE_FILE_NAMES:
        return "version_or_schema_anchor"
    if detected_type == "unity_asset_bundle":
        return "asset_bundle_candidate"
    if detected_type == "il2cpp_global_metadata":
        return "schema_symbol_candidate"
    if detected_type == "text_config":
        return "text_config_candidate"
    if detected_type == "wwise_soundbank" and "DecodedBanks" in rel:
        return "audio_locale_candidate"
    if detected_type.startswith("third_party"):
        return "low_third_party_runtime"
    if detected_type == "native_binary" and path.name in {"GameAssembly.dll", "NEP2.dll", "UnityPlayer.dll"}:
        return "reverse_engineering_anchor"
    return "low_or_unknown"


def _read_version_info(root: Path) -> dict[str, Any]:
    version_info: dict[str, Any] = {}
    manifest_path = root / "com.bilibili.nslg_Data" / "StreamingAssets" / "assets" / "manifest.json"
    if not manifest_path.exists():
        manifest_path = root / "StreamingAssets" / "assets" / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            version_info["manifest"] = {
                key: manifest.get(key)
                for key in [
                    "ProjectID",
                    "VersionServerUrl",
                    "m_AppVersion",
                    "m_GlobalBundleVersion",
                    "m_StreamingAssetsGlobalBundleVersion",
                    "m_AppGitVersion",
                    "m_GlobalBundleGitVersion",
                    "m_StreamingAssetsGlobalBundleGitVersion",
                    "m_HashCode",
                ]
                if key in manifest
            }
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            version_info["manifest_error"] = str(exc)

    for rel in ["pc_package_info.txt", "com.bilibili.nslg_Data/app.info"]:
        path = root / rel
        if path.exists():
            try:
                version_info[rel] = path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError as exc:
                version_info[f"{rel}_error"] = str(exc)
    return version_info
