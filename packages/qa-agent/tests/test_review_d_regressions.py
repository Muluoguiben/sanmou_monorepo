from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from pydantic import ValidationError

from qa_agent.chat.agent import ChatAgent, ChatTurn
from qa_agent.chat.llm_client import LLMResult
from qa_agent.index.search_index import SearchIndex
from qa_agent.ingestion.client_lua_crypto import build_lua_crypto_evidence_report
from qa_agent.ingestion.client_package import scan_client_package
from qa_agent.ingestion.config import AliasConfig, EnumConfig
from qa_agent.ingestion.models import HeroRawRecord, SourceRecord
from qa_agent.ingestion.normalize import normalize_hero_record
from qa_agent.ingestion.publish import publish_entries
from qa_agent.knowledge.loader import load_entries
from qa_agent.knowledge.models import KnowledgeEntry, SkillStaticProfile
from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.retrieval.retriever import Retriever
from qa_agent.service.query_service import QueryService

NO_EVIDENCE_ANSWER = "知识库暂未收录此问题。"
INVALID_CITATION_ANSWER = "回答引用未能与本轮知识库证据核对，请重新提问。"


def entry(**overrides):
    values = dict(id="skill-test", topic="测试战法", domain="skill", entry_kind="skill_profile",
                  facts=["有来源的事实"], source_ref="synthetic-source", updated_at=date(2026, 9, 8),
                  confidence=0.9, structured_data=SkillStaticProfile(name="测试战法", trigger_type="指挥"))
    values.update(overrides)
    return KnowledgeEntry(**values)


class ChatGroundingRegressionTests(unittest.TestCase):
    def client(self, text):
        client = MagicMock()
        client.generate.return_value = LLMResult(text, "fake", 7, 3, 0.1)
        client.generate_json.return_value = ["absent"]
        return client

    def test_empty_evidence_never_calls_answer_model(self):
        client = self.client("UNSUPPORTED CLAIM [invented-id]")
        agent = ChatAgent(Retriever([]), client)
        for _ in range(2):
            reply = agent.ask("absent")
            self.assertEqual(reply.answer, NO_EVIDENCE_ANSWER)
            self.assertEqual(reply.evidence, [])
            self.assertEqual((reply.prompt_tokens, reply.output_tokens, reply.elapsed_s), (0, 0, 0))
        client.generate.assert_not_called()
        client.generate_json.assert_not_called()
        self.assertEqual(agent.history[-1].content, NO_EVIDENCE_ANSWER)

    def test_unrelated_kb_and_prior_history_cannot_trigger_generation_on_miss(self):
        client = self.client("UNSUPPORTED [skill-test]")
        agent = ChatAgent(Retriever([entry()]), client)
        agent.history = [ChatTurn("assistant", "previous answer [skill-test]", ["skill-test"])]
        reply = agent.ask("absent-xyz")
        self.assertEqual(reply.answer, NO_EVIDENCE_ANSWER)
        client.generate.assert_not_called()
        client.generate_json.assert_not_called()

    def test_current_citation_accepted(self):
        answer = "有来源的事实 [skill-test]"
        reply = ChatAgent(Retriever([entry()]), self.client(answer)).ask("测试战法")
        self.assertEqual(reply.answer, answer)
        self.assertEqual(reply.prompt_tokens, 7)

    def test_unknown_missing_and_previous_turn_citations_rejected(self):
        for answer in ("UNSUPPORTED [invented-id]", "UNSUPPORTED", "[skill-test] [old-id]"):
            with self.subTest(answer=answer):
                agent = ChatAgent(Retriever([entry()]), self.client(answer))
                agent.history = [ChatTurn("assistant", "old claim [old-id]", ["old-id"])]
                reply = agent.ask("测试战法")
                self.assertEqual(reply.answer, INVALID_CITATION_ANSWER)
                self.assertEqual(agent.history[-1].content, INVALID_CITATION_ANSWER)


