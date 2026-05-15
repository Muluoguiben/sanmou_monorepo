from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pioneer_agent.perception.screenshot_interpreter import (
    SCREENSHOT_INTERPRETATION_INSTRUCTION,
    SCREENSHOT_INTERPRETATION_SCHEMA,
    ScreenshotInterpretation,
    interpret_screenshot,
)


class _VisionStub:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.calls: list[dict[str, Any]] = []

    def extract(
        self,
        image: bytes | Path,
        instruction: str,
        response_schema: dict[str, Any],
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "image": image,
                "instruction": instruction,
                "response_schema": response_schema,
            }
        )
        return SimpleNamespace(data=self.data)


class ScreenshotInterpreterTests(unittest.TestCase):
    def test_interpret_screenshot_uses_advisor_schema_and_validates_result(self) -> None:
        vision = _VisionStub(
            {
                "page_type": "chapter",
                "summary": "截图显示章节任务页面，有奖励待领取。",
                "visible_text": ["章节", "领取"],
                "key_facts": ["存在章节奖励入口"],
                "suggested_next_steps": ["确认奖励是否可领取"],
                "risks": ["截图只覆盖当前页面，无法确认资源全局状态"],
                "confidence": 0.82,
            }
        )

        result = interpret_screenshot(Path("screen.png"), client=vision)  # type: ignore[arg-type]

        self.assertIsInstance(result, ScreenshotInterpretation)
        self.assertEqual(result.page_type, "chapter")
        self.assertEqual(result.confidence, 0.82)
        self.assertEqual(vision.calls[0]["image"], Path("screen.png"))
        self.assertEqual(vision.calls[0]["instruction"], SCREENSHOT_INTERPRETATION_INSTRUCTION)
        self.assertEqual(vision.calls[0]["response_schema"], SCREENSHOT_INTERPRETATION_SCHEMA)


if __name__ == "__main__":
    unittest.main()
