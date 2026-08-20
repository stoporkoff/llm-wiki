# Prompt Source Ingestion

The UI accepts UTF-8 `.md`, `.markdown`, and `.txt` files up to 2 MB. This path is intended for
English role prompts, operating instructions, and project constraints.

```mermaid
sequenceDiagram
  actor User
  participant UI
  participant API
  participant Ingest as PromptWikiIngestionService
  participant Raw as Immutable raw store
  participant Wiki as Evidence wiki
  User->>UI: Select prompt.md
  UI->>API: multipart upload
  API->>Ingest: filename + bytes
  Ingest->>Raw: Content-addressed registration
  Ingest->>Wiki: Source page + stable evidence anchors
  Ingest->>Wiki: Rebuild index and graph; lint; log
  Ingest-->>UI: Source, page, digest, evidence count
```

The service preserves the exact upload under the runtime wiki's `raw/` directory, keyed by SHA-256.
It generates one source page containing stable paragraph-level evidence anchors and raw locations.
It does not invent concepts or claims. Requirements and architecture agents can immediately find
the source through their `search_wiki` tool.

The runtime wiki is stored in the `factory-data` Docker volume at `/data/knowledge`. Repository wiki
pages and runtime prompt pages are searched together. Only OpenAI is used for LLM inference;
registration, anchoring, indexing, graph generation, linting, storage, and observability are local.

## Current Boundary

Semantic entity/concept extraction is intentionally not performed during upload. A future
enrichment stage can use an OpenAI agent to propose affected pages, but deterministic provenance,
lint, and review must remain mandatory before committing those pages.
