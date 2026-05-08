from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch

from PIL import Image

from pioneer_agent.perception.vision import build_vision_client
from pioneer_agent.perception.vision.client import VisionError
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
        self.assertFalse(captured["payload"]["store"])
        content = captured["payload"]["messages"][1]["content"]
        self.assertIn("Read the page.", content[0]["text"])
        self.assertIn('"page_type"', content[0]["text"])
        self.assertTrue(
            content[1]["image_url"]["url"].startswith("data:image/png;base64,")
        )

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


if __name__ == "__main__":
    unittest.main()
