"""Stdlib-only export/verify of a bounded, non-executable research projection.

Never reads ZIPs, captures, credentials, bytecode, Q06 artifacts or the live KB.
The source bundle is local-only; only selected JSON fields enter this snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parent
BUNDLE_SHA = "173aa0b7317f5cac0090c161a159d7075f7d42e1e30285c38a3906a4d536e17f"
INPUTS = {
    "heroes": "materials/nslg-all-heroes-2026-10-13/profiles.json",
    "skills": "materials/nslg-all-skill-cards-2026-10-13/skills.json",
    "gear": "materials/nslg-gear-cards-2026-10-13/catalog.json",
    "mechanics": "materials/nslg-clarity-control-ui-10510132850058-2026-10-16/evidence-status-matrix.json",
    "report_a": "materials/nslg-battle-10504369850058-2026-10-15/report.json",
    "report_b": "materials/nslg-battle-10507264650058-2026-10-16/report.json",
}
COUNTS = {"heroes": 217, "skills": 1159, "gear": 327, "fates": 64, "mechanics": 64, "reports": 2}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def decode(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def pick(value, keys):
    return {key: value[key] for key in keys.split() if key in value}


def levels(value):
    return {key: {
        **pick(row, "skill_level orderLevel description errors launch_probability_percent"),
        "display_checks": [pick(f, "marker is_percentage value_exact display rational_display rational_agrees")
                           for f in row.get("formulas", [])],
    } for key, row in value.items()}


def project(source):
    """Pure field allowlist. No raw records, executable expressions or paths."""
    heroes, fates = [], {}
    for row in source["heroes"]["profiles"]:
        annotation = pick(row["annotations"], "name_status same_name_other_ids config_flags classifications zero_placeholder_pattern passes_regular_list_static_flags season_eligibility mapped_identity tags warnings")
        skill = pick(row["innate_skill"], "reference_id found missing_status")
        heroes.append({**pick(row, "hero_id name display_name attributes"),
                       "annotations": annotation, "innate_skill": skill,
                       "fate_ids": sorted({f["id"] for f in row["fates"]})})
        for fate in row["fates"]:
            record = {"id": fate["id"],
                      "data": pick(fate["data"], "name description need_hero_number hero effect_one effect_value_one effect_buff"),
                      "members": [pick(m, "hero_id name") for m in fate["members"]],
                      "conflicts": [pick(c, "fate_id name display_text effect_one effect_value_one effect_buff classification comparison adjudication") for c in fate.get("conflicts", [])]}
            if record["id"] in fates and fates[record["id"]] != record:
                raise ValueError("inconsistent repeated fate")
            fates[record["id"]] = record
    skills = []
    for row in source["skills"]["cards"].values():
        evolution = row.get("evolution", {})
        skills.append({**pick(row, "skill_id hero_ids name type_id type_name render_status unsupported_reasons scope coverage"),
                       "levels": levels(row["levels"]),
                       "annotations": pick(row["annotations"], "display_name primary_category classifications identity availability warnings"),
                       "probability": pick(row["probability"], "render_status note order_0_percent levels"),
                       "evolution": {**pick(evolution, "status scope class_field_raw class_field_interpretation"),
                                     "orders": {key: {"orderLevel": order["orderLevel"], "levels": levels(order["levels"])}
                                                for key, order in evolution.get("orders", {}).items()}}})
    gear = []
    for row in source["gear"]["items"]:
        gear.append({**pick(row, "category id name description type type_label main_attribute_range secondary_attribute_range attribute_type_status scenarios"),
                     "quality": pick(row["quality"], "raw label_from_reg label_code status")})
    for row in source["gear"]["affixes"]:
        gear.append({**pick(row, "kind id name type type_label scenarios actual_obtainability"),
                     "variants": [pick(v, "scenarios name description type type_label unique_ids weight ban_dianhua") for v in row["variants"]]})
    mechanics = []
    for row in source["mechanics"]["rows"]:
        mechanics.append({**pick(row, "id origin title category client_basis_status battle_evidence_status battle_observed_scope still_missing original_foundation_status_unchanged full_compound_rule_battle_verified"),
                          "client_basis": pick(row.get("client_basis", {}), "sha256 rule_id statement version evidence_refs source_bundle_sha256"),
                          "event_references": [pick(e, "battle_id source_index index_base round event_name") for e in row.get("battle_evidence", [])],
                          "ui_references": [{**pick(e, "evidence_kind observation_id battle_id source_json_available round quote raw_event_index_available index_policy"),
                                             "screenshot_sha256": e.get("screenshot", {}).get("sha256")}
                                            for e in row.get("ui_battle_evidence", [])]})
    reports = []
    for label in ("report_a", "report_b"):
        row = source[label]
        if row["event_count"] != len(row["events"]):
            raise ValueError("event count mismatch")
        reports.append({"source_label": label,
                        **pick(row, "battle_id sample_kind event_count slice_count event_integer_width decode_complete decode_complete_scope real_battle_verified source_association_independently_authenticated complete_tcp_connection native_control_acceptance_observed client_dispatch_not_replayed control_condition_unobserved warnings"),
                        "terminal_event_name": row["events"][-1]["event_name"],
                        "raw_events_included": False})
    result = {"heroes": heroes, "fates": [fates[k] for k in sorted(fates)],
              "skills": sorted(skills, key=lambda r: r["skill_id"]), "gear": gear,
              "mechanics": mechanics, "reports": reports}
    if {key: len(value) for key, value in result.items()} != COUNTS:
        raise ValueError("unexpected projection counts")
    return result


def audit_public(value):
    """Supplementary disclosure scan, not a universal secret/privacy proof."""
    denied_keys = {"raw_payload", "session_anchor", "raw_hero", "raw_record", "raw_body", "raw_item",
                   "embedded_chunk_name", "source_proofs", "sourceproof", "fields", "teamId",
                   "access_token", "refresh_token", "password", "api_key", "cookie", "iv", "cipher_key"}
    for key, item in value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ():
        if key in denied_keys:
            raise ValueError("forbidden public field")
        audit_public(item)
    if isinstance(value, str):
        if re.search(r"[A-Za-z]:[\\/]|/home/|/Users/|/mnt/|BEGIN .*PRIVATE KEY|Bearer\s+[A-Za-z0-9_-]{12,}|sk-[A-Za-z0-9_-]{16,}", value):
            raise ValueError("sensitive string in projection")


def export(source_root, output=ROOT):
    source_root, output = Path(source_root).resolve(), Path(output).resolve()
    manifest_bytes = (source_root / "BUNDLE-MANIFEST.json").read_bytes()
    if digest(manifest_bytes) != BUNDLE_SHA:
        raise ValueError("source bundle manifest changed")
    manifest = decode(manifest_bytes)
    rows = {row["path"]: row for row in manifest["files"]}
    if len(rows) != len(manifest["files"]):
        raise ValueError("duplicate input path")
    source, sources = {}, {}
    for label, relative in INPUTS.items():
        path = source_root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(source_root):
            raise ValueError("source path escape")
        data = path.read_bytes()
        expected = rows[relative]
        if len(data) != expected["bytes"] or digest(data) != expected["sha256"]:
            raise ValueError("source bytes changed")
        source[label] = decode(data)
        sources[label] = {"relative_path": relative, "bytes": len(data), "sha256": digest(data),
                          "source_bundle_sha256": source[label].get("source_bundle_sha256")}
    projected = project(source)
    audit_public(projected)
    content = {f"data/{name}.json": encode({"schema": "sanmou-rea-research-projection/v1",
               "review_state": "pending_domain_review", "knowledge_publishable": False,
               "execution_authority": "none", "executable": False, "records": records})
               for name, records in projected.items()}
    content["SOURCE-MANIFEST.json"] = encode({"schema": "sanmou-rea-local-source-binding/v1",
        "bundle_manifest_sha256": BUNDLE_SHA, "sources": sources,
        "source_bundle_files_excluding_manifest": len(rows), "source_package_count": len(manifest["packages"]),
        "source_file_bytes": sum(row["bytes"] for row in manifest["files"]),
        "full_source_bundle_in_repository": False,
        "exclusions": ["archives", "bytecode", "native_binaries", "metadata_database", "network_captures",
                       "raw_battle_events", "raw_screenshots", "credentials", "absolute_source_paths", "Q06a"]})
    targets = [output / name for name in content]
    if any(path.exists() or path.is_symlink() for path in targets):
        raise FileExistsError("create-only snapshot output")
    for name, data in content.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.parent.resolve().is_relative_to(output):
            raise ValueError("output path escape")
        with target.open("xb") as handle:
            handle.write(data)
    return {"counts": COUNTS, "files": len(content), "bytes": sum(map(len, content.values()))}


def seal(root=ROOT):
    root = Path(root).resolve()
    manifest = root / "MANIFEST.json"
    if manifest.exists():
        raise FileExistsError("manifest exists")
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("snapshot symlink")
        if path.is_file():
            data = path.read_bytes()
            files.append({"path": path.relative_to(root).as_posix(), "bytes": len(data), "sha256": digest(data)})
    with manifest.open("xb") as handle:
        handle.write(encode({"schema": "sanmou-rea-public-snapshot-manifest/v1", "files": files,
                             "self_hash_excluded": True, "counts": COUNTS}))


def verify(root=ROOT):
    root = Path(root).resolve()
    manifest = decode((root / "MANIFEST.json").read_bytes())
    expected = {"MANIFEST.json"}
    for row in manifest["files"]:
        name = row["path"]
        rel = PurePosixPath(name)
        if rel.is_absolute() or ".." in rel.parts or "\\" in name or name in expected:
            raise ValueError("unsafe or duplicate manifest path")
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("unsafe snapshot file")
        data = path.read_bytes()
        if len(data) != row["bytes"] or digest(data) != row["sha256"]:
            raise ValueError("snapshot digest mismatch")
        expected.add(name)
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if actual != expected:
        raise ValueError("snapshot inventory mismatch")
    for name, count in COUNTS.items():
        doc = decode((root / "data" / f"{name}.json").read_bytes())
        if len(doc["records"]) != count or doc["knowledge_publishable"] is not False or doc["executable"] is not False:
            raise ValueError("snapshot boundary mismatch")
        audit_public(doc)
    return {"status": "PASS", "files": len(expected), "counts": COUNTS,
            "manifest_sha256": digest((root / "MANIFEST.json").read_bytes())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--export", type=Path, metavar="LOCAL_BUNDLE")
    group.add_argument("--seal", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = export(args.export) if args.export else seal() if args.seal else verify()
    print(json.dumps(result, ensure_ascii=False))
