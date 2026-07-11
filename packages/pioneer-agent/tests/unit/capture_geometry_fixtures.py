from __future__ import annotations

from pioneer_agent.core.models import CaptureGeometry


def capture_geometry(
    frame_size: tuple[int, int],
    *,
    backend: str = "wgc",
    hwnd: int = 101,
    pid: int = 202,
    capture_origin: tuple[int, int] = (0, 0),
    outer_rect: tuple[int, int, int, int] | None = None,
) -> CaptureGeometry:
    width, height = frame_size
    left, top = capture_origin
    capture_rect = (left, top, left + width, top + height)
    if outer_rect is None:
        outer_rect = capture_rect
    outer_left, outer_top, outer_right, outer_bottom = outer_rect
    return CaptureGeometry.model_validate(
        {
            "schema_version": 1,
            "capture_backend": backend,
            "outer_window": {
                "hwnd": hwnd,
                "pid": pid,
                "left": outer_left,
                "top": outer_top,
                "right": outer_right,
                "bottom": outer_bottom,
                "width": outer_right - outer_left,
                "height": outer_bottom - outer_top,
            },
            "capture_rect": {
                "left": capture_rect[0],
                "top": capture_rect[1],
                "right": capture_rect[2],
                "bottom": capture_rect[3],
                "width": width,
                "height": height,
            },
            "capture_origin": {"x": left, "y": top},
            "frame_size": [width, height],
        }
    )


def capture_geometry_payload(
    frame_size: tuple[int, int],
    **kwargs: object,
) -> dict[str, object]:
    return capture_geometry(frame_size, **kwargs).model_dump(mode="json")
