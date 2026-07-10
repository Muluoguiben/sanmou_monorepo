from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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


class AdvisorHistoryItem(BaseModel):
    history_id: str
    created_at: str
    image_path: str
    screenshot_url: str
    mock_mode: bool = False
    platform: str | None = None
    page_type: str | None = None
    recommended_action_type: str | None = None
    account_label: str | None = None


class AdvisorHistoryDetail(BaseModel):
    item: AdvisorHistoryItem
    report: dict[str, Any]


class AdvisorApiService:
    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        default_mock_mode: bool | None = None,
        kill_switch: KillSwitch | None = None,
        qa_query_service: Any | None = None,
    ) -> None:
        self.project_root = _project_root()
        self.data_dir = data_dir or _default_data_dir(self.project_root)
        self.upload_dir = self.data_dir / "uploads"
        self.report_log = self.data_dir / "reports.jsonl"
        self.kill_switch = kill_switch or KillSwitch(default_kill_switch_path(self.project_root))
        self._qa_query_service = qa_query_service
        self._qa_query_load_attempted = qa_query_service is not None
        self._qa_query_error: str | None = None
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

    def list_history(self, *, limit: int = 50) -> list[AdvisorHistoryItem]:
        records = self._read_history_records()
        safe_limit = max(1, min(limit, 200))
        return [record["item"] for record in records[-safe_limit:]][::-1]

    def get_history_detail(self, history_id: str) -> AdvisorHistoryDetail:
        for record in self._read_history_records():
            item = record["item"]
            if item.history_id == history_id:
                return AdvisorHistoryDetail(item=item, report=record["report"])
        raise HTTPException(status_code=404, detail=f"history item not found: {history_id}")

    def history_screenshot_path(self, history_id: str) -> Path:
        detail = self.get_history_detail(history_id)
        path = Path(detail.item.image_path)
        try:
            path.relative_to(self.upload_dir)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="history screenshot path is outside upload directory") from exc
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"history screenshot missing: {history_id}")
        return path

    def chat(self, request: AdvisorChatRequest) -> AdvisorChatResponse:
        message = request.message.strip()
        if not request.report:
            return AdvisorChatResponse(
                answer="先上传一张游戏截图，我会基于识别出的状态给出下一步建议。当前对话不会执行任何自动化操作。",
                evidence=[],
            )

        qa_response = self._qa_chat(request)
        if qa_response is not None:
            return qa_response

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

    def _qa_chat(self, request: AdvisorChatRequest) -> AdvisorChatResponse | None:
        message = request.message.strip()
        if not _should_use_qa_chat(message):
            return None
        service = self._get_qa_query_service()
        if service is None:
            return None
        domain = _infer_qa_domain(message)
        response = service.answer_rule_question(message, domain=domain)
        evidence = _qa_evidence_strings(response)
        if not evidence:
            return None

        report = request.report or {}
        recommended = report.get("recommended_action") or {}
        summary = report.get("current_state_summary") or {}
        page_type = summary.get("page_type") or summary.get("interpreted_page_type") or "unknown"
        action_type = recommended.get("action_type") or "none"
        answer = (
            f"结合当前截图上下文：页面={page_type}，推荐动作={action_type}。"
            f"知识库建议：{response.answer}"
        )
        return AdvisorChatResponse(
            answer=answer,
            evidence=evidence[:8],
            mode="qa_query_service",
        )

    def _get_qa_query_service(self) -> Any | None:
        if self._qa_query_service is not None:
            return self._qa_query_service
        if self._qa_query_load_attempted:
            return None
        self._qa_query_load_attempted = True
        if _env_bool("SANMOU_ADVISOR_DISABLE_QA_CHAT", default=False):
            self._qa_query_error = "disabled by SANMOU_ADVISOR_DISABLE_QA_CHAT"
            return None
        try:
            qa_src = self.project_root / "packages" / "qa-agent" / "src"
            if qa_src.exists() and str(qa_src) not in sys.path:
                sys.path.insert(0, str(qa_src))
            from qa_agent.adapters import QaKnowledgeProvider

            source_root = self.project_root / "packages" / "qa-agent" / "knowledge_sources"
            self._qa_query_service = QaKnowledgeProvider.from_knowledge_root(source_root)
            return self._qa_query_service
        except Exception as exc:  # noqa: BLE001
            self._qa_query_error = str(exc)
            return None

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
            "history_id": uuid4().hex,
            "created_at": datetime.now(UTC).isoformat(),
            "image_path": str(image_path),
            "mock_mode": mock_mode,
            "report": report.model_dump(mode="json"),
        }
        with self.report_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _read_history_records(self) -> list[dict[str, Any]]:
        if not self.report_log.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.report_log.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                report = payload.get("report")
                if not isinstance(report, dict):
                    continue
                history_id = str(payload.get("history_id") or f"line-{index}")
                item = _history_item_from_payload(history_id, payload, report)
                records.append({"item": item, "report": report})
        return records


