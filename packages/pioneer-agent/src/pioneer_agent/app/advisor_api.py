from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from pioneer_agent.adapters.capture import CaptureFrame, ScreenshotFileCaptureAdapter
from pioneer_agent.core.device import AccountSession, DevicePlatform, ObservationSourceType
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState, SelectionResult
from pioneer_agent.perception.screenshot_interpreter import (
    ScreenshotInterpretation,
    interpret_screenshot,
)
from pioneer_agent.perception.vision import build_vision_client
from pioneer_agent.perception.vision_sync import VisionSync, VisionSyncSummary
from pioneer_agent.runtime.advisor_loop import AdvisorLoop, AdvisorReport, build_advisor_report
from pioneer_agent.safety.kill_switch import KillSwitch, default_kill_switch_path

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class AdvisorChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    report: dict[str, Any] | None = None


class AdvisorChatResponse(BaseModel):
    answer: str
    evidence: list[str] = Field(default_factory=list)
    mode: str = "local_advisor"


class KillSwitchStatus(BaseModel):
    triggered: bool
    path: str


class AdvisorApiService:
    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        default_mock_mode: bool | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self.project_root = _project_root()
        self.data_dir = data_dir or _default_data_dir(self.project_root)
        self.upload_dir = self.data_dir / "uploads"
        self.report_log = self.data_dir / "reports.jsonl"
        self.kill_switch = kill_switch or KillSwitch(default_kill_switch_path(self.project_root))
        self.default_mock_mode = (
            _env_bool("SANMOU_ADVISOR_MOCK", default=False)
            if default_mock_mode is None
            else default_mock_mode
        )
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def kill_switch_status(self) -> KillSwitchStatus:
        return KillSwitchStatus(
            triggered=self.kill_switch.is_triggered(),
            path=str(self.kill_switch.path),
        )

    def trigger_kill_switch(self) -> KillSwitchStatus:
        self.kill_switch.trigger()
        return self.kill_switch_status()

    def clear_kill_switch(self) -> KillSwitchStatus:
        self.kill_switch.clear()
        return self.kill_switch_status()

    def analyze_upload(
        self,
        *,
        upload: UploadFile,
        platform: DevicePlatform,
        account_label: str | None,
        server_id: str | None,
        season_id: str | None,
        role_name: str | None,
        vision_provider: str | None,
        mock_mode: bool | None,
    ) -> AdvisorReport:
        path = self._save_upload(upload)
        account = AccountSession(
            account_label=_blank_to_none(account_label),
            server_id=_blank_to_none(server_id),
            season_id=_blank_to_none(season_id),
            role_name=_blank_to_none(role_name),
        )
        use_mock = self.default_mock_mode if mock_mode is None else mock_mode
        if use_mock:
            report = self._mock_report(path=path, platform=platform, account=account)
        else:
            report = self._real_report(
                path=path,
                platform=platform,
                account=account,
                vision_provider=_blank_to_none(vision_provider),
            )
        self._append_report(path, report, mock_mode=use_mock)
        return report

    def chat(self, request: AdvisorChatRequest) -> AdvisorChatResponse:
        message = request.message.strip()
        if not request.report:
            return AdvisorChatResponse(
                answer="先上传一张游戏截图，我会基于识别出的状态给出下一步建议。当前对话不会执行任何自动化操作。",
                evidence=[],
            )

        recommended = request.report.get("recommended_action") or {}
        interpretation = request.report.get("screenshot_interpretation") or {}
        summary = request.report.get("current_state_summary") or {}
        evidence = list(request.report.get("evidence") or [])[:8]
        action_type = recommended.get("action_type") or "none"
        confidence = request.report.get("confidence", 0)
        page_type = summary.get("page_type") or "unknown"

        if any(token in message for token in ("识别", "看到", "画面", "截图")):
            facts = interpretation.get("key_facts") or []
            visible_text = interpretation.get("visible_text") or []
            answer = (
                f"这张图的解读：{interpretation.get('summary') or '暂未形成明确摘要'}。"
                f"可见信息：{json.dumps(visible_text[:8], ensure_ascii=False)}。"
                f"关键事实：{json.dumps(facts[:8], ensure_ascii=False)}。"
            )
        elif any(token in message for token in ("风险", "安全吗", "会不会", "能不能打", "打地")):
            risk = recommended.get("risk") or {}
            interpreted_risks = interpretation.get("risks") or []
            answer = (
                f"当前截图识别页面是 {page_type}，推荐动作是 {action_type}。"
                f"风险信息：{json.dumps(risk, ensure_ascii=False) if risk else '未发现额外风险字段'}。"
                f"视觉不确定项：{json.dumps(interpreted_risks[:6], ensure_ascii=False) if interpreted_risks else '暂无'}。"
                "首版 Advisor 只给建议，不会自动点击；涉及打地、放弃土地、阵容迁移这类动作后续也应保持人工确认。"
            )
        elif any(token in message for token in ("下一步", "干嘛", "建议", "优先")):
            params = recommended.get("params") or {}
            next_steps = interpretation.get("suggested_next_steps") or []
            answer = (
                f"下一步建议关注 {action_type}。"
                f"关键参数：{json.dumps(params, ensure_ascii=False)}。"
                f"截图层面的建议：{json.dumps(next_steps[:5], ensure_ascii=False) if next_steps else '暂无'}。"
                f"当前置信度约 {confidence}，建议结合截图中的资源、章节和队伍状态人工确认。"
            )
        else:
            answer = (
                f"我已基于当前截图生成 Advisor 报告：页面={page_type}，推荐动作={action_type}。"
                f"截图摘要：{interpretation.get('summary') or '暂无'}。"
                "你可以继续问“下一步做什么”“这个动作风险高吗”“这张图识别到了什么”。"
            )
        return AdvisorChatResponse(answer=answer, evidence=evidence)

    def _save_upload(self, upload: UploadFile) -> Path:
        suffix = Path(upload.filename or "screenshot.png").suffix.lower()
        if suffix not in IMAGE_SUFFIXES:
            suffix = ".png"
        safe_name = _safe_filename(Path(upload.filename or "screenshot").stem)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        path = self.upload_dir / f"{stamp}-{uuid4().hex[:8]}-{safe_name}{suffix}"

        total = 0
        with path.open("wb") as handle:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="screenshot is larger than 10MB")
                handle.write(chunk)

        try:
            with Image.open(path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="uploaded file is not a valid image") from exc
        return path

    def _real_report(
        self,
        *,
        path: Path,
        platform: DevicePlatform,
        account: AccountSession,
        vision_provider: str | None,
    ) -> AdvisorReport:
        capture = ScreenshotFileCaptureAdapter(path, platform=platform)
        try:
            vision = build_vision_client(vision_provider)
            loop = AdvisorLoop(capture, VisionSync(vision), account_session=account)
            report = loop.tick()
            interpretation = interpret_screenshot(path, client=vision)
            return report.model_copy(
                update=_interpretation_report_update(report, interpretation)
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"advisor analysis failed: {exc}") from exc

    def _mock_report(
        self,
        *,
        path: Path,
        platform: DevicePlatform,
        account: AccountSession,
    ) -> AdvisorReport:
        capture = ScreenshotFileCaptureAdapter(path, platform=platform)
        frame = capture.capture()
        with Image.open(path) as image:
            width, height = image.size
        state = RuntimeState(
            global_state={
                "mode": "advisor_mock",
                "phase_tag": "unknown",
            },
            progress={
                "chapter_claimable": None,
                "current_chapter_id": None,
            },
            economy={
                "resources": {},
            },
            field_meta={
                "global_state.mode": {
                    "value": "advisor_mock",
                    "confidence": 1.0,
                    "source": "advisor_api.mock",
                    "updated_at": frame.captured_at,
                }
            },
        )
        action = CandidateAction(
            action_id="advisor-review-screenshot",
            action_type=ActionType.WAIT_FOR_RESOURCE,
            params={
                "note": "mock_mode: screenshot accepted; enable a vision provider for real recommendations",
                "image_width": width,
                "image_height": height,
            },
            preconditions=["screenshot_uploaded"],
            expected_gain={"validated_upload": True},
            expected_cost={},
            risk={"automation": "none", "mode": "advisor_only"},
            timing={"immediate": True},
            interruptibility={"interruptible": True},
            source_state_refs=["uploaded_screenshot", "device_session.profile"],
            score_total=1.0,
            score_breakdown={"mock": 1.0},
        )
        summary = VisionSyncSummary(
            page_type="unknown",
            domains_run=["mock_upload"],
            notes=["mock_mode enabled; no vision model was called"],
        )
        selection = SelectionResult(
            selected_action=action,
            ranked_actions=[action],
            selection_reason={
                "selection_mode": "mock",
                "triggered_rules": ["screenshot_uploaded"],
                "summary": "截图已上传。当前为 mock 模式，只验证桌面端上传和报告展示链路。",
            },
        )
        return build_advisor_report(
            frame=CaptureFrame(
                png=frame.png,
                captured_at=frame.captured_at,
                device_session=frame.device_session,
                source_type=ObservationSourceType.SCREENSHOT_FILE,
                metadata={"path": str(path), "mock_mode": True},
            ),
            state=state,
            selection=selection,
            vision_summary=summary,
            account_session=account,
            screenshot_interpretation=ScreenshotInterpretation(
                page_type="unknown",
                summary="截图已上传，当前为 mock 模式；请关闭模拟模式并配置视觉模型以获得真实画面解读。",
                visible_text=[],
                key_facts=[f"图片尺寸 {width}x{height}", "上传链路正常"],
                suggested_next_steps=["关闭模拟模式", "选择 OpenAI 或 Gemini 视觉模型", "重新上传真实游戏截图"],
                risks=["mock 模式未调用视觉模型，不能代表真实识别结果"],
                confidence=1.0,
            ),
        )

    def _append_report(self, image_path: Path, report: AdvisorReport, *, mock_mode: bool) -> None:
        self.report_log.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "created_at": datetime.now(UTC).isoformat(),
            "image_path": str(image_path),
            "mock_mode": mock_mode,
            "report": report.model_dump(mode="json"),
        }
        with self.report_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def create_app(service: AdvisorApiService | None = None) -> FastAPI:
    service = service or AdvisorApiService()
    app = FastAPI(title="Sanmou Advisor API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "app://sanmou-advisor"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.service = service

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "data_dir": str(service.data_dir),
            "mock_default": service.default_mock_mode,
            "kill_switch": service.kill_switch_status().model_dump(mode="json"),
        }

    @app.get("/api/advisor/platforms")
    def platforms() -> dict[str, list[str]]:
        return {"platforms": [item.value for item in DevicePlatform]}

    @app.get("/api/runtime/kill-switch")
    def get_kill_switch() -> KillSwitchStatus:
        return service.kill_switch_status()

    @app.post("/api/runtime/kill-switch")
    def trigger_kill_switch() -> KillSwitchStatus:
        return service.trigger_kill_switch()

    @app.delete("/api/runtime/kill-switch")
    def clear_kill_switch() -> KillSwitchStatus:
        return service.clear_kill_switch()

    @app.post("/api/advisor/analyze")
    def analyze(
        screenshot: Annotated[UploadFile, File()],
        platform: Annotated[str, Form()] = DevicePlatform.UNKNOWN.value,
        account_label: Annotated[str | None, Form()] = None,
        server_id: Annotated[str | None, Form()] = None,
        season_id: Annotated[str | None, Form()] = None,
        role_name: Annotated[str | None, Form()] = None,
        vision_provider: Annotated[str | None, Form()] = None,
        mock_mode: Annotated[bool | None, Form()] = None,
    ) -> AdvisorReport:
        try:
            device_platform = DevicePlatform(platform)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"unsupported platform: {platform}") from exc
        return service.analyze_upload(
            upload=screenshot,
            platform=device_platform,
            account_label=account_label,
            server_id=server_id,
            season_id=season_id,
            role_name=role_name,
            vision_provider=vision_provider,
            mock_mode=mock_mode,
        )

    @app.post("/api/advisor/chat")
    def chat(request: AdvisorChatRequest) -> AdvisorChatResponse:
        return service.chat(request)

    return app


def _interpretation_report_update(
    report: AdvisorReport,
    interpretation: ScreenshotInterpretation,
) -> dict[str, Any]:
    current_state_summary = dict(report.current_state_summary)
    current_state_summary.update(
        {
            "interpreted_page_type": interpretation.page_type,
            "interpretation_summary": interpretation.summary,
        }
    )
    vision_summary = dict(report.vision_summary)
    vision_summary["interpretation"] = interpretation.model_dump(mode="json")
    evidence = list(report.evidence)
    if "vision.interpretation" not in evidence:
        evidence.append("vision.interpretation")
    return {
        "screenshot_interpretation": interpretation,
        "current_state_summary": current_state_summary,
        "vision_summary": vision_summary,
        "evidence": evidence,
        "confidence": min(report.confidence, interpretation.confidence),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Sanmou Advisor API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SANMOU_ADVISOR_PORT", "8765")))
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--mock", action="store_true", help="Default analyze calls to mock mode.")
    args = parser.parse_args(argv)

    global app
    app = create_app(AdvisorApiService(data_dir=args.data_dir, default_mock_mode=args.mock))

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _default_data_dir(project_root: Path) -> Path:
    return project_root / "data" / "advisor"


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return cleaned[:48] or "screenshot"


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main())
