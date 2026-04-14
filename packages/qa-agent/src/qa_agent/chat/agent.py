from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from qa_agent.chat.llm_client import LLMClient, build_llm_client
from qa_agent.chat.prompts import QUERY_REWRITE_PROMPT, SYSTEM_PROMPT
from qa_agent.knowledge.models import Domain
from qa_agent.retrieval.retriever import RetrievedChunk, Retriever
from qa_agent.vision.extractor import ImageExtractor, VisionExtraction
from qa_agent.vision.image_loader import prepare_image_inputs

logger = logging.getLogger(__name__)


@dataclass
class ChatTurn:
    role: str  # "user" or "assistant"
    content: str
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ChatReply:
    answer: str
    evidence: list[RetrievedChunk]
    queries: list[str]
    prompt_tokens: int
    output_tokens: int
    elapsed_s: float
    identified_entities: list[str] = field(default_factory=list)
    unresolved_entities: list[str] = field(default_factory=list)
    vision_raw_text: str = ""


class ChatAgent:
    def __init__(
        self,
        retriever: Retriever,
        client: LLMClient | None = None,
        *,
        top_k_per_query: int = 3,
        total_evidence_cap: int = 8,
        image_extractor: ImageExtractor | None = None,
    ) -> None:
        self.retriever = retriever
        self.client = client or build_llm_client()
        self.top_k_per_query = top_k_per_query
        self.total_evidence_cap = total_evidence_cap
        self._image_extractor = image_extractor
        self.history: list[ChatTurn] = []

    @classmethod
    def from_knowledge_dir(cls, knowledge_dir: Path) -> "ChatAgent":
        return cls(retriever=Retriever.from_knowledge_dir(knowledge_dir))

    def reset(self) -> None:
        self.history.clear()

    def ask(
        self,
        question: str,
        *,
        images: list[str] | None = None,
    ) -> ChatReply:
        vision: VisionExtraction | None = None
        identified: list[str] = []
        unresolved: list[str] = []
        if images:
            prepared = prepare_image_inputs(images)
            if prepared:
                vision = self._get_image_extractor().extract(prepared, question=question)
                identified, unresolved = self._resolve_vision_entities(vision)

        queries = self._rewrite_queries(question)
        # Inject resolved vision entities as extra retrieval queries so their
        # KB entries land in evidence. Unresolved candidates are dropped —
        # the answering LLM never learns of fabrication-prone names.
        for name in identified:
            if name not in queries:
                queries.append(name)

        chunks = self.retriever.retrieve_multi(
            queries,
            top_k_per_query=self.top_k_per_query,
            total_cap=self.total_evidence_cap,
        )
        user_message = self._compose_user_message(
            question, chunks, identified=identified, unresolved=unresolved
        )

        gemini_history = [
            {"role": turn.role, "content": turn.content} for turn in self.history
        ]
        resp = self.client.generate(
            system_prompt=SYSTEM_PROMPT,
            history=gemini_history,
            user_message=user_message,
        )

        self.history.append(ChatTurn(role="user", content=question))
        self.history.append(
            ChatTurn(
                role="assistant",
                content=resp.text,
                evidence_ids=[c.entry.id for c in chunks],
            )
        )

        return ChatReply(
            answer=resp.text.strip(),
            evidence=chunks,
            queries=queries,
            prompt_tokens=resp.prompt_tokens,
            output_tokens=resp.output_tokens,
            elapsed_s=resp.elapsed_s,
            identified_entities=identified,
            unresolved_entities=unresolved,
            vision_raw_text=vision.raw_text if vision else "",
        )

    def _get_image_extractor(self) -> ImageExtractor:
        if self._image_extractor is None:
            # Lazy so constructing a ChatAgent without vision use doesn't
            # require OpenAI env to be configured.
            self._image_extractor = ImageExtractor()
        return self._image_extractor

    def _resolve_vision_entities(
        self, vision: VisionExtraction
    ) -> tuple[list[str], list[str]]:
        """Return (identified, unresolved) canonical names.

        A candidate resolves when the retriever's alias index matches it to
        at least one KB entry of the expected domain. Unresolved names are
        reported back to the caller (and mentioned to the LLM as 'unknown')
        but NEVER injected as retrieval queries — that would let the
        answering pass hallucinate about names we can't ground.
        """
        identified: list[str] = []
        unresolved: list[str] = []
        seen: set[str] = set()
        for ent, expected_domain in [
            *[(e, Domain.HERO) for e in vision.heroes],
            *[(e, Domain.SKILL) for e in vision.skills],
        ]:
            if ent.name in seen:
                continue
            seen.add(ent.name)
            matches = self.retriever.index.resolve_term(
                ent.name, domain=expected_domain
            )
            if matches:
                identified.append(matches[0].topic)
            else:
                unresolved.append(ent.name)
        return identified, unresolved

    def _rewrite_queries(self, question: str) -> list[str]:
        if not self.history:
            return [question]
        history_blob = "\n".join(
            f"{turn.role}: {turn.content[:160]}" for turn in self.history[-6:]
        )
        prompt = QUERY_REWRITE_PROMPT.format(history=history_blob, question=question)
        try:
            parsed = self.client.generate_json(
                system_prompt="你是简洁的检索查询生成器。只返回 JSON 数组。",
                user_message=prompt,
            )
            if isinstance(parsed, list) and parsed:
                queries = [str(q).strip() for q in parsed if str(q).strip()]
                if question not in queries:
                    queries.append(question)
                return queries[:4]
        except Exception as exc:  # noqa: BLE001
            logger.warning("query rewrite failed, falling back to raw question: %s", exc)
        return [question]

    @staticmethod
    def _compose_user_message(
        question: str,
        chunks: list[RetrievedChunk],
        *,
        identified: list[str] | None = None,
        unresolved: list[str] | None = None,
    ) -> str:
        if not chunks:
            evidence_block = "(evidence 为空 — 知识库未匹配到任何相关条目)"
        else:
            evidence_block = "\n\n".join(c.as_prompt_block() for c in chunks)
        parts = [f"<evidence>\n{evidence_block}\n</evidence>"]
        if identified:
            parts.append(
                "<image_entities>\n"
                + "图中已识别并已对齐到知识库的条目：" + "、".join(identified)
                + "\n</image_entities>"
            )
        if unresolved:
            parts.append(
                "<image_unresolved>\n"
                + "图中出现但知识库未收录的名字（不要据此回答，也不要猜）："
                + "、".join(unresolved)
                + "\n</image_unresolved>"
            )
        parts.append(f"用户问题：{question}")
        return "\n\n".join(parts)
