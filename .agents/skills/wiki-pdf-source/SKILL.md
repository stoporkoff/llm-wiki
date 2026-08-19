---
name: wiki-pdf-source
description: Extract and verify PDF sources for an evidence-linked file wiki with page-level provenance. Use when llm-wiki ingests, refreshes, or audits PDF files, including detecting scanned pages that require OCR. Do not use for creating, editing, signing, or visually redesigning PDFs.
---

# Wiki PDF Source

Extract PDF evidence without changing the registered raw source. This is a source adapter for the
`llm-wiki` workflow, not an independent wiki compiler.

## Procedure

1. Confirm that `llm-wiki` registered the source under `raw/` before extraction.
2. Run the deterministic extractor:

   ```text
   docker run --rm --volume "<workspace>:/workspace" llm-wiki:local --root /workspace extract <raw-path> --output .llm-wiki/cache/<source-id>.md
   ```

3. Verify that extracted text retains `## Page N` boundaries.
4. Compare suspiciously empty pages with the PDF page count. Treat them as possible scans, not as
   empty evidence.
5. Return the cache path, page mapping, warnings, and extraction status to `llm-wiki`.

## Boundaries

- Never edit, replace, optimize, or annotate the raw PDF.
- Never invent text for unreadable pages.
- Do not turn extracted text directly into final wiki pages.
- Cite the registered PDF and page number, never the cache file, as evidence.
- If OCR is required and no OCR capability is available, report the affected pages as unprocessed.