class KnowledgeIntegrityRegressionTests(unittest.TestCase):
    def test_blank_facts_rejected_before_query(self):
        for facts in ([], ["   "], ["\t", "\n", "\u3000"]):
            with self.subTest(facts=facts), self.assertRaises(ValidationError):
                entry(facts=facts)

    def test_mixed_facts_normalized_and_queryable(self):
        item = entry(facts=[" ", " 内容 ", "\t"])
        self.assertEqual(item.facts, ["内容"])
        self.assertIn("内容", QueryService([item]).lookup_topic("测试战法").answer)

    def test_missing_attribute_components_remain_unknown_and_zero_is_known(self):
        raw = HeroRawRecord(canonical_name="测试", base_attributes={"military": 100, "command": 0, "initiative": 12},
                            growth_attributes={"military": 2, "command": 0, "intelligence": 1},
                            source=SourceRecord(source_url="https://example.invalid", source_site="fixture",
                                                source_captured_at=datetime(2026, 9, 8)))
        staged = normalize_hero_record(raw, AliasConfig(), EnumConfig())
        self.assertEqual(staged.entry.structured_data.max_attributes.model_dump(),
                         dict(military=190, intelligence=None, command=0, initiative=None))

    def test_cross_bucket_migration_preserves_canonical_id_and_new_source(self):
        for incoming_id in ("skill-test", "video-new-id"):
            with self.subTest(incoming_id=incoming_id), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                publish_entries([entry(facts=["old-content"], source_ref="old-source")], root)
                updated = entry(id=incoming_id, facts=["new-content"], source_ref="new-source",
                                structured_data=SkillStaticProfile(name="测试战法", trigger_type="主动"))
                publish_entries([updated], root)
                loaded = load_entries(discover_source_paths(root))
                self.assertEqual([e.id for e in loaded], ["skill-test"])
                self.assertEqual(loaded[0].facts, ["new-content"])
                self.assertEqual(loaded[0].source_ref, "new-source")
                self.assertEqual(yaml.safe_load((root / "profiles/skills/command.yaml").read_text()), [])
                self.assertIn("new-content", QueryService(loaded).lookup_topic("测试战法").answer)

    def test_duplicate_loader_and_direct_index_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = yaml.safe_dump([entry().model_dump(mode="json")], allow_unicode=True)
            for name in ("a.yaml", "b.yaml"):
                (root / name).write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_entries(discover_source_paths(root))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            SearchIndex([entry(), entry(facts=["conflict"])])

    def test_conflicting_topic_ids_abort_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, identifier in (("a.yaml", "first-id"), ("b.yaml", "second-id")):
                (root / name).write_text(yaml.safe_dump([entry(id=identifier).model_dump(mode="json")]), encoding="utf-8")
            before = {p.name: p.read_bytes() for p in root.glob("*.yaml")}
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                publish_entries([entry()], root)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.glob("*.yaml")})


