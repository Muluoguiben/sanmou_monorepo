from __future__ import annotations

import ast
import asyncio
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
import unittest

from PIL import Image

from pioneer_agent.adapters.capture import CaptureFrame
from pioneer_agent.app.game_mcp import build_live_server, build_parser
from pioneer_agent.core.device import (
    CapabilityFlags,
    DevicePlatform,
    DeviceProfile,
    DeviceSession,
    ObservationSource,
    ObservationSourceType,
)
from pioneer_agent.core.models import (
    CaptureGeometry,
    CapturePoint,
    CaptureRect,
    CaptureWindowIdentity,
    ObservationSnapshot,
    RuntimeState,
)
from pioneer_agent.perception.vision_sync import VisionSyncSummary


NOW = datetime(2026, 8, 27, 1, 30, tzinfo=UTC)
PRIVATE_URI = r"C:\private\sanmou.png"
PRIVATE_METADATA = "must-not-cross-mcp"


def _png() -> bytes:
    image = Image.new("RGB", (32, 18), (4, 5, 6))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _geometry() -> CaptureGeometry:
    window = CaptureWindowIdentity(
        left=10,
        top=20,
        right=42,
        bottom=38,
        width=32,
        height=18,
        hwnd=100,
        pid=200,
    )
    return CaptureGeometry(
        capture_backend="wgc",
        outer_window=window,
        capture_rect=CaptureRect(
            left=10,
            top=20,
            right=42,
            bottom=38,
            width=32,
            height=18,
        ),
        capture_origin=CapturePoint(x=10, y=20),
        frame_size=(32, 18),
    )


class _Capture:
    def __init__(self) -> None:
        capabilities = CapabilityFlags(
            observe_only=True,
            live_capture=True,
            reliable_window_info=True,
        )
        self._session = DeviceSession(
            profile=DeviceProfile(
                platform=DevicePlatform.PC_CLIENT,
                resolution=(32, 18),
                screenshot_size=(32, 18),
            ),
            source=ObservationSource(
                source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
                uri=PRIVATE_URI,
                metadata={"private": PRIVATE_METADATA},
                capabilities=capabilities,
            ),
            capabilities=capabilities,
        )
        self.captures = 0

    @property
    def device_session(self) -> DeviceSession:
        return self._session

    @property
    def capabilities(self) -> CapabilityFlags:
        return self._session.capabilities

    def capture(self) -> CaptureFrame:
        self.captures += 1
        self._session = self._session.mark_observed(NOW)
        return CaptureFrame(
            png=_png(),
            captured_at=NOW,
            device_session=self._session,
            source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
            capture_geometry=_geometry(),
            metadata={"private": PRIVATE_METADATA},
        )

    def screenshot(self, save_path=None):  # noqa: ANN001
        return self.capture().png


class _VisionSync:
    def __init__(self) -> None:
        self.geometry: CaptureGeometry | None = None

    def sync(
        self,
        image,
        state=None,
        *,
        captured_at=None,
        capture_geometry=None,
    ):  # noqa: ANN001
        self.geometry = capture_geometry
        runtime_state = RuntimeState(
            progress={"chapter_claimable": True, "current_chapter_id": 8}
        )
        observation = ObservationSnapshot(
            observation_id="production-observation-1",
            captured_at=captured_at,
            frame_sha256=hashlib.sha256(image).hexdigest(),
            frame_size=(32, 18),
            capture_geometry=capture_geometry,
            page_type="chapter",
            domains_run=["resource_bar", "chapter_panel"],
            observed_state=runtime_state,
            source="vision_sync",
        )
        return runtime_state, VisionSyncSummary(
            page_type="chapter",
            domains_run=["resource_bar", "chapter_panel"],
            notes=[],
            observation=observation,
        )


class GameMCPLiveProviderTests(unittest.TestCase):
    def test_explicit_live_composition_observes_and_never_executes(self) -> None:
        args = build_parser().parse_args(["--windows-bridge"])
        capture = _Capture()
        vision = _VisionSync()
        server = build_live_server(args, capture=capture, vision_sync=vision)

        async def exercise() -> list[dict]:
            results = []
            for name in (
                "session_status",
                "observe_game",
                "get_runtime_state",
                "get_advisor_report",
                "list_action_candidates",
            ):
                _content, structured = await server.call_tool(name, {})
                results.append(structured)
            return results

        status, observed, state, report, candidates = asyncio.run(exercise())

        self.assertEqual(status["session"]["capture_health"], "unknown")
        self.assertEqual(observed["status"], "ok")
        self.assertEqual(observed["execution_authority"], "none")
        self.assertEqual(observed["observation"]["capture_geometry"]["outer_window"]["hwnd"], 100)
        self.assertEqual(state["observation"]["observation_id"], "production-observation-1")
        self.assertEqual(report["advisor_report"]["mode"], "advisor")
        self.assertTrue(candidates["candidates"])
        self.assertTrue(all(item["executable"] is False for item in candidates["candidates"]))
        self.assertTrue(all(item["execution_authority"] == "none" for item in candidates["candidates"]))
        self.assertEqual(capture.captures, 1)
        self.assertEqual(vision.geometry, _geometry())
        serialized = json.dumps([status, observed, state, report, candidates], ensure_ascii=False)
        self.assertNotIn(PRIVATE_URI, serialized)
        self.assertNotIn(PRIVATE_METADATA, serialized)

    def test_live_entrypoint_requires_an_explicit_source(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])

    def test_live_composition_has_no_executor_or_control_import(self) -> None:
        source_root = Path(__file__).resolve().parents[2] / "src" / "pioneer_agent"
        paths = [
            source_root / "app" / "game_mcp.py",
            source_root / "mcp_server" / "live_provider.py",
        ]
        imported: set[str] = set()
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
        forbidden = (
            "pioneer_agent.executor",
            "pioneer_agent.adapters.control",
            "pioneer_agent.runtime.autonomous_loop",
            "pioneer_agent.runtime.replay_runtime",
            "pioneer_agent.verifier",
        )
        self.assertFalse(
            {
                name
                for name in imported
                if any(name == item or name.startswith(f"{item}.") for item in forbidden)
            }
        )


if __name__ == "__main__":
    unittest.main()
