from __future__ import annotations

from pathlib import Path

from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.knowledge.models import Domain, QueryResponse
from qa_agent.mcp_server.advisor_tools import AdvisorReplayTools
from qa_agent.service.query_service import QueryService


class KnowledgeToolHandler:
    def __init__(self, service: QueryService, advisor_tools: AdvisorReplayTools | None = None) -> None:
        self.service = service
        self.advisor_tools = advisor_tools or AdvisorReplayTools.from_qa_project_root(Path(__file__).resolve().parents[3])

    @classmethod
    def from_project_root(cls, project_root: Path) -> "KnowledgeToolHandler":
        source_paths = discover_source_paths(project_root / "knowledge_sources")
        return cls(
            QueryService.from_source_paths(source_paths),
            advisor_tools=AdvisorReplayTools.from_qa_project_root(project_root),
        )

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
            {
                "name": "advisor_golden_replay_status",
                "description": "Summarize Sanmou Advisor fixture coverage and golden replay expectation failures.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "include_fixture_results": {
                            "type": "boolean",
                            "default": True,
                            "description": "When true, run fixture replay and compare against the golden expectation manifest.",
                        }
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "advisor_fixture_eval",
                "description": "Run offline Sanmou Advisor replay for one runtime-state fixture and return the selected action.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "fixture": {
                            "type": "string",
                            "description": "Fixture filename under pioneer-agent tests/fixtures, or a repo-relative fixture path.",
                        },
                        "expected_action_type": {
                            "type": ["string", "null"],
                            "description": "Optional expected selected action type. Defaults to the golden manifest value when present.",
                        },
                    },
                    "required": ["fixture"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "advisor_terminal_source_evidence_eval",
                "description": "Preflight low-risk terminal source evidence before adding it to golden expectations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action_type": {
                            "type": "string",
                            "description": "Low-risk action type being evidenced.",
                        },
                        "terminal_source_evidence": {
                            "type": "object",
                            "description": "Terminal source evidence object to validate.",
                        },
                        "fixture": {
                            "type": ["string", "null"],
                            "description": "Optional fixture name that will own this evidence.",
                        },
                        "page": {
                            "type": ["string", "null"],
                            "description": "Optional manifest page override.",
                        },
                    },
                    "required": ["action_type", "terminal_source_evidence"],
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
        elif name == "advisor_golden_replay_status":
            payload = self.advisor_tools.golden_replay_status(
                include_fixture_results=arguments.get("include_fixture_results", True)
            )
            return self._payload_tool_result(payload)
        elif name == "advisor_fixture_eval":
            payload = self.advisor_tools.fixture_eval(
                fixture=arguments["fixture"],
                expected_action_type=arguments.get("expected_action_type"),
            )
            return self._payload_tool_result(payload)
        elif name == "advisor_terminal_source_evidence_eval":
            payload = self.advisor_tools.terminal_source_evidence_eval(
                action_type=arguments["action_type"],
                terminal_source_evidence=arguments["terminal_source_evidence"],
                fixture=arguments.get("fixture"),
                page=arguments.get("page"),
            )
            return self._payload_tool_result(payload)
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

    @staticmethod
    def _payload_tool_result(payload: dict) -> dict:
        return {
            "content": [{"type": "text", "text": json_dumps(payload)}],
            "structuredContent": payload,
            "isError": False,
        }


def json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)
