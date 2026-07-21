"""Bounded perceptual fingerprints for Record & Replay corpus isolation.

The gate fully decodes pixels locally and combines multiple independent visual
signals.  Hash buckets only generate candidates; a pair is rejected only after
grayscale and color similarity also agree.  No image or fingerprint is exposed
to a model or serialized in the public audit report.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from statistics import median
from typing import Iterable
import warnings

from PIL import Image, UnidentifiedImageError

from pioneer_agent.record_replay.models import FrameRecord, ImageFormat


VISUAL_FINGERPRINT_ALGORITHM = "sanmou-multisignal-v1"
MAX_DECODED_PIXELS = 16_777_216
MAX_VISUAL_FRAMES = 16_384
MAX_TOTAL_DECODED_PIXELS = 536_870_912
MAX_VISUAL_CANDIDATE_COMPARISONS = 2_000_000
CANONICAL_EDGE = 32
HASH_EDGE = 8
HISTOGRAM_BINS = 8
CROP_RATIOS = (0.0, 0.025, 0.05)
BLOCK_HASH_DISTANCE_LIMIT = 6
DIFFERENCE_HASH_DISTANCE_LIMIT = 8
GRAYSCALE_MAE_LIMIT = 0.06
RGB_MEAN_DISTANCE_LIMIT = 0.06
RGB_HISTOGRAM_DISTANCE_LIMIT = 0.10
ASPECT_LOG_DISTANCE_LIMIT = 0.08


@dataclass(frozen=True)
class VisualHashVariant:
    block_mean_hash: int
    difference_hash: int
    canonical_grayscale: bytes


@dataclass(frozen=True)
class VisualFrameFingerprint:
    session_id: str
    frame_id: str
    encoded_sha256: str
    decoded_pixels: int
    aspect_ratio: float
    rgb_mean: tuple[float, float, float]
    rgb_histogram: tuple[int, ...]
    histogram_pixels: int
    variants: tuple[VisualHashVariant, ...]


@dataclass(frozen=True)
class VisualNearDuplicateAudit:
    algorithm: str
    frame_count: int
    candidate_comparison_count: int


def fingerprint_frame(
    frame: FrameRecord,
    payload: bytes,
) -> VisualFrameFingerprint:
    """Decode one exact frame and derive non-serialized visual features."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as source:
                source_format = (source.format or "").upper()
                width, height = source.size
                if width <= 0 or height <= 0 or width * height > MAX_DECODED_PIXELS:
                    raise ValueError("recording frame exceeds decoded pixel limits")
                if getattr(source, "n_frames", 1) != 1:
                    raise ValueError("recording frame must contain exactly one image")
                expected_format = {
                    ImageFormat.PNG: "PNG",
                    ImageFormat.WEBP: "WEBP",
                }[frame.image_format]
                if source_format != expected_format:
                    raise ValueError("recording frame format does not match its record")
                if source.size != frame.image_size:
                    raise ValueError("decoded frame dimensions do not match its record")
                source.load()
                rgb = source.convert("RGB")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("recording frame exceeds safe decoder limits") from exc
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("recording frame pixels cannot be decoded") from exc

    rgb_signature = rgb.resize(
        (CANONICAL_EDGE, CANONICAL_EDGE), Image.Resampling.LANCZOS
    )
    rgb_mean, rgb_histogram = _color_signature(rgb_signature)
    variants: list[VisualHashVariant] = []
    seen_boxes: set[tuple[int, int, int, int]] = set()
    for crop_ratio in CROP_RATIOS:
        crop_x = int(round(rgb.width * crop_ratio))
        crop_y = int(round(rgb.height * crop_ratio))
        box = (crop_x, crop_y, rgb.width - crop_x, rgb.height - crop_y)
        if box in seen_boxes:
            continue
        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError("recording frame is too small for visual normalization")
        seen_boxes.add(box)
        grayscale = rgb.crop(box).convert("L")
        canonical = grayscale.resize(
            (CANONICAL_EDGE, CANONICAL_EDGE), Image.Resampling.LANCZOS
        )
        variants.append(
            VisualHashVariant(
                block_mean_hash=_block_mean_hash(canonical),
                difference_hash=_difference_hash(grayscale),
                canonical_grayscale=canonical.tobytes(),
            )
        )
    if not variants:
        raise ValueError("recording frame produced no visual fingerprint variants")
    return VisualFrameFingerprint(
        session_id=frame.session_id,
        frame_id=frame.frame_id,
        encoded_sha256=frame.sha256,
        decoded_pixels=rgb.width * rgb.height,
        aspect_ratio=rgb.width / rgb.height,
        rgb_mean=rgb_mean,
        rgb_histogram=rgb_histogram,
        histogram_pixels=CANONICAL_EDGE * CANONICAL_EDGE,
        variants=tuple(variants),
    )


