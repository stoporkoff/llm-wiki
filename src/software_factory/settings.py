from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FactorySettings:
    data_dir: Path
    agent_specs_dir: Path
    model: str
    reasoning_effort: str
    wiki_root: Path

    @classmethod
    def from_environment(cls) -> FactorySettings:
        return cls(
            data_dir=Path(os.environ.get("FACTORY_DATA_DIR", ".factory")).resolve(),
            agent_specs_dir=Path(os.environ.get("FACTORY_AGENT_SPECS", "agent_specs")).resolve(),
            model=os.environ.get("OPENAI_MODEL", "gpt-5.6-terra"),
            reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "medium"),
            wiki_root=Path(os.environ.get("FACTORY_WIKI_ROOT", ".factory/knowledge")).resolve(),
        )
