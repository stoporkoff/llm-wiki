# Ingest Workflow

1. Locate the workspace. If `.llm-wiki/state.json` is absent, run `llm-wiki init`.
2. Select the minimum relevant installed file skills based on source types. Use them to inspect
   content without modifying the originals.
3. Register each source with `llm-wiki register <path>`. Work from the registered `raw/` copy.
   If no relevant file skill exists, `llm-wiki extract <raw-path> --output <temporary-path>` is the
   fallback for a supported format.
4. Read `.llm-wiki/schema.md`, `wiki/index.md`, `wiki/overview.md`, and existing pages matching the
   source's likely entities and concepts.
5. Create or update the source page with stable evidence anchors and exact raw locations.
6. Update affected entity and concept pages. Reconcile aliases and compare claims with existing
   evidence. Flag contradictions and superseded claims explicitly.
7. Update `wiki/overview.md` only when the source materially changes the global synthesis.
8. Run `llm-wiki index`, `llm-wiki graph`, and `llm-wiki lint`.
9. Repair deterministic issues introduced by this ingest. Do not rewrite unrelated pages.
10. Append a concise ingest entry with `llm-wiki log ingest "<source and pages changed>"`.

For batch ingestion, process sources one at a time so provenance, failures, and page mutations stay
reviewable. A single source should update every genuinely affected page, but must not create pages
for incidental names with no durable value.
