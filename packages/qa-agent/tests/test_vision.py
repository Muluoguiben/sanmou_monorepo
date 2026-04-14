from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from qa_agent.chat.agent import ChatAgent
from qa_agent.chat.openai_client import ChatResult
from qa_agent.retrieval.retriever import Retriever
from qa_agent.vision.extractor import ImageExtractor, VisionExtraction
from qa_agent.vision.image_loader import prepare_image_inputs


KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge_sources"


class ImageLoaderTests(unittest.TestCase):
    def test_http_url_passthrough(self) -> None:
        out = prepare_image_inputs(["https://example.com/a.png"])
        self.assertEqual(out, ["https://example.com/a.png"])

    def test_data_uri_passthrough(self) -> None:
        uri = "data:image/png;base64,AAAA"
        self.assertEqual(prepare_image_inputs([uri]), [uri])

    def test_local_path_encoded(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n")  # PNG magic header, 8 bytes
            path = f.name
        try:
            out = prepare_image_inputs([path])
            self.assertEqual(len(out), 1)
            self.assertTrue(out[0].startswith("data:image/png;base64,"))
            payload = out[0].split(",", 1)[1]
            self.assertEqual(
                base64.b64decode(payload), b"\x89PNG\r\n\x1a\n"
            )
        finally:
            Path(path).unlink(missing_ok=True)

    def test_missing_local_path_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            prepare_image_inputs(["/definitely/not/a/real/path.png"])

    def test_empty_strings_skipped(self) -> None:
        self.assertEqual(prepare_image_inputs(["", "  "]), [])


class ImageExtractorTests(unittest.TestCase):
    def test_parses_well_formed_json(self) -> None:
        client = MagicMock()
        client.generate.return_value = ChatResult(
            text='{"heroes":[{"name":"诸葛亮","confidence":0.9}],'
                 '"skills":[{"name":"八阵图","confidence":0.7}],'
                 '"text_snippets":["第二回合"]}',
            model="gpt-5.4-mini",
            prompt_tokens=10,
            output_tokens=20,
            elapsed_s=1.2,
        )
        extractor = ImageExtractor(client=client)
        result = extractor.extract(["https://x/y.png"], question="这是谁？")
        self.assertEqual([h.name for h in result.heroes], ["诸葛亮"])
        self.assertEqual([s.name for s in result.skills], ["八阵图"])
        self.assertEqual(result.text_snippets, ["第二回合"])
        self.assertAlmostEqual(result.elapsed_s, 1.2)

    def test_strips_json_fence(self) -> None:
        client = MagicMock()
        client.generate.return_value = ChatResult(
            text='```json\n{"heroes":[{"name":"关羽","confidence":1}],'
                 '"skills":[],"text_snippets":[]}\n```',
            model="x", prompt_tokens=0, output_tokens=0, elapsed_s=0.1,
        )
        result = ImageExtractor(client=client).extract(["https://x/a.png"])
        self.assertEqual([h.name for h in result.heroes], ["关羽"])

    def test_malformed_json_yields_empty(self) -> None:
        client = MagicMock()
        client.generate.return_value = ChatResult(
            text="not json at all", model="x",
            prompt_tokens=0, output_tokens=0, elapsed_s=0.1,
        )
        result = ImageExtractor(client=client).extract(["https://x/a.png"])
        self.assertTrue(result.is_empty())
        self.assertEqual(result.raw_text, "not json at all")

    def test_empty_image_list_short_circuits(self) -> None:
        client = MagicMock()
        result = ImageExtractor(client=client).extract([])
        self.assertTrue(result.is_empty())
        client.generate.assert_not_called()

    def test_drops_entities_without_name(self) -> None:
        client = MagicMock()
        client.generate.return_value = ChatResult(
            text='{"heroes":[{"name":"","confidence":0.9},'
                 '{"name":"张飞","confidence":"bad"}],'
                 '"skills":"not-a-list","text_snippets":["x"]}',
            model="x", prompt_tokens=0, output_tokens=0, elapsed_s=0,
        )
        result = ImageExtractor(client=client).extract(["https://x/a.png"])
        self.assertEqual([h.name for h in result.heroes], ["张飞"])
        self.assertEqual(result.heroes[0].confidence, 0.5)  # bad → default
        self.assertEqual(result.skills, [])


class ChatAgentVisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.retriever = Retriever.from_knowledge_dir(KNOWLEDGE_DIR)

    def _make_agent(self, vision: VisionExtraction) -> tuple[ChatAgent, MagicMock]:
        llm = MagicMock()
        llm.generate.return_value = ChatResult(
            text="模拟回答", model="gpt-5.4-mini",
            prompt_tokens=1, output_tokens=1, elapsed_s=0.1,
        )
        extractor = MagicMock()
        extractor.extract.return_value = vision
        agent = ChatAgent(
            retriever=self.retriever,
            client=llm,
            image_extractor=extractor,
        )
        return agent, llm

    def test_resolved_hero_injected_as_query_and_identified(self) -> None:
        from qa_agent.vision.extractor import ExtractedEntity

        vision = VisionExtraction(
            heroes=[ExtractedEntity(name="卧龙", confidence=0.9)],
            skills=[],
            text_snippets=[],
            raw_text="raw",
        )
        agent, llm = self._make_agent(vision)
        reply = agent.ask("他强吗？", images=["https://x/a.png"])

        # "卧龙" is a KB alias → resolved to canonical topic "诸葛亮"
        self.assertIn("诸葛亮", reply.identified_entities)
        self.assertEqual(reply.unresolved_entities, [])
        self.assertIn("诸葛亮", reply.queries)
        # Evidence should contain a hero entry for 诸葛亮
        hero_topics = [c.entry.topic for c in reply.evidence]
        self.assertIn("诸葛亮", hero_topics)
        # LLM was called with a user message tagging the resolved entity
        sent_user_msg = llm.generate.call_args.kwargs["user_message"]
        self.assertIn("<image_entities>", sent_user_msg)
        self.assertIn("诸葛亮", sent_user_msg)

    def test_unresolved_name_not_injected_as_query(self) -> None:
        from qa_agent.vision.extractor import ExtractedEntity

        vision = VisionExtraction(
            heroes=[ExtractedEntity(name="虚构武将XYZ", confidence=0.8)],
            skills=[],
            text_snippets=[],
        )
        agent, llm = self._make_agent(vision)
        reply = agent.ask("这个人？", images=["https://x/a.png"])

        self.assertEqual(reply.identified_entities, [])
        self.assertIn("虚构武将XYZ", reply.unresolved_entities)
        self.assertNotIn("虚构武将XYZ", reply.queries)
        sent_user_msg = llm.generate.call_args.kwargs["user_message"]
        self.assertIn("<image_unresolved>", sent_user_msg)
        self.assertIn("虚构武将XYZ", sent_user_msg)

    def test_no_images_skips_vision(self) -> None:
        vision = VisionExtraction()
        agent, _ = self._make_agent(vision)
        reply = agent.ask("诸葛亮是谁？")
        self.assertEqual(reply.identified_entities, [])
        self.assertEqual(reply.unresolved_entities, [])
        self.assertEqual(reply.vision_raw_text, "")


if __name__ == "__main__":
    unittest.main()
