from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

# Keep the fit window conservative and model-agnostic.
MAX_IMAGE_WIDTH = 1280
MAX_IMAGE_PIXELS = 1_150_000
MAX_IMAGE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime_type: str
    original_size: tuple[int, int]
    prepared_size: tuple[int, int]
    resized: bool


def prepare_image(image: bytes | Path) -> PreparedImage:
    if isinstance(image, Path):
        raw = image.read_bytes()
    else:
        raw = image

    img = Image.open(io.BytesIO(raw))
    mime_type = Image.MIME.get(img.format or "", "image/png")
    original_size = (img.width, img.height)
    target_size = _compute_target_size(img.width, img.height)

    prepared_img = img
    resized = False
    if target_size != original_size:
        prepared_img = img.resize(target_size, Image.Resampling.LANCZOS)
        resized = True
    else:
        if len(raw) <= MAX_IMAGE_BYTES:
            return PreparedImage(
                data=raw,
                mime_type=mime_type,
                original_size=original_size,
                prepared_size=original_size,
                resized=False,
            )

    buf = io.BytesIO()
    prepared_img.save(buf, format="PNG", optimize=True)
    prepared_bytes = buf.getvalue()
    if len(prepared_bytes) <= MAX_IMAGE_BYTES:
        return PreparedImage(
            data=prepared_bytes,
            mime_type="image/png",
            original_size=original_size,
            prepared_size=prepared_img.size,
            resized=resized,
        )

    # Preserve aspect ratio while shrinking further until request-size constraints are met.
    current = prepared_img
    while len(prepared_bytes) > MAX_IMAGE_BYTES and min(current.size) > 1:
        target_width = max(1, int(current.width * 0.9))
        target_height = max(1, int(current.height * 0.9))
        # Respect original aspect ratio better than a single downscale step.
        target_size = _compute_target_size(target_width, target_height, force_within_pixels=False)
        if target_size == current.size:
            break
        current = current.resize(target_size, Image.Resampling.LANCZOS)
        resized = True
        buf = io.BytesIO()
        current.save(buf, format="PNG", optimize=True)
        prepared_bytes = buf.getvalue()

    return PreparedImage(
        data=prepared_bytes,
        mime_type="image/png",
        original_size=original_size,
        prepared_size=current.size,
        resized=resized,
    )


def _compute_target_size(
    width: int,
    height: int,
    *,
    max_long_edge: int = MAX_IMAGE_WIDTH,
    max_pixels: int = MAX_IMAGE_PIXELS,
    force_within_pixels: bool = True,
) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid image size: {width}x{height}")

    if width <= max_long_edge and height <= max_long_edge and (
        not force_within_pixels or width * height <= max_pixels
    ):
        return width, height

    if width >= height:
        h_from_pixels = int(math.sqrt(max_pixels / (width / height)))
        w_from_pixels = int(h_from_pixels * (width / height))
        target_width = min(w_from_pixels, max_long_edge)
        target_height = int(target_width * (height / width))
    else:
        w_from_pixels = int(math.sqrt(max_pixels / (height / width)))
        h_from_pixels = int(w_from_pixels * (height / width))
        target_height = min(h_from_pixels, max_long_edge)
        target_width = int(target_height * (width / height))

    target_width = max(1, min(target_width, width))
    target_height = max(1, min(target_height, height))
    return target_width, target_height
