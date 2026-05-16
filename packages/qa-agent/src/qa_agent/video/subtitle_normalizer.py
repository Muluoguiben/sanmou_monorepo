"""Subtitle normalization for Bilibili AI 中文字幕.

B 站 AI ASR 把三谋专有名词频繁同音替换（黄府松→皇甫嵩、屹然不动→岿然不动 等），
让 `qa_agent.video.openai/gemini` extractor 抽出来的 `hero_names` / `core_skills`
含错别字。本模块在 LLM extractor 之前对 `VideoKnowledgeDocument.segments` 跑一遍
中文规范化，按以下优先级替换：

1. **Manual homophone dict**（`config/subtitle_homophones.yaml`）— 硬编码同音错字。
2. **Hero/Skill alias dict**（从 `knowledge_sources/profiles/{heroes,skills}/*.yaml`
   的 topic + aliases + structured_data.name/aliases 自动构建）— 别名归一到正字。
3. **Fuzzy edit-distance ≤ 1** — 仅作用于 ≥3 字 canonical token，避免 2 字名
   (郭嘉 vs 郭昭) 误匹配；fuzzy 命中默认置 confidence=0.60，且只在 source token
   不命中 canonical 自身时触发。

替换日志（每一次替换 / 候选）以 `SubtitleNormalizationLog` 形式写回 evidence YAML，
便于 review。日志条目字段：`before / after / source(homophone|alias|fuzzy|manual_candidate)
/ rule_type / confidence / segment_id / video_id / scope`。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml
from pydantic import BaseModel, Field

from qa_agent.knowledge.loader import load_entries_from_file
from qa_agent.knowledge.models import (
    EntryKind,
    HeroStaticProfile,
    KnowledgeEntry,
    SkillStaticProfile,
)

from .models import (
    VideoCombatCandidate,
    VideoHeroCandidate,
    VideoKnowledgeDocument,
    VideoLineupCandidate,
    VideoSegment,
    VideoSkillCandidate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Log model — written back into evidence YAML
# ---------------------------------------------------------------------------


class SubtitleNormalizationLog(BaseModel):
    segment_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    before: str = Field(min_length=1)
    after: str = Field(min_length=1)
    source: str  # homophone | alias | fuzzy | manual_candidate
    rule_type: str  # exact | edit_distance | manual_review
    confidence: float = Field(ge=0.0, le=1.0)
    scope: str  # transcript | ocr_line | visual_summary
    kind: str | None = None  # hero | skill | lineup | other


# ---------------------------------------------------------------------------
# Dictionary loading
# ---------------------------------------------------------------------------


@dataclass
class NormalizationRule:
    source: str
    canonical: str
    kind: str  # hero | skill | lineup | other
    confidence: float
    rule_source: str  # homophone | alias

    def __post_init__(self) -> None:
        if not self.source or not self.canonical:
            raise ValueError("source / canonical must be non-empty")


@dataclass
class AmbiguousPattern:
    pattern: str
    candidates: list[str]
    kind: str
    confidence: float


@dataclass
class NormalizationDictionary:
    """Loaded dictionary used to rewrite subtitle / OCR / visual_summary text.

    `exact_rules` is sorted by descending `source` length so longer surface forms
    win during greedy left-to-right replacement. `canonical_terms` is the set of
    KB canonical names used for ≥3-char fuzzy edit-distance fallback.
    """

    exact_rules: list[NormalizationRule] = field(default_factory=list)
    canonical_terms: set[str] = field(default_factory=set)
    canonical_kind: dict[str, str] = field(default_factory=dict)  # term → hero|skill
    ambiguous_patterns: list[AmbiguousPattern] = field(default_factory=list)

    def sorted_exact_rules(self) -> list[NormalizationRule]:
        return sorted(self.exact_rules, key=lambda r: (-len(r.source), r.source))


def _iter_profile_entries(profiles_dir: Path) -> Iterable[KnowledgeEntry]:
    if not profiles_dir.exists():
        return []
    for path in sorted(profiles_dir.rglob("*.yaml")):
        # skip registry/meta files which only carry batch-level rules
        if path.name == "registry.yaml":
            continue
        try:
            yield from load_entries_from_file(path)
        except Exception as exc:  # noqa: BLE001 — bad yaml shouldn't break pipeline
            logger.warning("subtitle_normalizer: failed to load %s: %s", path, exc)


def _extract_terms_for_entry(entry: KnowledgeEntry) -> tuple[str, list[str], str]:
    """Return (canonical, aliases, kind) for a hero/skill profile entry.

    Falls back to topic + entry.aliases when structured_data is missing.
    """
    aliases: list[str] = list(entry.aliases)
    canonical = entry.topic
    kind = "other"
    if entry.entry_kind == EntryKind.HERO_PROFILE and isinstance(entry.structured_data, HeroStaticProfile):
        canonical = entry.structured_data.name or canonical
        aliases.extend(entry.structured_data.aliases)
        kind = "hero"
    elif entry.entry_kind == EntryKind.SKILL_PROFILE and isinstance(entry.structured_data, SkillStaticProfile):
        canonical = entry.structured_data.name or canonical
        aliases.extend(entry.structured_data.aliases)
        kind = "skill"
    return canonical, aliases, kind


def build_dictionary_from_profiles(
    *,
    knowledge_sources_dir: Path,
    homophones_path: Path | None,
) -> NormalizationDictionary:
    """Build a NormalizationDictionary from on-disk KB profiles + homophone YAML.

    Inputs:
    - `knowledge_sources_dir`: typically `packages/qa-agent/knowledge_sources/`.
      Walks both `profiles/heroes/*.yaml` and `profiles/skills/*.yaml`.
    - `homophones_path`: optional manual homophone YAML (see
      `config/subtitle_homophones.yaml`).

    The same alias may map to multiple canonicals in theory; we keep the **first**
    binding seen and warn on conflict so the dictionary stays deterministic.
    """
    dictionary = NormalizationDictionary()
    seen_sources: dict[str, str] = {}

    # 1) hero / skill profiles
    for sub in ("profiles/heroes", "profiles/skills"):
        for entry in _iter_profile_entries(knowledge_sources_dir / sub):
            canonical, aliases, kind = _extract_terms_for_entry(entry)
            if not canonical:
                continue
            dictionary.canonical_terms.add(canonical)
            dictionary.canonical_kind.setdefault(canonical, kind)
            for alias in aliases:
                alias = alias.strip()
                if not alias or alias == canonical:
                    continue
                if alias in seen_sources and seen_sources[alias] != canonical:
                    logger.debug(
                        "subtitle_normalizer: alias %r maps to both %s and %s — keeping first",
                        alias,
                        seen_sources[alias],
                        canonical,
                    )
                    continue
                seen_sources[alias] = canonical
                dictionary.exact_rules.append(
                    NormalizationRule(
                        source=alias,
                        canonical=canonical,
                        kind=kind,
                        confidence=0.90,
                        rule_source="alias",
                    )
                )

    # 2) manual homophone YAML
    if homophones_path is not None and homophones_path.exists():
        payload = yaml.safe_load(homophones_path.read_text(encoding="utf-8")) or {}
        for item in payload.get("homophones", []) or []:
            source = str(item.get("source", "")).strip()
            canonical = str(item.get("canonical", "")).strip()
            if not source or not canonical:
                continue
            kind = str(item.get("kind", "other")).strip() or "other"
            confidence = float(item.get("confidence", 0.85))
            if source in seen_sources and seen_sources[source] != canonical:
                logger.debug(
                    "subtitle_normalizer: homophone %r already bound to %s; manual override → %s",
                    source,
                    seen_sources[source],
                    canonical,
                )
            seen_sources[source] = canonical
            dictionary.exact_rules.append(
                NormalizationRule(
                    source=source,
                    canonical=canonical,
                    kind=kind,
                    confidence=confidence,
                    rule_source="homophone",
                )
            )
            dictionary.canonical_terms.add(canonical)
            dictionary.canonical_kind.setdefault(canonical, kind)
        for item in payload.get("ambiguous", []) or []:
            pattern = str(item.get("pattern", "")).strip()
            cands = [str(x).strip() for x in (item.get("canonical_candidates") or []) if str(x).strip()]
            if not pattern or not cands:
                continue
            dictionary.ambiguous_patterns.append(
                AmbiguousPattern(
                    pattern=pattern,
                    candidates=cands,
                    kind=str(item.get("kind", "other")).strip() or "other",
                    confidence=float(item.get("confidence", 0.60)),
                )
            )

    return dictionary


# ---------------------------------------------------------------------------
# Edit-distance utilities (Levenshtein with early-exit threshold 1)
# ---------------------------------------------------------------------------


def _levenshtein_le1(a: str, b: str) -> bool:
    """True iff Levenshtein(a, b) <= 1. Fast path for length diff >1."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = 0
        for ca, cb in zip(a, b):
            if ca != cb:
                diff += 1
                if diff > 1:
                    return False
        return diff == 1
    # insertion / deletion: pick longer as 'long', shorter as 'short'
    long_, short = (a, b) if la > lb else (b, a)
    i = j = diffs = 0
    while i < len(long_) and j < len(short):
        if long_[i] == short[j]:
            i += 1
            j += 1
        else:
            diffs += 1
            if diffs > 1:
                return False
            i += 1
    return True


