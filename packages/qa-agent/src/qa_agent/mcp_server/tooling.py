from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError

from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.knowledge.models import Domain, QueryResponse
from qa_agent.mcp_server.advisor_tools import AdvisorReplayTools
from qa_agent.service.query_service import QueryService


DomainName: TypeAlias = Literal[*tuple(domain.value for domain in Domain)]


class StrictToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LookupTopicInput(StrictToolInput):
    topic: StrictStr = Field(min_length=1, description="Knowledge topic to look up.")
    domain: DomainName | None = Field(default=None, description="Optional knowledge domain filter.")


class AnswerRuleQuestionInput(StrictToolInput):
    question: StrictStr = Field(min_length=1, description="Narrow game-rule question to answer.")
    domain: DomainName | None = Field(default=None, description="Optional knowledge domain filter.")


class ResolveTermInput(StrictToolInput):
    term: StrictStr = Field(min_length=1, description="Alias or game term to resolve.")
    domain: DomainName | None = Field(default=None, description="Optional knowledge domain filter.")


class AdvisorGoldenReplayStatusInput(StrictToolInput):
    include_fixture_results: StrictBool = Field(
        default=True,
        description="Run fixture replay and compare it with the golden expectation manifest.",
    )


class AdvisorFixtureEvalInput(StrictToolInput):
    fixture: StrictStr = Field(
        min_length=1,
        description="Fixture filename or repo-relative path under pioneer-agent tests/fixtures.",
    )
    expected_action_type: StrictStr | None = Field(
        default=None,
        description="Optional expected selected action type; defaults to the golden manifest value.",
    )


class AdvisorTerminalSourceEvidenceEvalInput(StrictToolInput):
    action_type: StrictStr = Field(min_length=1, description="Low-risk action type being evidenced.")
    terminal_source_evidence: dict[str, Any] = Field(
        description="Terminal source evidence object to validate.",
    )
    fixture: StrictStr | None = Field(
        default=None,
        description="Optional fixture name that will own this evidence.",
    )
    page: StrictStr | None = Field(default=None, description="Optional manifest page override.")


TOOL_NAMES = (
    "lookup_topic",
    "answer_rule_question",
    "resolve_term",
    "advisor_golden_replay_status",
    "advisor_fixture_eval",
    "advisor_terminal_source_evidence_eval",
)

TOOL_DESCRIPTIONS = {
    "lookup_topic": "Look up a standard knowledge topic and return structured evidence.",
    "answer_rule_question": "Answer a narrow game-rule question using curated knowledge entries only.",
    "resolve_term": "Resolve an alias or term to the canonical topic in the knowledge base.",
    "advisor_golden_replay_status": (
        "Summarize Sanmou Advisor fixture coverage and golden replay expectation failures."
    ),
    "advisor_fixture_eval": (
        "Run offline Sanmou Advisor replay for one runtime-state fixture and return the selected action."
    ),
    "advisor_terminal_source_evidence_eval": (
        "Preflight low-risk terminal source evidence before adding it to golden expectations."
    ),
}

TOOL_INPUT_MODELS: dict[str, type[StrictToolInput]] = {
    "lookup_topic": LookupTopicInput,
    "answer_rule_question": AnswerRuleQuestionInput,
    "resolve_term": ResolveTermInput,
    "advisor_golden_replay_status": AdvisorGoldenReplayStatusInput,
    "advisor_fixture_eval": AdvisorFixtureEvalInput,
    "advisor_terminal_source_evidence_eval": AdvisorTerminalSourceEvidenceEvalInput,
}

READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "openWorldHint": False,
}


def validate_tool_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    model = TOOL_INPUT_MODELS.get(name)
    if model is None:
        raise ValueError(f"Unknown tool: {name}")
    try:
        validated = model.model_validate(arguments)
    except ValidationError as exc:
        issues = ", ".join(
            f"{'.'.join(str(part) for part in error['loc'])}:{error['type']}"
            for error in exc.errors()
        )
        raise ValueError(f"Invalid arguments for {name}: {issues}") from exc
    return validated.model_dump(mode="json", exclude_unset=True)


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
        return [
            {
                "name": name,
                "description": TOOL_DESCRIPTIONS[name],
                "inputSchema": TOOL_INPUT_MODELS[name].model_json_schema(),
                "annotations": dict(READ_ONLY_ANNOTATIONS),
            }
            for name in TOOL_NAMES
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        arguments = validate_tool_arguments(name, arguments)
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
