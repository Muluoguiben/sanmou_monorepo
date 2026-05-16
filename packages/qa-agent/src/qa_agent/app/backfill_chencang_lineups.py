"""Back-fill empty hero_names / core_skills on the chencang Bilibili staging
using the lineup frame extractor (task #11, P2).

Reads a directory of `--with-frames` bundles (one per BVID), runs the vision
ImageExtractor over the lineup frames that align with each staging entry's
source_ref time window, snaps recognized names to KB-canonical via the
subtitle_normalizer dictionary, and fills only the empty slots. Existing
values are never overwritten; every fill is traced in structured_data.notes.

Usage:
    python -m qa_agent.app.backfill_chencang_lineups \
        --staging packages/qa-agent/ingestion/staging/videos/bilibili-chencang-2026-05-14.yaml \
        --bundles-dir /tmp/bili-chencang-frames \
        [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from qa_agent.video.lineup_frame_extractor import LineupFrameExtractor
from qa_agent.video.subtitle_normalizer import (
    build_dictionary_from_profiles,
    default_homophones_path,
    default_knowledge_sources_dir,
)

_BVID_RE = re.compile(r"(BV[0-9A-Za-z]+)")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Back-fill chencang staging hero/skill from video frames.")
    p.add_argument("--staging", required=True, help="Path to the chencang staging YAML.")
    p.add_argument("--bundles-dir", required=True, help="Dir with <BVID>.yaml --with-frames bundles.")
    p.add_argument("--dry-run", action="store_true", help="Do not write the staging YAML back.")
    p.add_argument("--package-root", default=None, help="qa-agent package root (KB dictionary).")
    return p


def _make_canonicalizer(package_root: Path):
    """Return raw-name -> KB-canonical using the subtitle_normalizer dict.

    Only exact alias/homophone rules are applied (no fuzzy) — frame OCR names
    are short tokens where fuzzy is unsafe (task #8/#9 2-char safety lesson).
    """
    dictionary = build_dictionary_from_profiles(
        knowledge_sources_dir=default_knowledge_sources_dir(package_root),
        homophones_path=default_homophones_path(package_root),
    )
    exact = {r.source: r.canonical for r in dictionary.exact_rules}

    def _canon(name: str) -> str:
        return exact.get(name.strip(), name.strip())

    return _canon


def main() -> None:
    args = _build_parser().parse_args()
    staging_path = Path(args.staging).resolve()
    bundles_dir = Path(args.bundles_dir).resolve()
    package_root = (
        Path(args.package_root).resolve()
        if args.package_root
        else Path(__file__).resolve().parents[3]
    )

    staging = yaml.safe_load(staging_path.read_text(encoding="utf-8"))

    bundles_by_bvid: dict[str, dict] = {}
    for yml in sorted(bundles_dir.glob("*.yaml")):
        m = _BVID_RE.search(yml.name)
        if not m:
            continue
        try:
            bundles_by_bvid[m.group(1)] = yaml.safe_load(yml.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"skip bundle {yml.name}: {exc}")

    from qa_agent.vision.extractor import ImageExtractor

    extractor = LineupFrameExtractor(
        ImageExtractor(),
        canonicalize=_make_canonicalizer(package_root),
    )
    staging, stats = extractor.backfill_entries(staging, bundles_by_bvid)

    if not args.dry_run:
        staging_path.write_text(
            yaml.dump(staging, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "staging": str(staging_path),
                "bundles_loaded": sorted(bundles_by_bvid),
                "dry_run": args.dry_run,
                "stats": {
                    "entries_total": stats.entries_total,
                    "entries_targeted": stats.entries_targeted,
                    "entries_filled_hero": stats.entries_filled_hero,
                    "entries_filled_skill": stats.entries_filled_skill,
                    "frames_analyzed": stats.frames_analyzed,
                    "vision_errors": stats.vision_errors,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