_FUZZY_NEIGHBORHOOD_PAD = 2


def _fuzzy_match_canonical(
    text: str,
    canonical_terms: set[str],
    *,
    min_length: int = 3,
) -> list[tuple[int, int, str]]:
    """Return non-overlapping (start, end, canonical) fuzzy matches for `text`.

    Slides a window of size `len(canonical)` for every canonical term of length
    ≥ `min_length` and records spans where Levenshtein ≤ 1 AND the substring is
    not already equal to canonical (caller handles exact matches via the rule
    table). Greedy non-overlap by leftmost-longest.

    Guardrails against false positives (2026-05-15 lessons from chencang batch):

    1. **Neighborhood canonical check**: if the substring's local neighborhood
       (`±_FUZZY_NEIGHBORHOOD_PAD` chars) already contains a DIFFERENT canonical
       name as a substring, the fuzzy match is suppressed. This stops cases like
       `祝融夫人` → `祝甘夫人` (where `融夫人` is edit-distance 1 from canonical
       `甘夫人`) and `皇甫嵩带` → `皇甫嵩2` (where the canonical `皇甫嵩2`
       exists but `皇甫嵩` is already present untouched).
    2. **Self-overlap check**: if the substring equals (post-strip) one of the
       canonical terms via exact match, treat as no-op.
    """
    candidates: list[tuple[int, int, str, int]] = []  # (start, end, canonical, len)
    for canonical in canonical_terms:
        L = len(canonical)
        if L < min_length:
            continue
        for start in range(len(text) - L + 1):
            chunk = text[start : start + L]
            if chunk == canonical:
                continue  # already correct, no rewrite needed
            if not _levenshtein_le1(chunk, canonical):
                continue
            if _neighborhood_has_other_canonical(
                text=text,
                start=start,
                end=start + L,
                proposed_canonical=canonical,
                canonical_terms=canonical_terms,
            ):
                continue
            candidates.append((start, start + L, canonical, L))
    if not candidates:
        return []
    candidates.sort(key=lambda c: (c[0], -c[3]))  # leftmost, longest
    chosen: list[tuple[int, int, str]] = []
    cursor = 0
    for start, end, canonical, _length in candidates:
        if start < cursor:
            continue
        chosen.append((start, end, canonical))
        cursor = end
    return chosen


