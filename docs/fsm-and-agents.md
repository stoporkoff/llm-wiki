# FSM and Agent Network

```mermaid
stateDiagram-v2
  [*] --> created
  created --> discovery
  discovery --> planning
  planning --> implementing
  implementing --> releasing
  releasing --> testing
  testing --> reviewing
  reviewing --> packaging
  packaging --> previewing
  previewing --> completed
  created --> failed
  discovery --> failed
  planning --> failed
  implementing --> failed
  releasing --> failed
  testing --> failed
  reviewing --> failed
  packaging --> failed
  previewing --> failed
  completed --> [*]
  failed --> [*]
```

Every transition is persisted before work begins. Exceptions move the current non-terminal state
to `failed`; no stage is silently skipped and no failed session publishes a trusted tool.

| State | Agent topology | Gate |
| --- | --- | --- |
| discovery | Requirements Analyst | Testable scope and acceptance criteria |
| planning | Architect then Team Lead | Valid plan with supported roles |
| implementing | Selected developers in parallel | Owned artifacts and reports |
| releasing | Infrastructure Engineer | Docker and preview manifests |
| testing | QA and Security in parallel | Test evidence and no critical finding |
| reviewing | Delivery Reviewer | Verdict begins with `APPROVED` |
| packaging | Tool Curator | Strict reuse contract |
| previewing | Release Manager | Verified localhost preview URL |

## Manager Pattern

```mermaid
flowchart TB
  O[Orchestrator / manager] --> RA[Requirements Analyst]
  O --> SA[Solution Architect]
  O --> TL[Team Lead]
  O --> FE[Frontend Developer]
  O --> BE[Backend Developer]
  O --> DBA[Database Engineer]
  O --> IE[Infrastructure Engineer]
  O --> QA[QA Engineer]
  O --> SR[Security Reviewer]
  O --> DR[Delivery Reviewer]
  O --> TC[Tool Curator]
  O --> RM[Release Manager]
```

Agents do not hand control to one another. The orchestrator retains state, composition, failure
semantics, and the final result while specialists keep focused context and tools.

## Prompt Contract

```mermaid
flowchart LR
  Frontmatter[Frontmatter metadata] --> Spec[AgentSpec]
  Body[Versioned English instructions] --> Spec
  Spec --> Allowlist[Tool allowlist]
  Spec --> Gateway[Responses API request]
  Spec --> Hash[Prompt version hash]
  Hash --> Events[Session event]
```

Prompts are repository-owned configuration. Completed agent events record a content hash so quality
and cost can be compared by prompt version without exporting prompt contents as telemetry.

## Adding an Agent

1. Create `agent_specs/<role>.md` with YAML frontmatter and English instructions.
2. Grant only the tools required by that role.
3. Assign it to a stage or the Team Lead supported-role parser.
4. Define its write root in `WorkspacePolicy` if it mutates files.
5. Add a deterministic fake response to the orchestration test.
6. Add representative eval cases before changing production prompt behavior.
