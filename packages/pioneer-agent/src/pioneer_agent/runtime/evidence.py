from __future__ import annotations

from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field

EvidenceSourceType = Literal["vision", "state", "selector", "strategy_snapshot", "qa"]
TRUSTED_ENTRY_ID_SOURCES: set[EvidenceSourceType] = {"strategy_snapshot", "qa"}


class EvidenceValidationError(ValueError):
    """Raised when recommendation evidence references unverifiable knowledge ids."""


class AdvisorEvidence(BaseModel):
    evidence_id: str
    source_type: EvidenceSourceType
    ref: str | None = None
    entry_id: str | None = None
    topic: str | None = None
    domain: str | None = None
    summary: str = ""
    source_ref: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_legacy_string(self) -> str:
        if self.ref:
            return self.ref
        if self.entry_id and self.topic:
            suffix = f":{self.topic}" if self.topic else ""
            return f"{self.source_type}:{self.entry_id}{suffix}"
        if self.entry_id:
            return f"{self.source_type}:{self.entry_id}"
        return self.evidence_id


def state_evidence(ref: str, *, confidence: float | None = None, source: str | None = None) -> AdvisorEvidence:
    metadata: dict[str, Any] = {}
    if source:
        metadata["source"] = source
    return AdvisorEvidence(
        evidence_id=f"state:{ref}",
        source_type="state",
        ref=ref,
        confidence=confidence,
        metadata=metadata,
    )


def vision_evidence(
    ref: str,
    *,
    summary: str = "",
    confidence: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> AdvisorEvidence:
    return AdvisorEvidence(
        evidence_id=ref,
        source_type="vision",
        ref=ref,
        summary=summary,
        confidence=confidence,
        metadata=dict(metadata or {}),
    )


def selector_rule_evidence(rule: str) -> AdvisorEvidence:
    ref = f"selector.rule:{rule}"
    return AdvisorEvidence(
        evidence_id=ref,
        source_type="selector",
        ref=ref,
        summary="selector priority rule triggered",
    )


def strategy_snapshot_evidence(
    *,
    entry_id: str,
    topic: str | None,
    domain: str | None,
    summary: str,
    source_ref: str | None,
    strategy_key: str | None,
) -> AdvisorEvidence:
    return AdvisorEvidence(
        evidence_id=f"strategy_snapshot:{entry_id}",
        source_type="strategy_snapshot",
        ref=f"strategy_snapshot:{entry_id}",
        entry_id=entry_id,
        topic=topic,
        domain=domain,
        summary=summary,
        source_ref=source_ref,
        metadata={"strategy_key": strategy_key} if strategy_key else {},
    )


def validate_evidence_entry_ids(
    evidence: Iterable[AdvisorEvidence],
    *,
    allowed_entry_ids: Iterable[str],
) -> None:
    allowed = {str(entry_id) for entry_id in allowed_entry_ids if entry_id}
    for item in evidence:
        if not item.entry_id:
            continue
        if item.source_type not in TRUSTED_ENTRY_ID_SOURCES:
            raise EvidenceValidationError(
                f"Evidence entry_id {item.entry_id!r} cannot come from source {item.source_type!r}"
            )
        if item.entry_id not in allowed:
            raise EvidenceValidationError(
                f"Evidence entry_id {item.entry_id!r} is not present in allowed QA/snapshot ids"
            )
