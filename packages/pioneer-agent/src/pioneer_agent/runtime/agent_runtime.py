from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sanmou_common.config import ConfigLoader
from pioneer_agent.core.enums import EventType, RuntimeStage
from pioneer_agent.core.models import AgentEvent, RuntimeContext
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.executor.runner import ActionRunner
from pioneer_agent.perception.sync_service import StateSyncService
from pioneer_agent.selector.action_selector import ActionSelector
from pioneer_agent.storage.logger import AgentLogger


class AgentRuntime:
    def __init__(
        self,
        config_loader: ConfigLoader,
        logger: AgentLogger,
        sync_service: StateSyncService | None = None,
    ) -> None:
        self.config_loader = config_loader
        self.logger = logger
        self.sync_service = sync_service or StateSyncService()
        self.deriver = StateDeriver()
        self.selector = ActionSelector()
        self.runner = ActionRunner()
        self.context = RuntimeContext(session_id=str(uuid4()))

    def run_once(self) -> None:
        self.context.stage = RuntimeStage.SYNCING
        state, sync_summary = self.sync_service.full_sync()
        self.logger.log_sync_summary(self.context.session_id, sync_summary)
        derived_state = self.deriver.derive(state)
        self.logger.log_runtime_state(
            self.context.session_id,
            derived_state.model_dump(mode="json"),
            sync_summary=sync_summary,
        )

        self.context.stage = RuntimeStage.PLANNING
        result = self.selector.select(derived_state)
        self.logger.log_selection(self.context.session_id, result)

        if result.selected_action is None:
            self.context.last_event = AgentEvent(
                event_type=EventType.FALLBACK_REPLAN,
                event_time=datetime.utcnow(),
            )
            return

        self.context.stage = RuntimeStage.EXECUTING
        execution = self.runner.run(result.selected_action)
        self.logger.log_execution(self.context.session_id, execution)
        self.context.stage = RuntimeStage.WAITING
