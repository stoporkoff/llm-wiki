# Page Schema

Use UTF-8 Markdown and JSON-compatible YAML values. Every generated page begins with:

```yaml
---
id: "entity:postgresql"
type: "entity"
title: "PostgreSQL"
status: "active"
sources: ["sources/4ab12-report"]
updated: "2026-08-18T12:00:00Z"
---
```

## Page types

- `source`: one page per immutable raw source; summarize structure and durable evidence.
- `entity`: a named person, organization, product, project, place, system, or other concrete thing.
- `concept`: an idea, practice, method, theme, property, or category spanning sources.
- `synthesis`: a reusable answer, comparison, timeline, or analysis derived from multiple pages.

Use stable lowercase ASCII slugs. Merge aliases into one canonical page and list aliases in the
body when useful. Never encode lifecycle state only in prose.

## Evidence

Write atomic claims as bullets. End each factual bullet with one or more direct citations:

```markdown
- PostgreSQL is the primary transactional store. [[sources/4ab12-report#evidence-003]]
```

On source pages, preserve short evidence blocks with stable anchors:

```markdown
<a id="evidence-003"></a>
### Evidence 003

> A concise source excerpt or faithful extraction.

Raw location: `raw/4ab12-report.pdf`, page 12
```

Keep excerpts short. For large passages, describe the evidence and preserve an exact raw location.

## Relationships and uncertainty

Use explicit prose plus wikilinks for relationships. Label inference, ambiguity, contradiction,
and supersession rather than silently choosing one claim. Do not overwrite historical evidence;
mark the prior claim and link the newer evidence.
