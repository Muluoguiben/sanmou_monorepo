"""Normalize image inputs (http URL / data URI / local path) to values the
OpenAI vision API accepts in `image_url.url`.

Keep this boring on purpose — the vision provider is bound to OpenAI-compat,
and both `http(s)://...` and `data:image/...;base64,...` are passed through
verbatim by the gateway. Local paths are read and base64-encoded.
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

_ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def prepare_image_inputs(inputs: list[str]) -> list[str]:
    """Return a list of strings safe to put in OpenAI `image_url.url`.

    - `http://` / `https://` → unchanged
    - `data:image/...;base64,...` → unchanged
    - Anything else → treated as a filesystem path, read, base64-encoded
      into a `data:` URI. Raises FileNotFoundError or ValueError on failure.
    """
    out: list[str] = []
    for raw in inputs:
        s = raw.strip()
        if not s:
            continue
        if s.startswith(("http://", "https://", "data:")):
            out.append(s)
            continue
        out.append(_encode_local_path(s))
    return out


def _encode_local_path(path_str: str) -> str:
    path = Path(path_str).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"image path not found: {path}")
    mime, _ = mimetypes.guess_type(path.name)
    if mime is None:
        # Fall back to JPEG — most screenshots are JPEG/PNG, and OpenAI
        # accepts JPEG for either.
        mime = "image/jpeg"
    if mime not in _ALLOWED_MIMES:
        raise ValueError(f"unsupported image mime {mime!r} for {path}")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"
