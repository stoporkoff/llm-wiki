from __future__ import annotations

import asyncio
import json
from pathlib import Path

from software_factory.domain import AgentRunResult, AgentSpec, WorkflowState
from software_factory.orchestrator import SoftwareFactoryOrchestrator
from software_factory.repository import SQLiteSessionRepository
from software_factory.session_artifact import SessionArtifactWriter
from software_factory.telemetry import FactoryTelemetry
from software_factory.tool_store import ReusableToolStore
from software_factory.tools import RunTestsTool, ToolContext, ToolRegistry, prepare_frontend_preview
from software_factory.wiki_ingestion import PromptWikiIngestionService


class FakeAgentGateway:
    async def run(
        self,
        spec: AgentSpec,
        instruction: str,
        workspace: Path,
        session_id: str,
    ) -> AgentRunResult:
        outputs = {
            "requirements-analyst": "Acceptance: a Hello World page is locally viewable.",
            "solution-architect": "Use a static accessible frontend.",
            "team-lead": json.dumps(
                {
                    "summary": "Build one static page",
                    "tasks": [
                        {
                            "role": "frontend-developer",
                            "objective": "Create the page",
                            "acceptance_criteria": ["Shows Hello World"],
                        }
                    ],
                }
            ),
            "frontend-developer": "Created frontend/index.html.",
            "infrastructure-engineer": "Created Docker delivery assets.",
            "qa-engineer": "QA PASSED\nAll tests passed with exit code 0.",
            "security-reviewer": "SECURITY PASSED\nNO CRITICAL FINDINGS",
            "reviewer": "APPROVED: page and tests inspected.",
            "tool-curator": json.dumps(
                {
                    "name": "hello-world-page",
                    "description": "Accessible static Hello World page template.",
                    "kind": "template",
                    "entrypoint": "frontend/index.html",
                    "reusable": True,
                    "tags": ["frontend", "static"],
                }
            ),
            "release-manager": f"READY /previews/{session_id}/\ndocker compose up --build",
        }
        if spec.id == "frontend-developer":
            target = workspace / "frontend" / "templates" / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<h1>Hello World</h1>\n", encoding="utf-8")
        if spec.id == "qa-engineer":
            target = workspace / "tests" / "test_page.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("passed\n", encoding="utf-8")
        if spec.id == "infrastructure-engineer":
            deploy = workspace / "deploy"
            deploy.mkdir(parents=True, exist_ok=True)
            (deploy / "preview.yaml").write_text(
                "apiVersion: factory.llm-wiki.dev/v1alpha1\n"
                "kind: StaticPreview\nmetadata:\n  name: hello-world\n"
                "spec:\n  root: frontend\n  entrypoint: templates/index.html\n",
                encoding="utf-8",
            )
            (deploy / "compose.yaml").write_text(
                "services:\n  web:\n    build:\n      dockerfile: deploy/frontend.Dockerfile\n",
                encoding="utf-8",
            )
            (deploy / "Dockerfile").write_text(
                "FROM nginx:1.29-alpine\n", encoding="utf-8"
            )
        return AgentRunResult(outputs[spec.id], tool_calls=1, input_tokens=10, output_tokens=5)


def specs() -> dict[str, AgentSpec]:
    ids = (
        "requirements-analyst",
        "solution-architect",
        "team-lead",
        "frontend-developer",
        "backend-developer",
        "database-engineer",
        "infrastructure-engineer",
        "qa-engineer",
        "security-reviewer",
        "reviewer",
        "tool-curator",
        "release-manager",
    )
    return {
        agent_id: AgentSpec(agent_id, agent_id, agent_id, (), f"Prompt for {agent_id}")
        for agent_id in ids
    }


