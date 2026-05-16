from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from PIL import Image

from pioneer_agent.core.device import DevicePlatform


def _require_api_deps():
    try:
        from fastapi.testclient import TestClient
        from starlette.datastructures import UploadFile

        from pioneer_agent.app.advisor_api import AdvisorApiService, AdvisorChatRequest, create_app
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"advisor API dependencies not installed: {exc}") from exc
    return UploadFile, AdvisorApiService, AdvisorChatRequest, TestClient, create_app


class AdvisorApiTests(unittest.TestCase):
    def test_mock_analyze_upload_writes_report_and_blocks_execution(self) -> None:
        UploadFile, AdvisorApiService, _AdvisorChatRequest, _TestClient, _create_app = _require_api_deps()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "screen.png"
            Image.new("RGB", (320, 180), (20, 30, 40)).save(image_path)
            service = AdvisorApiService(data_dir=root / "advisor", default_mock_mode=True)

            with image_path.open("rb") as handle:
                upload = UploadFile(file=handle, filename="screen.png")
                report = service.analyze_upload(
                    upload=upload,
                    platform=DevicePlatform.IOS,
                    account_label="test",
                    server_id="s1",
                    season_id="s0",
                    role_name="主公",
                    vision_provider=None,
                    mock_mode=True,
                )

            self.assertEqual(report.mode, "advisor")
            self.assertEqual(report.device_session.profile.platform, DevicePlatform.IOS)
            self.assertIsNotNone(report.recommended_action)
            self.assertFalse(report.recommended_action.executable)  # type: ignore[union-attr]
            self.assertIsNotNone(report.screenshot_interpretation)
            self.assertIn("上传链路正常", report.screenshot_interpretation.key_facts)  # type: ignore[union-attr]
            self.assertTrue((root / "advisor" / "reports.jsonl").exists())

    def test_local_chat_uses_report_context(self) -> None:
        UploadFile, AdvisorApiService, AdvisorChatRequest, _TestClient, _create_app = _require_api_deps()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "screen.png"
            Image.new("RGB", (320, 180), "black").save(image_path)
            service = AdvisorApiService(data_dir=root / "advisor", default_mock_mode=True)

            with image_path.open("rb") as handle:
                upload = UploadFile(file=handle, filename="screen.png")
                report = service.analyze_upload(
                    upload=upload,
                    platform=DevicePlatform.PC_CLIENT,
                    account_label=None,
                    server_id=None,
                    season_id=None,
                    role_name=None,
                    vision_provider=None,
                    mock_mode=True,
                )

            response = service.chat(
                AdvisorChatRequest(message="下一步做什么", report=report.model_dump(mode="json"))
            )
            self.assertEqual(response.mode, "local_advisor")
            self.assertIn("下一步", response.answer)

            vision_response = service.chat(
                AdvisorChatRequest(message="这张图识别到了什么", report=report.model_dump(mode="json"))
            )
            self.assertIn("这张图的解读", vision_response.answer)
            self.assertIn("关键事实", vision_response.answer)

    def test_chat_uses_qa_query_service_for_knowledge_questions(self) -> None:
        _UploadFile, AdvisorApiService, AdvisorChatRequest, _TestClient, _create_app = _require_api_deps()

        class _FakeQaQueryService:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str | None]] = []

            def answer_rule_question(self, question: str, domain: str | None = None):  # noqa: ANN001
                self.calls.append((question, domain))
                return SimpleNamespace(
                    answer="优先升级征兵所，兵力瓶颈解除后再看资源建筑。",
                    evidence=[
                        SimpleNamespace(
                            entry_id="building-priority-recruit",
                            topic="征兵所升级",
                            summary="征兵所影响预备兵与补兵节奏。",
                            source_ref="knowledge_sources/rules/buildings.yaml",
                        )
                    ],
                )

        qa = _FakeQaQueryService()
        with TemporaryDirectory() as tmp:
            service = AdvisorApiService(
                data_dir=Path(tmp) / "advisor",
                default_mock_mode=True,
                qa_query_service=qa,
            )
            response = service.chat(
                AdvisorChatRequest(
                    message="建筑升级优先级是什么",
                    report={
                        "recommended_action": {"action_type": "upgrade_building"},
                        "current_state_summary": {"page_type": "city"},
                        "evidence": [],
                    },
                )
            )

        self.assertEqual(response.mode, "qa_query_service")
        self.assertIn("页面=city", response.answer)
        self.assertIn("优先升级征兵所", response.answer)
        self.assertIn("building-priority-recruit", response.evidence[0])
        self.assertEqual(qa.calls, [("建筑升级优先级是什么", "building")])

    def test_kill_switch_api_can_trigger_and_clear_stop_file(self) -> None:
        (
            _UploadFile,
            AdvisorApiService,
            _AdvisorChatRequest,
            TestClient,
            create_app,
        ) = _require_api_deps()
        from pioneer_agent.safety.kill_switch import KillSwitch

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdvisorApiService(
                data_dir=root / "advisor",
                default_mock_mode=True,
                kill_switch=KillSwitch(root / "STOP"),
            )
            client = TestClient(create_app(service))

            initial = client.get("/api/runtime/kill-switch")
            self.assertEqual(initial.status_code, 200)
            self.assertFalse(initial.json()["triggered"])

            triggered = client.post("/api/runtime/kill-switch")
            self.assertEqual(triggered.status_code, 200)
            self.assertTrue(triggered.json()["triggered"])
            self.assertTrue((root / "STOP").exists())

            cleared = client.delete("/api/runtime/kill-switch")
            self.assertEqual(cleared.status_code, 200)
            self.assertFalse(cleared.json()["triggered"])
            self.assertFalse((root / "STOP").exists())


if __name__ == "__main__":
    unittest.main()
