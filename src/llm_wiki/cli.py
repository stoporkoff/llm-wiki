import argparse
import json
from pathlib import Path

from llm_wiki.extractors import extract_text
from llm_wiki.workspace import WikiWorkspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-wiki", description="Deterministic utilities for an agent-maintained file wiki."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Wiki workspace root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Create a new wiki workspace")

    register = subparsers.add_parser("register", help="Copy an immutable source into raw/")
    register.add_argument("path", type=Path)

    extract = subparsers.add_parser("extract", help="Extract text with deterministic converters")
    extract.add_argument("path", type=Path)
    extract.add_argument("--output", type=Path)

    search = subparsers.add_parser("search", help="Search compiled Markdown pages")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)

    log = subparsers.add_parser("log", help="Append an operation to wiki/log.md")
    log.add_argument("operation", choices=["ingest", "query", "lint", "refresh"])
    log.add_argument("message")

    subparsers.add_parser("index", help="Rebuild wiki/index.md")
    subparsers.add_parser("graph", help="Rebuild graph/graph.json from wikilinks")
    subparsers.add_parser("lint", help="Validate workspace invariants")
    subparsers.add_parser("status", help="Print workspace state as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    workspace = WikiWorkspace(arguments.root.resolve())
    if arguments.command == "init":
        workspace.initialize()
        result: object = {"status": "initialized", "root": str(workspace.root)}
    elif arguments.command == "register":
        result = workspace.register_source(arguments.path.resolve())
    elif arguments.command == "extract":
        extracted = extract_text(arguments.path.resolve())
        if arguments.output is None:
            print(extracted)
            return 0
        output = arguments.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(extracted, encoding="utf-8")
        result = {"path": str(output), "characters": len(extracted)}
    elif arguments.command == "search":
        result = workspace.search(arguments.query, arguments.limit)
    elif arguments.command == "log":
        workspace.append_log(arguments.operation, arguments.message)
        result = {"status": "logged"}
    elif arguments.command == "index":
        result = workspace.rebuild_index()
    elif arguments.command == "graph":
        result = workspace.rebuild_graph()
    elif arguments.command == "lint":
        issues = workspace.lint()
        print(json.dumps({"issues": issues, "count": len(issues)}, indent=2))
        return 1 if issues else 0
    else:
        result = workspace.status()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
