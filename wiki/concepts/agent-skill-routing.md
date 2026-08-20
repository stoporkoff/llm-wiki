---
id: "concept:agent-skill-routing"
type: "concept"
title: "Agent skill routing"
status: "active"
sources: ["sources/8d30919d7507-architecture"]
updated: "2026-08-19T07:40:02Z"
---

# Agent skill routing

- A repository-scoped agent skill owns the knowledge compilation workflow.
  [[sources/8d30919d7507-architecture#evidence-002]]
- The workflow selects specialized file skills only when the source format requires them and loads
  only relevant instructions. [[sources/8d30919d7507-architecture#evidence-002]]

## Relationships

- The workflow compiles the [[concepts/file-first-knowledge-store]].
- Compilation must preserve [[concepts/evidence-linked-answers]].
