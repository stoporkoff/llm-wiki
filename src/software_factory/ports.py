from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from software_factory.domain import AgentRunResult, AgentSpec, FactorySession, SessionEvent


class AgentGateway(Protocol):
    async def run(
        self,
        spec: AgentSpec,
        instruction: str,
        workspace: Path,
        session_id: str,
    ) -> AgentRunResult: ...


class SessionRepository(Protocol):
    def create(self, session: FactorySession) -> None: ...

    def get(self, session_id: str) -> FactorySession | None: ...

    def list_sessions(self, limit: int = 50) -> list[FactorySession]: ...

    def save(self, session: FactorySession) -> None: ...

    def append_event(self, event: SessionEvent) -> None: ...

    def events(self, session_id: str, after: int = 0) -> list[dict[str, Any]]: ...
