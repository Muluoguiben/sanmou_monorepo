"""Local handoff bundle integrity tests; synthetic inputs never prove sampling."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from pydantic import ValidationError
from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, SealedJson

from pioneer_agent.training.artifact_bundle import (
    BootstrapContextPayload, BootstrapSourcePayload, BundleFile, BundleLimits, BundleManifest,
    BundleValidationError, TokenPayload,
    export_bundle, import_bundle,
)
from pioneer_agent.training.contracts import (
    ArtifactRef, BatchIdentity, BootstrapEvidence, PolicyStepProjection, ProjectionRequest,
    RewardEvent, TokenArtifact,
)
from pioneer_agent.training.projection import TrainingProjector
from pioneer_agent.training import artifact_bundle as implementation


FIXTURE = json.loads((Path(__file__).parent / "fixtures/training_bundle/scenarios.json").read_text())


def replace(model, **updates):
    return type(model).model_validate({**model.model_dump(), **updates})


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(episode, segment="segment-1"):
    policy = policy_manifest()
    return BatchIdentity(
        role_session_id=f"role-{episode}", episode_id=episode, learning_segment_id=segment,
        batch_id="batch-1", behavior_policy_revision=policy.sha256, critic_revision="critic-1",
        reference_revision="reference-1", tokenizer_revision="tokenizer-1",
        template_revision="template-1", sampling_revision=policy.sampling.sha256,
    )


def policy_manifest():
    return PolicyManifest(
        policy_id="policy-1", model="synthetic-model", checkpoint_revision="checkpoint-1",
        adapter_revision="adapter-1", tokenizer_revision="tokenizer-1", chat_template_revision="template-1",
        prompt_revision="prompt-1", sampling=SealedJson.from_value({"temperature": 1.0}), model_context_limit=4096,
    )


class BundleBuilder:
    def __init__(self):
        self.files = []
        self.payloads = {}

    def add(self, artifact_id, kind, owner, raw, decision=None, invocation=None):
        path = artifact_id + ".json"
        self.files.append(BundleFile(
            relative_path=path, artifact_id=artifact_id, kind=kind, owner_projection_id=owner,
            decision_id=decision, invocation_id=invocation, sha256=sha(raw), byte_length=len(raw),
        ))
        self.payloads[path] = raw
        return ArtifactRef(artifact_id=artifact_id, sha256=sha(raw), byte_length=len(raw))

    def projection(self, episode, values, *, segment="segment-1", start=0, prefix=None, truncated=False):
        ident = identity(episode, segment)
        owner = f"p-{episode}-{segment}"
        steps = []
        for row, value in enumerate(values):
            index = start + row
            decision, invocation = f"decision-{index}", f"invocation-{index}"
            context_id = f"{owner}-context-{index}"
            context = PolicyRequest(
                episode_id=episode, run_id=f"run-{episode}", decision_id=decision, invocation_id=invocation,
                context_id=context_id, task_ref="task-1", binding_ref=ident.role_session_id,
                observation_ref=f"observation-{index}", manifest=policy_manifest(),
                messages=SealedJson.from_value([{"role": "user", "content": f"state-{episode}-{index}"}]),
                tools=SealedJson.from_value([]), estimated_input_tokens=2, reserved_output_tokens=32,
            ).payload
            context_ref = self.add(context_id, "context", owner, context, decision, invocation)
            token_payload = TokenPayload(
                input_token_ids=(100 + index, 101), response_token_ids=(200,), attention_mask=(1, 1, 1),
                position_ids=(0, 1, 2), response_origins=("policy",), policy_token_mask=(1,),
            )
            token_raw = token_payload.model_dump_json().encode()
            token_ref = self.add(f"{owner}-tokens-{index}", "tokens", owner, token_raw, decision, invocation)
            tokens = TokenArtifact(artifact_ref=token_ref, **token_payload.model_dump(exclude={"schema_version"}))
            steps.append(PolicyStepProjection(
                identity=ident, decision_id=decision, invocation_id=invocation, decision_index=index,
                row_index=row, context_artifact=context_ref, tokens=tokens, old_logprobs=(-0.5,),
                critic_outputs=(999.0, float(value), 999.0), pre_token_value_indices=(1,),
            ))
        events = []
        if start == 0:
            events.append(RewardEvent(
                event_id=f"{owner}-invalid", role_session_id=ident.role_session_id, episode_id=episode,
                learning_segment_id=segment, decision_id="decision-0", invocation_id="invocation-0",
                decision_index=0, delta_invalid=1,
            ))
        if not truncated:
            final = steps[-1]
            events.append(RewardEvent(
                event_id=f"{owner}-success", role_session_id=ident.role_session_id, episode_id=episode,
                learning_segment_id=segment, decision_id=final.decision_id, invocation_id=final.invocation_id,
                decision_index=final.decision_index, delta_success=1,
            ))
        boundary = None
        if truncated:
            refs = {}
            for kind in ("bootstrap_state", "bootstrap_observation"):
                source = BootstrapSourcePayload(
                    source_kind=kind.removeprefix("bootstrap_"), identity=ident,
                    cutoff_decision_index=steps[-1].decision_index,
                    content=SealedJson.from_value({"state": "verified-next"}),
                )
                refs[kind] = self.add(f"{owner}-{kind}", kind, owner,
                                      source.model_dump_json().encode())
            context = BootstrapContextPayload(
                identity=ident, cutoff_decision_index=steps[-1].decision_index,
                builder_version="builder-1", source_cutoff="cutoff-1",
                state_artifact=refs["bootstrap_state"], observation_artifact=refs["bootstrap_observation"],
                messages=SealedJson.from_value([{"role": "user", "content": "verified-next-state"}]),
                tools=SealedJson.from_value([]), input_token_ids=(100, 101), attention_mask=(1, 1), position_ids=(0, 1),
            )
            refs["bootstrap_context"] = self.add(f"{owner}-bootstrap_context", "bootstrap_context", owner,
                                                  context.model_dump_json().encode())
            boundary = BootstrapEvidence(
                identity=ident, end_reason="segment_limit", cutoff_decision_index=steps[-1].decision_index,
                next_state_artifact=refs["bootstrap_state"], next_observation_artifact=refs["bootstrap_observation"],
                next_context_artifact=refs["bootstrap_context"], builder_version="builder-1", source_cutoff="cutoff-1",
                value=0.4, effects_verified=True, rewards_settled=True,
            )
        req = ProjectionRequest(
            identity=ident, steps=tuple(steps), reward_events=tuple(events), reward_revision="reward-1",
            rewards_complete=True, end_reason="segment_limit" if truncated else "task_success",
            prefix=prefix, bootstrap=boundary,
        )
        self.add(owner, "projection", owner, req.model_dump_json().encode())
        return req

    def manifest(self, source_kind="synthetic"):
        first = identity("episode-1")
        fields = {key: getattr(first, key) for key in implementation._VERSION_FIELDS}
        return BundleManifest(source_kind=source_kind, files=tuple(sorted(self.files, key=lambda f: f.relative_path)), **fields)


class TrainingArtifactBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sanmou-bundle-test-", dir="/private/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def builder(self, both=True):
        builder = BundleBuilder()
        for item in FIXTURE["episodes"][:2 if both else 1]:
            builder.projection(item["episode_id"], item["values"])
        return builder

    def export(self, builder=None, name="bundle", **kwargs):
        builder = builder or self.builder()
        path = self.root / name
        result = export_bundle(path, builder.manifest(), builder.payloads, **kwargs)
        return path, result

    def rewrite_file_and_manifest(self, path, entry, raw):
        """Corrupt one task-created fixture, preserving a self-consistent outer hash."""
        (path / entry.relative_path).write_bytes(raw)
        manifest = BundleManifest.model_validate_json((path / "manifest.json").read_bytes())
        changed = replace(entry, sha256=sha(raw), byte_length=len(raw))
        manifest = replace(manifest, files=tuple(changed if f.artifact_id == entry.artifact_id else f for f in manifest.files))
        (path / "manifest.json").write_bytes(manifest.model_dump_json().encode())

    def rebind_original(self, builder, entry, changed, *, bootstrap=False):
        """Update both descriptor and reference to expose semantic relabeling."""
        builder.payloads[entry.relative_path] = changed
        builder.files = [replace(f, sha256=sha(changed), byte_length=len(changed)) if f == entry else f
                         for f in builder.files]
        projection = next(f for f in builder.files if f.kind == "projection" and f.artifact_id == entry.owner_projection_id)
        req = json.loads(builder.payloads[projection.relative_path])
        if bootstrap:
            ref = req["bootstrap"][bootstrap if isinstance(bootstrap, str) else "next_context_artifact"]
        else:
            row = next(s for s in req["steps"] if s["context_artifact"]["artifact_id"] == entry.artifact_id)
            ref = row["context_artifact"]
        ref.update(sha256=sha(changed), byte_length=len(changed))
        raw = encoded(req)
        builder.payloads[projection.relative_path] = raw
        builder.files = [replace(f, sha256=sha(raw), byte_length=len(raw)) if f == projection else f
                         for f in builder.files]

    def test_two_complete_episodes_export_import_and_repeat_digest(self):
        builder = self.builder()
        originals = dict(builder.payloads)
        path, exported = self.export(builder)
        before = {p.name: p.read_bytes() for p in path.iterdir()}
        first, second = import_bundle(path), import_bundle(path)
        self.assertEqual(first, second)
        self.assertEqual(exported.bundle_digest, first.bundle_digest)
        self.assertEqual(builder.payloads, originals)
        self.assertEqual(before, {p.name: p.read_bytes() for p in path.iterdir()})
        self.assertEqual(len(first.projections), 2)
        for projection, fixture in zip(first.projections, FIXTURE["episodes"]):
            self.assertTrue(projection.result.eligible)
            self.assertEqual(projection.request.identity.episode_id, fixture["episode_id"])
            for actual, expected in zip(projection.result.advantages.returns, fixture["returns"]):
                self.assertAlmostEqual(actual, expected)
        self.assertEqual(first.source_kind, "synthetic")
        self.assertFalse(first.on_policy_runtime_evidence)
        self.assertFalse(first.remote_transfer_verified)
        self.assertFalse(first.ms5_ready)

    def test_runtime_declaration_is_not_on_policy_evidence(self):
        builder = self.builder()
        result = export_bundle(self.root / "runtime", builder.manifest("runtime"), builder.payloads)
        self.assertEqual(result.source_kind, "runtime")
        self.assertFalse(result.on_policy_runtime_evidence)

    def test_same_input_to_distinct_new_directories_has_same_digest(self):
        builder = self.builder()
        _, first = self.export(builder, "first")
        _, second = self.export(builder, "second")
        self.assertEqual(first.bundle_digest, second.bundle_digest)

    def test_existing_destination_is_never_overwritten_even_if_empty(self):
        path, original = self.export()
        manifest_before = (path / "manifest.json").read_bytes()
        builder = self.builder()
        with self.assertRaises(BundleValidationError):
            export_bundle(path, builder.manifest(), builder.payloads)
        self.assertEqual((path / "manifest.json").read_bytes(), manifest_before)
        empty = self.root / "existing-empty"
        empty.mkdir()
        with self.assertRaises(BundleValidationError):
            export_bundle(empty, builder.manifest(), builder.payloads)
        self.assertEqual(list(empty.iterdir()), [])

    def test_truncation_bootstrap_and_two_segment_prefix_recomputed(self):
        builder = BundleBuilder()
        first = builder.projection("episode-1", [0.2, 0.3], truncated=True)
        prefix = TrainingProjector().build(first).next_prefix
        builder.projection("episode-1", [0.4], segment="segment-2", start=2, prefix=prefix)
        builder.projection("episode-2", [0.1, 0.2])
        _, result = self.export(builder)
        self.assertEqual(len(result.projections), 3)
        for actual, expected in zip(result.projections[0].result.advantages.returns, FIXTURE["bootstrap"]["returns"]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(result.projections[1].result.manifest.rewards, (1.0,))

    def test_forged_prefix_counts_fail_even_with_correct_file_hash(self):
        builder = BundleBuilder()
        first = builder.projection("episode-1", [0.2, 0.3], truncated=True)
        prefix = TrainingProjector().build(first).next_prefix
        forged = replace(prefix, counts=replace(prefix.counts, invalid=5))
        builder.projection("episode-1", [0.4], segment="segment-2", start=2, prefix=forged)
        with self.assertRaisesRegex(BundleValidationError, "prefix counts"):
            self.export(builder)
        self.assertFalse((self.root / "bundle").exists())

    def test_prefix_source_must_be_in_bundle(self):
        first_builder = BundleBuilder()
        first = first_builder.projection("episode-1", [0.2, 0.3], truncated=True)
        prefix = TrainingProjector().build(first).next_prefix
        second_builder = BundleBuilder()
        second_builder.projection("episode-1", [0.4], segment="segment-2", start=2, prefix=prefix)
        with self.assertRaisesRegex(BundleValidationError, "root|prefix source"):
            self.export(second_builder)

    def test_manifest_rejects_escape_absolute_subdirectory_and_windows_paths(self):
        entry = self.builder(False).files[0]
        for name in ("../x.json", "/private/tmp/x.json", "folder/x.json", "folder\\x.json", "x:stream.json",
                     "manifest.json", ".hidden.json", "x\x00.json"):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                replace(entry, relative_path=name)

    def test_manifest_rejects_duplicate_ids_case_collisions_and_wrong_owners(self):
        builder = self.builder(False)
        manifest = builder.manifest()
        with self.assertRaises(ValidationError):
            replace(manifest, files=manifest.files + (manifest.files[0],))
        entry = manifest.files[0]
        collision = replace(entry, artifact_id="different", relative_path=entry.relative_path.upper().replace(".JSON", ".json"))
        with self.assertRaises(ValidationError):
            replace(manifest, files=manifest.files + (collision,))
        with self.assertRaises(ValidationError):
            replace(manifest, files=(replace(entry, owner_projection_id="not-there"), *manifest.files[1:]))

    def test_missing_and_extra_payloads_rejected_without_source_mutation(self):
        builder = self.builder(False)
        path, _ = self.export(builder)
        extra = path / "extra.json"
        extra.write_text("{}")
        with self.assertRaisesRegex(BundleValidationError, "extra"):
            import_bundle(path)
        # Construct a separate incomplete export fixture rather than delete.
        partial = self.root / "partial"
        partial.mkdir()
        (partial / "manifest.json").write_text(builder.manifest().model_dump_json())
        with self.assertRaisesRegex(BundleValidationError, "missing"):
            import_bundle(partial)

    def test_extra_directory_rejected(self):
        path, _ = self.export()
        (path / "nested").mkdir()
        with self.assertRaises(BundleValidationError):
            import_bundle(path)

    def test_symlink_file_and_hardlink_file_rejected(self):
        builder = self.builder(False)
        for link_kind in ("symlink", "hardlink"):
            path = self.root / link_kind
            path.mkdir()
            (path / "manifest.json").write_text(builder.manifest().model_dump_json())
            for index, (name, raw) in enumerate(builder.payloads.items()):
                if index:
                    (path / name).write_bytes(raw)
                    continue
                outside = self.root / f"outside-{link_kind}.json"
                outside.write_bytes(raw)
                if link_kind == "symlink":
                    (path / name).symlink_to(outside)
                else:
                    os.link(outside, path / name)
            with self.subTest(link_kind=link_kind), self.assertRaises(BundleValidationError):
                import_bundle(path)

    def test_symlink_bundle_and_parent_are_rejected(self):
        path, _ = self.export()
        alias = self.root / "alias"
        alias.symlink_to(path, target_is_directory=True)
        with self.assertRaises(BundleValidationError):
            import_bundle(alias)
        parent_alias = self.root / "parent-alias"
        parent_alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(BundleValidationError):
            import_bundle(parent_alias / "bundle")
        builder = self.builder()
        with self.assertRaises(BundleValidationError):
            export_bundle(parent_alias / "new-bundle", builder.manifest(), builder.payloads)

    def test_special_file_does_not_block_and_is_rejected(self):
        builder = self.builder(False)
        path = self.root / "fifo"
        path.mkdir()
        (path / "manifest.json").write_text(builder.manifest().model_dump_json())
        for index, (name, raw) in enumerate(builder.payloads.items()):
            if index == 0:
                os.mkfifo(path / name)
            else:
                (path / name).write_bytes(raw)
        with self.assertRaisesRegex(BundleValidationError, "non-regular"):
            import_bundle(path)

    def test_corrupt_hash_and_length_rejected(self):
        for mode in ("hash", "length"):
            builder = self.builder(False)
            path, _ = self.export(builder, mode)
            entry = builder.files[0]
            raw = builder.payloads[entry.relative_path]
            changed = raw[:-1] + b" " if mode == "hash" else raw + b" "
            (path / entry.relative_path).write_bytes(changed)
            with self.subTest(mode=mode), self.assertRaises(BundleValidationError):
                import_bundle(path)

    def test_rehashed_context_still_must_match_projection_artifact_ref(self):
        builder = self.builder(False)
        path, _ = self.export(builder)
        entry = next(f for f in builder.files if f.kind == "context")
        self.rewrite_file_and_manifest(path, entry, encoded({"messages": [], "tools": []}))
        with self.assertRaisesRegex(BundleValidationError, "reference.*original bytes"):
            import_bundle(path)

    def test_rehashed_and_referenced_context_cannot_relabel_another_invocation(self):
        for key in ("episode_id", "decision_id", "invocation_id", "binding_ref", "context_id"):
            builder = self.builder(False)
            entry = next(f for f in builder.files if f.kind == "context")
            wire = json.loads(builder.payloads[entry.relative_path])
            wire[key] = "other"
            self.rebind_original(builder, entry, PolicyRequest.from_wire(wire).payload)
            with self.subTest(key=key), self.assertRaisesRegex(BundleValidationError, "actual policy context identity"):
                self.export(builder, key)

    def test_context_run_and_task_are_frozen_within_each_episode(self):
        for key in ("run_id", "task_ref"):
            builder = self.builder(False)
            entry = [f for f in builder.files if f.kind == "context"][1]
            wire = json.loads(builder.payloads[entry.relative_path])
            wire[key] = "other-task-or-run"
            self.rebind_original(builder, entry, PolicyRequest.from_wire(wire).payload)
            with self.subTest(key=key), self.assertRaisesRegex(BundleValidationError, "run_id or task_ref"):
                self.export(builder, key)

    def test_same_episode_cannot_have_two_root_segments(self):
        builder = BundleBuilder()
        builder.projection("episode-1", [0.2])
        builder.projection("episode-1", [0.3], segment="segment-2")
        with self.assertRaisesRegex(BundleValidationError, "exactly one root"):
            self.export(builder)

    def test_continuation_cannot_duplicate_decision_invocation_or_index(self):
        for key, value in (("decision_id", "decision-0"), ("invocation_id", "invocation-0"), ("decision_index", 0)):
            builder = BundleBuilder()
            first = builder.projection("episode-1", [0.2, 0.3], truncated=True)
            prefix = TrainingProjector().build(first).next_prefix
            builder.projection("episode-1", [0.4], segment="segment-2", start=2, prefix=prefix)
            entry = next(f for f in builder.files if f.kind == "projection" and "segment-2" in f.artifact_id)
            req = json.loads(builder.payloads[entry.relative_path])
            req["steps"][0][key] = value
            raw = encoded(req)
            builder.payloads[entry.relative_path] = raw
            builder.files = [replace(f, sha256=sha(raw), byte_length=len(raw)) if f == entry else f for f in builder.files]
            with self.subTest(key=key), self.assertRaisesRegex(BundleValidationError, "duplicate decisions/invocations|overlapping"):
                self.export(builder, key)
    def test_rehashed_policy_context_cannot_switch_policy_versions(self):
        for key, value in (("tokenizer_revision", "other"), ("chat_template_revision", "other"),
                           ("sampling", {"temperature": 0.2}), ("checkpoint_revision", "other")):
            builder = self.builder(False)
            entry = next(f for f in builder.files if f.kind == "context")
            wire = json.loads(builder.payloads[entry.relative_path])
            wire["manifest"][key] = value
            self.rebind_original(builder, entry, PolicyRequest.from_wire(wire).payload)
            with self.subTest(key=key), self.assertRaisesRegex(BundleValidationError, "frozen policy versions"):
                self.export(builder, key)

    def test_arbitrary_json_is_not_a_policy_context_even_after_rebinding(self):
        builder = self.builder(False)
        entry = next(f for f in builder.files if f.kind == "context")
        self.rebind_original(builder, entry, b"{}")
        with self.assertRaisesRegex(BundleValidationError, "policy-service-v1"):
            self.export(builder)

    def test_noncanonical_context_is_not_claimed_as_captured_request_bytes(self):
        builder = self.builder(False)
        entry = next(f for f in builder.files if f.kind == "context")
        self.rebind_original(builder, entry, b" " + builder.payloads[entry.relative_path])
        with self.assertRaisesRegex(BundleValidationError, "canonical sent request"):
            self.export(builder)

    def test_token_payload_fields_must_match_even_when_hash_and_ref_are_rebound(self):
        fields = {
            "input_token_ids": [999, 101], "response_token_ids": [999], "attention_mask": [0, 1, 1],
            "position_ids": [3, 4, 5], "response_origins": ["environment"], "policy_token_mask": [0],
        }
        for field, value in fields.items():
            builder = self.builder(False)
            entry = next(f for f in builder.files if f.kind == "tokens")
            content = json.loads(builder.payloads[entry.relative_path])
            content[field] = value
            changed = encoded(content)
            builder.payloads[entry.relative_path] = changed
            builder.files = [replace(f, sha256=sha(changed), byte_length=len(changed)) if f == entry else f for f in builder.files]
            projection = next(f for f in builder.files if f.kind == "projection")
            req = json.loads(builder.payloads[projection.relative_path])
            ref = req["steps"][0]["tokens"]["artifact_ref"]
            ref.update(sha256=sha(changed), byte_length=len(changed))
            projection_raw = encoded(req)
            builder.payloads[projection.relative_path] = projection_raw
            builder.files = [replace(f, sha256=sha(projection_raw), byte_length=len(projection_raw)) if f == projection else f for f in builder.files]
            with self.subTest(field=field), self.assertRaisesRegex(BundleValidationError, "token payload differs"):
                self.export(builder, field)

    def test_bootstrap_original_is_checked(self):
        builder = BundleBuilder()
        builder.projection("episode-1", [0.2, 0.3], truncated=True)
        path, _ = self.export(builder)
        entry = next(f for f in builder.files if f.kind == "bootstrap_observation")
        self.rewrite_file_and_manifest(path, entry, encoded({"state": "different"}))
        with self.assertRaisesRegex(BundleValidationError, "reference.*original bytes"):
            import_bundle(path)

    def test_bootstrap_context_has_its_own_identity_cutoff_schema(self):
        for key, value in (("cutoff_decision_index", 5), ("builder_version", "other"), ("source_cutoff", "other")):
            builder = BundleBuilder()
            builder.projection("episode-1", [0.2, 0.3], truncated=True)
            entry = next(f for f in builder.files if f.kind == "bootstrap_context")
            original = BootstrapContextPayload.model_validate_json(builder.payloads[entry.relative_path])
            changed = replace(original, **{key: value}).model_dump_json().encode()
            self.rebind_original(builder, entry, changed, bootstrap=True)
            with self.subTest(key=key), self.assertRaisesRegex(BundleValidationError, "bootstrap context identity"):
                self.export(builder, key)
        builder = BundleBuilder()
        builder.projection("episode-1", [0.2, 0.3], truncated=True)
        entry = next(f for f in builder.files if f.kind == "bootstrap_context")
        raw = json.loads(builder.payloads[entry.relative_path])
        raw["invocation_id"] = "invented-invocation"
        self.rebind_original(builder, entry, encoded(raw), bootstrap=True)
        with self.assertRaisesRegex(BundleValidationError, "BootstrapContextPayload"):
            self.export(builder)

    def test_rehashed_bootstrap_source_cannot_change_identity_or_cutoff(self):
        for kind, field in (("bootstrap_state", "next_state_artifact"),
                            ("bootstrap_observation", "next_observation_artifact")):
            builder = BundleBuilder()
            builder.projection("episode-1", [0.2, 0.3], truncated=True)
            entry = next(f for f in builder.files if f.kind == kind)
            source = BootstrapSourcePayload.model_validate_json(builder.payloads[entry.relative_path])
            changed = replace(source, identity=identity("other-episode")).model_dump_json().encode()
            self.rebind_original(builder, entry, changed, bootstrap=field)
            with self.subTest(kind=kind), self.assertRaisesRegex(BundleValidationError, "bootstrap source identity"):
                self.export(builder, kind)

    def test_missing_serialized_version_and_ready_fields_are_not_defaulted(self):
        builder = self.builder(False)
        path, _ = self.export(builder)
        manifest = json.loads((path / "manifest.json").read_bytes())
        del manifest["schema_version"]
        (path / "manifest.json").write_bytes(encoded(manifest))
        with self.assertRaisesRegex(BundleValidationError, "incomplete serialized"):
            import_bundle(path)
        builder = self.builder(False)
        entry = next(f for f in builder.files if f.kind == "projection")
        request = json.loads(builder.payloads[entry.relative_path])
        del request["steps"][0]["context_artifact"]["ready"]
        raw = encoded(request)
        builder.payloads[entry.relative_path] = raw
        builder.files = [replace(f, sha256=sha(raw), byte_length=len(raw)) if f == entry else f for f in builder.files]
        with self.assertRaisesRegex(BundleValidationError, "incomplete serialized"):
            self.export(builder, "missing-ready")

    def test_cross_projection_owners_and_wrong_versions_rejected(self):
        builder = self.builder()
        manifest = builder.manifest()
        context = next(f for f in manifest.files if f.kind == "context")
        other = next(f.artifact_id for f in manifest.files if f.kind == "projection" and f.artifact_id != context.owner_projection_id)
        changed = replace(context, owner_projection_id=other)
        bad = replace(manifest, files=tuple(changed if f == context else f for f in manifest.files))
        with self.assertRaisesRegex(BundleValidationError, "owner"):
            export_bundle(self.root / "bad-owner", bad, builder.payloads)
        for field in implementation._VERSION_FIELDS:
            with self.subTest(field=field), self.assertRaisesRegex(BundleValidationError, "versions"):
                export_bundle(self.root / f"bad-{field}", replace(manifest, **{field: "other"}), builder.payloads)

    def test_unreferenced_but_listed_payload_is_rejected(self):
        builder = self.builder(False)
        owner = next(f.artifact_id for f in builder.files if f.kind == "projection")
        builder.add("unused", "bootstrap_state", owner, b"{}")
        with self.assertRaisesRegex(BundleValidationError, "unreferenced"):
            self.export(builder)

    def test_byte_file_count_json_depth_and_nodes_limits(self):
        path, _ = self.export()
        for limits in (BundleLimits(max_files=1), BundleLimits(max_manifest_bytes=1),
                       BundleLimits(max_file_bytes=1), BundleLimits(max_total_bytes=1),
                       BundleLimits(max_json_depth=1), BundleLimits(max_json_nodes=1)):
            with self.subTest(limits=limits), self.assertRaises(BundleValidationError):
                import_bundle(path, limits=limits)

    def test_duplicate_json_keys_and_invalid_nonfinite_json_rejected(self):
        builder = self.builder(False)
        path, _ = self.export(builder)
        manifest_raw = (path / "manifest.json").read_bytes()
        (path / "manifest.json").write_bytes(b'{"source_kind":"runtime",' + manifest_raw[1:])
        with self.assertRaisesRegex(BundleValidationError, "invalid JSON"):
            import_bundle(path)
        for raw in (b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}', b'not-json', b'"\xff"'):
            altered = dict(builder.payloads)
            entry = builder.files[0]
            altered[entry.relative_path] = raw
            manifest = replace(builder.manifest(), files=tuple(
                replace(f, sha256=sha(raw), byte_length=len(raw)) if f == entry else f for f in builder.manifest().files
            ))
            with self.subTest(raw=raw), self.assertRaises(BundleValidationError):
                export_bundle(self.root / "invalid", manifest, altered)

    def test_manifest_written_last_and_partial_failure_does_not_publish(self):
        builder = self.builder(False)
        real_write = implementation._write_new
        names = []
        def record(fd, name, raw):
            names.append(name)
            real_write(fd, name, raw)
        with mock.patch.object(implementation, "_write_new", side_effect=record):
            self.export(builder)
        self.assertEqual(names[-1], "manifest.json")
        partial = self.root / "failed"
        calls = 0
        def fail_after_one(fd, name, raw):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected write failure")
            real_write(fd, name, raw)
        with mock.patch.object(implementation, "_write_new", side_effect=fail_after_one):
            with self.assertRaises(BundleValidationError):
                export_bundle(partial, builder.manifest(), builder.payloads)
        self.assertTrue(partial.exists())
        self.assertFalse((partial / "manifest.json").exists())
        with self.assertRaises(BundleValidationError):
            import_bundle(partial)

    def test_mutation_during_validation_is_rejected(self):
        builder = self.builder(False)
        path, _ = self.export(builder)
        real_verify = implementation._verify_payloads
        def mutate(*args):
            result = real_verify(*args)
            target = path / builder.files[0].relative_path
            target.write_bytes(target.read_bytes() + b" ")
            return result
        with mock.patch.object(implementation, "_verify_payloads", side_effect=mutate):
            with self.assertRaisesRegex(BundleValidationError, "changed"):
                import_bundle(path)

    def test_absent_secure_filesystem_apis_fail_closed(self):
        path, _ = self.export()
        with mock.patch.object(os, "supports_dir_fd", set()):
            with self.assertRaisesRegex(BundleValidationError, "secure bundle IO"):
                import_bundle(path)


if __name__ == "__main__":
    unittest.main()
