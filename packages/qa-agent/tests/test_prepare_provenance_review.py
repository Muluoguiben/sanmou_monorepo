from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

from qa_agent.knowledge.models import KnowledgeEntry
from qa_agent.knowledge.provenance import entry_digest, load_provenance_json


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_provenance_review", PACKAGE / "scripts/prepare_provenance_review.py")
prep = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prep
SPEC.loader.exec_module(prep)
FIXTURE = PACKAGE / "tests/fixtures/provenance_review_v1/synthetic_inputs.json"


class PrepareProvenanceReviewTests(unittest.TestCase):
    def setUp(self):
        # Deliberately retain task-created scratch and failed outputs; no cleanup command.
        self.scratch = Path(tempfile.mkdtemp(prefix="sanmou-provenance-review-")).resolve()
        self.root = self.scratch / "repository"
        self.root.mkdir()
        self.git("init", "--quiet")
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIs(self.fixture["synthetic"], True)
        items = []
        for document in self.fixture["documents"]:
            path = self.root / document["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            text = (json.dumps(document["document"], ensure_ascii=False, indent=2) + "\n" if document["format"] == "json"
                    else yaml.safe_dump(document["document"], allow_unicode=True, sort_keys=False))
            path.write_text(text, encoding="utf-8")
            item = {"mapping_id": document["category"], "source_category": document["category"],
                    "content_nature": document["nature"], "source_path": document["path"],
                    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            item.update({key: document[key] for key in ("record_pointer", "entity_id_pointer", "entity_name_pointer",
                                                       "entity_namespace", "original_ref_pointer") if key in document})
            items.append(item)
        generator = self.root / prep.SCRIPT_PATH
        generator.parent.mkdir(parents=True, exist_ok=True)
        generator.write_bytes(prep.SCRIPT.read_bytes())
        self.commit = self.commit_all()
        self.mapping = {"protocol": "provenance-review-map-v1", "source_commit": self.commit, "synthetic": True, "items": items}
        self.mapping_path = self.scratch / "mapping.json"
        self.write_mapping()
        self.output = self.scratch / "review-output"

    def git(self, *args):
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
        result = subprocess.run(["git", "-c", "user.name=Synthetic Test", "-c", "user.email=synthetic@example.invalid",
                                 *args], cwd=self.root, env=env, capture_output=True, check=True)
        return result.stdout.decode().strip()

    def commit_all(self):
        self.git("add", "--all")
        self.git("-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "-m", "Synthetic test sources")
        return self.git("rev-parse", "HEAD")

    def write_mapping(self):
        self.mapping_path.write_text(json.dumps(self.mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def run_prepare(self):
        return prep.prepare(self.mapping_path, self.output, repository=self.root)

    def test_three_sources_preserve_exact_file_hashes_nodes_and_qualifiers(self):
        before = {item["source_path"]: (self.root / item["source_path"]).read_bytes() for item in self.mapping["items"]}
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
            result = self.run_prepare()
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(result["report"]["sidecar_count"], 3)
        self.assertEqual(result["report"]["draft_only_count"], 0)
        self.assertEqual(manifest["source_commit"], self.commit)
        self.assertEqual(manifest["generator"]["source_commit"], self.commit)
        self.assertEqual(manifest["generator"]["status"], "committed_exact_bytes")
        self.assertEqual(manifest["mapping_sha256"], hashlib.sha256(self.mapping_path.read_bytes()).hexdigest())
        drafts = json.loads((self.output / "review-drafts.json").read_text())
        by_category = {draft["source"]["category"]: draft for draft in drafts}
        for document in self.fixture["documents"]:
            draft = by_category[document["category"]]
            expected = prep._pointer(document["document"], document["record_pointer"])
            self.assertEqual(draft["source_node"], expected)
            self.assertEqual(json.loads(draft["content"]), expected)
            self.assertEqual(draft["content_sha256"], hashlib.sha256(draft["content"].encode()).hexdigest())
        for source in manifest["sources"]:
            self.assertEqual(source["sha256"], hashlib.sha256(before[source["path"]]).hexdigest())
            self.assertEqual((self.root / source["path"]).read_bytes(), before[source["path"]])
        for name, item in manifest["artifacts"].items():
            self.assertEqual(item["sha256"], hashlib.sha256((self.output / name).read_bytes()).hexdigest())

    def test_legacy_binding_is_exact_content_not_human_review(self):
        self.run_prepare()
        sidecars = load_provenance_json((self.output / "sidecars.json").read_text())
        basic = next(item for item in sidecars if item.source.category.value == "basic_knowledge")
        expected = KnowledgeEntry.model_validate(self.fixture["documents"][0]["document"][0])
        self.assertEqual(basic.legacy_entry_id, expected.id)
        self.assertEqual(basic.legacy_entry_sha256, entry_digest(expected))
        for item in sidecars:
            self.assertEqual(item.review.status, "unreviewed")
            self.assertIsNone(item.source.author)
            self.assertIsNone(item.source.published_at)
            self.assertIsNone(item.source.collected_at)
            self.assertIsNone(item.applicability.game_version)
            self.assertEqual(item.applicability.season_tags, ())
            self.assertFalse(item.knowledge_publishable)
            self.assertFalse(item.human_gold)
            self.assertEqual(item.execution_authority, "none")

    def test_unresolved_entity_produces_only_draft_without_guessing(self):
        for field in ("entity_id_pointer", "entity_name_pointer", "entity_namespace"):
            self.mapping["items"][2].pop(field)
        self.write_mapping()
        result = self.run_prepare()
        self.assertEqual(result["report"]["sidecar_count"], 2)
        self.assertEqual(result["report"]["draft_only_count"], 1)
        guide = next(item for item in json.loads((self.output / "review-drafts.json").read_text()) if item["mapping_id"] == "player_guide")
        self.assertIsNone(guide["source_identity"])
        self.assertIn("entity_correspondence_unresolved", guide["gaps"])
        self.assertTrue(all(value is None for value in guide["human_review"].values()))

    def test_exact_mapping_and_sidecar_duplicates_are_counted(self):
        self.mapping["items"].append(copy.deepcopy(self.mapping["items"][0]))
        another = copy.deepcopy(self.mapping["items"][0])
        another["mapping_id"] = "another-input-id"
        self.mapping["items"].append(another)
        self.write_mapping()
        report = self.run_prepare()["report"]
        self.assertEqual(report["input_count"], 5)
        self.assertEqual(report["exact_mapping_duplicates"], 1)
        self.assertEqual(report["sidecar_exact_duplicates"], 1)
        self.assertEqual(report["sidecar_count"], 3)

    def test_same_import_identity_conflicts_are_retained_for_review(self):
        other = copy.deepcopy(self.mapping["items"][2])
        other.update(mapping_id="alternate-origin", original_ref_pointer="/0/alternate_ref")
        self.mapping["items"].append(other)
        self.write_mapping()
        report = self.run_prepare()["report"]
        self.assertEqual(report["sidecar_count"], 4)
        self.assertEqual(len(report["identity_conflicts"]), 1)
        self.assertEqual(report["identity_conflicts"][0]["reason"], "same_identity_different_record")
        self.assertEqual(report["review_status"], "unreviewed")

    def test_contradictory_mapping_id_and_authority_fields_fail(self):
        other = copy.deepcopy(self.mapping["items"][0])
        other["record_pointer"] = "/1"
        self.mapping["items"].append(other)
        self.write_mapping()
        with self.assertRaisesRegex(ValueError, "contradictory"):
            self.run_prepare()
        self.assertFalse(self.output.exists())
        self.mapping["items"].pop()
        self.mapping["items"][0]["review_status"] = "reviewed"
        self.write_mapping()
        with self.assertRaises(ValueError):
            self.run_prepare()

    def test_path_escape_archives_and_wrong_category_are_rejected(self):
        original = copy.deepcopy(self.mapping["items"][0])
        for path in ("../outside.yaml", "/etc/passwd", "packages/qa-agent/knowledge_sources/../secret.yaml",
                     "docs/research/rea/2026-10-18/archive.zip", "packages/qa-agent/knowledge_sources/*.yaml"):
            self.mapping["items"][0] = {**original, "source_path": path}
            self.write_mapping()
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.run_prepare()
        self.mapping["items"][0] = {**original, "source_category": "rea_export"}
        self.write_mapping()
        with self.assertRaisesRegex(ValueError, "allowlist"):
            self.run_prepare()
        self.assertFalse(self.output.exists())

    def test_symlink_and_hardlink_inputs_are_rejected(self):
        source = self.root / self.mapping["items"][0]["source_path"]
        backup = source.with_name("retained-original.yaml")
        source.rename(backup)
        source.symlink_to(backup)
        with self.assertRaises((OSError, ValueError)):
            self.run_prepare()
        self.assertFalse(self.output.exists())
        alias = self.scratch / "mapping-hardlink.json"
        os.link(self.mapping_path, alias)
        with self.assertRaisesRegex(ValueError, "hard links"):
            prep.prepare(alias, self.output, repository=self.root)

    def test_symlink_directory_cannot_redirect_mapping_or_output(self):
        link = self.scratch / "linked-parent"
        link.symlink_to(self.scratch, target_is_directory=True)
        with self.assertRaises((OSError, ValueError)):
            prep.prepare(link / "mapping.json", self.output, repository=self.root)
        with self.assertRaises((OSError, ValueError)):
            prep.prepare(self.mapping_path, link / "redirected-output", repository=self.root)
        self.assertFalse((self.scratch / "redirected-output").exists())

    def test_uncommitted_or_wrong_hash_sources_are_rejected(self):
        source = self.root / self.mapping["items"][0]["source_path"]
        source.write_bytes(source.read_bytes() + b"\n# uncommitted\n")
        with self.assertRaisesRegex(ValueError, "differs from"):
            self.run_prepare()
        self.mapping["source_commit"] = self.commit_all()
        self.mapping["items"][0]["source_sha256"] = "a" * 64
        self.write_mapping()
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            self.run_prepare()
        self.assertFalse(self.output.exists())

    def test_untracked_source_does_not_become_committed_evidence(self):
        item = self.mapping["items"][0]
        existing = self.root / item["source_path"]
        new = existing.with_name("untracked.yaml")
        new.write_bytes(existing.read_bytes())
        item["source_path"] = new.relative_to(self.root).as_posix()
        self.write_mapping()
        with self.assertRaisesRegex(ValueError, "committed file"):
            self.run_prepare()

    def test_mapping_source_total_and_record_size_limits(self):
        for limit_name, value in (("MAX_MAPPING_BYTES", 20), ("MAX_SOURCE_BYTES", 20),
                                  ("MAX_TOTAL_SOURCE_BYTES", 20), ("MAX_RECORD_BYTES", 20)):
            with self.subTest(limit=limit_name), patch.object(prep, limit_name, value), self.assertRaises(ValueError):
                self.run_prepare()
            self.assertFalse(self.output.exists())

    def test_nonexistent_and_cross_record_identity_pointers_fail(self):
        self.mapping["items"][0]["record_pointer"] = "/99"
        self.write_mapping()
        with self.assertRaisesRegex(ValueError, "pointer"):
            self.run_prepare()
        self.mapping["items"][0]["record_pointer"] = "/0"
        self.mapping["items"][0]["entity_name_pointer"] = "/1/topic"
        self.write_mapping()
        with self.assertRaisesRegex(ValueError, "inside the selected record"):
            self.run_prepare()

    def test_reference_cannot_be_borrowed_from_a_different_record(self):
        self.mapping["items"][0]["original_ref_pointer"] = "/1/source_ref"
        self.write_mapping()
        with self.assertRaisesRegex(ValueError, "source reference pointer must stay inside"):
            self.run_prepare()
        self.assertFalse(self.output.exists())

    def test_duplicate_keys_aliases_and_bad_pointer_syntax_fail(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            prep._json_load(b'{"source_commit":"a","source_commit":"b"}')
        for data in (b"one: 1\none: 2\n", b"one: &a [1]\ntwo: *a\n"):
            with self.assertRaises(ValueError):
                prep._parse_source("synthetic.yaml", data)
        for pointer in ("", "records/0", "/records/00", "/records/-1", "/bad~2key"):
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                prep._pointer({"records": [1]}, pointer)

    def test_create_only_output_and_reproducible_bytes(self):
        first = self.run_prepare()
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        with self.assertRaises(FileExistsError):
            self.run_prepare()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})
        other = self.scratch / "review-output-second"
        second = prep.prepare(self.mapping_path, other, repository=self.root)
        self.assertEqual(first["manifest"], second["manifest"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in other.iterdir()})

    def test_output_cannot_be_created_in_source_tree(self):
        with self.assertRaisesRegex(ValueError, "restricted to data/agent_runs"):
            prep.prepare(self.mapping_path, self.root / "packages/qa-agent/knowledge_sources/output", repository=self.root)

    def test_partial_write_failure_keeps_incomplete_output_without_manifest(self):
        original = prep._write_file
        calls = 0
        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic write failure")
            original(*args)
        with patch.object(prep, "_write_file", side_effect=fail_second), self.assertRaises(OSError):
            self.run_prepare()
        self.assertTrue(self.output.exists())
        self.assertFalse((self.output / "manifest.json").exists())
        retained = {p.name: p.read_bytes() for p in self.output.iterdir()}
        with self.assertRaises(FileExistsError):
            self.run_prepare()
        self.assertEqual(retained, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_source_drift_before_final_manifest_is_rejected(self):
        original = prep._write_file
        source = self.root / self.mapping["items"][0]["source_path"]
        def mutate(directory, name, payload):
            original(directory, name, payload)
            if name == "sidecars.json":
                source.write_bytes(source.read_bytes() + b"\n# drift\n")
        with patch.object(prep, "_write_file", side_effect=mutate), self.assertRaisesRegex(ValueError, "source changed"):
            self.run_prepare()
        self.assertFalse((self.output / "manifest.json").exists())

    def test_output_artifact_tampering_never_produces_complete_manifest(self):
        original = prep._write_file
        def alter(directory, name, payload):
            original(directory, name, payload + b"changed" if name == "sidecars.json" else payload)
        with patch.object(prep, "_write_file", side_effect=alter), self.assertRaisesRegex(ValueError, "artifact changed"):
            self.run_prepare()
        self.assertFalse((self.output / "manifest.json").exists())

    def test_output_directory_replacement_does_not_redirect_writes(self):
        original = prep._write_file
        moved = self.scratch / "retained-original-output"
        def replace(directory, name, payload):
            original(directory, name, payload)
            if name == "sidecars.json":
                self.output.rename(moved)
                self.output.mkdir()
                (self.output / "sentinel").write_text("unchanged")
        with patch.object(prep, "_write_file", side_effect=replace), self.assertRaisesRegex(ValueError, "directory replaced"):
            self.run_prepare()
        self.assertEqual([p.name for p in self.output.iterdir()], ["sentinel"])
        self.assertFalse((moved / "manifest.json").exists())

    def test_directory_swap_between_created_stat_and_open_preserves_existing_data(self):
        original_open = prep.os.open
        existing = self.scratch / "existing-user-directory"
        existing.mkdir()
        (existing / "sentinel").write_text("retain this existing data")
        retained = self.scratch / "retained-new-directory"
        swapped = False
        def replace_before_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == self.output.name and flags & os.O_DIRECTORY and not swapped:
                self.output.rename(retained)
                existing.rename(self.output)
                swapped = True
            return original_open(path, flags, *args, **kwargs)
        with patch.object(prep.os, "open", side_effect=replace_before_open) as mocked_open:
            # Preserve the real runtime's dir_fd capability while instrumenting open.
            with patch.object(prep.os, "supports_dir_fd", {*prep.os.supports_dir_fd, mocked_open}), self.assertRaisesRegex(ValueError, "replaced before open"):
                self.run_prepare()
        self.assertTrue(swapped)
        self.assertEqual([path.name for path in self.output.iterdir()], ["sentinel"])
        self.assertEqual((self.output / "sentinel").read_text(), "retain this existing data")
        self.assertEqual(list(retained.iterdir()), [])

    def test_directory_swapped_before_identity_capture_must_still_be_empty(self):
        original_mkdir = prep.os.mkdir
        existing = self.scratch / "existing-nonempty-directory"
        existing.mkdir()
        (existing / "sentinel").write_text("retain this existing data")
        retained = self.scratch / "retained-unopened-directory"
        def replace_after_mkdir(path, *args, **kwargs):
            result = original_mkdir(path, *args, **kwargs)
            if path == self.output.name:
                self.output.rename(retained)
                existing.rename(self.output)
            return result
        with patch.object(prep.os, "mkdir", side_effect=replace_after_mkdir), self.assertRaisesRegex(ValueError, "must be empty"):
            self.run_prepare()
        self.assertEqual([path.name for path in self.output.iterdir()], ["sentinel"])
        self.assertEqual((self.output / "sentinel").read_text(), "retain this existing data")
        self.assertEqual(list(retained.iterdir()), [])

    def test_generator_commit_is_not_invented_when_script_differs(self):
        (self.root / prep.SCRIPT_PATH).write_text("# different committed generator\n")
        self.mapping["source_commit"] = self.commit_all()
        self.write_mapping()
        result = self.run_prepare()
        self.assertIsNone(result["manifest"]["generator"]["source_commit"])
        self.assertEqual(result["manifest"]["generator"]["status"], "uncommitted_working_tree_bytes")


if __name__ == "__main__":
    unittest.main()
