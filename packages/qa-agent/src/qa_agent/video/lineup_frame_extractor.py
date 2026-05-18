"""Lineup frame extractor — structured 阵容/武将 config from UP-master video frames.

Background (task #11, P2): the Bilibili AI-subtitle pipeline (task #8/#9)
cannot fill `hero_names` / `core_skills` when the UP master only *shows* the
team-config screen without reading every hero/skill aloud. This module
consumes a `--with-frames` bundle (ffmpeg-sampled stills), classifies which
frames are lineup/hero pages, runs the vision `ImageExtractor` over them, and
aggregates per time-window hero/skill signals so the existing staging entries
can be back-filled.

Design:
- Pure functions + small classes, vision access behind a Protocol so unit
  tests run with a fake extractor (no network / no real frames).
- Frame timestamps are recovered from the sampler's filename convention
  ``<BVID>-frame-<NNN>-<T>s.jpg`` (fallback: bundle segment frame_refs).
- Backfill is conservative: only *empty* hero_names / core_skills slots are
  filled; existing values are never overwritten. Every fill records a trace
  (frames used + raw vision names) so a human can audit before publish.
- Recognized names are snapped to KB canonical via the subtitle_normalizer
  dictionary so frame output stays consistent with task #8/#9 corrections.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

# Filename convention emitted by frame_sampler / fetch_bilibili_bundle:
#   BV1fXosBGEHd-frame-002-20s.jpg  -> timestamp 20.0s
_FRAME_TS_RE = re.compile(r"-frame-\d+-(\d+(?:\.\d+)?)s\.[A-Za-z0-9]+$")

# Subtitle/transcript signals that a segment is presenting a team/lineup page.
_LINEUP_TEXT_SIGNALS = (
    "队", "套", "组", "页", "阵容", "首发", "共存", "梯队", "配队", "队伍",
    "第一", "第二", "第三", "第四", "第五", "主C", "开荒",
)


class _VisionExtractorProtocol(Protocol):
    def extract(self, image_urls: list[str], *, question: str | None = ...): ...


# Frame-kind taxonomy (task #11 v2): only 汇总表 / 方案表 are worth per-column
# extraction; 克制图 is a counter graph (relations, not per-team config);
# `other` = talking-head / transition.
FRAME_SUMMARY_TABLE = "summary_table"   # 全流程阵容汇总表: 4-8 teams in columns
FRAME_SCHEME_TABLE = "scheme_table"     # 方案A/B 配置表: rows 阵型/战法/加点/...
FRAME_COUNTER_GRAPH = "counter_graph"   # 克制关系图: graph of matchups
FRAME_OTHER = "other"

_CLASSIFY_RULES = (
    ("汇总", FRAME_SUMMARY_TABLE),
    ("全流派", FRAME_SUMMARY_TABLE),
    ("全流程", FRAME_SUMMARY_TABLE),
    ("方案", FRAME_SCHEME_TABLE),
    ("共存", FRAME_SCHEME_TABLE),
    # 出队路线/路线图 X.0 tables list many teams in columns (eval found
    # BV1R4d3BfENk-frame-015 "陈仓之战·出队路线5.0-最终版" misclassified
    # other). Placed after 方案/共存 so a 方案 route table still wins scheme.
    ("出队路线", FRAME_SUMMARY_TABLE),
    ("路线图", FRAME_SUMMARY_TABLE),
    ("克制", FRAME_COUNTER_GRAPH),
    ("克制关系", FRAME_COUNTER_GRAPH),
)

TABLE_FRAME_KINDS = (FRAME_SUMMARY_TABLE, FRAME_SCHEME_TABLE)


def classify_frame_kind(text_signals: list[str]) -> str:
    """Cheap title/snippet heuristic → frame kind.

    Fed by the vision text_snippets (page title is the most reliable cue) or
    the segment transcript. Avoids spending a dedicated vision call just to
    classify. Order matters: 汇总/方案 before 克制 since a 方案 table can also
    mention 克制 in cell text.
    """
    blob = " ".join(s for s in text_signals if s)
    for needle, kind in _CLASSIFY_RULES:
        if needle in blob:
            return kind
    return FRAME_OTHER


def crop_into_columns(
    image_path: str,
    n_cols: int,
    out_dir: str,
    *,
    overlap_frac: float = 0.04,
    upscale: int = 2,
    top_crop_frac: float = 0.0,
) -> list[str]:
    """Split a table frame into `n_cols` equal-width column images.

    Each slice carries a small horizontal `overlap_frac` so a team's column
    isn't clipped at the seam, is optionally cropped below a `top_crop_frac`
    title band, and is upscaled `upscale`x (the sampled frames are only
    640x360 — upscaling + detail="original" recovers small 战法 text). Returns
    the written sub-image paths left→right.
    """
    from PIL import Image  # local import keeps module load light

    if n_cols < 1:
        raise ValueError("n_cols must be >= 1")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img = Image.open(image_path)
    w, h = img.size
    top = int(h * max(0.0, min(0.9, top_crop_frac)))
    col_w = w / n_cols
    ov = int(col_w * max(0.0, overlap_frac))
    stem = Path(image_path).stem
    paths: list[str] = []
    for i in range(n_cols):
        left = max(0, int(i * col_w) - ov)
        right = min(w, int((i + 1) * col_w) + ov)
        crop = img.crop((left, top, right, h))
        if upscale and upscale > 1:
            crop = crop.resize(
                (crop.width * upscale, crop.height * upscale), Image.LANCZOS
            )
        dest = out / f"{stem}-col{i + 1}of{n_cols}.png"
        crop.save(dest)
        paths.append(str(dest))
    return paths


@dataclass(frozen=True)
class FrameRef:
    """A single sampled frame with a recovered timestamp."""

    path: str
    timestamp_sec: float

    @property
    def is_local(self) -> bool:
        return not self.path.startswith(("http://", "https://"))


@dataclass
class FrameLineupSignal:
    """Aggregated hero/skill signals for one source time window."""

    bvid: str
    start_sec: float
    end_sec: float
    hero_names: list[str] = field(default_factory=list)
    core_skills: list[str] = field(default_factory=list)
    frames_used: list[str] = field(default_factory=list)
    raw_hero_names: list[str] = field(default_factory=list)
    raw_core_skills: list[str] = field(default_factory=list)


def parse_frame_timestamp(path: str) -> float | None:
    """Recover the sampled-frame timestamp from its filename, else None."""
    m = _FRAME_TS_RE.search(path)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:  # pragma: no cover - regex already constrains digits
        return None


def collect_frames_from_bundle(bundle: dict) -> list[FrameRef]:
    """Return every local sampled frame in a `--with-frames` bundle, sorted by ts.

    Story-thumbnail URLs (i*.hdslb.com/bfs/storyff/...) are skipped — they are
    auto-generated covers, not the UP master's lineup screen.
    """
    seen: dict[str, FrameRef] = {}
    for seg in bundle.get("segments", []) or []:
        seg_start = _as_float(seg.get("start_sec"), 0.0)
        for raw in seg.get("frame_paths", []) or []:
            if not isinstance(raw, str) or not raw:
                continue
            if raw.startswith(("http://", "https://")):
                continue  # story cover, not a sampled lineup frame
            if raw in seen:
                continue
            ts = parse_frame_timestamp(raw)
            if ts is None:
                ts = seg_start
            seen[raw] = FrameRef(path=raw, timestamp_sec=ts)
    return sorted(seen.values(), key=lambda f: f.timestamp_sec)


def frames_in_window(
    frames: list[FrameRef],
    start_sec: float,
    end_sec: float,
    *,
    margin_sec: float = 8.0,
    max_frames: int = 6,
) -> list[FrameRef]:
    """Frames whose timestamp falls in [start-margin, end+margin], capped."""
    lo = max(0.0, start_sec - margin_sec)
    hi = end_sec + margin_sec
    hits = [f for f in frames if lo <= f.timestamp_sec <= hi]
    if len(hits) <= max_frames:
        return hits
    # Evenly subsample to stay under the vision token budget.
    step = len(hits) / max_frames
    return [hits[int(i * step)] for i in range(max_frames)]


def looks_like_lineup_segment(transcript: str, ocr_lines: list[str] | None) -> bool:
    """Heuristic seed (from Spark's anchor list): does this segment narrate a
    team/lineup page? Used to prioritise which windows to spend vision on.
    """
    blob = (transcript or "") + " " + " ".join(ocr_lines or [])
    return any(sig in blob for sig in _LINEUP_TEXT_SIGNALS)


@dataclass
class BackfillStats:
    entries_total: int = 0
    entries_targeted: int = 0
    entries_filled_hero: int = 0
    entries_filled_skill: int = 0
    entries_pending: int = 0
    frames_analyzed: int = 0
    vision_errors: int = 0


def _as_float(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _parse_source_ref(source_ref: str) -> tuple[str, float, float] | None:
    """`BILIBILI:BV1kVohBPEeS#76-106` -> ('BV1kVohBPEeS', 76.0, 106.0)."""
    if not source_ref or "BV" not in source_ref:
        return None
    m = re.search(r"(BV[0-9A-Za-z]+)(?:#(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?))?", source_ref)
    if not m:
        return None
    bvid = m.group(1)
    if m.group(2) is None:
        return (bvid, 0.0, 1e9)
    return (bvid, float(m.group(2)), float(m.group(3)))


def _dedupe(seq: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in seq:
        x = (x or "").strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


class LineupFrameExtractor:
    """Runs the vision extractor over lineup frames and back-fills staging."""

    def __init__(
        self,
        extractor: _VisionExtractorProtocol,
        *,
        canonicalize=None,
        prepare_images=None,
        vision_params: dict | None = None,
    ) -> None:
        """`canonicalize`: optional ``str -> str`` mapping a raw recognized
        name to its KB-canonical form (typically wired to the
        subtitle_normalizer dictionary so frame names match task #8/#9).

        `prepare_images`: optional ``list[str] -> list[str]`` converting local
        frame paths to gateway-acceptable inputs (base64 data URIs). Defaults
        to ``qa_agent.vision.image_loader.prepare_image_inputs`` — the same
        step `vision_enrichment` uses. Passing local paths straight to the
        OpenAI-compatible gateway yields HTTP 400; tests inject identity.
        """
        self._extractor = extractor
        self._canon = canonicalize or (lambda s: s)
        # Dense-table vision params (task #11 v2, per GPT-5.4 vision cookbook).
        # Overridable so the model-comparison eval can sweep them.
        self._vision_params = vision_params if vision_params is not None else {
            "image_detail": "original",
            "reasoning_effort": "high",
            "verbosity": "high",
            "max_tokens": 2000,
        }
        if prepare_images is None:
            from qa_agent.vision.image_loader import prepare_image_inputs

            prepare_images = prepare_image_inputs
        self._prepare_images = prepare_images

    def extract_window(
        self,
        bvid: str,
        frames: list[FrameRef],
        start_sec: float,
        end_sec: float,
        *,
        stats: BackfillStats | None = None,
    ) -> FrameLineupSignal:
        sig = FrameLineupSignal(bvid=bvid, start_sec=start_sec, end_sec=end_sec)
        window = frames_in_window(frames, start_sec, end_sec)
        if not window:
            return sig
        sig.frames_used = [f.path for f in window]
        try:
            image_inputs = self._prepare_images([f.path for f in window])
        except Exception as exc:  # noqa: BLE001 - bad/missing frame, fail open
            logger.warning("lineup_frame_extractor: image prep failed %s#%s-%s: %s",
                           bvid, start_sec, end_sec, exc)
            if stats is not None:
                stats.vision_errors += 1
            return sig
        try:
            result = self._extractor.extract(
                image_inputs,
                question=(
                    "这是三国谋定天下 UP 主视频里的阵容/武将配置画面，"
                    "列出画面中可辨识的武将名与战法名。"
                ),
                **self._vision_params,
            )
        except Exception as exc:  # noqa: BLE001 - fail open per pipeline policy
            logger.warning("lineup_frame_extractor: vision failed %s#%s-%s: %s",
                           bvid, start_sec, end_sec, exc)
            if stats is not None:
                stats.vision_errors += 1
            return sig
        if stats is not None:
            stats.frames_analyzed += len(window)
        raw_heroes = [e.name for e in getattr(result, "heroes", [])]
        raw_skills = [e.name for e in getattr(result, "skills", [])]
        sig.raw_hero_names = _dedupe(raw_heroes)
        sig.raw_core_skills = _dedupe(raw_skills)
        sig.hero_names = _dedupe([self._canon(n) for n in raw_heroes])
        sig.core_skills = _dedupe([self._canon(n) for n in raw_skills])
        return sig

    def backfill_entries(
        self,
        staging: list[dict],
        bundles_by_bvid: dict[str, dict],
        *,
        allow_canonical_fill: bool = False,
    ) -> tuple[list[dict], BackfillStats]:
        """Fill *empty* hero_names / core_skills on staging entries from frames.

        Never overwrites existing values. Records a per-entry trace under
        ``structured_data.notes`` so a human can audit before publish.

        ``allow_canonical_fill`` gates whether frame-extracted names are written
        into the canonical ``hero_names``/``core_skills`` (publish-eligible) or
        only into ``frame_candidate_*`` + ``needs_review`` (pending). The task
        #11 v2 eval measured ≤0.56 GT hero recall for gpt-5.4* on the
        hand-verified frame, with errors that are *valid KB heroes on the wrong
        team* (low misfill, so a naive canonical check passes them). Per the
        "宁 pending 不污染 KB" doctrine this defaults to ``False``; flip to
        ``True`` only once a model clears the recall gate (see task #2/#4).
        """
        stats = BackfillStats(entries_total=len(staging))
        frame_cache: dict[str, list[FrameRef]] = {}

        for item in staging:
            entry = item.get("entry", item)
            sd = entry.get("structured_data")
            if not isinstance(sd, dict):
                continue
            hero_empty = not (sd.get("hero_names") or entry.get("hero_names"))
            skill_empty = not (sd.get("core_skills") or entry.get("core_skills"))
            if not (hero_empty or skill_empty):
                continue
            ref = _parse_source_ref(
                entry.get("source_ref") or sd.get("source_ref") or ""
            )
            if ref is None:
                continue
            bvid, s, e = ref
            bundle = bundles_by_bvid.get(bvid)
            if bundle is None:
                continue
            stats.entries_targeted += 1
            if bvid not in frame_cache:
                frame_cache[bvid] = collect_frames_from_bundle(bundle)
            sig = self.extract_window(
                bvid, frame_cache[bvid], s, e, stats=stats
            )
            trace: list[str] = []
            pending = False
            if hero_empty and sig.hero_names:
                if allow_canonical_fill:
                    sd["hero_names"] = sig.hero_names
                    stats.entries_filled_hero += 1
                    trace.append(
                        f"hero_names 由阵容图回填 (raw={sig.raw_hero_names})"
                    )
                else:
                    sd["frame_candidate_hero_names"] = sig.hero_names
                    pending = True
                    trace.append(
                        f"hero_names 候选待审 (raw={sig.raw_hero_names})"
                    )
            if skill_empty and sig.core_skills:
                if allow_canonical_fill:
                    sd["core_skills"] = sig.core_skills
                    stats.entries_filled_skill += 1
                    trace.append(
                        f"core_skills 由阵容图回填 (raw={sig.raw_core_skills})"
                    )
                else:
                    sd["frame_candidate_core_skills"] = sig.core_skills
                    pending = True
                    trace.append(
                        f"core_skills 候选待审 (raw={sig.raw_core_skills})"
                    )
            if pending:
                sd["needs_review"] = True
                stats.entries_pending += 1
            if trace:
                tag = "[task#11 阵容图抽取-候选待审]" if pending else "[task#11 阵容图抽取]"
                notes = sd.get("notes")
                if not isinstance(notes, list):
                    notes = []
                notes.append(
                    tag + " "
                    + "；".join(trace)
                    + f"；源帧={[Path(p).name for p in sig.frames_used]}"
                    + f"；source_ref={bvid}#{int(s)}-{int(e)}"
                )
                sd["notes"] = notes
        return staging, stats
