# Query Workflow

1. Read `wiki/index.md` and search compiled pages with `llm-wiki search "<question>"`.
2. Read the most relevant entity, concept, synthesis, and source pages. Follow useful wikilinks.
3. Verify important claims against source-page evidence blocks and raw locations when necessary.
4. Answer from accumulated knowledge. Cite wiki source anchors beside factual statements.
5. State conflicts, uncertainty, missing evidence, and freshness limitations directly.
6. Offer to save only a synthesis that is likely to be reused. Do not file routine answers.
7. When saving, follow the page schema, link all supporting pages, rebuild index and graph, lint,
   and append a `query` log entry.

Search raw files only when the compiled wiki lacks enough evidence or when verifying a disputed
claim. Do not silently turn a retrieval result into a fact.
