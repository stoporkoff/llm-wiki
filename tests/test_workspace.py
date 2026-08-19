import json
from pathlib import Path

from llm_wiki.extractors import extract_text
from llm_wiki.workspace import WikiWorkspace


def page(title: str, links: str = "") -> str:
    return (
        "---\n"
        'id: "concept:test"\n'
        'type: "concept"\n'
        f'title: "{title}"\n'
        'status: "active"\n'
        "sources: []\n"
        'updated: "2026-08-18T00:00:00Z"\n'
        "---\n\n"
        f"# {title}\n\n{links}\n"
    )


def test_initialize_creates_file_workspace(tmp_path: Path) -> None:
    workspace = WikiWorkspace(tmp_path)
    workspace.initialize()
    assert (tmp_path / "wiki/index.md").exists()
    assert (tmp_path / ".llm-wiki/state.json").exists()


def test_register_source_is_content_addressed(tmp_path: Path) -> None:
    workspace = WikiWorkspace(tmp_path)
    workspace.initialize()
    source = tmp_path / "outside.md"
    source.write_text("Evidence", encoding="utf-8")
    first = workspace.register_source(source)
    second = workspace.register_source(source)
    assert first["status"] == "registered"
    assert second["status"] == "unchanged"


def test_lint_detects_broken_wikilink(tmp_path: Path) -> None:
    workspace = WikiWorkspace(tmp_path)
    workspace.initialize()
    target = tmp_path / "wiki/concepts/example.md"
    target.write_text(page("Example", "See [[entities/missing]]."), encoding="utf-8")
    issues = workspace.lint()
    assert any(issue["code"] == "broken-wikilink" for issue in issues)


def test_index_and_graph_are_deterministic(tmp_path: Path) -> None:
    workspace = WikiWorkspace(tmp_path)
    workspace.initialize()
    entity = tmp_path / "wiki/entities/database.md"
    concept = tmp_path / "wiki/concepts/storage.md"
    entity.write_text(page("Database"), encoding="utf-8")
    concept.write_text(page("Storage", "Uses [[entities/database]]."), encoding="utf-8")
    counts = workspace.rebuild_index()
    graph = workspace.rebuild_graph()
    payload = json.loads((tmp_path / "graph/graph.json").read_text(encoding="utf-8"))
    assert counts["entities"] == 1
    assert graph == {"nodes": 2, "edges": 1}
    assert payload["edges"][0]["target"] == "entities/database"


def test_plain_text_extraction_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Evidence\n", encoding="utf-8")
    assert extract_text(source) == "Evidence"