def test_workflow_publishes_trusted_reusable_tool(tmp_path: Path) -> None:
    repository = SQLiteSessionRepository(tmp_path / "factory.db")
    store = ReusableToolStore(tmp_path / "tools")
    orchestrator = SoftwareFactoryOrchestrator(
        repository,
        FakeAgentGateway(),
        specs(),
        tmp_path / "workspaces",
        store,
        FactoryTelemetry(),
        SessionArtifactWriter(tmp_path / "workspaces", "test-model", "medium"),
    )

    created = orchestrator.create_session("Create a Hello World page")
    completed = asyncio.run(orchestrator.run(created.id))

    assert completed.state is WorkflowState.COMPLETED
    assert completed.result is not None
    assert completed.result["reusable_tool"]["status"] == "trusted"
    assert store.list_tools()[0]["id"] == "hello-world-page"
    assert any(event["kind"] == "tool-published" for event in repository.events(created.id))
    artifact = (tmp_path / "workspaces" / created.id / "session.yaml").read_text()
    assert "kind: SoftwareFactorySession" in artifact
    assert "phase: completed" in artifact
    assert "promptVersion:" in artifact
    assert "toolCalls: 10" in artifact
    assert completed.result["preview_url"] == f"/previews/{created.id}/"
    registry = ToolRegistry.default(tmp_path, store)
    preview = asyncio.run(
        registry.execute(
            "start_preview",
            {},
            ToolContext(orchestrator.workspace(created.id), "release-manager", created.id),
        )
    )
    assert json.loads(preview)["result"]["ready"] is True


class BlockedQAGateway(FakeAgentGateway):
    async def run(
        self,
        spec: AgentSpec,
        instruction: str,
        workspace: Path,
        session_id: str,
    ) -> AgentRunResult:
        result = await super().run(spec, instruction, workspace, session_id)
        if spec.id == "qa-engineer":
            return AgentRunResult("QA BLOCKED\nVitest is unavailable.")
        return result


def test_verification_fails_closed_before_final_review(tmp_path: Path) -> None:
    repository = SQLiteSessionRepository(tmp_path / "factory.db")
    orchestrator = SoftwareFactoryOrchestrator(
        repository,
        BlockedQAGateway(),
        specs(),
        tmp_path / "workspaces",
        ReusableToolStore(tmp_path / "tools"),
        FactoryTelemetry(),
        SessionArtifactWriter(tmp_path / "workspaces", "test-model", "medium"),
    )

    created = orchestrator.create_session("Create a Hello World page")
    failed = asyncio.run(orchestrator.run(created.id))

    assert failed.state is WorkflowState.FAILED
    assert failed.error == "Verification gate blocked: QA BLOCKED"
    events = repository.events(created.id)
    assert not any(event["actor"] == "reviewer" for event in events)
    assert not any(
        event["kind"] == "stage-completed" and event["message"] == "Verification passed"
        for event in events
    )


def test_frontend_tests_reject_floating_dependencies(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text(
        json.dumps(
            {
                "scripts": {"test": "vitest run"},
                "devDependencies": {"vitest": "latest"},
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        RunTestsTool().execute(
            {"suite": "frontend"},
            ToolContext(tmp_path, "qa-engineer", "test-session"),
        )
    )

    assert result == {
        "exit_code": 2,
        "output": "Floating `latest` dependencies are not allowed: vitest",
    }


def test_prompt_ingestion_creates_immutable_evidence_page(tmp_path: Path) -> None:
    service = PromptWikiIngestionService(tmp_path / "knowledge")

    result = service.ingest(
        "frontend-agent.md",
        b"# Frontend Agent\n\nUse semantic HTML.\n\nTest keyboard navigation.\n",
    )

    assert result["evidence_blocks"] == 3
    assert result["lint_issues"] == []
    assert service.status()["sources"] == 1
    assert len(str(service.status()["revision"])) == 16
    page = tmp_path / "knowledge" / str(result["page"])
    content = page.read_text(encoding="utf-8")
    assert '<a id="evidence-002"></a>' in content
    assert "Raw location: `raw/" in content


def test_prebuilt_frontend_preview_uses_dist_output(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    frontend = workspace / "frontend"
    deploy = workspace / "deploy"
    (frontend / "dist").mkdir(parents=True)
    deploy.mkdir(parents=True)
    (frontend / "package.json").write_text('{"scripts":{"build":"vite build"}}\n')
    (frontend / "dist" / "index.html").write_text("<h1>Built</h1>\n")
    manifest_path = deploy / "preview.yaml"
    manifest_path.write_text(
        "apiVersion: factory.llm-wiki.dev/v1alpha1\n"
        "kind: StaticPreview\n"
        "spec:\n  root: frontend\n  entrypoint: index.html\n"
    )

    prepared = asyncio.run(prepare_frontend_preview(workspace, manifest_path))

    assert prepared == {"root": "frontend/dist", "entrypoint": "index.html"}
    assert "root: frontend/dist" in manifest_path.read_text()
