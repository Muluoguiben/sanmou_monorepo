from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from qa_agent.chat.gemini_client import GeminiChatClient
from qa_agent.chat.prompts import QUERY_REWRITE_PROMPT, SYSTEM_PROMPT
from qa_agent.retrieval.retriever import RetrievedChunk, Retriever

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


class ChatAgent:
    def __init__(
        self,
        retriever: Retriever,
        client: GeminiChatClient | None = None,
        *,
        top_k_per_query: int = 3,
        total_evidence_cap: int = 8,
    ) -> None:
        self.retriever = retriever
        self.client = client or GeminiChatClient()
        self.top_k_per_query = top_k_per_query
        self.total_evidence_cap = total_evidence_cap
        self.history: list[ChatTurn] = []

    @classmethod
    def from_knowledge_dir(cls, knowledge_dir: Path) -> "ChatAgent":
        return cls(retriever=Retriever.from_knowledge_dir(knowledge_dir))

    def reset(self) -> None:
        self.history.clear()

    def ask(self, question: str) -> ChatReply:
        queries = self._rewrite_queries(question)
        chunks = self.retriever.retrieve_multi(
            queries,
            top_k_per_query=self.top_k_per_query,
            total_cap=self.total_evidence_cap,
        )
        user_message = self._compose_user_message(question, chunks)

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
        )

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
    def _compose_user_message(question: str, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            evidence_block = "(evidence 为空 — 知识库未匹配到任何相关条目)"
        else:
            evidence_block = "\n\n".join(c.as_prompt_block() for c in chunks)
        return (
            f"<evidence>\n{evidence_block}\n</evidence>\n\n"
            f"用户问题：{question}"
        )
