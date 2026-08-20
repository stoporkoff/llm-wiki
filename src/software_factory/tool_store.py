from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from software_factory.scoring import DeliveryScorecard


@dataclass(frozen=True)
class PublishedTool:
    id: str
    version: str
    status: str
    manifest_path: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "version": self.version,
            "status": self.status,
            "manifest_path": self.manifest_path.as_posix(),
        }


class ReusableToolStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def publish(
        self,
        session_id: str,
        workspace: Path,
        contract: dict[str, Any],
        scorecard: DeliveryScorecard,
    ) -> PublishedTool:
        tool_id = self._slug(str(contract["name"]))
        version = f"0.1.0-{session_id[:8]}"
        destination = self._root / tool_id / version
        if destination.exists():
            shutil.rmtree(destination)
        payload = destination / "payload"
        payload.mkdir(parents=True)
        for component in ("frontend", "backend", "database", "deploy", "tests"):
            source = workspace / component
            if source.is_dir():
                shutil.copytree(source, payload / component)
        manifest = {
            "schema_version": 1,
            "id": tool_id,
            "version": version,
            "status": scorecard.status,
            "source_session_id": session_id,
            "contract": contract,
            "scorecard": scorecard.to_dict(),
            "components": sorted(path.name for path in payload.iterdir()),
        }
        manifest_path = destination / "tool.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return PublishedTool(tool_id, version, scorecard.status, manifest_path)

    def list_tools(self, trusted_only: bool = True) -> list[dict[str, Any]]:
        manifests = []
        for path in self._root.glob("*/*/tool.json"):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if not trusted_only or manifest["status"] == "trusted":
                manifests.append(manifest)
        return sorted(manifests, key=lambda item: (item["id"], item["version"]))

    def apply(self, tool_id: str, component: str, destination: Path) -> list[str]:
        matches = [item for item in self.list_tools() if item["id"] == tool_id]
        if not matches:
            raise ValueError(f"Trusted reusable tool not found: {tool_id}")
        selected = matches[-1]
        source = self._root / selected["id"] / selected["version"] / "payload" / component
        if not source.is_dir():
            raise ValueError(f"Tool {tool_id} does not provide component {component}")
        destination.mkdir(parents=True, exist_ok=True)
        copied = []
        for path in source.rglob("*"):
            if path.is_file():
                target = destination / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                copied.append(target.relative_to(destination).as_posix())
        return copied

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return slug[:64] or "generated-tool"
