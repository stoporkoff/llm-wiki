from __future__ import annotations

import asyncio
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any

import yaml

from software_factory.telemetry import FactoryTelemetry
from software_factory.tool_store import ReusableToolStore


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolContext:
    workspace: Path
    role: str
    session_id: str


class WorkspacePolicy:
    _write_roots: dict[str, tuple[str, ...]] = {
        "team-lead": (),
        "frontend-developer": ("frontend",),
        "backend-developer": ("backend",),
        "database-engineer": ("database",),
        "qa-engineer": ("tests",),
        "infrastructure-engineer": ("deploy",),
        "reviewer": (),
    }
    _blocked_names = {".env", ".git", "secrets", "credentials"}

    def resolve(self, context: ToolContext, relative_path: str, write: bool = False) -> Path:
        candidate = (context.workspace / relative_path).resolve()
        root = context.workspace.resolve()
        if candidate != root and root not in candidate.parents:
            raise ToolError("Path escapes the session workspace")
        relative = candidate.relative_to(root)
        if any(part.casefold() in self._blocked_names for part in relative.parts):
            raise ToolError("Path is protected")
        if write:
            allowed = self._write_roots.get(context.role, ())
            if not relative.parts or relative.parts[0] not in allowed:
                raise ToolError(f"Role {context.role} cannot write {relative.as_posix()}")
        return candidate


class FactoryTool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]

    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": True,
        }

    @abstractmethod
    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]: ...


class ListFilesTool(FactoryTool):
    name = "list_files"
    description = "List regular files in the session workspace. Returns relative paths."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Relative directory path."}},
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, policy: WorkspacePolicy) -> None:
        self._policy = policy

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        directory = self._policy.resolve(context, str(arguments["path"]))
        if not directory.exists():
            return {"files": [], "warning": "Directory does not exist"}
        if not directory.is_dir():
            raise ToolError("Requested path is not a directory")
        files = [
            path.relative_to(context.workspace).as_posix()
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        ]
        return {"files": files[:500], "truncated": len(files) > 500}


class ReadFileTool(FactoryTool):
    name = "read_file"
    description = "Read a UTF-8 text file from the session workspace. Returns content or an error."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Relative file path."}},
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, policy: WorkspacePolicy) -> None:
        self._policy = policy

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        path = self._policy.resolve(context, str(arguments["path"]))
        if not path.is_file():
            raise ToolError("File does not exist")
        content = path.read_text(encoding="utf-8")
        if len(content) > 100_000:
            return {"content": content[:100_000], "truncated": True}
        return {"content": content, "truncated": False}


class WriteFileTool(FactoryTool):
    name = "write_file"
    description = "Create or replace one UTF-8 file within the role's allowed workspace directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative destination path."},
            "content": {"type": "string", "description": "Complete UTF-8 file content."},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def __init__(self, policy: WorkspacePolicy) -> None:
        self._policy = policy

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        path = self._policy.resolve(context, str(arguments["path"]), write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = str(arguments["content"])
        path.write_text(content, encoding="utf-8", newline="\n")
        return {
            "path": path.relative_to(context.workspace).as_posix(),
            "characters": len(content),
        }


class RunTestsTool(FactoryTool):
    name = "run_tests"
    description = (
        "Run one approved local test suite. Returns exit code and bounded combined output."
    )
    parameters = {
        "type": "object",
        "properties": {
            "suite": {
                "type": "string",
                "enum": ["python", "frontend"],
                "description": "Approved suite to execute.",
            }
        },
        "required": ["suite"],
        "additionalProperties": False,
    }

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        suite = str(arguments["suite"])
        commands = {
            "python": [os.environ.get("PYTHON", "python"), "-m", "pytest", "-q"],
            "frontend": ["npm", "test", "--", "--run"],
        }
        process = await asyncio.create_subprocess_exec(
            *commands[suite],
            cwd=context.workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=120)
        except TimeoutError:
            process.kill()
            await process.wait()
            return {"exit_code": 124, "output": "Test process timed out after 120 seconds."}
        output = output_bytes.decode(errors="replace")[-20_000:]
        return {"exit_code": process.returncode, "output": output}


class SearchWikiTool(FactoryTool):
    name = "search_wiki"
    description = "Search the project's compiled Markdown wiki. Returns ranked paths and excerpts."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Terms to search for in the wiki."}
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, wiki_paths: tuple[Path, ...]) -> None:
        self._wiki_paths = wiki_paths

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        terms = {
            term.casefold()
            for term in re.findall(r"[\w-]+", str(arguments["query"]))
            if len(term) > 1
        }
        results: list[dict[str, Any]] = []
        for wiki_path in self._wiki_paths:
            if not wiki_path.exists():
                continue
            for path in wiki_path.rglob("*.md"):
                text = path.read_text(encoding="utf-8")
                score = sum(text.casefold().count(term) for term in terms)
                if score:
                    excerpt = next(
                        (
                            line.strip()
                            for line in text.splitlines()
                            if any(term in line.casefold() for term in terms)
                        ),
                        "",
                    )
                    results.append(
                        {
                            "path": path.relative_to(wiki_path).as_posix(),
                            "score": score,
                            "excerpt": excerpt[:500],
                        }
                    )
        results.sort(key=lambda item: (-item["score"], item["path"]))
        return {"results": results[:10]}


