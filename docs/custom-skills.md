# Custom Source Skills

LLM Wiki uses small repository-scoped skills as file adapters. Codex discovers them from
`.agents/skills/`, initially reads only each skill's `name` and `description`, and loads the full
`SKILL.md` only when the description matches the active task.

## Included adapters

| Skill | Inputs | Responsibility |
|---|---|---|
| `$wiki-pdf-source` | PDF | Page-aware extraction and scan detection |
| `$wiki-office-source` | DOCX, PPTX | Document and slide structure preservation |
| `$wiki-tabular-source` | XLSX, CSV, TSV | Sheet, row, column, and cell provenance |

The parent `$llm-wiki` skill registers sources, chooses adapters, reconciles evidence, updates wiki
pages, runs lint, and writes the operation log. Adapters must not mutate the wiki or raw sources.

## Create a skill with Codex

Invoke the built-in skill creator and specify the repository destination:

```text
$skill-creator Create a repo-scoped skill at .agents/skills/wiki-audio-source. It must extract
audio and video for llm-wiki, preserve timestamps and speaker labels, avoid editing wiki pages,
and allow implicit invocation.
```

Restart Codex if the new skill does not appear after automatic discovery.

## Create a skill manually

Create `.agents/skills/<skill-name>/SKILL.md`:

```markdown
---
name: wiki-audio-source
description: Extract audio and video sources for an evidence-linked file wiki with timestamp and speaker provenance. Use when llm-wiki ingests, refreshes, or audits recordings. Do not use for media editing or unrelated transcription.
---

# Wiki Audio Source

## Procedure

1. Confirm that llm-wiki registered the source.
2. Extract a timestamped transcript into `.llm-wiki/cache/`.
3. Return the cache path, timestamp mapping, warnings, and status to llm-wiki.

## Boundaries

- Never modify the raw source.
- Never write final wiki pages.
- Never cite the cache file as evidence.
```

Optionally add `agents/openai.yaml`:

```yaml
interface:
  display_name: "Wiki Audio Source"
  short_description: "Extract recordings with timestamp provenance"
  default_prompt: "Use $wiki-audio-source to extract this recording for the wiki."

policy:
  allow_implicit_invocation: true
```

The directory name and frontmatter `name` must match. Use lowercase letters, digits, and hyphens.
Make the description state the supported inputs, exact operation, trigger conditions, and explicit
non-goals. Keep detailed procedures in the body so they consume context only after selection.

## Routing contract

Every source adapter must:

1. Accept a registered immutable source under `raw/`.
2. Write only temporary extraction artifacts under `.llm-wiki/cache/`.
3. Preserve the finest practical provenance location.
4. Return output path, location mapping, warnings, and status.
5. Leave all semantic and wiki mutations to `$llm-wiki`.

This separation prevents two skills from updating the same page and makes adapter replacement safe.

## Verify selection

Test explicit invocation first:

```text
$wiki-pdf-source Extract raw/<registered-pdf> and report page-level warnings.
```

Then test implicit routing through the parent:

```text
Use the wiki to ingest report.pdf and preserve page citations.
```

Codex should select `$llm-wiki` for the overall operation and `$wiki-pdf-source` for extraction.
If it selects the wrong adapter, narrow overlapping descriptions instead of adding routing logic to
prompts.

See the official [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills) for the
current discovery model and metadata fields.
