from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from software_factory.container import ApplicationContainer
from software_factory.domain import TERMINAL_STATES, WorkflowState
from software_factory.tools import ToolError, prepare_frontend_preview


class CreateSessionRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=10_000)


def create_app(container: ApplicationContainer | None = None) -> FastAPI:
    active = container or ApplicationContainer.build()
    app = FastAPI(title="LLM Wiki Software Factory", version="0.1.0")
    app.state.container = active
    app.state.tasks = set()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/agents")
    async def agents() -> list[dict[str, object]]:
        specs = active.orchestrator.specs
        return [
            {
                "id": spec.id,
                "display_name": spec.display_name,
                "description": spec.description,
                "tools": list(spec.tools),
            }
            for spec in specs.values()
        ]

    @app.get("/api/workflow")
    async def workflow() -> list[dict[str, object]]:
        return active.orchestrator.stage_catalog()

    @app.get("/api/tools")
    async def reusable_tools(trusted_only: bool = True) -> list[dict[str, object]]:
        return active.tool_store.list_tools(trusted_only=trusted_only)

    @app.get("/api/wiki/status")
    async def wiki_status() -> dict[str, object]:
        return active.wiki_ingestion.status()

    @app.post("/api/wiki/sources", status_code=201)
    async def ingest_prompt(source: Annotated[UploadFile, File()]) -> dict[str, object]:
        try:
            return active.wiki_ingestion.ingest(source.filename or "prompt.md", await source.read())
        except (UnicodeDecodeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/sessions")
    async def sessions() -> list[dict[str, object]]:
        return [session.to_dict() for session in active.repository.list_sessions()]

    @app.post("/api/sessions", status_code=202)
    async def create_session(request: CreateSessionRequest) -> dict[str, object]:
        session = active.orchestrator.create_session(request.goal)
        task = asyncio.create_task(active.orchestrator.run(session.id))
        app.state.tasks.add(task)
        task.add_done_callback(app.state.tasks.discard)
        return session.to_dict()

    @app.get("/api/sessions/{session_id}")
    async def session(session_id: str) -> dict[str, object]:
        value = active.repository.get(session_id)
        if value is None:
            raise HTTPException(status_code=404, detail="Session not found")
        response = value.to_dict()
        response["terminal"] = value.state in TERMINAL_STATES
        return response

    @app.get("/api/sessions/{session_id}/events")
    async def events(
        session_id: str,
        after: int = Query(default=0, ge=0),
    ) -> list[dict[str, object]]:
        if active.repository.get(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return active.repository.events(session_id, after)

    @app.get("/api/sessions/{session_id}/stream")
    async def stream(session_id: str) -> StreamingResponse:
        if active.repository.get(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")

        async def event_source() -> AsyncIterator[str]:
            cursor = 0
            while True:
                pending = active.repository.events(session_id, cursor)
                for event in pending:
                    cursor = int(event["id"])
                    yield f"data: {json.dumps(event)}\n\n"
                current = active.repository.get(session_id)
                if current is None or (current.state in TERMINAL_STATES and not pending):
                    break
                await asyncio.sleep(0.5)

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/sessions/{session_id}/files")
    async def files(session_id: str) -> list[str]:
        if active.repository.get(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
        workspace = active.orchestrator.workspace(session_id)
        return [
            path.relative_to(workspace).as_posix()
            for path in sorted(workspace.rglob("*"))
            if path.is_file()
        ]

    @app.get("/api/sessions/{session_id}/artifact")
    async def session_artifact(session_id: str) -> FileResponse:
        if active.repository.get(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
        path = active.orchestrator.workspace(session_id) / "session.yaml"
        return FileResponse(path, media_type="application/yaml", filename=f"{session_id}.yaml")

    @app.get("/api/session-comparisons")
    async def compare_sessions(
        ids: Annotated[list[str], Query(min_length=2, max_length=10)],
    ) -> list[object]:
        comparisons: list[object] = []
        for session_id in ids:
            path = active.orchestrator.workspace(session_id) / "session.yaml"
            if not path.is_file():
                raise HTTPException(
                    status_code=404, detail=f"Session artifact not found: {session_id}"
                )
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            comparisons.append(
                {
                    "id": session_id,
                    "goal": value["spec"]["goal"],
                    "model": value["spec"]["model"],
                    "reasoningEffort": value["spec"]["reasoningEffort"],
                    "knowledge": value["spec"]["knowledge"],
                    "promptVersions": {
                        agent["id"]: agent["promptVersion"]
                        for agent in value["spec"]["agents"]
                    },
                    "phase": value["status"]["phase"],
                    "metrics": value["status"]["metrics"],
                    "scorecard": value["status"]["scorecard"],
                    "reusableTool": value["status"]["reusableTool"],
                }
            )
        return comparisons

    @app.get("/previews/{session_id}/", include_in_schema=False)
    @app.get("/previews/{session_id}/{asset_path:path}", include_in_schema=False)
    async def preview(session_id: str, asset_path: str = "") -> FileResponse:
        session = active.repository.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.state is not WorkflowState.COMPLETED:
            raise HTTPException(status_code=409, detail="Preview is not ready")
        workspace = active.orchestrator.workspace(session_id)
        manifest_path = workspace / "deploy" / "preview.yaml"
        try:
            prepared = await prepare_frontend_preview(workspace, manifest_path)
        except (OSError, ValueError, ToolError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        root = (workspace / prepared["root"]).resolve()
        entrypoint = prepared["entrypoint"]
        requested_path = asset_path or entrypoint
        target = (root / requested_path).resolve()
        if asset_path and not target.is_file():
            target = (root / Path(entrypoint).parent / asset_path).resolve()
        if root not in target.parents and target != root:
            raise HTTPException(status_code=400, detail="Invalid preview path")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="Preview asset not found")
        return FileResponse(target)

    web_dir = Path(__file__).parent / "web"
    app.mount("/assets", StaticFiles(directory=web_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    return app


app = create_app()
