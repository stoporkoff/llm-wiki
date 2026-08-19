# Skill Routing

Select skills from the list exposed by the host. Do not scan unrelated directories or assume that
a skill exists merely because it is named in an example.

## Selection order

1. Honor skills explicitly named by the user when they apply to the source operation.
2. Match source type and requested operation against skill descriptions.
3. Select the smallest set that covers every required capability.
4. Read each selected `SKILL.md` completely before processing the source.
5. Let specialist skills parse or transform their formats; keep evidence integration under the
   `llm-wiki` workflow.

Do not select two skills with the same role unless one demonstrably handles a missing capability.
Do not load review, generation, deployment, or publishing skills for ordinary source ingestion.

## Capability signals

| Source or request | Bundled match | Capability to select |
|---|---|---|
| PDF | `$wiki-pdf-source` | PDF reading, scan detection, and page-aware extraction |
| DOCX or rich text | `$wiki-office-source` | Document reading with structure preservation |
| XLSX, CSV, or tabular data | `$wiki-tabular-source` | Sheet, row, column, and cell preservation |
| PPTX | `$wiki-office-source` | Presentation reading and slide structure |
| Existing image | None | Image understanding or OCR, never image generation alone |
| Audio or video | None | Transcription and timestamp preservation |
| Source-code tree | None | Codebase navigation and repository-aware reading |
| Archive | None | Safe archive inspection before extracting members |
| Mixed batch | Matching adapters | One specialist per distinct capability, reused across files |

Plain UTF-8 Markdown, text, JSON, XML, YAML, CSV, and TSV normally need no additional skill unless
the user requests domain-specific analysis.

## Boundaries

- A specialist skill may produce temporary extracted text under `.llm-wiki/cache/`; it must not
  edit the registered raw source.
- Preserve page, slide, sheet, cell, timestamp, path, or line locations whenever the format offers
  them.
- Treat a specialist's summary as an intermediate artifact, not evidence. Cite the registered raw
  source location in final wiki pages.
- If a selected skill requires an unavailable tool or permission, use a supported deterministic
  fallback or report that source as unprocessed. Do not silently degrade provenance.
- Never install another skill, connect an external service, or send a source off-machine without
  explicit user authorization.

## Adapter handoff

Each adapter returns four items to the parent workflow: the temporary extraction path, a mapping to
source locations, extraction warnings, and a success or partial-failure status. The parent
`llm-wiki` skill remains responsible for semantic reconciliation and every write under `wiki/`.