def _neighborhood_has_other_canonical(
    *,
    text: str,
    start: int,
    end: int,
    proposed_canonical: str,
    canonical_terms: set[str],
    pad: int = _FUZZY_NEIGHBORHOOD_PAD,
) -> bool:
    """Return True if a canonical name OTHER than `proposed_canonical` appears
    as a substring of `text[start-pad : end+pad]`.
    """
    window_start = max(0, start - pad)
    window_end = min(len(text), end + pad)
    window = text[window_start:window_end]
    if not window:
        return False
    for term in canonical_terms:
        if term == proposed_canonical:
            continue
        if not term:
            continue
        if term in window:
            return True
    return False


# ---------------------------------------------------------------------------
# Core string rewrite
# ---------------------------------------------------------------------------


def _greedy_replace_exact(
    text: str,
    rules: list[NormalizationRule],
) -> tuple[str, list[NormalizationRule]]:
    """Apply exact `rules` greedily left-to-right; return rewritten text + applied rules.

    Rules are assumed pre-sorted by descending source length. Multiple
    occurrences of the same rule each produce an applied entry so the log
    reflects every replacement.
    """
    applied: list[NormalizationRule] = []
    out_chars: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        matched: NormalizationRule | None = None
        for rule in rules:
            L = len(rule.source)
            if L == 0:
                continue
            if i + L <= n and text[i : i + L] == rule.source:
                matched = rule
                break
        if matched is None:
            out_chars.append(text[i])
            i += 1
        else:
            out_chars.append(matched.canonical)
            applied.append(matched)
            i += len(matched.source)
    return "".join(out_chars), applied


