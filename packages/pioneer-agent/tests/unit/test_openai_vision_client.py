from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch

from PIL import Image

from pioneer_agent.perception.vision import build_vision_client
from pioneer_agent.perception.vision.client import VisionError
from pioneer_agent.perception.vision.model_routing import get_vision_model_profile
from pioneer_agent.perception.vision.openai_client import OpenAIVisionClient


def _png_bytes() -> bytes:
    image = Image.new("RGB", (8, 8), "white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class OpenAIVisionClientTests(unittest.TestCase):
    def test_extract_sends_sub2api_required_fields_and_parses_json(self) -> None:
        captured: dict = {}

        def fake_post(url, *, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "model": "gpt-5.4",
                    "choices": [
                        {
                            "message": {
                                "content": '```json\n{"page_type":"city","resources":{}}\n```'
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 5},
                }
            )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "PIONEER_OPENAI_MODEL": "gpt-5.4",
                "PIONEER_OPENAI_BASE_URL": "http://example.test/v1",
                "PIONEER_OPENAI_REASONING_EFFORT": "medium",
            },
            clear=False,
        ):
            with patch("pioneer_agent.perception.vision.openai_client.load_vision_env"):
                with patch(
                    "pioneer_agent.perception.vision.openai_client.requests.post",
                    fake_post,
                ):
                    client = OpenAIVisionClient()
                    result = client.extract(
                        image=_png_bytes(),
                        instruction="Read the page.",
                        response_schema={
                            "type": "object",
                            "properties": {"page_type": {"type": "string"}},
                            "required": ["page_type"],
                        },
                    )

        self.assertEqual(result.data["page_type"], "city")
        self.assertEqual(result.model, "gpt-5.4")
        self.assertEqual(result.prompt_tokens, 12)
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(captured["url"], "http://example.test/v1/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(captured["payload"]["model"], "gpt-5.4")
        self.assertEqual(captured["payload"]["reasoning_effort"], "medium")
        self.assertEqual(captured["payload"]["max_tokens"], 1024)
        self.assertFalse(captured["payload"]["store"])
        content = captured["payload"]["messages"][1]["content"]
        self.assertIn("Read the page.", content[0]["text"])
        self.assertIn('"page_type"', content[0]["text"])
        self.assertTrue(
            content[1]["image_url"]["url"].startswith("data:image/png;base64,")
        )
        self.assertNotIn("detail", content[1]["image_url"])
        self.assertEqual(result.original_size, (8, 8))
        self.assertEqual(result.prepared_size, (8, 8))
        self.assertFalse(result.resized)

    def test_missing_api_key_raises_vision_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch("pioneer_agent.perception.vision.openai_client.load_vision_env"):
                with self.assertRaises(VisionError):
                    OpenAIVisionClient()

    def test_factory_selects_openai_provider(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("pioneer_agent.perception.vision.openai_client.load_vision_env"):
                client = build_vision_client("openai")
        self.assertIsInstance(client, OpenAIVisionClient)

    def test_dense_table_profile_sets_original_detail_and_high_reasoning(self) -> None:
        captured: dict = {}

        def fake_post(url, *, headers, json, timeout):
            captured["payload"] = json
            return _FakeResponse(
                {
                    "model": "gpt-5.4",
                    "choices": [{"message": {"content": '{"page_type":"team"}'}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 9},
                }
            )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "PIONEER_OPENAI_BASE_URL": "http://example.test/v1",
            },
            clear=False,
        ):
            with patch("pioneer_agent.perception.vision.openai_client.load_vision_env"):
                with patch(
                    "pioneer_agent.perception.vision.openai_client.requests.post",
                    fake_post,
                ):
                    client = OpenAIVisionClient(profile="dense_table")
                    result = client.extract(
                        image=_png_bytes(),
                        instruction="Read table.",
                        response_schema={"type": "object", "properties": {}},
                    )

        self.assertEqual(result.data["page_type"], "team")
        self.assertEqual(captured["payload"]["model"], "gpt-5.4")
        self.assertEqual(captured["payload"]["reasoning_effort"], "high")
        self.assertEqual(captured["payload"]["max_tokens"], 2000)
        self.assertEqual(captured["payload"]["text"]["verbosity"], "high")
        content = captured["payload"]["messages"][1]["content"]
        self.assertEqual(content[1]["image_url"]["detail"], "original")
        trace = client.consume_trace_events()
        self.assertEqual(trace[0]["profile"], "dense_table")
        self.assertEqual(trace[0]["image_detail"], "original")

    def test_extract_call_can_override_profile_knobs(self) -> None:
        captured: dict = {}

        def fake_post(url, *, headers, json, timeout):
            captured["payload"] = json
            return _FakeResponse(
                {
                    "model": "gpt-5.4",
                    "choices": [{"message": {"content": '{"ok":true}'}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("pioneer_agent.perception.vision.openai_client.load_vision_env"):
                with patch(
                    "pioneer_agent.perception.vision.openai_client.requests.post",
                    fake_post,
                ):
                    client = OpenAIVisionClient(profile="dense_table")
                    client.extract(
                        image=_png_bytes(),
                        instruction="Read.",
                        response_schema={"type": "object", "properties": {}},
                        reasoning_effort="low",
                        image_detail="high",
                        verbosity="medium",
                        max_tokens=256,
                    )

        self.assertEqual(captured["payload"]["reasoning_effort"], "low")
        self.assertEqual(captured["payload"]["max_tokens"], 256)
        self.assertEqual(captured["payload"]["text"]["verbosity"], "medium")
        content = captured["payload"]["messages"][1]["content"]
        self.assertEqual(content[1]["image_url"]["detail"], "high")

    def test_factory_accepts_profile_and_explicit_gpt_model(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("pioneer_agent.perception.vision.openai_client.load_vision_env"):
                dense = build_vision_client("openai:dense_table")
                explicit = build_vision_client("gpt-5.4-mini")
        self.assertIsInstance(dense, OpenAIVisionClient)
        self.assertIsInstance(explicit, OpenAIVisionClient)

    def test_model_profile_registry_documents_routing_defaults(self) -> None:
        realtime = get_vision_model_profile("realtime")
        dense = get_vision_model_profile("dense-table")
        self.assertEqual(realtime.reasoning_effort, "low")
        self.assertIsNone(realtime.image_detail)
        self.assertEqual(dense.reasoning_effort, "high")
        self.assertEqual(dense.image_detail, "original")


if __name__ == "__main__":
    unittest.main()