class ListReusableToolsTool(FactoryTool):
    name = "list_reusable_tools"
    description = "List trusted generated templates that can accelerate implementation."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def __init__(self, store: ReusableToolStore) -> None:
        self._store = store

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        tools = self._store.list_tools()
        return {
            "tools": [
                {
                    "id": item["id"],
                    "version": item["version"],
                    "description": item["contract"]["description"],
                    "components": item["components"],
                    "score": item["scorecard"]["total"],
                }
                for item in tools
            ]
        }


class ApplyReusableToolTool(FactoryTool):
    name = "apply_reusable_tool"
    description = "Copy one component from a trusted generated template into your owned path."
    parameters = {
        "type": "object",
        "properties": {
            "tool_id": {"type": "string", "description": "Trusted tool identifier."},
            "component": {
                "type": "string",
                "enum": ["frontend", "backend", "database", "deploy", "tests"],
            },
        },
        "required": ["tool_id", "component"],
        "additionalProperties": False,
    }

    def __init__(self, store: ReusableToolStore, policy: WorkspacePolicy) -> None:
        self._store = store
        self._policy = policy

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        component = str(arguments["component"])
        destination = self._policy.resolve(context, component, write=True)
        copied = self._store.apply(str(arguments["tool_id"]), component, destination)
        return {"component": component, "files": copied}


class StartPreviewTool(FactoryTool):
    name = "start_preview"
    description = "Validate deploy/preview.yaml and expose its static frontend through localhost."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        manifest_path = context.workspace / "deploy" / "preview.yaml"
        compose_path = context.workspace / "deploy" / "compose.yaml"
        if not manifest_path.is_file():
            raise ToolError("deploy/preview.yaml is missing")
        if not compose_path.is_file():
            raise ToolError("deploy/compose.yaml is missing")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        expected = {
            "apiVersion": "factory.llm-wiki.dev/v1alpha1",
            "kind": "StaticPreview",
        }
        if not isinstance(manifest, dict) or any(
            manifest.get(key) != value for key, value in expected.items()
        ):
            raise ToolError("Preview manifest apiVersion or kind is invalid")
        spec = manifest.get("spec")
        if not isinstance(spec, dict):
            raise ToolError("Preview manifest spec must be an object")
        root = str(spec.get("root", ""))
        entrypoint = str(spec.get("entrypoint", ""))
        preview_root = (context.workspace / root).resolve()
        preview_entrypoint = (preview_root / entrypoint).resolve()
        workspace = context.workspace.resolve()
        if (
            not root
            or not entrypoint
            or preview_root == workspace
            or workspace not in preview_root.parents
            or preview_root not in preview_entrypoint.parents
            or not preview_entrypoint.is_file()
            or preview_entrypoint.suffix.lower() not in {".html", ".htm"}
        ):
            raise ToolError(
                "Static preview root and HTML entrypoint must exist inside the workspace"
            )
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        if not isinstance(compose, dict) or not isinstance(compose.get("services"), dict):
            raise ToolError("Compose file must declare services")
        if not compose["services"]:
            raise ToolError("Compose file must declare at least one service")
        deploy_directory = context.workspace / "deploy"
        dockerfiles = [deploy_directory / "Dockerfile", *deploy_directory.glob("*.Dockerfile")]
        if not any(path.is_file() for path in dockerfiles):
            raise ToolError("At least one deploy/Dockerfile or deploy/*.Dockerfile is required")
        return {
            "url": f"/previews/{context.session_id}/",
            "root": root,
            "entrypoint": entrypoint,
            "ready": True,
        }


class ToolRegistry:
    def __init__(self, tools: list[FactoryTool], telemetry: FactoryTelemetry | None = None) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._telemetry = telemetry or FactoryTelemetry()

    @classmethod
    def default(
        cls,
        project_root: Path | None = None,
        reusable_store: ReusableToolStore | None = None,
        telemetry: FactoryTelemetry | None = None,
        runtime_wiki_path: Path | None = None,
    ) -> ToolRegistry:
        policy = WorkspacePolicy()
        root = project_root or Path.cwd()
        store = reusable_store or ReusableToolStore(root / ".factory" / "tools")
        return cls(
            [
                ListFilesTool(policy),
                ReadFileTool(policy),
                WriteFileTool(policy),
                RunTestsTool(),
                SearchWikiTool(
                    tuple(
                        dict.fromkeys(
                            path.resolve()
                            for path in (root / "wiki", runtime_wiki_path)
                            if path is not None
                        )
                    )
                ),
                ListReusableToolsTool(store),
                ApplyReusableToolTool(store, policy),
                StartPreviewTool(),
            ],
            telemetry,
        )

    def definitions(self, names: tuple[str, ...]) -> list[dict[str, Any]]:
        return [self._require(name).definition() for name in names]

    async def execute(
        self,
        name: str,
        arguments: str | dict[str, Any],
        context: ToolContext,
    ) -> str:
        parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
        started = monotonic()
        ok = False
        with self._telemetry.span(
            "factory.tool",
            {"session.id": context.session_id, "agent.id": context.role, "tool.name": name},
        ):
            try:
                result = await self._require(name).execute(parsed, context)
                ok = True
                return json.dumps({"ok": True, "result": result})
            except (OSError, ToolError, ValueError) as error:
                return json.dumps({"ok": False, "error": str(error)})
            finally:
                duration_ms = round((monotonic() - started) * 1000)
                self._telemetry.tool_completed(context.role, name, duration_ms, ok)

    def _require(self, name: str) -> FactoryTool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise ToolError(f"Unknown tool: {name}") from error