def _apply_fuzzy(
    text: str,
    canonical_terms: set[str],
    *,
    min_length: int = 3,
) -> tuple[str, list[tuple[str, str]]]:
    """Apply fuzzy edit-distance-≤1 rewrites; return new text + (before, after) pairs."""
    matches = _fuzzy_match_canonical(text, canonical_terms, min_length=min_length)
    if not matches:
        return text, []
    rewrites: list[tuple[str, str]] = []
    out: list[str] = []
    cursor = 0
    for start, end, canonical in matches:
        out.append(text[cursor:start])
        rewrites.append((text[start:end], canonical))
        out.append(canonical)
        cursor = end
    out.append(text[cursor:])
    return "".join(out), rewrites


# ---------------------------------------------------------------------------
# Public API: normalize_text / normalize_document
# ---------------------------------------------------------------------------


@dataclass
class NormalizationStats:
    segments_processed: int = 0
    segments_changed: int = 0
    exact_replacements: int = 0
    fuzzy_replacements: int = 0
    ambiguous_candidates: int = 0


def normalize_text(
    text: str,
    dictionary: NormalizationDictionary,
    *,
    segment_id: str,
    video_id: str,
    scope: str,
    enable_fuzzy: bool = True,
    log_sink: list[SubtitleNormalizationLog] | None = None,
) -> str:
    """Normalize a single text payload using the dictionary.

    Order: exact rules (homophone + alias) → fuzzy edit-distance-≤1 → ambiguous
    candidate emission. Each replacement / candidate is logged into `log_sink`.
    Returns the rewritten string (unchanged if no rule fires).
    """
    if not text:
        return text
    rules = dictionary.sorted_exact_rules()
    new_text, applied = _greedy_replace_exact(text, rules)
    if log_sink is not None:
        for rule in applied:
            log_sink.append(
                SubtitleNormalizationLog(
                    segment_id=segment_id,
                    video_id=video_id,
                    before=rule.source,
                    after=rule.canonical,
                    source=rule.rule_source,
                    rule_type="exact",
                    confidence=rule.confidence,
                    scope=scope,
                    kind=rule.kind,
                )
            )

    if enable_fuzzy and dictionary.canonical_terms:
        new_text, fuzzy_rewrites = _apply_fuzzy(new_text, dictionary.canonical_terms, min_length=3)
        if log_sink is not None:
            for before, after in fuzzy_rewrites:
                log_sink.append(
                    SubtitleNormalizationLog(
                        segment_id=segment_id,
                        video_id=video_id,
                        before=before,
                        after=after,
                        source="fuzzy",
                        rule_type="edit_distance",
                        confidence=0.60,
                        scope=scope,
                        kind=dictionary.canonical_kind.get(after, "other"),
                    )
                )

    # Ambiguous patterns produce candidates only — no rewrite.
    for amb in dictionary.ambiguous_patterns:
        if amb.pattern and amb.pattern in new_text and log_sink is not None:
            log_sink.append(
                SubtitleNormalizationLog(
                    segment_id=segment_id,
                    video_id=video_id,
                    before=amb.pattern,
                    after=" | ".join(amb.candidates),
                    source="manual_candidate",
                    rule_type="manual_review",
                    confidence=amb.confidence,
                    scope=scope,
                    kind=amb.kind,
                )
            )

    return new_text


