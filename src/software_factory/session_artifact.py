from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any

import yaml

from software_factory.domain import AgentSpec, FactorySession, utc_now


class SessionArtifactWriter:
    api_version = "factory.llm-wiki.dev/v1alpha1"
    kind = "SoftwareFactorySession"

    def __init__(
        self,
        workspace_root: Path,
        model: str,
        reasoning_effort: str,
        knowledge_snapshot: Callable[[], dict[str, object]] | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._knowledge_snapshot = knowledge_snapshot or (lambda: {})
        self._lock = RLock()

    def initialize(
        self,
        session: FactorySession,
        specs: dict[str, AgentSpec],
        stages: list[dict[str, object]],
    ) -> Path:
        artifact = {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "metadata": {
                "name": session.id,
                "createdAt": session.created_at,
                "labels": {"factory.llm-wiki.dev/state": session.state.value},
            },
            "spec": {
                "goal": session.goal,
                "model": self._model,
                "reasoningEffort": self._reasoning_effort,
                "knowledge": self._knowledge_snapshot(),
                "workflow": stages,
                "agents": [
                    {
                        "id": spec.id,
                        "displayName": spec.display_name,
                        "description": spec.description,
                        "model": spec.model or self._model,
                        "promptVersion": sha256(spec.instructions.encode()).hexdigest()[:12],
                        "tools": list(spec.tools),
                    }
                    for spec in sorted(specs.values(), key=lambda item: item.id)
                ],
            },
            "status": {
                "phase": session.state.value,
                "updatedAt": session.updated_at,
                "completedAt": None,
                "eventCount": 0,
                "timeline": [],
                "agentResults": {},
                "metrics": {
                    "agentDurationMs": 0,
                    "stageDurationMs": 0,
                    "toolCalls": 0,
                    "inputTokens": 0,
                    "outputTokens": 0,
                    "cachedTokens": 0,
                },
                "artifacts": [],
                "scorecard": None,
                "reusableTool": None,
                "error": None,
            },
        }
        path = self.path(session.id)
        self._write(path, artifact)
        return path

    def record_event(
        self,
        session_id: str,
        kind: str,
        actor: str,
        message: str,
        payload: dict[str, Any],
        created_at: str,
    ) -> None:
        with self._lock:
            path = self.path(session_id)
            artifact = self._read(path)
            status = artifact["status"]
            status["updatedAt"] = created_at
            status["eventCount"] += 1
            status["timeline"].append(
                {
                    "sequence": status["eventCount"],
                    "at": created_at,
                    "kind": kind,
                    "actor": actor,
                    "message": message,
                }
            )
            if kind == "state-changed":
                status["phase"] = payload["current"]
                artifact["metadata"]["labels"]["factory.llm-wiki.dev/state"] = payload[
                    "current"
                ]
            elif kind == "agent-completed":
                status["agentResults"][actor] = payload.get("output", "")
                metrics = status["metrics"]
                metrics["agentDurationMs"] += int(payload.get("duration_ms", 0))
                metrics["toolCalls"] += int(payload.get("tool_calls", 0))
                metrics["inputTokens"] += int(payload.get("input_tokens", 0))
                metrics["outputTokens"] += int(payload.get("output_tokens", 0))
                metrics["cachedTokens"] += int(payload.get("cached_tokens", 0))
            elif kind == "stage-completed":
                status["metrics"]["stageDurationMs"] += int(payload.get("duration_ms", 0))
            self._write(path, artifact)

    def finalize(self, session: FactorySession, workspace: Path) -> None:
        with self._lock:
            path = self.path(session.id)
            artifact = self._read(path)
            status = artifact["status"]
            status["phase"] = session.state.value
            status["updatedAt"] = utc_now()
            status["completedAt"] = status["updatedAt"]
            status["error"] = session.error
            status["artifacts"] = [
                item.relative_to(workspace).as_posix()
                for item in sorted(workspace.rglob("*"))
                if item.is_file() and item != path
            ]
            if session.result:
                status["scorecard"] = session.result.get("scorecard")
                status["reusableTool"] = session.result.get("reusable_tool")
            self._write(path, artifact)

    def path(self, session_id: str) -> Path:
        return self._workspace_root / session_id / "session.yaml"

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Invalid session artifact: {path}")
        return value

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".yaml.tmp")
        temporary.write_text(
            yaml.safe_dump(value, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(path)
