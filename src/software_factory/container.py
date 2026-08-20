from __future__ import annotations

from dataclasses import dataclass

from software_factory.openai_gateway import OpenAIResponsesAgentGateway
from software_factory.orchestrator import SoftwareFactoryOrchestrator
from software_factory.repository import SQLiteSessionRepository
from software_factory.session_artifact import SessionArtifactWriter
from software_factory.settings import FactorySettings
from software_factory.specs import AgentSpecRepository
from software_factory.telemetry import FactoryTelemetry
from software_factory.tool_store import ReusableToolStore
from software_factory.tools import ToolRegistry
from software_factory.wiki_ingestion import PromptWikiIngestionService


@dataclass(frozen=True)
class ApplicationContainer:
    settings: FactorySettings
    repository: SQLiteSessionRepository
    orchestrator: SoftwareFactoryOrchestrator
    tool_store: ReusableToolStore
    wiki_ingestion: PromptWikiIngestionService

    @classmethod
    def build(cls, settings: FactorySettings | None = None) -> ApplicationContainer:
        active_settings = settings or FactorySettings.from_environment()
        active_settings.data_dir.mkdir(parents=True, exist_ok=True)
        repository = SQLiteSessionRepository(active_settings.data_dir / "factory.db")
        telemetry = FactoryTelemetry.configure()
        tool_store = ReusableToolStore(active_settings.data_dir / "tools")
        wiki_ingestion = PromptWikiIngestionService(active_settings.wiki_root)
        tools = ToolRegistry.default(
            active_settings.agent_specs_dir.parent,
            tool_store,
            telemetry,
            active_settings.wiki_root / "wiki",
        )
        specs = AgentSpecRepository(active_settings.agent_specs_dir).load_all()
        gateway = OpenAIResponsesAgentGateway(
            tools, active_settings.model, active_settings.reasoning_effort
        )
        artifact_writer = SessionArtifactWriter(
            active_settings.data_dir / "workspaces",
            active_settings.model,
            active_settings.reasoning_effort,
            wiki_ingestion.status,
        )
        orchestrator = SoftwareFactoryOrchestrator(
            repository=repository,
            gateway=gateway,
            specs=specs,
            workspace_root=active_settings.data_dir / "workspaces",
            tool_store=tool_store,
            telemetry=telemetry,
            artifact_writer=artifact_writer,
        )
        return cls(active_settings, repository, orchestrator, tool_store, wiki_ingestion)
