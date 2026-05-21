from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.ingestion.client_runtime_init_registry_probe import (
    build_runtime_init_registry_probe_report,
)


class RuntimeInitRegistryProbeTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "runtime_init_registry_probe_round178.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 178,
                    "slice": "runtime_init_registry_probe",
                    "input_artifacts": [
                        {
                            "file_name": "RuntimeInitializeOnLoads.json",
                            "role": "runtime_initialize_onloads_json",
                            "size_bytes": 2053,
                            "sha256": "a" * 64,
                        },
                        {
                            "file_name": "GameAssembly.dll",
                            "role": "module:GameAssembly.dll",
                            "size_bytes": 94127168,
                            "sha256": "b" * 64,
                        },
                    ],
                    "registry_summary": {
                        "file_name": "RuntimeInitializeOnLoads.json",
                        "present": True,
                        "size_bytes": 2053,
                        "sha256": "a" * 64,
                        "entry_count": 12,
                        "unity_class_entry_count": 4,
                        "non_unity_class_entry_count": 8,
                        "load_type_counts": {"4": 2},
                        "entries": [
                            {
                                "index": 0,
                                "assembly_name": "Assembly-CSharp",
                                "namespace": "NSLGame.Patcher",
                                "class_name": "GameUpdater",
                                "method_name": "InitLuaEnv",
                                "load_types": 4,
                                "is_unity_class": False,
                            }
                        ],
                        "init_lua_env_entries": [
                            {
                                "index": 0,
                                "assembly_name": "Assembly-CSharp",
                                "namespace": "NSLGame.Patcher",
                                "class_name": "GameUpdater",
                                "method_name": "InitLuaEnv",
                                "load_types": 4,
                                "is_unity_class": False,
                            }
                        ],
                        "address_or_token_field_count": 0,
                        "address_or_token_fields": [],
                        "schema_fields": ["assemblyName", "nameSpace", "className"],
                    },
                    "module_records": [
                        {
                            "module": "UnityPlayer.dll",
                            "present": True,
                            "size_bytes": 31099968,
                            "sha256": "c" * 64,
                            "string_hits": {
                                "RuntimeInitializeOnLoads.json": {
                                    "count_capped": 2,
                                    "sample_file_offsets_hex": ["0x1234"],
                                },
                                "InitLuaEnv": {
                                    "count_capped": 0,
                                    "sample_file_offsets_hex": [],
                                },
                            },
                            "pe_summary": {"image_base": "0x180000000"},
                        }
                    ],
                    "unityplayer_runtime_json_xrefs": {
                        "module": "UnityPlayer.dll",
                        "string_hit_count": 2,
                        "code_ref_count": 1,
                        "refs": [
                            {
                                "ref_rva": "0xdfeaa9",
                                "target_rva": "0x1a5a2f0",
                                "section": ".text",
                                "function_begin": "0xdfea90",
                                "function_end": "0xdff1d5",
                            }
                        ],
                    },
                    "counts": {
                        "runtime_initialize_entry_count": 12,
                        "runtime_initialize_init_lua_env_entry_count": 1,
                        "registry_address_or_token_field_count": 0,
                        "module_count": 5,
                        "modules_with_runtime_init_json_hits": 1,
                        "modules_with_init_lua_env_hits": 0,
                        "unityplayer_runtime_json_code_ref_count": 1,
                    },
                    "route_conclusion": {
                        "runtime_initialize_registry_present": True,
                        "init_lua_env_declared_in_registry": True,
                        "registry_contains_native_method_address_or_token": False,
                        "unityplayer_runtime_json_loader_xrefs_found": True,
                        "init_lua_env_native_method_address_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "textasset_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "registry declares InitLuaEnv",
                        "strongest_negative_signal": "registry has no method address",
                        "search_policy": "continue protected metadata ownership",
                    },
                    "evidence_refs": [
                        "NSLG_RUNTIME_INIT_REGISTRY:round178:summary",
                    ],
                    "next_static_targets": ["recover protected metadata ownership"],
                    "limitations": ["registry does not include native addresses"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_registry_probe_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_runtime_init_registry_probe_report(
                input_path=input_path,
                source_id="fixture-runtime-init-registry-probe",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.runtime_init_registry_probe.v1")
        self.assertEqual(report.source_id, "fixture-runtime-init-registry-probe")
        self.assertEqual(report.counts["runtime_initialize_entry_count"], 12)
        self.assertEqual(report.counts["unityplayer_runtime_json_code_ref_count"], 1)
        self.assertEqual(report.registry_summary["init_lua_env_entries"][0]["method_name"], "InitLuaEnv")
        self.assertFalse(report.route_conclusion["registry_contains_native_method_address_or_token"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_runtime_init_registry_probe import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "runtime-init-registry-probe.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_runtime_init_registry_probe",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-runtime-init-registry-probe",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.runtime_init_registry_probe.v1")
        self.assertEqual(data["source_id"], "fixture-runtime-init-registry-probe")
        self.assertEqual(data["counts"]["registry_address_or_token_field_count"], 0)
        self.assertEqual(summary["unityplayer_runtime_json_code_ref_count"], 1)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
