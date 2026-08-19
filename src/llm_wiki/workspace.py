from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PAGE_DIRECTORIES = ("sources", "entities", "concepts", "syntheses")
REQUIRED_PAGE_FIELDS = {"id", "type", "title", "status", "sources", "updated"}
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    result: dict[str, Any] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if value.startswith("["):
            try:
                result[key.strip()] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        result[key.strip()] = value.strip('"')
    return result


@dataclass(frozen=True)
class SearchResult:
    path: str
    title: str
    score: int
    excerpt: str


class WikiWorkspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw_path = root / "raw"
        self.wiki_path = root / "wiki"
        self.state_path = root / ".llm-wiki" / "state.json"
        self.graph_path = root / "graph" / "graph.json"

    def initialize(self) -> None:
        self.raw_path.mkdir(parents=True, exist_ok=True)
        for directory in PAGE_DIRECTORIES:
            (self.wiki_path / directory).mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._write_json(self.state_path, {"version": 1, "sources": {}})
        self._write_if_missing(
            self.wiki_path / "index.md", "# Wiki Index\n\nNo compiled pages yet.\n"
        )
        self._write_if_missing(
            self.wiki_path / "overview.md",
            "# Overview\n\nThis overview is maintained by the LLM Wiki agent.\n",
        )
        self._write_if_missing(self.wiki_path / "log.md", "# Activity Log\n")
        self._write_if_missing(
            self.root / ".llm-wiki" / "schema.md",
            "# Workspace Schema\n\nSee `.agents/skills/llm-wiki/references/page-schema.md`.\n",
        )

    def register_source(self, source_path: Path) -> dict[str, object]:
        self._require_initialized()
        if not source_path.is_file():
            raise ValueError(f"Source is not a file: {source_path}")
        digest = sha256_file(source_path)
        state = self._read_state()
        existing = state["sources"].get(digest)
        if existing:
            return {"status": "unchanged", **existing}
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", source_path.name).strip("-")
        target = self.raw_path / f"{digest[:12]}-{safe_name or 'source'}"
        if source_path != target:
            if target.exists() and sha256_file(target) != digest:
                raise RuntimeError(f"Content-addressed target collision: {target}")
            if not target.exists():
                shutil.copy2(source_path, target)
        record = {
            "path": target.relative_to(self.root).as_posix(),
            "sha256": digest,
            "size": target.stat().st_size,
            "registered_at": utc_timestamp(),
        }
        state["sources"][digest] = record
        self._write_json(self.state_path, state)
        return {"status": "registered", **record}

    def search(self, query: str, limit: int = 10) -> list[dict[str, object]]:
        self._require_initialized()
        terms = {term.casefold() for term in re.findall(r"[\w-]+", query) if len(term) > 1}
        results: list[SearchResult] = []
        for path in self._page_files():
            text = path.read_text(encoding="utf-8")
            folded = text.casefold()
            score = sum(folded.count(term) for term in terms)
            if score == 0:
                continue
            metadata = parse_frontmatter(path)
            excerpt = next(
                (
                    line.strip()
                    for line in text.splitlines()
                    if any(term in line.casefold() for term in terms)
                ),
                "",
            )
            results.append(
                SearchResult(
                    path=path.relative_to(self.root).as_posix(),
                    title=str(metadata.get("title", path.stem)),
                    score=score,
                    excerpt=excerpt[:500],
                )
            )
        results.sort(key=lambda item: (-item.score, item.path))
        return [asdict(result) for result in results[: max(1, limit)]]

    def append_log(self, operation: str, message: str) -> None:
        self._require_initialized()
        clean_message = " ".join(message.split())
        with (self.wiki_path / "log.md").open("a", encoding="utf-8", newline="\n") as log:
            log.write(f"\n## [{utc_timestamp()}] {operation} | {clean_message}\n")

    def rebuild_index(self) -> dict[str, int]:
        self._require_initialized()
        groups: dict[str, list[tuple[str, str]]] = {name: [] for name in PAGE_DIRECTORIES}
        for path in self._page_files():
            metadata = parse_frontmatter(path)
            group = path.parent.name
            relative = path.relative_to(self.wiki_path).with_suffix("").as_posix()
            groups[group].append((str(metadata.get("title", path.stem)), relative))
        lines = ["# Wiki Index", ""]
        for group, pages in groups.items():
            lines.extend((f"## {group.title()}", ""))
            lines.extend(f"- [[{relative}|{title}]]" for title, relative in sorted(pages))
            if not pages:
                lines.append("- None")
            lines.append("")
        (self.wiki_path / "index.md").write_text("\n".join(lines), encoding="utf-8")
        return {group: len(pages) for group, pages in groups.items()}

    def rebuild_graph(self) -> dict[str, int]:
        self._require_initialized()
        nodes: list[dict[str, str]] = []
        edges: list[dict[str, str]] = []
        for path in self._page_files():
            source = path.relative_to(self.wiki_path).with_suffix("").as_posix()
            metadata = parse_frontmatter(path)
            nodes.append({"id": source, "title": str(metadata.get("title", path.stem))})
            text = path.read_text(encoding="utf-8")
            for target in WIKILINK_PATTERN.findall(text):
                edges.append({"source": source, "target": target})
        self._write_json(self.graph_path, {"nodes": nodes, "edges": edges})
        return {"nodes": len(nodes), "edges": len(edges)}

    def lint(self) -> list[dict[str, str]]:
        self._require_initialized()
        issues: list[dict[str, str]] = []
        state = self._read_state()
        for digest, record in state["sources"].items():
            source_path = self.root / record["path"]
            if not source_path.exists():
                issues.append({"code": "missing-source", "path": record["path"]})
            elif sha256_file(source_path) != digest:
                issues.append({"code": "mutated-source", "path": record["path"]})
        known_pages = {
            path.relative_to(self.wiki_path).with_suffix("").as_posix()
            for path in self._page_files()
        }
        for path in self._page_files():
            relative = path.relative_to(self.root).as_posix()
            metadata = parse_frontmatter(path)
            for field in sorted(REQUIRED_PAGE_FIELDS - metadata.keys()):
                issues.append({"code": "missing-frontmatter", "path": relative, "detail": field})
            for target in WIKILINK_PATTERN.findall(path.read_text(encoding="utf-8")):
                if target not in known_pages:
                    issues.append({"code": "broken-wikilink", "path": relative, "detail": target})
        return issues

    def status(self) -> dict[str, object]:
        self._require_initialized()
        state = self._read_state()
        pages = list(self._page_files())
        return {
            "root": str(self.root),
            "sources": len(state["sources"]),
            "pages": len(pages),
            "issues": len(self.lint()),
        }

    def _page_files(self) -> list[Path]:
        return sorted(
            path
            for directory in PAGE_DIRECTORIES
            for path in (self.wiki_path / directory).glob("*.md")
        )

    def _read_state(self) -> dict[str, Any]:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _require_initialized(self) -> None:
        if not self.state_path.exists():
            raise RuntimeError("Not an LLM Wiki workspace. Run `llm-wiki init` first.")

    @staticmethod
    def _write_if_missing(path: Path, content: str) -> None:
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
