"""Standalone, read-only Windows recorder for a Sanmou demonstration.

Run this file with Windows Python. It never imports a control adapter, opens a
socket, elevates itself, or dispatches input. Raw Input is used only to observe
physical gestures while the bound Unity window is foreground.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import UTC, datetime
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time
from typing import Any, Callable
from uuid import UUID, uuid4


RECORDER_VERSION = "windows-standalone-v1"
TARGET_PROCESS_NAME = "com.bilibili.nslg"
TARGET_WINDOW_CLASS = "UnityWndClass"
SCHEMA_VERSION = 1
FOCUS_QUARANTINE_MS = 100
DRAG_THRESHOLD_PX = 6
PRE_CAPTURE_INTERVAL_MS = 200
MAX_PRE_FRAME_AGE_MS = 1_000
MAX_BATCH_EVENTS = 64
MAX_BATCH_WINDOW_MS = 2_000

SAFE_KEY_NAMES = {
    0x08: "backspace",
    0x09: "tab",
    0x0D: "enter",
    0x1B: "escape",
    0x20: "space",
    0x21: "page_up",
    0x22: "page_down",
    0x23: "end",
    0x24: "home",
    0x25: "left",
    0x26: "up",
    0x27: "right",
    0x28: "down",
    0x2E: "delete",
}
MODIFIER_VKS = {0x10: "shift", 0x11: "ctrl", 0x12: "alt"}


def safe_key_name(vk_code: int) -> str | None:
    """Return only navigation keys; printable input is never persisted."""
    return SAFE_KEY_NAMES.get(vk_code)


def capture_relative_point(
    absolute_x: int,
    absolute_y: int,
    geometry: dict[str, Any],
) -> tuple[dict[str, int], dict[str, float]] | None:
    origin = geometry["capture_origin"]
    width, height = geometry["frame_size"]
    x = absolute_x - int(origin["x"])
    y = absolute_y - int(origin["y"])
    if not (0 <= x < width and 0 <= y < height):
        return None
    return {"x": x, "y": y}, {"x": x / width, "y": y / height}


def _load_capture_module() -> Any:
    if os.name != "nt":
        raise RuntimeError("Windows Record & Replay requires Windows Python")
    import importlib.util

    module_path = Path(__file__).with_name("win_capture.py")
    spec = importlib.util.spec_from_file_location("sanmou_readonly_capture", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load the Sanmou capture implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_workflow_validator() -> Callable[[str], str]:
    import importlib.util

    module_path = Path(__file__).parents[1] / "record_replay" / "validation.py"
    spec = importlib.util.spec_from_file_location(
        "sanmou_record_replay_validation", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load Record & Replay validation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_workflow_name


class JsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = path.open("xb")
        self.sequence = 0
        self.record_count = 0
        self.frame_count = 0
        self.input_event_count = 0
        self.capture_error_count = 0
        self.total_frame_bytes = 0

    def append(self, value: dict[str, Any]) -> dict[str, Any]:
        record = dict(value)
        record["sequence"] = self.sequence
        payload = (
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        self.handle.write(payload)
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.sequence += 1
        self.record_count += 1
        if record["record_type"] == "frame":
            self.frame_count += 1
            self.total_frame_bytes += int(record["byte_size"])
        elif record["record_type"] == "input":
            self.input_event_count += 1
        elif record["record_type"] == "capture_error":
            self.capture_error_count += 1
        return record

    def close(self) -> str:
        if not self.handle.closed:
            self.handle.flush()
            os.fsync(self.handle.fileno())
            self.handle.close()
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


class RawInputCollector:
    """Collect click/drag/scroll and allowlisted navigation keys via Raw Input."""

    def __init__(self, target_hwnd: int, target_pid: int, *, max_events: int) -> None:
        self.target_hwnd = target_hwnd
        self.target_pid = target_pid
        self.events: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=max_events)
        self.ignored_event_count = 0
        self.fatal_error: str | None = None
        self.stop_requested = threading.Event()
        self.ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._window_hwnd: int | None = None
        self._last_foreground: int | None = None
        self._foreground_since_ns = 0
        self._pressed_buttons: dict[str, dict[str, Any]] = {}
        self._pressed_modifiers: set[str] = set()
        self.pointer_gesture_active = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()
        if not self.ready.wait(timeout=5):
            raise RuntimeError(self.fatal_error or "Raw Input recorder did not become ready")
        if self.fatal_error:
            raise RuntimeError(self.fatal_error)

    def stop(self) -> None:
        self.stop_requested.set()
        if self._window_hwnd:
            ctypes.windll.user32.PostMessageW(self._window_hwnd, 0x0010, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _message_loop(self) -> None:
        try:
            self._run_message_loop()
        except Exception as exc:  # pragma: no cover - Windows failure path
            self.fatal_error = f"raw_input_failed:{type(exc).__name__}:{exc}"
            self.stop_requested.set()
            self.ready.set()

    def _run_message_loop(self) -> None:  # pragma: no cover - exercised on Windows
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.PostMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.PostMessageW.restype = wintypes.BOOL
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        class RAWINPUTDEVICE(ctypes.Structure):
            _fields_ = [
                ("usUsagePage", wintypes.USHORT),
                ("usUsage", wintypes.USHORT),
                ("dwFlags", wintypes.DWORD),
                ("hwndTarget", wintypes.HWND),
            ]

        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.RegisterRawInputDevices.argtypes = [
            ctypes.POINTER(RAWINPUTDEVICE),
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.RegisterRawInputDevices.restype = wintypes.BOOL
        user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = ctypes.c_ssize_t
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.DestroyWindow.restype = wintypes.BOOL
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.IsWindow.restype = wintypes.BOOL
        user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
        user32.UnregisterClassW.restype = wintypes.BOOL
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.PostQuitMessage.restype = None

        def wndproc(hwnd: int, message: int, wparam: int, lparam: int) -> int:
            if message == 0x00FF:  # WM_INPUT
                try:
                    self._handle_raw_input(lparam)
                except Exception as exc:
                    self.fatal_error = f"raw_input_decode_failed:{type(exc).__name__}:{exc}"
                    self.stop_requested.set()
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)
                return 0
            if message == 0x0312:  # WM_HOTKEY
                self.stop_requested.set()
                return 0
            if message == 0x0010:  # WM_CLOSE
                user32.DestroyWindow(hwnd)
                return 0
            if message == 0x0002:  # WM_DESTROY
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)

        self._wndproc_ref = WNDPROC(wndproc)
        class_name = f"SanmouRecordReplay-{uuid4()}"
        instance = kernel32.GetModuleHandleW(None)
        window_class = WNDCLASSW(
            0,
            self._wndproc_ref,
            0,
            0,
            instance,
            None,
            None,
            None,
            None,
            class_name,
        )
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            raise ctypes.WinError()
        HWND_MESSAGE = wintypes.HWND(-3)
        hwnd = user32.CreateWindowExW(
            0, class_name, class_name, 0, 0, 0, 0, 0, HWND_MESSAGE, None, instance, None
        )
        if not hwnd:
            raise ctypes.WinError()
        self._window_hwnd = hwnd
        devices = (RAWINPUTDEVICE * 2)(
            RAWINPUTDEVICE(1, 2, 0x00000100, hwnd),  # generic mouse, INPUTSINK
            RAWINPUTDEVICE(1, 6, 0x00000100, hwnd),  # generic keyboard, INPUTSINK
        )
        if not user32.RegisterRawInputDevices(
            devices, len(devices), ctypes.sizeof(RAWINPUTDEVICE)
        ):
            raise ctypes.WinError()
        # Ctrl+Shift+F12 is consumed by RegisterHotKey and never written as input.
        if not user32.RegisterHotKey(hwnd, 1, 0x0002 | 0x0004 | 0x4000, 0x7B):
            raise RuntimeError("stop_hotkey_registration_failed")
        foreground = int(user32.GetForegroundWindow() or 0)
        root = int(user32.GetAncestor(foreground, 2) or foreground)
        self._last_foreground = root
        self._foreground_since_ns = time.perf_counter_ns()
        if self._foreground_matches_target(root):
            self._foreground_since_ns -= FOCUS_QUARANTINE_MS * 1_000_000
        self.ready.set()

        message = wintypes.MSG()
        while not self.stop_requested.is_set():
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result == -1:
                raise ctypes.WinError()
            if result == 0:
                break
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        user32.UnregisterHotKey(hwnd, 1)
        if user32.IsWindow(hwnd):
            user32.DestroyWindow(hwnd)
        user32.UnregisterClassW(class_name, instance)

    def _handle_raw_input(self, raw_handle: int) -> None:  # pragma: no cover - Windows
        user32 = ctypes.windll.user32
        user32.GetRawInputData.argtypes = [
            wintypes.HANDLE,
            wintypes.UINT,
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.UINT),
            wintypes.UINT,
        ]
        user32.GetRawInputData.restype = wintypes.UINT
        size = wintypes.UINT(0)
        header_size = ctypes.sizeof(RAWINPUTHEADER)
        first_result = user32.GetRawInputData(
            wintypes.HANDLE(raw_handle),
            0x10000003,
            None,
            ctypes.byref(size),
            header_size,
        )
        if first_result != 0 or size.value < header_size:
            raise RuntimeError("GetRawInputData size query failed")
        buffer = ctypes.create_string_buffer(size.value)
        copied = user32.GetRawInputData(
            wintypes.HANDLE(raw_handle),
            0x10000003,
            buffer,
            ctypes.byref(size),
            header_size,
        )
        if copied == 0xFFFFFFFF or copied != size.value:
            raise RuntimeError("GetRawInputData payload read failed")
        raw = ctypes.cast(buffer, ctypes.POINTER(RAWINPUT)).contents
        if raw.header.dwType == 0:
            self._handle_mouse(raw.data.mouse)
        elif raw.header.dwType == 1:
            self._handle_keyboard(raw.data.keyboard)

    def _target_is_foreground(self) -> bool:  # pragma: no cover - Windows
        user32 = ctypes.windll.user32
        foreground = int(user32.GetForegroundWindow() or 0)
        root = int(user32.GetAncestor(foreground, 2) or foreground)
        now = time.perf_counter_ns()
        if root != self._last_foreground:
            self._last_foreground = root
            self._foreground_since_ns = now
        if not self._foreground_matches_target(root):
            self.ignored_event_count += 1
            return False
        if now - self._foreground_since_ns < FOCUS_QUARANTINE_MS * 1_000_000:
            self.ignored_event_count += 1
            return False
        return True

    def _foreground_matches_target(self, root: int) -> bool:  # pragma: no cover - Windows
        if root != self.target_hwnd:
            return False
        pid = wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(
            wintypes.HWND(root), ctypes.byref(pid)
        )
        return int(pid.value) == self.target_pid

    def _cursor(self) -> tuple[int, int]:  # pragma: no cover - Windows
        point = wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            raise ctypes.WinError()
        return int(point.x), int(point.y)

    def _handle_mouse(self, mouse: Any) -> None:  # pragma: no cover - Windows
        flags = int(mouse.usButtonFlags)
        mapping = (
            (0x0001, "left", True),
            (0x0002, "left", False),
            (0x0004, "right", True),
            (0x0008, "right", False),
            (0x0010, "middle", True),
            (0x0020, "middle", False),
        )
        for bit, button, pressed in mapping:
            if not flags & bit:
                continue
            if not self._target_is_foreground():
                self._pressed_buttons.pop(button, None)
                if not self._pressed_buttons:
                    self.pointer_gesture_active.clear()
                continue
            x, y = self._cursor()
            now_ns = time.perf_counter_ns()
            now_iso = datetime.now(UTC).isoformat()
            if pressed:
                self.pointer_gesture_active.set()
                self._pressed_buttons[button] = {
                    "x": x,
                    "y": y,
                    "started_ns": now_ns,
                    "started_at": now_iso,
                }
            else:
                start = self._pressed_buttons.pop(button, None)
                if start is None:
                    if not self._pressed_buttons:
                        self.pointer_gesture_active.clear()
                    self.ignored_event_count += 1
                    continue
                distance = math.hypot(x - start["x"], y - start["y"])
                self._emit(
                    {
                        "kind": "drag" if distance >= DRAG_THRESHOLD_PX else "click",
                        "button": button,
                        "start_abs": {"x": start["x"], "y": start["y"]},
                        "end_abs": {"x": x, "y": y},
                        "started_ns": start["started_ns"],
                        "ended_ns": now_ns,
                        "occurred_at": start["started_at"],
                        "ended_at": now_iso,
                        "modifiers": sorted(self._pressed_modifiers),
                    }
                )
                # Keep the ring paused until the completed gesture is visible
                # in the queue; otherwise a post-press capture could race in as
                # the event's alleged pre-input frame.
                if not self._pressed_buttons:
                    self.pointer_gesture_active.clear()
        if flags & 0x0400 and self._target_is_foreground():
            x, y = self._cursor()
            delta = ctypes.c_short(int(mouse.usButtonData)).value
            now_ns = time.perf_counter_ns()
            now_iso = datetime.now(UTC).isoformat()
            self._emit(
                {
                    "kind": "scroll",
                    "start_abs": {"x": x, "y": y},
                    "started_ns": now_ns,
                    "ended_ns": now_ns,
                    "occurred_at": now_iso,
                    "ended_at": now_iso,
                    "scroll_delta": delta,
                    "modifiers": sorted(self._pressed_modifiers),
                }
            )

    def _handle_keyboard(self, keyboard: Any) -> None:  # pragma: no cover - Windows
        vk = int(keyboard.VKey)
        message = int(keyboard.Message)
        is_down = message in {0x0100, 0x0104}
        is_up = message in {0x0101, 0x0105}
        modifier = MODIFIER_VKS.get(vk)
        if modifier:
            if is_down:
                self._pressed_modifiers.add(modifier)
            elif is_up:
                self._pressed_modifiers.discard(modifier)
            return
        if not is_down or not self._target_is_foreground():
            return
        key = safe_key_name(vk)
        if key is None:
            self.ignored_event_count += 1
            return
        now_ns = time.perf_counter_ns()
        now_iso = datetime.now(UTC).isoformat()
        self._emit(
            {
                "kind": "key_press",
                "key": key,
                "started_ns": now_ns,
                "ended_ns": now_ns,
                "occurred_at": now_iso,
                "ended_at": now_iso,
                "modifiers": sorted(self._pressed_modifiers),
            }
        )

    def _emit(self, event: dict[str, Any]) -> None:
        try:
            self.events.put_nowait(event)
        except queue.Full:
            self.fatal_error = "raw_input_queue_overflow"
            self.stop_requested.set()


if os.name == "nt":  # Structures must match the native RAWINPUT layout.
    ULONG_PTR = wintypes.WPARAM

    class RAWINPUTHEADER(ctypes.Structure):
        _fields_ = [
            ("dwType", wintypes.DWORD),
            ("dwSize", wintypes.DWORD),
            ("hDevice", wintypes.HANDLE),
            ("wParam", wintypes.WPARAM),
        ]

    class _BUTTONS(ctypes.Structure):
        _fields_ = [("usButtonFlags", wintypes.USHORT), ("usButtonData", wintypes.USHORT)]

    class _BUTTON_UNION(ctypes.Union):
        _anonymous_ = ("buttons",)
        _fields_ = [("ulButtons", wintypes.ULONG), ("buttons", _BUTTONS)]

    class RAWMOUSE(ctypes.Structure):
        _anonymous_ = ("button_union",)
        _fields_ = [
            ("usFlags", wintypes.USHORT),
            ("button_union", _BUTTON_UNION),
            ("ulRawButtons", wintypes.ULONG),
            ("lLastX", wintypes.LONG),
            ("lLastY", wintypes.LONG),
            ("ulExtraInformation", wintypes.ULONG),
        ]

    class RAWKEYBOARD(ctypes.Structure):
        _fields_ = [
            ("MakeCode", wintypes.USHORT),
            ("Flags", wintypes.USHORT),
            ("Reserved", wintypes.USHORT),
            ("VKey", wintypes.USHORT),
            ("Message", wintypes.UINT),
            ("ExtraInformation", wintypes.ULONG),
        ]

    class _RAW_UNION(ctypes.Union):
        _fields_ = [("mouse", RAWMOUSE), ("keyboard", RAWKEYBOARD)]

    class RAWINPUT(ctypes.Structure):
        _anonymous_ = ("data",)
        _fields_ = [("header", RAWINPUTHEADER), ("data", _RAW_UNION)]


def record(args: argparse.Namespace) -> Path:
    _require_windows_runtime()
    _validate_record_args(args)
    capture_module = _load_capture_module()
    capture_module._enable_physical_pixel_coordinates()
    hwnd, pid, title, process_started_at = _resolve_target_window()
    started_at = datetime.now(UTC)
    started_ns = time.perf_counter_ns()
    initial_png, initial_geometry = _capture(capture_module, hwnd, args.backend)
    initial_captured_at = datetime.now(UTC)
    initial_completed_ns = time.perf_counter_ns()

    session_id = str(UUID(args.session_id))
    root = _session_root(session_id)
    root.mkdir(parents=True, exist_ok=False)
    frames_dir = root / "frames"
    frames_dir.mkdir()
    incomplete = root / "INCOMPLETE"
    incomplete.write_text("recording\n", encoding="utf-8")
    writer = JsonlWriter(root / "events.jsonl")
    settings = {
        "backend": args.backend,
        "settle_ms": args.settle_ms,
        "long_edge": args.long_edge,
        "image_format": args.image_format,
        "webp_quality": args.webp_quality,
        "max_events": args.max_events,
        "max_bytes": args.max_bytes,
    }
    target = {
        "process_name": TARGET_PROCESS_NAME,
        "window_class": TARGET_WINDOW_CLASS,
        "hwnd": hwnd,
        "pid": pid,
        "process_started_at": process_started_at,
        "title": title,
    }
    manifest = _manifest(
        session_id=session_id,
        workflow_name=args.workflow_name,
        status="recording",
        started_at=started_at,
        target=target,
        initial_geometry=initial_geometry,
        settings=settings,
    )
    _atomic_json(root / "manifest.json", manifest)

    current_frame = _save_frame(
        writer,
        frames_dir,
        session_id=session_id,
        role="start",
        png=initial_png,
        geometry=initial_geometry,
        captured_at=initial_captured_at,
        elapsed_ms=max(0, int((initial_completed_ns - started_ns) / 1_000_000)),
        image_format=args.image_format,
        long_edge=args.long_edge,
        webp_quality=args.webp_quality,
    )
    latest_prior: dict[str, Any] = {
        "png": initial_png,
        "geometry": initial_geometry,
        "captured_at": initial_captured_at,
        "elapsed_ms": max(0, int((initial_completed_ns - started_ns) / 1_000_000)),
        "completed_ns": initial_completed_ns,
        "record": current_frame,
    }
    next_pre_capture_ns = initial_completed_ns + PRE_CAPTURE_INTERVAL_MS * 1_000_000
    collector = RawInputCollector(hwnd, pid, max_events=args.max_events)
    final_status = "completed"
    failure_code: str | None = None
    failure_reason: str | None = None
    stop_reason = "duration"
    try:
        _ensure_frame_budget(writer, args.max_bytes)
        collector.start()
        pending_stop_reason: str | None = None
        while True:
            requested = _requested_stop(
                collector,
                root=root,
                hwnd=hwnd,
                pid=pid,
                process_started_at=process_started_at,
                started_ns=started_ns,
                duration_seconds=args.duration_seconds,
            )
            if requested is not None:
                stop_reason = requested
                break
            now_ns = time.perf_counter_ns()
            if (
                now_ns >= next_pre_capture_ns
                and collector.events.empty()
                and not collector.pointer_gesture_active.is_set()
            ):
                prior_png, prior_geometry = _capture(capture_module, hwnd, args.backend)
                prior_captured_at = datetime.now(UTC)
                prior_completed_ns = time.perf_counter_ns()
                # An input may arrive while WGC is capturing. Keep the earlier
                # candidate in that case; a frame completed after the input is
                # never allowed to masquerade as its pre-input observation.
                if (
                    collector.events.empty()
                    and not collector.pointer_gesture_active.is_set()
                ):
                    latest_prior = {
                        "png": prior_png,
                        "geometry": prior_geometry,
                        "captured_at": prior_captured_at,
                        "elapsed_ms": _elapsed_ms(started_ns),
                        "completed_ns": prior_completed_ns,
                        "record": None,
                    }
                next_pre_capture_ns = (
                    prior_completed_ns + PRE_CAPTURE_INTERVAL_MS * 1_000_000
                )
            try:
                first = collector.events.get(timeout=0.05)
            except queue.Empty:
                continue
            batch, pending_stop_reason = _collect_input_batch(
                first,
                collector=collector,
                settle_ms=args.settle_ms,
                remaining_event_budget=args.max_events - writer.input_event_count,
                stop_check=lambda: _requested_stop(
                    collector,
                    root=root,
                    hwnd=hwnd,
                    pid=pid,
                    process_started_at=process_started_at,
                    started_ns=started_ns,
                    duration_seconds=args.duration_seconds,
                ),
            )
            first_started_ns = min(int(raw["started_ns"]) for raw in batch)
            if int(latest_prior["completed_ns"]) > first_started_ns:
                raise RuntimeError("pre_input_frame_completed_after_input")
            prior_age_ms = max(
                0,
                int((first_started_ns - int(latest_prior["completed_ns"])) / 1_000_000),
            )
            if prior_age_ms > MAX_PRE_FRAME_AGE_MS:
                raise RuntimeError("pre_input_frame_stale")
            before_frame = latest_prior.get("record")
            if before_frame is None:
                before_frame = _save_frame(
                    writer,
                    frames_dir,
                    session_id=session_id,
                    role="pre_input",
                    png=latest_prior["png"],
                    geometry=latest_prior["geometry"],
                    captured_at=latest_prior["captured_at"],
                    elapsed_ms=latest_prior["elapsed_ms"],
                    image_format=args.image_format,
                    long_edge=args.long_edge,
                    webp_quality=args.webp_quality,
                )
                _ensure_frame_budget(writer, args.max_bytes)
                latest_prior["record"] = before_frame
            post_png, post_geometry = _capture(capture_module, hwnd, args.backend)
            post_captured_at = datetime.now(UTC)
            post_elapsed_ms = _elapsed_ms(started_ns)
            post_completed_ns = time.perf_counter_ns()
            after_frame_id = f"frame-{uuid4()}"
            geometry_changed = post_geometry != before_frame["capture_geometry"]
            valid_events: list[dict[str, Any]] = []
            for raw in batch:
                event = _build_input_record(
                    raw,
                    session_id=session_id,
                    started_ns=started_ns,
                    hwnd=hwnd,
                    pid=pid,
                    geometry=before_frame["capture_geometry"],
                    before_frame_id=before_frame["frame_id"],
                    after_frame_id=after_frame_id,
                    ambiguous_burst=len(batch) > 1,
                    geometry_changed=geometry_changed,
                )
                if event is None:
                    collector.ignored_event_count += 1
                    continue
                valid_events.append(event)
            if writer.input_event_count + len(valid_events) > args.max_events:
                raise RuntimeError("max_events_exceeded")
            if not valid_events:
                latest_prior = {
                    "png": post_png,
                    "geometry": post_geometry,
                    "captured_at": post_captured_at,
                    "elapsed_ms": post_elapsed_ms,
                    "completed_ns": post_completed_ns,
                    "record": None,
                }
                next_pre_capture_ns = (
                    post_completed_ns + PRE_CAPTURE_INTERVAL_MS * 1_000_000
                )
                if pending_stop_reason is not None:
                    stop_reason = pending_stop_reason
                    break
                continue
            post_frame_file = _prepare_frame_file(
                frames_dir,
                sequence=writer.sequence + len(valid_events),
                role="post-input",
                png=post_png,
                image_format=args.image_format,
                long_edge=args.long_edge,
                webp_quality=args.webp_quality,
                frame_id=after_frame_id,
            )
            for event in valid_events:
                writer.append(event)
            post_frame = writer.append(
                _frame_record(
                    post_frame_file,
                    session_id=session_id,
                    role="post_input",
                    png=post_png,
                    geometry=post_geometry,
                    captured_at=post_captured_at,
                    elapsed_ms=post_elapsed_ms,
                )
            )
            current_frame = post_frame
            latest_prior = {
                "png": post_png,
                "geometry": post_geometry,
                "captured_at": post_captured_at,
                "elapsed_ms": post_elapsed_ms,
                "completed_ns": post_completed_ns,
                "record": post_frame,
            }
            next_pre_capture_ns = post_completed_ns + PRE_CAPTURE_INTERVAL_MS * 1_000_000
            _ensure_frame_budget(writer, args.max_bytes)
            if pending_stop_reason is not None:
                stop_reason = pending_stop_reason
                break
    except KeyboardInterrupt:
        stop_reason = "ctrl_c"
    except Exception as exc:
        final_status = "failed"
        failure_code = str(exc).split(":", 1)[0][:80] or "recording_failed"
        failure_reason = f"{type(exc).__name__}: {exc}"[:500]
    finally:
        collector.stop()

    if final_status == "completed":
        try:
            end_png, end_geometry = _capture(capture_module, hwnd, args.backend)
            end_frame = _save_frame(
                writer,
                frames_dir,
                session_id=session_id,
                role="end",
                png=end_png,
                geometry=end_geometry,
                captured_at=datetime.now(UTC),
                elapsed_ms=_elapsed_ms(started_ns),
                image_format=args.image_format,
                long_edge=args.long_edge,
                webp_quality=args.webp_quality,
            )
            current_frame = end_frame
            _ensure_frame_budget(writer, args.max_bytes)
        except Exception as exc:
            final_status = "failed"
            failure_code = "final_capture_failed"
            failure_reason = f"{type(exc).__name__}: {exc}"[:500]

    events_sha = writer.close()
    manifest.update(
        {
            "status": final_status,
            "ended_at": datetime.now(UTC).isoformat(),
            "events_sha256": events_sha,
            "record_count": writer.record_count,
            "frame_count": writer.frame_count,
            "input_event_count": writer.input_event_count,
            "ignored_event_count": collector.ignored_event_count,
            "capture_error_count": writer.capture_error_count,
            "total_frame_bytes": writer.total_frame_bytes,
            "failure_code": failure_code,
            "failure_reason": failure_reason,
            "stop_reason": stop_reason,
        }
    )
    _atomic_json(root / "manifest.json", manifest)
    if final_status == "completed":
        incomplete.unlink(missing_ok=True)
    return root


def _manifest(
    *,
    session_id: str,
    workflow_name: str,
    status: str,
    started_at: datetime,
    target: dict[str, Any],
    initial_geometry: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "workflow_name": workflow_name,
        "status": status,
        "started_at": started_at.isoformat(),
        "ended_at": None,
        "target": target,
        "initial_capture_geometry": initial_geometry,
        "capture": settings,
        "safety": {
            "observe_only": True,
            "input_dispatch": False,
            "clipboard_recorded": False,
            "printable_text_recorded": False,
            "execution_authority": "none",
            "safe_for_live_replay": False,
            "privacy_reviewed": False,
        },
        "events_path": "events.jsonl",
        "events_sha256": None,
        "record_count": 0,
        "frame_count": 0,
        "input_event_count": 0,
        "ignored_event_count": 0,
        "capture_error_count": 0,
        "total_frame_bytes": 0,
        "review_status": "unreviewed",
        "inferred_from_single_demo": True,
        "failure_code": None,
        "failure_reason": None,
        "recorder_version": RECORDER_VERSION,
        "recording_model_exercised": False,
        "action_correlated_runtime_trace": False,
        "closure_eligible": False,
    }


def _session_root(session_id: str) -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is unavailable")
    return Path(local_app_data) / "SanmouRecordReplay" / "sessions" / session_id


def _resolve_target_window() -> tuple[int, int, str, str]:
    import win32gui
    import win32process

    candidates: list[tuple[int, int, str, str]] = []

    def visit(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return True
        if win32gui.GetClassName(hwnd) != TARGET_WINDOW_CLASS:
            return True
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if right - left < 48 or bottom - top < 48 or left <= -10000 or top <= -10000:
            return True
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_name, process_started_at = _process_identity(pid)
        if process_name.casefold() != TARGET_PROCESS_NAME.casefold():
            return True
        candidates.append((hwnd, pid, win32gui.GetWindowText(hwnd), process_started_at))
        return True

    win32gui.EnumWindows(visit, None)
    if len(candidates) != 1:
        raise RuntimeError(f"expected_one_usable_sanmou_window:found={len(candidates)}")
    return candidates[0]


def _process_identity(pid: int) -> tuple[str, str]:
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError()
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise ctypes.WinError()
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            raise ctypes.WinError()
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        timestamp = (ticks - 116444736000000000) / 10_000_000
        started_at = datetime.fromtimestamp(timestamp, UTC).isoformat()
        return Path(buffer.value).stem, started_at
    finally:
        kernel32.CloseHandle(handle)


def _assert_same_target(hwnd: int, pid: int, process_started_at: str) -> None:
    import win32gui
    import win32process

    if not win32gui.IsWindow(hwnd):
        raise RuntimeError("target_window_closed")
    if win32gui.IsIconic(hwnd):
        raise RuntimeError("target_window_minimized")
    if win32gui.GetClassName(hwnd) != TARGET_WINDOW_CLASS:
        raise RuntimeError("target_window_class_changed")
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    if right - left < 48 or bottom - top < 48 or left <= -10000 or top <= -10000:
        raise RuntimeError("target_window_geometry_unusable")
    _, current_pid = win32process.GetWindowThreadProcessId(hwnd)
    if current_pid != pid:
        raise RuntimeError("target_window_pid_changed")
    process_name, current_started_at = _process_identity(pid)
    if process_name.casefold() != TARGET_PROCESS_NAME.casefold():
        raise RuntimeError("target_process_changed")
    if current_started_at != process_started_at:
        raise RuntimeError("target_process_was_replaced")


def _capture(module: Any, hwnd: int, backend: str) -> tuple[bytes, dict[str, Any]]:
    _assert_window_not_minimized(hwnd)
    png, geometry = module.capture_window_with_backend(hwnd, backend=backend)
    module._validate_capture_sanity(png, hwnd=hwnd)
    return png, geometry


def _assert_window_not_minimized(hwnd: int) -> None:
    import win32gui

    if not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
        raise RuntimeError("target_window_not_capturable")
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    if right - left < 48 or bottom - top < 48 or left <= -10000 or top <= -10000:
        raise RuntimeError("target_window_not_capturable")


def _prepare_frame_file(
    frames_dir: Path,
    *,
    sequence: int,
    role: str,
    png: bytes,
    image_format: str,
    long_edge: int,
    webp_quality: int,
    frame_id: str | None = None,
) -> dict[str, Any]:
    from PIL import Image

    source_sha = hashlib.sha256(png).hexdigest()
    with Image.open(BytesIO(png)) as image:
        image.load()
        converted = image.convert("RGB")
        if max(converted.size) > long_edge:
            converted.thumbnail((long_edge, long_edge), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        if image_format == "webp":
            converted.save(buffer, format="WEBP", quality=webp_quality, method=4)
        else:
            converted.save(buffer, format="PNG", optimize=True)
        encoded = buffer.getvalue()
        image_size = list(converted.size)
    suffix = "webp" if image_format == "webp" else "png"
    frame_id = frame_id or f"frame-{uuid4()}"
    unique_suffix = uuid4().hex[:12]
    filename = f"{sequence:06d}-{role}-{source_sha[:12]}-{unique_suffix}.{suffix}"
    path = frames_dir / filename
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return {
        "frame_id": frame_id,
        "path": f"frames/{filename}",
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "byte_size": len(encoded),
        "image_format": image_format,
        "image_size": image_size,
        "source_png_sha256": source_sha,
    }


def _frame_record(
    prepared: dict[str, Any],
    *,
    session_id: str,
    role: str,
    png: bytes,
    geometry: dict[str, Any],
    captured_at: datetime,
    elapsed_ms: int,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "frame",
        "session_id": session_id,
        "frame_id": prepared["frame_id"],
        "role": role,
        "captured_at": captured_at.isoformat(),
        "elapsed_ms": elapsed_ms,
        "path": prepared["path"],
        "sha256": prepared["sha256"],
        "byte_size": prepared["byte_size"],
        "image_format": prepared["image_format"],
        "image_size": prepared["image_size"],
        "source_png_sha256": hashlib.sha256(png).hexdigest(),
        "capture_geometry": geometry,
    }


def _save_frame(
    writer: JsonlWriter,
    frames_dir: Path,
    *,
    session_id: str,
    role: str,
    png: bytes,
    geometry: dict[str, Any],
    captured_at: datetime,
    elapsed_ms: int,
    image_format: str,
    long_edge: int,
    webp_quality: int,
) -> dict[str, Any]:
    prepared = _prepare_frame_file(
        frames_dir,
        sequence=writer.sequence,
        role=role,
        png=png,
        image_format=image_format,
        long_edge=long_edge,
        webp_quality=webp_quality,
    )
    return writer.append(
        _frame_record(
            prepared,
            session_id=session_id,
            role=role,
            png=png,
            geometry=geometry,
            captured_at=captured_at,
            elapsed_ms=elapsed_ms,
        )
    )


def _build_input_record(
    raw: dict[str, Any],
    *,
    session_id: str,
    started_ns: int,
    hwnd: int,
    pid: int,
    geometry: dict[str, Any],
    before_frame_id: str,
    after_frame_id: str,
    ambiguous_burst: bool,
    geometry_changed: bool,
) -> dict[str, Any] | None:
    kind = raw["kind"]
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "input",
        "session_id": session_id,
        "event_id": f"event-{uuid4()}",
        "kind": kind,
        "occurred_at": raw["occurred_at"],
        "ended_at": raw["ended_at"],
        "elapsed_ms": max(0, int((raw["started_ns"] - started_ns) / 1_000_000)),
        "duration_ms": max(0, int((raw["ended_ns"] - raw["started_ns"]) / 1_000_000)),
        "window_hwnd": hwnd,
        "window_pid": pid,
        "foreground_verified": True,
        "capture_geometry": geometry,
        "start_point": None,
        "end_point": None,
        "start_normalized": None,
        "end_normalized": None,
        "button": raw.get("button"),
        "scroll_delta": raw.get("scroll_delta"),
        "key": raw.get("key"),
        "modifiers": raw.get("modifiers", []),
        "before_frame_id": before_frame_id,
        "after_frame_id": after_frame_id,
        "ambiguous_burst": ambiguous_burst,
        "geometry_changed": geometry_changed,
        "printable_text_omitted": True,
    }
    if "start_abs" in raw:
        start = capture_relative_point(raw["start_abs"]["x"], raw["start_abs"]["y"], geometry)
        if start is None:
            return None
        record["start_point"], record["start_normalized"] = start
    if kind == "drag":
        end = capture_relative_point(raw["end_abs"]["x"], raw["end_abs"]["y"], geometry)
        if end is None:
            return None
        record["end_point"], record["end_normalized"] = end
    return record


def _atomic_json(path: Path, value: object) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _elapsed_ms(started_ns: int) -> int:
    return max(0, int((time.perf_counter_ns() - started_ns) / 1_000_000))


def _requested_stop(
    collector: RawInputCollector,
    *,
    root: Path,
    hwnd: int,
    pid: int,
    process_started_at: str,
    started_ns: int,
    duration_seconds: float,
) -> str | None:
    if collector.fatal_error:
        raise RuntimeError(collector.fatal_error)
    _assert_same_target(hwnd, pid, process_started_at)
    if (root / "STOP").exists():
        return "stop_file"
    if collector.stop_requested.is_set():
        return "hotkey"
    elapsed_seconds = (time.perf_counter_ns() - started_ns) / 1_000_000_000
    if duration_seconds and elapsed_seconds >= duration_seconds:
        return "duration"
    return None


def _ensure_frame_budget(writer: JsonlWriter, max_bytes: int) -> None:
    if writer.total_frame_bytes > max_bytes:
        raise RuntimeError("max_bytes_exceeded")


def _collect_input_batch(
    first: dict[str, Any],
    *,
    collector: RawInputCollector,
    settle_ms: int,
    remaining_event_budget: int,
    stop_check: Callable[[], str | None],
) -> tuple[list[dict[str, Any]], str | None]:
    batch = [first]
    quiet_deadline = time.perf_counter() + settle_ms / 1000
    hard_deadline = time.perf_counter() + MAX_BATCH_WINDOW_MS / 1000
    limit = min(MAX_BATCH_EVENTS, max(1, remaining_event_budget))
    while len(batch) < limit:
        requested = stop_check()
        if requested is not None:
            return batch, requested
        remaining = min(
            quiet_deadline - time.perf_counter(),
            hard_deadline - time.perf_counter(),
        )
        if remaining <= 0:
            break
        try:
            batch.append(collector.events.get(timeout=remaining))
            quiet_deadline = time.perf_counter() + settle_ms / 1000
        except queue.Empty:
            break
    return batch, stop_check()


def _validate_record_args(args: argparse.Namespace) -> None:
    _load_workflow_validator()(str(args.workflow_name))
    if args.duration_seconds < 0 or args.duration_seconds > 3_600:
        raise ValueError("duration-seconds must be between 0 and 3600")
    if not 100 <= args.settle_ms <= 2_000:
        raise ValueError("settle-ms must be between 100 and 2000")
    if not 320 <= args.long_edge <= 2_560:
        raise ValueError("long-edge must be between 320 and 2560")
    if not 20 <= args.webp_quality <= 90:
        raise ValueError("webp-quality must be between 20 and 90")
    if not 1 <= args.max_events <= 10_000:
        raise ValueError("max-events must be between 1 and 10000")
    if args.max_bytes < 1_048_576:
        raise ValueError("max-bytes must be at least 1 MiB")


def _require_windows_runtime() -> None:
    if os.name != "nt":
        raise RuntimeError("record command must run under Windows Python")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record one Sanmou Windows demonstration.")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--duration-seconds", type=float, default=0.0)
    parser.add_argument("--backend", choices=("auto", "wgc", "dxgi"), default="auto")
    parser.add_argument("--settle-ms", type=int, default=350)
    parser.add_argument("--long-edge", type=int, default=1280)
    parser.add_argument("--image-format", choices=("webp", "png"), default="webp")
    parser.add_argument("--webp-quality", type=int, default=60)
    parser.add_argument("--max-events", type=int, default=500)
    parser.add_argument("--max-bytes", type=int, default=268_435_456)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    UUID(args.session_id)
    try:
        _validate_record_args(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        root = record(args)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}))
        return 2
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            {"status": manifest["status"], "session_dir": str(root), "session_id": manifest["session_id"]},
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
