---
name: wiki-office-source
description: Extract structured DOCX and PPTX sources for an evidence-linked file wiki. Use when llm-wiki ingests, refreshes, or audits Word documents or PowerPoint presentations and must preserve headings, paragraphs, tables, slide numbers, and speaker notes when available. Do not use for authoring or editing Office files.
---

# Wiki Office Source

Extract Office document evidence while preserving the locations needed for later citations. This
skill supplies structured source text to `llm-wiki`; it does not compile wiki knowledge itself.

## Procedure

1. Confirm that `llm-wiki` registered the source under `raw/` before extraction.
2. Run the deterministic extractor:

   ```text
   docker run --rm --volume "<workspace>:/workspace" llm-wiki:local --root /workspace extract <raw-path> --output .llm-wiki/cache/<source-id>.md
   ```

3. For DOCX, preserve heading order, paragraph order, and table boundaries.
4. For PPTX, preserve `## Slide N` boundaries and distinguish slide text from notes when possible.
5. Return the cache path, structural mapping, warnings, and extraction status to `llm-wiki`.

## Boundaries

- Never modify the registered DOCX or PPTX file.
- Never flatten away available heading, table, or slide locations.
- Do not treat document metadata or generated summaries as factual evidence.
- Do not write final source, entity, concept, or synthesis pages.
- Cite the registered source and its structural location, never the cache file.