def normalize_document(
    document: VideoKnowledgeDocument,
    dictionary: NormalizationDictionary,
    *,
    enable_fuzzy: bool = True,
) -> tuple[VideoKnowledgeDocument, list[SubtitleNormalizationLog], NormalizationStats]:
    """Rewrite every segment's transcript / ocr_lines / visual_summary in place
    against `dictionary`, returning the new document, full log list, and stats.

    The original document is not mutated.
    """
    stats = NormalizationStats()
    logs: list[SubtitleNormalizationLog] = []
    new_segments: list[VideoSegment] = []
    video_id = document.source.video_id

    for segment in document.segments:
        stats.segments_processed += 1
        before_logs_len = len(logs)
        new_transcript = normalize_text(
            segment.transcript,
            dictionary,
            segment_id=segment.segment_id,
            video_id=video_id,
            scope="transcript",
            enable_fuzzy=enable_fuzzy,
            log_sink=logs,
        )
        new_ocr_lines = [
            normalize_text(
                line,
                dictionary,
                segment_id=segment.segment_id,
                video_id=video_id,
                scope="ocr_line",
                enable_fuzzy=enable_fuzzy,
                log_sink=logs,
            )
            for line in segment.ocr_lines
        ]
        new_visual_summary = normalize_text(
            segment.visual_summary,
            dictionary,
            segment_id=segment.segment_id,
            video_id=video_id,
            scope="visual_summary",
            enable_fuzzy=enable_fuzzy,
            log_sink=logs,
        )

        new_logs_for_segment = logs[before_logs_len:]
        if new_logs_for_segment:
            for entry in new_logs_for_segment:
                if entry.source == "manual_candidate":
                    stats.ambiguous_candidates += 1
                elif entry.source == "fuzzy":
                    stats.fuzzy_replacements += 1
                else:
                    stats.exact_replacements += 1

        changed = (
            new_transcript != segment.transcript
            or new_ocr_lines != segment.ocr_lines
            or new_visual_summary != segment.visual_summary
        )
        if changed:
            stats.segments_changed += 1
            new_segments.append(
                segment.model_copy(
                    update={
                        "transcript": new_transcript,
                        "ocr_lines": new_ocr_lines,
                        "visual_summary": new_visual_summary,
                    }
                )
            )
        else:
            new_segments.append(segment)

    new_document = document.model_copy(update={"segments": new_segments})
    return new_document, logs, stats


