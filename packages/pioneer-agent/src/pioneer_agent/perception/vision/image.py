from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

MAX_IMAGE_WIDTH = 1280
MAX_IMAGE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime_type: str


def prepare_image(image: bytes | Path) -> PreparedImage:
    if isinstance(image, Path):
        raw = image.read_bytes()
    else:
        raw = image

    img = Image.open(io.BytesIO(raw))
    mime_type = Image.MIME.get(img.format or "", "image/png")
    needs_resize = img.width > MAX_IMAGE_WIDTH or len(raw) > MAX_IMAGE_BYTES
    if not needs_resize:
        return PreparedImage(data=raw, mime_type=mime_type)

    ratio = MAX_IMAGE_WIDTH / img.width
    new_size = (MAX_IMAGE_WIDTH, int(img.height * ratio))
    resized = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG", optimize=True)
    return PreparedImage(data=buf.getvalue(), mime_type="image/png")
