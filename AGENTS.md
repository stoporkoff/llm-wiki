# Repository Instructions

Use the repository-scoped `llm-wiki` skill for requests that ingest sources, maintain the wiki,
query accumulated knowledge, inspect contradictions, or lint the knowledge base.

For non-text ingestion, let `llm-wiki` select the smallest matching repository source adapter.
Adapters may write temporary extraction output under `.llm-wiki/cache/`; only `llm-wiki` may write
knowledge under `wiki/`.

Treat `raw/` as immutable. Store agent-maintained knowledge only under `wiki/`, deterministic
state under `.llm-wiki/`, and generated graph data under `graph/`.

All repository content, generated pages, metadata, logs, and user-facing documentation must be
written in English.