def normalize_candidate_fields(
    document: VideoKnowledgeDocument,
    dictionary: NormalizationDictionary,
    *,
    enable_fuzzy: bool = True,
    log_sink: list[SubtitleNormalizationLog] | None = None,
) -> VideoKnowledgeDocument:
    """Post-extraction sweep: rewrite candidate text fields against the same
    dictionary so a noisy LLM output still lands as canonical in the staging YAML.

    Covers `lineup_candidates`: topic, aliases, hero_names, core_skills,
    facts, constraints, notes. For `hero_candidates`/`skill_candidates`/
    `combat_candidates`: relevant single-token name + facts/constraints.

    Short tokens (< 3 chars) are normalized only via exact rules (no fuzzy)
    regardless of `enable_fuzzy`, matching the 2-char safety rule.
    """

    def _norm(text: str, segment_id: str, scope: str, *, short_token: bool = False) -> str:
        return normalize_text(
            text,
            dictionary,
            segment_id=segment_id,
            video_id=document.source.video_id,
            scope=scope,
            enable_fuzzy=enable_fuzzy and not short_token,
            log_sink=log_sink,
        )

    def _norm_list(values: list[str], segment_id: str, scope: str, *, short_token: bool = False) -> list[str]:
        return [_norm(v, segment_id, scope, short_token=short_token) for v in values]

    new_lineups: list[VideoLineupCandidate] = []
    for cand in document.lineup_candidates:
        new_lineups.append(
            cand.model_copy(
                update={
                    "topic": _norm(cand.topic, cand.segment_id, "candidate.topic"),
                    "aliases": _norm_list(cand.aliases, cand.segment_id, "candidate.alias", short_token=True),
                    "hero_names": _norm_list(cand.hero_names, cand.segment_id, "candidate.hero_name", short_token=True),
                    "core_skills": _norm_list(cand.core_skills, cand.segment_id, "candidate.core_skill", short_token=True),
                    "facts": _norm_list(cand.facts, cand.segment_id, "candidate.fact"),
                    "constraints": _norm_list(cand.constraints, cand.segment_id, "candidate.constraint"),
                    "notes": _norm_list(cand.notes, cand.segment_id, "candidate.note"),
                }
            )
        )

    new_heroes: list[VideoHeroCandidate] = [
        cand.model_copy(
            update={
                "hero_name": _norm(cand.hero_name, cand.segment_id, "candidate.hero_name", short_token=True),
                "facts": _norm_list(cand.facts, cand.segment_id, "candidate.fact"),
                "constraints": _norm_list(cand.constraints, cand.segment_id, "candidate.constraint"),
                "related_topics": _norm_list(cand.related_topics, cand.segment_id, "candidate.related_topic", short_token=True),
            }
        )
        for cand in document.hero_candidates
    ]

    new_skills: list[VideoSkillCandidate] = [
        cand.model_copy(
            update={
                "skill_name": _norm(cand.skill_name, cand.segment_id, "candidate.skill_name", short_token=True),
                "facts": _norm_list(cand.facts, cand.segment_id, "candidate.fact"),
                "constraints": _norm_list(cand.constraints, cand.segment_id, "candidate.constraint"),
                "related_topics": _norm_list(cand.related_topics, cand.segment_id, "candidate.related_topic", short_token=True),
            }
        )
        for cand in document.skill_candidates
    ]

    new_combats: list[VideoCombatCandidate] = [
        cand.model_copy(
            update={
                "topic": _norm(cand.topic, cand.segment_id, "candidate.topic"),
                "facts": _norm_list(cand.facts, cand.segment_id, "candidate.fact"),
                "constraints": _norm_list(cand.constraints, cand.segment_id, "candidate.constraint"),
                "related_topics": _norm_list(cand.related_topics, cand.segment_id, "candidate.related_topic", short_token=True),
            }
        )
        for cand in document.combat_candidates
    ]

    return document.model_copy(
        update={
            "lineup_candidates": new_lineups,
            "hero_candidates": new_heroes,
            "skill_candidates": new_skills,
            "combat_candidates": new_combats,
        }
    )


def default_homophones_path(package_root: Path | None = None) -> Path:
    """Resolve the canonical homophones YAML path.

    `package_root` should be the `packages/qa-agent/` directory; defaults to the
    one this module lives under.
    """
    if package_root is None:
        package_root = Path(__file__).resolve().parents[3]  # …/packages/qa-agent
    return package_root / "config" / "subtitle_homophones.yaml"


def default_knowledge_sources_dir(package_root: Path | None = None) -> Path:
    if package_root is None:
        package_root = Path(__file__).resolve().parents[3]
    return package_root / "knowledge_sources"
