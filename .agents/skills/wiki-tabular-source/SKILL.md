---
name: wiki-tabular-source
description: Extract XLSX, CSV, and TSV sources for an evidence-linked file wiki with sheet, row, column, and cell provenance. Use when llm-wiki ingests, refreshes, or audits tabular files and must preserve table structure or distinguish formulas from stored values. Do not use for unrelated analytics or spreadsheet editing.
---

# Wiki Tabular Source

Extract tabular evidence into a reviewable intermediate representation. Keep semantic integration
and all wiki mutations under the `llm-wiki` workflow.

## Procedure

1. Confirm that `llm-wiki` registered the source under `raw/` before extraction.
2. Run the deterministic extractor:

   ```text
   docker run --rm --volume "<workspace>:/workspace" llm-wiki:local --root /workspace extract <raw-path> --output .llm-wiki/cache/<source-id>.md
   ```

3. Preserve sheet names for XLSX and header order for every supported format.
4. Preserve row numbers and cell or column locations needed to verify claims.
5. Flag formula cells when stored values may be stale or unavailable.
6. Return the cache path, range mapping, warnings, and extraction status to `llm-wiki`.

## Boundaries

- Never edit the registered workbook or delimited file.
- Never silently reinterpret identifiers, dates, units, empty cells, or formulas.
- Do not aggregate or infer facts unless the parent `llm-wiki` task requests it.
- Do not write final wiki pages.
- Cite the registered source and sheet or range, never the cache file.
