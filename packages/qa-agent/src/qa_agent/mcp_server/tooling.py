from __future__ import annotations

from pathlib import Path

from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.knowledge.models import Domain, QueryResponse
from qa_agent.service.query_service import QueryService


class KnowledgeToolHandler:
    def __init__(self, service: QueryService) -> None:
        self.service = service

    @classmethod
    def from_project_root(cls, project_root: Path) -> "KnowledgeToolHandler":
        source_paths = discover_source_paths(project_root / "knowledge_sources")
        return cls(QueryService.from_source_paths(source_paths))

    def tool_definitions(self) -> list[dict]:
        domain_enum = [domain.value for domain in Domain]
        return [
            {
                "name": "lookup_topic",
                "description": "Look up a standard knowledge topic and return structured evidence.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "domain": {"type": "string", "enum": domain_enum},
                    },
                    "required": ["topic"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "answer_rule_question",
                "description": "Answer a narrow game-rule question using curated knowledge entries only.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "domain": {"type": "string", "enum": domain_enum},
                    },
                    "required": ["question"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "resolve_term",
                "description": "Resolve an alias or term to the canonical topic in the knowledge base.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "domain": {"type": "string", "enum": domain_enum},
                    },
                    "required": ["term"],
                    "additionalProperties": False,
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        if name == "lookup_topic":
            response = self.service.lookup_topic(arguments["topic"], arguments.get("domain"))
        elif name == "answer_rule_question":
            response = self.service.answer_rule_question(arguments["question"], arguments.get("domain"))
        elif name == "resolve_term":
            response = self.service.resolve_term(arguments["term"], arguments.get("domain"))
        else:
            raise ValueError(f"Unknown tool: {name}")
        return self._tool_result(response)

    @staticmethod
    def _tool_result(response: QueryResponse) -> dict:
        payload = response.model_dump(mode="json")
        return {
            "content": [{"type": "text", "text": response.model_dump_json(indent=2)}],
            "structuredContent": payload,
            "isError": False,
        }
