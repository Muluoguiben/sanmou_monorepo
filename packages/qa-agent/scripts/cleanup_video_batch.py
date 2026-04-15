"""Consolidate & clean up the 19-video staging batch before publishing.

Rules (from user review 2026-04-15):
- Drop candidates with no resolvable heroes, pseudo-hero lineup names
  (孙大圣/不虚宝宝), or cross-game contamination (张良/张灵).
- Normalize hero names via configs/hero_aliases.yaml (祝融→祝融夫人, 甄姬→甄洛 …).
- If any hero fails to resolve against KB canonical names after aliasing,
  drop the candidate — it's either ASR error or wrong game.
- Skills: strip "Hero-Skill" compounds → Skill; drop the placeholder
  "输出技能"; drop parenthetical descriptive blobs; apply skill aliases.
- Write one consolidated staging YAML ready for publish_staging.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

from qa_agent.knowledge.loader import load_entries
from qa_agent.ingestion.config import load_alias_config

DROP_HEROES = {"孙大圣", "不虚宝宝", "张良", "张灵"}
PLACEHOLDER_SKILLS = {"输出技能"}


def _strip_compound_skill(raw: str) -> str:
    # "孙策-制霸江东" → "制霸江东"; "徐盛自带技能（描述...）" → drop
    if "（" in raw or "(" in raw:
        return ""
    if "-" in raw:
        raw = raw.split("-", 1)[1].strip()
    return raw.strip()


def _resolve_hero(name: str, canonical: dict[str, str], valid: set[str]) -> str | None:
    if not name:
        return None
    resolved = canonical.get(name, name)
    return resolved if resolved in valid else None


def _resolve_skill(name: str, canonical: dict[str, str]) -> str:
    name = _strip_compound_skill(name)
    if not name or name in PLACEHOLDER_SKILLS:
        return ""
    return canonical.get(name, name)


_SEASON_TAG_RE = re.compile(r"^S\d{1,2}$", re.IGNORECASE)


def _normalize_season_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for t in tags or []:
        t = (t or "").strip()
        if _SEASON_TAG_RE.match(t):
            out.append(t.upper())
    return out


def _clean_entry(entry: dict, hero_canonical: dict, hero_valid: set, skill_canonical: dict) -> dict | None:
    sd = entry.get("structured_data") or {}
    raw_heroes = sd.get("hero_names") or []
    if any(h in DROP_HEROES for h in raw_heroes):
        return None
    if not raw_heroes:
        return None
    resolved_heroes: list[str] = []
    for h in raw_heroes:
        r = _resolve_hero(h, hero_canonical, hero_valid)
        if r is None:
            return None  # unresolved hero → drop whole candidate
        if r not in resolved_heroes:
            resolved_heroes.append(r)
    if len(resolved_heroes) < 2:
        return None  # info too thin

    resolved_skills: list[str] = []
    for s in sd.get("core_skills") or []:
        r = _resolve_skill(s, skill_canonical)
        if r and r not in resolved_skills:
            resolved_skills.append(r)

    sd = dict(sd)
    sd["hero_names"] = resolved_heroes
    sd["core_skills"] = resolved_skills
    sd["season_tags"] = _normalize_season_tags(sd.get("season_tags") or [])
    entry = dict(entry)
    entry["structured_data"] = sd

    # keep related_topics aligned with resolved heroes
    rt = entry.get("related_topics") or []
    mapped = []
    for t in rt:
        r = hero_canonical.get(t, t)
        if r in hero_valid and r not in mapped:
            mapped.append(r)
    if mapped:
        entry["related_topics"] = mapped
    return entry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True, help="Dir containing BV*/video-staging-reviewed.yaml")
    parser.add_argument("--output", required=True, help="Consolidated publish-ready staging YAML")
    parser.add_argument("--knowledge-dir", default="knowledge_sources")
    parser.add_argument("--configs-dir", default="configs")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    knowledge_dir = Path(args.knowledge_dir)
    if not knowledge_dir.is_absolute():
        knowledge_dir = project_root / knowledge_dir
    configs_dir = Path(args.configs_dir)
    if not configs_dir.is_absolute():
        configs_dir = project_root / configs_dir

    entries = load_entries(sorted(knowledge_dir.rglob("*.yaml")))
    hero_valid = {e.topic for e in entries if e.entry_kind == "hero_profile"}

    hero_alias = load_alias_config(configs_dir / "hero_aliases.yaml")
    skill_alias = load_alias_config(configs_dir / "skill_aliases.yaml")

    batch_dir = Path(args.batch_dir)
    if not batch_dir.is_absolute():
        batch_dir = project_root / batch_dir

    consolidated: list[dict] = []
    kept = 0
    dropped = 0
    for staging_file in sorted(batch_dir.glob("BV*/video-staging-reviewed.yaml")):
        raw = yaml.safe_load(staging_file.read_text(encoding="utf-8")) or []
        for item in raw:
            entry = item.get("entry")
            if not entry:
                continue
            cleaned = _clean_entry(entry, hero_alias.canonical_map, hero_valid, skill_alias.canonical_map)
            if cleaned is None:
                dropped += 1
                continue
            kept += 1
            consolidated.append(
                {
                    "metadata": item.get("metadata"),
                    "entry": cleaned,
                }
            )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = project_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(consolidated, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"kept={kept} dropped={dropped} output={output_path}")


if __name__ == "__main__":
    main()
