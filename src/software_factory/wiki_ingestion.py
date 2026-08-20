from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any

import yaml

from llm_wiki.workspace import WikiWorkspace, utc_timestamp


class PromptWikiIngestionService:
    _allowed_suffixes = {".md", ".markdown", ".txt"}

    def __init__(self, root: Path) -> None:
        self._workspace = WikiWorkspace(root)
        self._lock = RLock()
        self._workspace.initialize()

    def ingest(self, filename: str, content: bytes) -> dict[str, Any]:
        with self._lock:
            return self._ingest(filename, content)

    def _ingest(self, filename: str, content: bytes) -> dict[str, Any]:
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.casefold()
        if suffix not in self._allowed_suffixes:
            raise ValueError("Only Markdown and plain-text prompt files are supported")
        if not content or len(content) > 2_000_000:
            raise ValueError("Prompt file must contain between 1 byte and 2 MB")
        text = content.decode("utf-8")
        digest = sha256(content).hexdigest()
        upload = self._workspace.root / ".llm-wiki" / "cache" / "uploads" / safe_name
        upload.parent.mkdir(parents=True, exist_ok=True)
        upload.write_bytes(content)
        try:
            registration = self._workspace.register_source(upload)
        finally:
            upload.unlink(missing_ok=True)

        raw_path = str(registration["path"])
        page_relative = f"sources/{digest[:12]}-prompt"
        page_path = self._workspace.wiki_path / f"{page_relative}.md"
        title = self._title(text, Path(safe_name).stem)
        evidence = self._evidence_blocks(text)
        metadata = {
            "id": f"source:{digest[:12]}-prompt",
            "type": "source",
            "title": title,
            "status": "active",
            "sources": [],
            "updated": utc_timestamp(),
            "sha256": digest,
            "source_kind": "agent-prompt",
        }
        lines = ["---", yaml.safe_dump(metadata, sort_keys=False).strip(), "---", "", f"# {title}"]
        lines.extend(("", "## Source", "", f"Immutable prompt source: `{raw_path}`"))
        for evidence_index, block in enumerate(evidence, start=1):
            anchor = f"evidence-{evidence_index:03d}"
            lines.extend(
                (
                    "",
                    f'<a id="{anchor}"></a>',
                    f"### Evidence {evidence_index:03d}",
                    "",
                    *[f"> {line}" if line else ">" for line in block.splitlines()],
                    "",
                    f"Raw location: `{raw_path}`, block {evidence_index}",
                )
            )
        page_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        index_counts = self._workspace.rebuild_index()
        graph = self._workspace.rebuild_graph()
        issues = self._workspace.lint()
        self._workspace.append_log("ingest", f"{safe_name} -> {page_relative}")
        return {
            "status": registration["status"],
            "source": raw_path,
            "page": f"wiki/{page_relative}.md",
            "sha256": digest,
            "evidence_blocks": len(evidence),
            "index": index_counts,
            "graph": graph,
            "lint_issues": issues,
        }

    def status(self) -> dict[str, object]:
        status = self._workspace.status()
        digest = sha256()
        for path in sorted(self._workspace.wiki_path.rglob("*.md")):
            digest.update(path.relative_to(self._workspace.root).as_posix().encode())
            digest.update(path.read_bytes())
        status["revision"] = digest.hexdigest()[:16]
        return status

    @staticmethod
    def _evidence_blocks(text: str) -> list[str]:
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        return blocks[:500]

    @staticmethod
    def _title(text: str, fallback: str) -> str:
        heading = next(
            (line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")),
            "",
        )
        return heading or fallback.replace("-", " ").replace("_", " ").title()
