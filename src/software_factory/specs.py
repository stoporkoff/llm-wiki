from __future__ import annotations

import re
from pathlib import Path

import yaml

from software_factory.domain import AgentSpec


class AgentSpecError(ValueError):
    pass


class AgentSpecRepository:
    _frontmatter = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def load_all(self) -> dict[str, AgentSpec]:
        specs = {spec.id: spec for spec in map(self._load, sorted(self._directory.glob("*.md")))}
        if not specs:
            raise AgentSpecError(f"No agent specifications found in {self._directory}")
        return specs

    def _load(self, path: Path) -> AgentSpec:
        content = path.read_text(encoding="utf-8")
        match = self._frontmatter.match(content)
        if not match:
            raise AgentSpecError(f"Invalid agent specification frontmatter: {path}")
        metadata = yaml.safe_load(match.group(1))
        if not isinstance(metadata, dict):
            raise AgentSpecError(f"Agent specification metadata must be a mapping: {path}")
        required = {"id", "display_name", "description", "tools"}
        missing = required - metadata.keys()
        if missing:
            raise AgentSpecError(f"Missing {sorted(missing)} in {path}")
        tools = metadata["tools"]
        if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
            raise AgentSpecError(f"Agent tools must be a string list: {path}")
        return AgentSpec(
            id=str(metadata["id"]),
            display_name=str(metadata["display_name"]),
            description=str(metadata["description"]),
            tools=tuple(tools),
            model=str(metadata["model"]) if metadata.get("model") else None,
            instructions=match.group(2).strip(),
        )
