from pioneer_agent.adapters.capture import (
    CaptureAdapter,
    CaptureFrame,
    ScreenshotFileCaptureAdapter,
    WatchFolderCaptureAdapter,
    WindowsBridgeCaptureAdapter,
)
def __getattr__(name: str):
    # Capture imports must not load the control dependency graph.
    if name in {"ControlAdapter", "UnsupportedControlAdapter", "WindowsBridgeControlAdapter"}:
        from pioneer_agent.adapters import control
        return getattr(control, name)
    raise AttributeError(name)


__all__ = [
    "CaptureAdapter",
    "CaptureFrame",
    "ScreenshotFileCaptureAdapter",
    "WatchFolderCaptureAdapter",
    "WindowsBridgeCaptureAdapter",
    "ControlAdapter",
    "UnsupportedControlAdapter",
    "WindowsBridgeControlAdapter",
]
