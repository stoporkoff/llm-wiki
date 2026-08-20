---
id: "source:8d30919d7507-architecture"
type: "source"
title: "Architecture decision: primary knowledge store"
status: "active"
sources: []
updated: "2026-08-19T07:40:02Z"
---

# Architecture decision: primary knowledge store

This source defines the initial storage, compilation, routing, and evidence rules for the project.

## Evidence

<a id="evidence-001"></a>
### Evidence 001

> The team selected a file-based Markdown workspace as the primary knowledge store.

Raw location: `raw/8d30919d7507-architecture.md`, lines 3–4

<a id="evidence-002"></a>
### Evidence 002

> The repository-scoped agent skill owns the compilation workflow.

Raw location: `raw/8d30919d7507-architecture.md`, lines 6–8

<a id="evidence-003"></a>
### Evidence 003

> Every extracted claim must retain an exact source location. Answers must cite the evidence used.

Raw location: `raw/8d30919d7507-architecture.md`, line 10

<a id="evidence-004"></a>
### Evidence 004

> If the available evidence does not support an answer, the agent must say that it does not know.

Raw location: `raw/8d30919d7507-architecture.md`, line 11

## Related knowledge

- [[concepts/file-first-knowledge-store]]
- [[concepts/agent-skill-routing]]
- [[concepts/evidence-linked-answers]]
