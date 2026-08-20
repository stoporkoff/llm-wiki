from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any

from software_factory.domain import (
    AgentRunResult,
    AgentSpec,
    FactorySession,
    SessionEvent,
    WorkflowState,
    utc_now,
)
from software_factory.fsm import WorkflowStateMachine
from software_factory.ports import AgentGateway, SessionRepository
from software_factory.scoring import DeliveryScorer
from software_factory.session_artifact import SessionArtifactWriter
from software_factory.stages import StagePipeline, WorkflowContext
from software_factory.telemetry import FactoryTelemetry
from software_factory.tool_store import ReusableToolStore


class SoftwareFactoryOrchestrator:
    def __init__(
        self,
        repository: SessionRepository,
        gateway: AgentGateway,
        specs: dict[str, AgentSpec],
        workspace_root: Path,
        tool_store: ReusableToolStore,
        telemetry: FactoryTelemetry,
        artifact_writer: SessionArtifactWriter,
        state_machine: WorkflowStateMachine | None = None,
        pipeline: StagePipeline | None = None,
        scorer: DeliveryScorer | None = None,
    ) -> None:
        self._repository = repository
        self._gateway = gateway
        self._specs = specs
        self._workspace_root = workspace_root
        self._tool_store = tool_store
        self._telemetry = telemetry
        self._artifact_writer = artifact_writer
        self._state_machine = state_machine or WorkflowStateMachine()
        self._pipeline = pipeline or StagePipeline.default()
        self._scorer = scorer or DeliveryScorer()
        self._validate_pipeline()

    @property
    def specs(self) -> dict[str, AgentSpec]:
        return dict(self._specs)

    def stage_catalog(self) -> list[dict[str, object]]:
        return self._pipeline.catalog()

    def create_session(self, goal: str) -> FactorySession:
        session = FactorySession(goal=goal.strip())
        self._repository.create(session)
        self._artifact_writer.initialize(session, self._specs, self.stage_catalog())
        self._event(session.id, "session-created", "system", "Delivery session created")
        return session

    def workspace(self, session_id: str) -> Path:
        return self._workspace_root / session_id

    async def run(self, session_id: str) -> FactorySession:
        session = self._require_session(session_id)
        workspace = self.workspace(session.id)
        workspace.mkdir(parents=True, exist_ok=True)

        async def invoke(agent_id: str, instruction: str) -> AgentRunResult:
            return await self._run_agent(session, agent_id, instruction, workspace)

        context = WorkflowContext(session=session, invoke=invoke)
        with self._telemetry.span("factory.workflow", {"session.id": session.id}):
            try:
                for stage in self._pipeline.stages:
                    self._transition(session, stage.definition.state)
                    self._event(
                        session.id,
                        "stage-started",
                        "orchestrator",
                        f"{stage.definition.display_name} started",
                        stage.definition.to_dict(),
                    )
                    started = monotonic()
                    with self._telemetry.span(
                        "factory.stage",
                        {
                            "session.id": session.id,
                            "stage": stage.definition.state.value,
                            "mode": stage.definition.mode.value,
                        },
                    ):
                        await stage.execute(context)
                    self._event(
                        session.id,
                        "stage-completed",
                        "orchestrator",
                        f"{stage.definition.display_name} passed",
                        {
                            "duration_ms": round((monotonic() - started) * 1000),
                            "gate": stage.definition.gate,
                        },
                    )

                scorecard = self._scorer.score(context, workspace)
                published = self._tool_store.publish(
                    session.id, workspace, context.tool_contract or {}, scorecard
                )
                self._telemetry.delivery_scored(scorecard.status, scorecard.total)
                reusable_tool = published.to_dict()
                session.result = context.to_dict() | {
                    "scorecard": scorecard.to_dict(),
                    "reusable_tool": reusable_tool,
                }
                self._event(
                    session.id,
                    "tool-published",
                    "tool-curator",
                    f"Reusable tool published as {published.status}",
                    reusable_tool | {"score": scorecard.total},
                )
                self._transition(session, WorkflowState.COMPLETED)
            except Exception as error:
                session.error = str(error)
                if session.state not in {WorkflowState.COMPLETED, WorkflowState.FAILED}:
                    self._transition(session, WorkflowState.FAILED)
                self._event(session.id, "session-failed", "system", str(error))
            finally:
                self._artifact_writer.finalize(session, workspace)
                self._telemetry.session_completed(session.state.value)
        return session

    async def _run_agent(
        self,
        session: FactorySession,
        agent_id: str,
        instruction: str,
        workspace: Path,
    ) -> AgentRunResult:
        spec = self._specs[agent_id]
        self._event(session.id, "agent-started", agent_id, f"{spec.display_name} started")
        started = monotonic()
        with self._telemetry.span(
            "factory.agent", {"session.id": session.id, "agent.id": agent_id}
        ):
            result = await self._gateway.run(spec, instruction, workspace, session.id)
        duration_ms = result.duration_ms or round((monotonic() - started) * 1000)
        self._telemetry.agent_completed(agent_id, duration_ms, result.tool_calls)
        self._telemetry.tokens(
            agent_id, result.input_tokens, result.output_tokens, result.cached_tokens
        )
        self._event(
            session.id,
            "agent-completed",
            agent_id,
            f"{spec.display_name} completed",
            {
                "duration_ms": duration_ms,
                "tool_calls": result.tool_calls,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cached_tokens": result.cached_tokens,
                "output": result.output,
                "prompt_version": sha256(spec.instructions.encode()).hexdigest()[:12],
            },
        )
        return result

    def _transition(self, session: FactorySession, target: WorkflowState) -> None:
        previous = session.state
        session.state = self._state_machine.transition(previous, target)
        session.updated_at = utc_now()
        self._repository.save(session)
        self._event(
            session.id,
            "state-changed",
            "orchestrator",
            f"State changed from {previous.value} to {target.value}",
            {"previous": previous.value, "current": target.value},
        )

    def _event(
        self,
        session_id: str,
        kind: str,
        actor: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = SessionEvent(session_id, kind, actor, message, payload or {})
        self._repository.append_event(event)
        self._artifact_writer.record_event(
            session_id, kind, actor, message, event.payload, event.created_at
        )

    def _require_session(self, session_id: str) -> FactorySession:
        session = self._repository.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def _validate_pipeline(self) -> None:
        missing = {
            agent
            for stage in self._pipeline.stages
            for agent in stage.definition.agents
            if agent not in self._specs
        }
        if missing:
            raise ValueError(f"Missing agent specifications: {', '.join(sorted(missing))}")