def audit_visual_near_duplicates(
    fingerprints: list[VisualFrameFingerprint],
) -> VisualNearDuplicateAudit:
    """Reject near-clone frames across distinct corpus sessions."""

    if len(fingerprints) > MAX_VISUAL_FRAMES:
        raise ValueError("corpus exceeds the visual fingerprint frame limit")
    if sum(item.decoded_pixels for item in fingerprints) > MAX_TOTAL_DECODED_PIXELS:
        raise ValueError("corpus exceeds the visual fingerprint pixel limit")
    block_index: dict[tuple[int, int], set[int]] = {}
    difference_index: dict[tuple[int, int], set[int]] = {}
    comparisons = 0
    indexed: list[VisualFrameFingerprint] = []

    for fingerprint in fingerprints:
        block_candidates = _bucket_candidates(
            fingerprint,
            index=block_index,
            field="block_mean_hash",
        )
        difference_candidates = _bucket_candidates(
            fingerprint,
            index=difference_index,
            field="difference_hash",
        )
        for candidate_index in sorted(block_candidates & difference_candidates):
            candidate = indexed[candidate_index]
            if candidate.session_id == fingerprint.session_id:
                continue
            comparisons += 1
            if comparisons > MAX_VISUAL_CANDIDATE_COMPARISONS:
                raise ValueError("corpus exceeds the visual comparison limit")
            if _is_near_duplicate(candidate, fingerprint):
                raise ValueError(
                    "visual near-duplicate detected across corpus sessions"
                )
        current_index = len(indexed)
        indexed.append(fingerprint)
        _index_fingerprint(
            fingerprint,
            index=block_index,
            item_index=current_index,
            field="block_mean_hash",
        )
        _index_fingerprint(
            fingerprint,
            index=difference_index,
            item_index=current_index,
            field="difference_hash",
        )

    return VisualNearDuplicateAudit(
        algorithm=VISUAL_FINGERPRINT_ALGORITHM,
        frame_count=len(fingerprints),
        candidate_comparison_count=comparisons,
    )


def _block_mean_hash(canonical: Image.Image) -> int:
    reduced = canonical.resize((HASH_EDGE, HASH_EDGE), Image.Resampling.LANCZOS)
    pixels = reduced.tobytes()
    threshold = median(pixels)
    return _bits_to_int(value >= threshold for value in pixels)


def _difference_hash(grayscale: Image.Image) -> int:
    reduced = grayscale.resize(
        (HASH_EDGE + 1, HASH_EDGE), Image.Resampling.LANCZOS
    )
    pixels = reduced.tobytes()
    bits = []
    for row in range(HASH_EDGE):
        offset = row * (HASH_EDGE + 1)
        bits.extend(
            pixels[offset + column] >= pixels[offset + column + 1]
            for column in range(HASH_EDGE)
        )
    return _bits_to_int(bits)


def _bits_to_int(bits: Iterable[bool]) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | int(bool(bit))
    return value


def _color_signature(
    image: Image.Image,
) -> tuple[tuple[float, float, float], tuple[int, ...]]:
    pixels = image.tobytes()
    count = image.width * image.height
    means = tuple(
        sum(pixels[channel::3]) / (count * 255.0)
        for channel in range(3)
    )
    histogram: list[int] = []
    for channel in range(3):
        bins = [0] * HISTOGRAM_BINS
        for value in pixels[channel::3]:
            bins[min(value * HISTOGRAM_BINS // 256, HISTOGRAM_BINS - 1)] += 1
        histogram.extend(bins)
    return (means[0], means[1], means[2]), tuple(histogram)


def _bucket_candidates(
    fingerprint: VisualFrameFingerprint,
    *,
    index: dict[tuple[int, int], set[int]],
    field: str,
) -> set[int]:
    candidates: set[int] = set()
    for variant in fingerprint.variants:
        value = getattr(variant, field)
        for chunk_index in range(16):
            chunk = (value >> (chunk_index * 4)) & 0xF
            candidates.update(index.get((chunk_index, chunk), ()))
    return candidates


def _index_fingerprint(
    fingerprint: VisualFrameFingerprint,
    *,
    index: dict[tuple[int, int], set[int]],
    item_index: int,
    field: str,
) -> None:
    keys: set[tuple[int, int]] = set()
    for variant in fingerprint.variants:
        value = getattr(variant, field)
        keys.update(
            (chunk_index, (value >> (chunk_index * 4)) & 0xF)
            for chunk_index in range(16)
        )
    for key in keys:
        index.setdefault(key, set()).add(item_index)


def _is_near_duplicate(
    first: VisualFrameFingerprint,
    second: VisualFrameFingerprint,
) -> bool:
    if abs(math.log(first.aspect_ratio / second.aspect_ratio)) > ASPECT_LOG_DISTANCE_LIMIT:
        return False
    if _rgb_mean_distance(first.rgb_mean, second.rgb_mean) > RGB_MEAN_DISTANCE_LIMIT:
        return False
    if _histogram_distance(first, second) > RGB_HISTOGRAM_DISTANCE_LIMIT:
        return False
    for first_variant in first.variants:
        for second_variant in second.variants:
            if (
                (first_variant.block_mean_hash ^ second_variant.block_mean_hash).bit_count()
                > BLOCK_HASH_DISTANCE_LIMIT
            ):
                continue
            if (
                (first_variant.difference_hash ^ second_variant.difference_hash).bit_count()
                > DIFFERENCE_HASH_DISTANCE_LIMIT
            ):
                continue
            if (
                _grayscale_mae(
                    first_variant.canonical_grayscale,
                    second_variant.canonical_grayscale,
                )
                <= GRAYSCALE_MAE_LIMIT
            ):
                return True
    return False


def _rgb_mean_distance(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> float:
    return sum(abs(left - right) for left, right in zip(first, second, strict=True)) / 3


def _histogram_distance(
    first: VisualFrameFingerprint,
    second: VisualFrameFingerprint,
) -> float:
    if first.histogram_pixels != second.histogram_pixels:
        raise ValueError("visual histogram normalization is inconsistent")
    difference = sum(
        abs(left - right)
        for left, right in zip(
            first.rgb_histogram, second.rgb_histogram, strict=True
        )
    )
    return difference / (6 * first.histogram_pixels)


def _grayscale_mae(first: bytes, second: bytes) -> float:
    if len(first) != len(second) or not first:
        raise ValueError("visual grayscale normalization is inconsistent")
    return sum(
        abs(left - right) for left, right in zip(first, second, strict=True)
    ) / (len(first) * 255.0)
