"""One local entry's causal IDs and detached declarations; not a tracing service."""
from datetime import UTC, datetime
from hashlib import sha256
import json
from uuid import uuid4

from .task_contracts import (
    CausalTraceEvent, PolicyContext, TaskSpec, TraceDeclaration, TraceEmissionError,
    TraceEvent, TraceProvenance,
)
from .task_policy import FakeDecisionPolicy, RuleDecisionPolicy


def canonical_digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


class CausalTraceProducer:
    def __init__(self, runner):
        self.runner = runner
        self.lifetime = uuid4().hex
        self.window = None
        self.parent = self.lifetime
        self.control_parent = None
        self.failure = None
        self.primary = None
        self.business_failure = None
        self.emitting = False

    def remember(self, primary):
        if primary is not None and not isinstance(primary, TraceEmissionError):
            if self.primary is None:
                self.primary = primary
            if self.failure is not None:
                note = "trace_emission_error:" + self.failure.error_type
                if note not in getattr(primary, "__notes__", ()):
                    primary.add_note(note)

    def check(self, *, exit=False):
        if self.failure is not None:
            if exit and self.business_failure is not None:
                return
            if self.primary is None:
                raise self.failure
            if not exit:
                raise self.primary

    def failed_business(self, reason):
        # Only a genuine result established before trace failure can take precedence.
        if self.failure is None or self.primary is not None:
            self.business_failure = reason

    def _failed(self, error, primary=None):
        if self.failure is None:
            self.failure = TraceEmissionError("causal_trace_failed:" + type(error).__name__)
            self.failure.error_type = type(error).__name__
            self.failure.__cause__ = error
        self.remember(primary or self.primary)

    def provenance(self, context=None):
        r = self.runner
        task = TaskSpec.model_validate(r.state.task.model_dump(mode="json"))
        version = getattr(r.policy, "policy_version", None)
        declaration = TraceDeclaration(status="unknown") if version is None else TraceDeclaration(status="declared", value=version)
        builtin = type(r.policy) in (RuleDecisionPolicy, FakeDecisionPolicy)
        absent = TraceDeclaration(status="absent")
        unknown = TraceDeclaration(status="unknown")
        component = absent if builtin and not r.policy.uses_model else unknown
        return TraceProvenance(task_digest=canonical_digest(task.model_dump(mode="json")),
            task_version=task.version, state_version=r.state.version, policy_id=r.policy.policy_id,
            policy_version=declaration,
            context_digest=None if context is None else canonical_digest(context.model_dump(mode="json")),
            model=component, prompt=component, skill=component, kb=component)

    def invocation(self, context=None):
        self.check()
        try:
            detached = None if context is None else PolicyContext.model_validate(context.model_dump(mode="json"))
            provenance = self.provenance(detached)
            return uuid4().hex, provenance
        except Exception as error:
            self._failed(error)
            self.check()

    def emit(self, event, *, primary=None, invocation_id=None, provenance=None,
             event_id=None, parent=None, advance=True):
        self.remember(primary)
        if self.failure is not None:
            return None
        if self.emitting:
            self._failed(RuntimeError("reentrant_trace_emission"), primary)
            return None
        try:
            record = CausalTraceEvent(**event.model_dump(), trace_version=2,
                event_id=event_id or uuid4().hex, emitted_at=datetime.now(UTC),
                lifetime_id=self.lifetime, window_id=self.window,
                parent_event_id=None if event.event == "lifetime_start" else parent if parent is not None else self.parent,
                invocation_id=invocation_id, provenance=provenance or self.provenance())
            self.emitting = True
            self.runner.trace.emit(record)
            if self.failure is None and advance:
                self.parent = record.event_id
            return record.event_id if self.failure is None else None
        except BaseException as error:
            self._failed(error, primary)
            return None
        finally:
            self.emitting = False

    def event(self, event_name, **kwargs):
        return TraceEvent(run_id=self.runner.state.run_id, step_id=self.runner.step_id, event=event_name, **kwargs)

    def start(self, entry):
        self.emit(self.event("lifetime_start", name=entry), event_id=self.lifetime)

    def start_window(self):
        self.check()
        self.window = uuid4().hex
        self.parent = self.lifetime
        self.control_parent = None
        self.emit(self.event("window_start"), event_id=self.window)
        self.check()

    def control(self, name):
        event_id = self.emit(self.event("control", name=name), parent=self.lifetime, advance=False)
        if event_id is not None:
            self.control_parent = event_id

    def outcome(self, *, primary=None, end=False):
        self.remember(primary)
        r = self.runner
        business = r.state.status if primary is None else "failed"
        if isinstance(primary, BaseException) and type(primary).__name__ == "CancelledError":
            business = "cancelled"
        parent = self.control_parent if r.state.reason in {"cancel_requested", "pause_requested"} else None
        self.emit(self.event("lifetime_end" if end else "outcome", name=r.state.reason, business=business,
            error_type=None if primary is None else type(primary).__name__, metadata={"reason": r.state.reason}),
            primary=primary, parent=parent)
        if not end:
            self.window = None