class ClientScanRegressionTests(unittest.TestCase):
    def test_root_symlink_and_ancestor_alias_are_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "game-install"
            private = root / "LocalPersistentData"
            private.mkdir(parents=True)
            (private / "account-cache.txt").write_text("SYNTHETIC_PRIVATE_ROOT_MARKER", encoding="utf-8")
            alias = root / "public-root"
            ancestor_alias = Path(tmp) / "game-alias"
            alias.symlink_to(private, target_is_directory=True)
            ancestor_alias.symlink_to(root, target_is_directory=True)
            for scan_root in (alias, ancestor_alias / "LocalPersistentData"):
                for include_runtime_files in (False, True):
                    with self.subTest(scan_root=scan_root, opt_in=include_runtime_files), self.assertRaises(ValueError):
                        scan_client_package(scan_root, include_runtime_files=include_runtime_files)

    def test_runtime_root_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "localpersistentdata"
            root.mkdir()
            (root / "cache.txt").write_text("SYNTHETIC_RUNTIME_OPT_IN", encoding="utf-8")
            with self.assertRaises(ValueError):
                scan_client_package(root)
            self.assertEqual(scan_client_package(root, include_runtime_files=True).included_files, 1)

    def test_windows_reparse_bit_on_root_or_ancestor_is_rejected(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "parent" / "client"
            root.mkdir(parents=True)
            original_lstat = Path.lstat
            for unsafe in (root, root.parent):
                def fake_lstat(path, *args, **kwargs):
                    info = original_lstat(path, *args, **kwargs)
                    if path == unsafe:
                        return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                    return info
                with self.subTest(unsafe=unsafe), patch.object(Path, "lstat", fake_lstat):
                    with self.assertRaises(ValueError):
                        scan_client_package(root)

    def test_symlinks_hardlinks_external_targets_and_version_links_are_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "client"
            private = root / "LocalPersistentData"
            private.mkdir(parents=True)
            target = private / "account-cache.txt"
            target.write_text("SYNTHETIC_PRIVATE_MARKER", encoding="utf-8")
            external = Path(tmp) / "external.txt"
            external.write_text("SYNTHETIC_EXTERNAL_MARKER", encoding="utf-8")
            try:
                (root / "asset.txt").symlink_to(target)
                (root / "external.txt").symlink_to(external)
                (root / "pc_package_info.txt").symlink_to(target)
                (root / "alias-dir").symlink_to(private, target_is_directory=True)
                os.link(target, root / "hard.txt")
            except OSError as exc:
                self.skipTest(f"link creation unavailable: {exc}")
            result = scan_client_package(root).model_dump_json()
            self.assertNotIn("SYNTHETIC_PRIVATE_MARKER", result)
            self.assertNotIn("SYNTHETIC_EXTERNAL_MARKER", result)
            self.assertEqual(scan_client_package(root).included_files, 0)

    def test_swap_between_check_and_open_is_rejected_before_read(self):
        from qa_agent.ingestion import client_package
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim = root / "asset.txt"
            victim.write_text("public", encoding="utf-8")
            secret = root / "LocalPersistentData" / "secret.txt"
            secret.parent.mkdir()
            secret.write_text("SYNTHETIC_PRIVATE_MARKER", encoding="utf-8")
            actual_open = os.open
            def swap(path, flags, *args, **kwargs):
                if Path(path) == victim:
                    victim.unlink()
                    victim.symlink_to(secret)
                return actual_open(path, flags, *args, **kwargs)
            with patch.object(client_package.os, "open", side_effect=swap):
                result = scan_client_package(root)
            self.assertEqual(result.included_files, 0)
            self.assertNotIn("SYNTHETIC_PRIVATE_MARKER", result.model_dump_json())

    def test_safe_file_head_and_hash_bind_same_bytes(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"UnityFS" + b"x" * 200
            (root / "asset.bin").write_bytes(payload)
            result = scan_client_package(root)
            self.assertEqual(result.files[0].sha256, hashlib.sha256(payload).hexdigest())
            self.assertEqual(result.files[0].size_bytes, len(payload))
            self.assertEqual(result.files[0].head_ascii, payload[:64].decode())

    def test_windows_and_posix_payload_paths_only_expose_basename(self):
        for path in (r"C:\Users\SyntheticUser\private-capture\hero.bytes", r"\\server\private\hero.bytes",
                     "/mnt/c/Users/SyntheticUser/private/hero.bytes", "hero.bytes"):
            with self.subTest(path=path):
                report = build_lua_crypto_evidence_report({"payload_block_analysis": [{"file": path}]}, source_id="synthetic")
                self.assertEqual(report.payload_block_samples[0].file_name, "hero.bytes")
                self.assertNotIn("SyntheticUser", report.model_dump_json())


if __name__ == "__main__":
    unittest.main()
