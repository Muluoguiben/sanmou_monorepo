"""Read-only coverage/provenance inventory. JSON goes to stdout; no KB writes or requests."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import yaml

from qa_agent.knowledge.models import KnowledgeEntry
from qa_agent.knowledge.provenance import (
    KnowledgeProvenance, audit_imports, canonical_digest, entry_digest, load_provenance_json,
)


def _source_files(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("knowledge root must be a non-symlink directory")
    paths = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in [*dirs, *files]:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"symlink in knowledge root: {path.relative_to(root)}")
        paths.extend(Path(directory) / name for name in files if name.endswith(".yaml"))
    if not paths:
        raise ValueError("knowledge root contains no YAML sources")
    return sorted(paths)


def build_inventory(knowledge_root: Path, records: list[KnowledgeProvenance] | None = None) -> dict:
    """Bind optional sidecars to exact normalized legacy entries, without changing them."""
    entries: dict[str, KnowledgeEntry] = {}
    locations = {}
    source_manifest = []
    for path in _source_files(knowledge_root):
        raw = path.read_bytes()
        data = yaml.safe_load(raw.decode("utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"knowledge source is not a list: {path.relative_to(knowledge_root)}")
        relative = path.relative_to(knowledge_root).as_posix()
        source_manifest.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest()})
        for index, item in enumerate(data):
            entry = KnowledgeEntry.model_validate(item)
            if entry.id in entries:
                raise ValueError(f"duplicate knowledge entry id: {entry.id}")
            entries[entry.id] = entry
            locations[entry.id] = {"path": relative, "record_index": index}

    imports = audit_imports(records or [])
    bound: dict[str, list[KnowledgeProvenance]] = {}
    for record in imports.records:
        if record.legacy_entry_id is None:
            continue
        entry = entries.get(record.legacy_entry_id)
        if entry is None:
            raise ValueError(f"sidecar references absent entry: {record.legacy_entry_id}")
        if record.legacy_entry_sha256 != entry_digest(entry):
            raise ValueError(f"sidecar digest mismatch: {entry.id}")
        if record.synthetic:
            raise ValueError("synthetic sidecars cannot claim formal KB provenance coverage")
        bound.setdefault(entry.id, []).append(record)

    inventory = []
    gap_counts: Counter = Counter()
    for entry_id, entry in sorted(entries.items()):
        linked = bound.get(entry_id, [])
        gaps = set()
        if not linked:
            gaps.add("provenance_not_recorded")
        for record in linked:
            for missing, present in {
                "original_hash_unknown": record.source.original_sha256 is not None,
                "source_revision_unknown": record.source.revision is not None,
                "published_at_unknown": record.source.published_at is not None,
                "collected_at_unknown": record.source.collected_at is not None,
                "game_version_unknown": record.applicability.game_version is not None,
                "season_unknown": bool(record.applicability.season_tags),
                "validity_interval_unknown": record.applicability.valid_from is not None and record.applicability.valid_until is not None,
                "source_location_unknown": record.location.kind != "unknown",
                "review_not_declared": record.review.status != "unreviewed",
            }.items():
                if not present:
                    gaps.add(missing)
            if record.source.category.value == "player_guide" and record.source.author is None:
                gaps.add("guide_author_unknown")
            if record.source.category.value == "rea_export" and record.source.parser_version is None:
                gaps.add("parser_version_unknown")
        gap_counts.update(gaps)
        inventory.append({
            "entry_id": entry_id, "domain": entry.domain.value, "entry_kind": entry.entry_kind.value,
            "topic": entry.topic, "aliases": entry.aliases, "source_ref": entry.source_ref,
            "legacy_source_type": entry.source_type.value, "updated_at": entry.updated_at.isoformat(),
            "entry_sha256": entry_digest(entry), "location": locations[entry_id],
            "source_categories": sorted({item.source.category.value for item in linked}),
            "declared_review_statuses": sorted({item.review.status for item in linked}),
            "provenance_record_digests": sorted(canonical_digest(item.model_dump(mode="json")) for item in linked),
            "gaps": sorted(gaps),
        })
    return {
        "protocol": "knowledge-inventory-v1", "source_manifest": source_manifest,
        "kb_file_manifest_sha256": canonical_digest(source_manifest),
        "source_file_count": len(source_manifest), "entry_count": len(entries),
        "by_domain": dict(sorted(Counter(entry.domain.value for entry in entries.values()).items())),
        "by_entry_kind": dict(sorted(Counter(entry.entry_kind.value for entry in entries.values()).items())),
        "entries_with_provenance": len(bound), "entries_without_provenance": len(entries) - len(bound),
        "gap_counts": dict(sorted(gap_counts.items())), "entries": inventory,
        "provenance": {"input_count": imports.input_count, "exact_duplicates": imports.exact_duplicates,
                       "unique_count": len(imports.records),
                       "unattached_count": sum(item.legacy_entry_id is None for item in imports.records),
                       "conflicts": [item.model_dump(mode="json") for item in imports.conflicts]},
        "review_identity_authenticated": False, "human_gold": False,
        "knowledge_publishable": False, "execution_authority": "none",
        "interpretation": "Coverage describes stored entries, not game completeness or factual correctness. Legacy source_type/confidence/updated_at do not certify provenance, review, or validity.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provenance", type=Path, help="Explicit JSON sidecars; references inside are never opened")
    args = parser.parse_args(argv)
    try:
        records = []
        if args.provenance:
            if args.provenance.is_symlink() or not args.provenance.is_file():
                raise ValueError("provenance must be a regular non-symlink JSON file")
            records = load_provenance_json(args.provenance.read_text(encoding="utf-8"))
        root = Path(__file__).resolve().parents[3] / "knowledge_sources"
        result = build_inventory(root, records)
    except (ValueError, OSError, yaml.YAMLError) as error:
        parser.exit(2, f"inventory failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
