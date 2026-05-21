from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.ingestion.client_package import scan_client_package


class ClientPackageScanTests(unittest.TestCase):
    def _make_client_root(self, tmp: Path) -> Path:
        root = tmp / "NSLG Game"
        manifest_dir = root / "com.bilibili.nslg_Data" / "StreamingAssets" / "assets"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "ProjectID": "Windows-Release",
                    "VersionServerUrl": "https://example.invalid/release/ob",
                    "m_AppVersion": "1.29.0",
                    "m_AppGitVersion": "abc123",
                    "m_HashCode": 123,
                    "m_BundleInfos": [],
                }
            ),
            encoding="utf-8",
        )
        data_dir = root / "com.bilibili.nslg_Data"
        (data_dir / "data.unity3d").write_bytes(b"UnityFS\x00fake-bundle")
        metadata_dir = data_dir / "il2cpp_data" / "Metadata"
        metadata_dir.mkdir(parents=True)
        (metadata_dir / "global-metadata.dat").write_bytes(bytes.fromhex("FA B1 1B AF") + b"metadata")
        (root / "GameAssembly.dll").write_bytes(b"MZnative")
        runtime_dir = root / "LocalPersistentData"
        runtime_dir.mkdir()
        (runtime_dir / "account-cache.txt").write_text("runtime", encoding="utf-8")
        (data_dir / "Plugins" / "x86_64").mkdir(parents=True)
        (data_dir / "Plugins" / "x86_64" / "SPLog.db").write_bytes(b"sqlite")
        return root

    def test_scan_skips_runtime_files_and_classifies_assets(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = self._make_client_root(Path(raw_tmp))
            manifest = scan_client_package(root)
        self.assertEqual(manifest.version_info["manifest"]["m_AppVersion"], "1.29.0")
        self.assertEqual(manifest.skipped_files, 2)
        by_path = {file.relative_path: file for file in manifest.files}
        self.assertEqual(by_path["com.bilibili.nslg_Data/data.unity3d"].detected_type, "unity_asset_bundle")
        self.assertEqual(
            by_path["com.bilibili.nslg_Data/il2cpp_data/Metadata/global-metadata.dat"].knowledge_value,
            "version_or_schema_anchor",
        )
        self.assertEqual(by_path["GameAssembly.dll"].knowledge_value, "reverse_engineering_anchor")
        self.assertNotIn("LocalPersistentData/account-cache.txt", by_path)
        self.assertNotIn("com.bilibili.nslg_Data/Plugins/x86_64/SPLog.db", by_path)
        self.assertIsNone(manifest.root_path)

    def test_cli_writes_yaml_manifest(self) -> None:
        from qa_agent.app.scan_nslg_client import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            root = self._make_client_root(tmp)
            output = tmp / "manifest.yaml"
            stdout = io.StringIO()
            with patch.object(sys, "argv", ["scan_nslg_client", "--root", str(root), "--output", str(output)]):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output.read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], "nslg.client_package_manifest.v1")
        self.assertEqual(data["version_info"]["manifest"]["m_AppVersion"], "1.29.0")
        self.assertIn("included_files", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
