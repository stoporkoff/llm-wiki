from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class WorkflowState(StrEnum):
    CREATED = "created"
    DISCOVERY = "discovery"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    RELEASING = "releasing"
    TESTING = "testing"
    REVIEWING = "reviewing"
    PACKAGING = "packaging"
    PREVIEWING = "previewing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionMode(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DYNAMIC = "dynamic"


TERMINAL_STATES = {WorkflowState.COMPLETED, WorkflowState.FAILED}


@dataclass(frozen=True)
class AgentSpec:
    id: str
    display_name: str
    description: str
    tools: tuple[str, ...]
    instructions: str
    model: str | None = None


@dataclass(frozen=True)
class WorkItem:
    role: str
    objective: str
    acceptance_criteria: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionPlan:
    summary: str
    tasks: tuple[WorkItem, ...]


@dataclass(frozen=True)
class AgentRunResult:
    output: str
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    duration_ms: int = 0


@dataclass(frozen=True)
class StageDefinition:
    state: WorkflowState
    display_name: str
    description: str
    mode: ExecutionMode
    agents: tuple[str, ...]
    gate: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        value["mode"] = self.mode.value
        return value


@dataclass
class FactorySession:
    goal: str
    id: str = field(default_factory=lambda: uuid4().hex)
    state: WorkflowState = WorkflowState.CREATED
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        return value


@dataclass(frozen=True)
class SessionEvent:
    session_id: str
    kind: str
    actor: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
