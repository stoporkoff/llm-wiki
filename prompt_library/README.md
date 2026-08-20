# General Agent Prompt Library

These English Markdown prompts are designed as starting evidence for the factory wiki. Upload them
through the Prompt Knowledge form, then create paired sessions to observe how prompt versions,
tokens, tools, latency, and delivery scores change.

They are deliberately framework-neutral. Each prompt establishes scope, evidence requirements,
tool discipline, completion criteria, and fail-closed reporting. Adapt project constraints in a
new version rather than silently editing a prompt used by previous comparison runs.

| File | Role |
| --- | --- |
| `requirements-analyst.md` | Scope and measurable outcomes |
| `team-lead.md` | Decomposition and coordination |
| `frontend-engineer.md` | Accessible browser delivery |
| `backend-engineer.md` | Typed API and application logic |
| `database-engineer.md` | Durable data design |
| `infrastructure-engineer.md` | Docker and local operations |
| `qa-engineer.md` | Executable verification |
| `security-engineer.md` | Defensive review and threat analysis |

Never put secrets, customer data, credentials, or private keys in prompt files.