def create_app(
    service: AdvisorApiService | None = None,
    *,
    runtime_admin_enabled: bool = False,
) -> FastAPI:
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
    app.state.runtime_admin_enabled = runtime_admin_enabled

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ok",
            "data_dir": str(service.data_dir),
            "mock_default": service.default_mock_mode,
            "runtime_admin_enabled": runtime_admin_enabled,
        }
        if runtime_admin_enabled:
            payload["kill_switch"] = service.kill_switch_status().model_dump(mode="json")
        return payload

    @app.get("/api/advisor/platforms")
    def platforms() -> dict[str, list[str]]:
        return {"platforms": [item.value for item in DevicePlatform]}

    @app.get("/api/advisor/history")
    def advisor_history(limit: int = 50) -> dict[str, list[AdvisorHistoryItem]]:
        return {"items": service.list_history(limit=limit)}

    @app.get("/api/advisor/history/{history_id}")
    def advisor_history_detail(history_id: str) -> AdvisorHistoryDetail:
        return service.get_history_detail(history_id)

    @app.get("/api/advisor/history/{history_id}/screenshot")
    def advisor_history_screenshot(history_id: str) -> FileResponse:
        return FileResponse(service.history_screenshot_path(history_id))

    if runtime_admin_enabled:
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


def _should_use_qa_chat(message: str) -> bool:
    markers = (
        "建筑",
        "升级",
        "打地",
        "土地",
        "战损",
        "兵力",
        "阵容",
        "武将",
        "战法",
        "赛季",
        "机制",
        "优先级",
        "开荒",
    )
    return any(marker in message for marker in markers)


def _infer_qa_domain(message: str) -> str | None:
    if any(marker in message for marker in ("建筑", "升级", "征兵所", "仓库")):
        return "building"
    if any(marker in message for marker in ("打地", "土地", "战损", "兵力", "军令", "克制")):
        return "combat"
    if any(marker in message for marker in ("阵容", "队伍", "开荒")):
        return "solution"
    if any(marker in message for marker in ("武将", "英雄")):
        return "hero"
    if "战法" in message:
        return "skill"
    return None


def _qa_evidence_strings(response: Any) -> list[str]:
    evidence: list[str] = []
    for item in getattr(response, "evidence", []) or []:
        entry_id = getattr(item, "entry_id", "unknown")
        topic = getattr(item, "topic", "unknown")
        summary = getattr(item, "summary", "")
        source_ref = getattr(item, "source_ref", "")
        suffix = f" [{source_ref}]" if source_ref else ""
        evidence.append(f"{entry_id}: {topic} - {summary}{suffix}")
    return evidence


def _history_item_from_payload(
    history_id: str,
    payload: dict[str, Any],
    report: dict[str, Any],
) -> AdvisorHistoryItem:
    device_session = report.get("device_session") if isinstance(report.get("device_session"), dict) else {}
    profile = device_session.get("profile") if isinstance(device_session.get("profile"), dict) else {}
    summary = report.get("current_state_summary") if isinstance(report.get("current_state_summary"), dict) else {}
    vision_summary = report.get("vision_summary") if isinstance(report.get("vision_summary"), dict) else {}
    interpretation = report.get("screenshot_interpretation") if isinstance(report.get("screenshot_interpretation"), dict) else {}
    recommended = report.get("recommended_action") if isinstance(report.get("recommended_action"), dict) else {}
    account = report.get("account_session") if isinstance(report.get("account_session"), dict) else {}
    page_type = (
        interpretation.get("page_type")
        or summary.get("interpreted_page_type")
        or summary.get("page_type")
        or vision_summary.get("page_type")
    )
    return AdvisorHistoryItem(
        history_id=history_id,
        created_at=str(payload.get("created_at") or ""),
        image_path=str(payload.get("image_path") or ""),
        screenshot_url=f"/api/advisor/history/{history_id}/screenshot",
        mock_mode=bool(payload.get("mock_mode")),
        platform=profile.get("platform"),
        page_type=page_type,
        recommended_action_type=recommended.get("action_type"),
        account_label=account.get("account_label"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Sanmou Advisor API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SANMOU_ADVISOR_PORT", "8765")))
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--mock", action="store_true", help="Default analyze calls to mock mode.")
    parser.add_argument(
        "--enable-runtime-admin",
        action="store_true",
        help="Explicitly expose local runtime kill-switch administration routes.",
    )
    args = parser.parse_args(argv)

    global app
    app = create_app(
        AdvisorApiService(data_dir=args.data_dir, default_mock_mode=args.mock),
        runtime_admin_enabled=args.enable_runtime_admin,
    )

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
