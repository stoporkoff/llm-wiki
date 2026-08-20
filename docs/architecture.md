# Software Factory Architecture

## Purpose

The Software Factory turns a user goal into locally runnable software through an explicit,
observable finite-state workflow. A manager-style orchestrator retains control while specialist
agents receive narrow prompts and tools. Approved outputs are evaluated and packaged as reusable
templates for later sessions. The file wiki remains an evidence source, not the workflow engine.

## System Context

```mermaid
C4Context
  title Local Software Factory
  Person(user, "User", "Defines an outcome and reviews execution evidence")
  System(factory, "Software Factory", "Plans, builds, verifies, scores, and packages software")
  System_Ext(openai, "OpenAI Responses API", "Reasoning and tool selection")
  System_Ext(observability, "Local Observability", "Jaeger traces and Grafana metrics")
  System_Ext(wiki, "File Wiki", "Evidence-backed constraints and decisions")
  Rel(user, factory, "Creates and monitors sessions", "HTTP")
  Rel(factory, openai, "Runs bounded agents", "HTTPS")
  Rel(factory, wiki, "Searches", "read-only tool")
  Rel(factory, observability, "Exports OTLP", "HTTP")
```

## Container View

```mermaid
flowchart LR
  Browser[Browser UI] --> API[FastAPI application]
  API --> Orchestrator[SoftwareFactoryOrchestrator]
  Orchestrator --> FSM[WorkflowStateMachine]
  Orchestrator --> Pipeline[StagePipeline]
  Pipeline --> Gateway[OpenAIResponsesAgentGateway]
  Gateway --> OpenAI[OpenAI Responses API]
  Gateway --> Registry[ToolRegistry]
  Registry --> Workspace[(Session workspace)]
  Registry --> Wiki[(Markdown wiki)]
  Registry --> Tools[(Reusable tool store)]
  Orchestrator --> SQLite[(SQLite sessions and events)]
  API -. OTLP .-> Collector[OpenTelemetry Collector]
  Collector --> Jaeger[Jaeger v2]
  Collector --> Prometheus[Prometheus]
  Prometheus --> Grafana[Grafana]
```

## Runtime Components

| Component | Responsibility | Must not do |
| --- | --- | --- |
| FastAPI | Validate HTTP input and expose session state | Contain workflow policy |
| Orchestrator | Own lifecycle, events, gates, and failures | Implement specialist work |
| FSM | Enforce legal transitions | Infer or skip stages |
| Stage | Coordinate one bounded phase | Access OpenAI directly |
| Agent gateway | Run Responses API tool loops | Grant undeclared tools |
| Tool registry | Validate and execute tool contracts | Allow path escape or secrets |
| Agent spec | Declare role, prompt, and tool allowlist | Own durable state |
| Repository | Persist deterministic state and events | Store API credentials |
| Tool store | Publish and apply evaluated templates | Trust unscored output |

## Dependency Direction

```mermaid
classDiagram
  class SoftwareFactoryOrchestrator
  class SessionRepository { <<protocol>> }
  class AgentGateway { <<protocol>> }
  class StagePipeline
  class WorkflowStage { <<abstract>> }
  class WorkflowStateMachine
  class DeliveryScorer
  class ReusableToolStore
  SoftwareFactoryOrchestrator --> SessionRepository
  SoftwareFactoryOrchestrator --> AgentGateway
  SoftwareFactoryOrchestrator --> StagePipeline
  SoftwareFactoryOrchestrator --> WorkflowStateMachine
  SoftwareFactoryOrchestrator --> DeliveryScorer
  SoftwareFactoryOrchestrator --> ReusableToolStore
  StagePipeline *-- WorkflowStage
```

Domain policy depends on protocols. Infrastructure implements them. The orchestrator is testable
with a deterministic fake gateway, so the HTTP and OpenAI SDKs do not become the architecture.

## End-to-End Sequence

```mermaid
sequenceDiagram
  autonumber
  actor User
  participant UI
  participant API
  participant O as Orchestrator
  participant A as Stage Agents
  participant T as Tool Registry
  participant R as Repository
  participant P as Tool Publisher
  User->>UI: Enter delivery goal
  UI->>API: POST /api/sessions
  API->>R: Create session
  API-->>UI: 202 + session id
  API->>O: Run asynchronously
  loop Every FSM stage
    O->>R: Persist state and stage event
    O->>A: Invoke bounded agent(s)
    A->>T: Use allowlisted tools
    T-->>A: Structured result
    A-->>O: Stage output
  end
  O->>P: Score and package approved artifacts
  P-->>O: Candidate or trusted manifest
  O->>R: Persist final result
  UI->>API: Poll state, events, files
  API-->>UI: Execution evidence
```

## Concurrency Model

```mermaid
flowchart TD
  D[Discovery] --> A[Architecture]
  A --> P[Team Lead plan]
  P --> F{Selected specialists}
  F -->|parallel| FE[Frontend Developer]
  F -->|parallel| BE[Backend Developer]
  F -->|parallel| DB[Database Engineer]
  FE --> I[Infrastructure Engineer]
  BE --> I
  DB --> I
  I --> V[Verification barrier]
  V -->|parallel| QA[QA Engineer]
  V -->|parallel| SEC[Security Reviewer]
  QA --> R[Final Reviewer]
  SEC --> R
  R --> TC[Tool Curator]
  TC --> LP[Local preview gate]
  LP --> S[Scoring and packaging]
```

Concurrency is allowed only inside a stage. The next state starts after an explicit barrier. Role
ownership prevents concurrent writers from modifying the same top-level path.

## Trust Boundaries

```mermaid
flowchart LR
  subgraph Untrusted
    Goal[User text]
    Model[Model output]
    Generated[Generated files]
  end
  subgraph Enforced
    Schema[Strict tool schemas]
    Policy[WorkspacePolicy]
    Gates[FSM gates]
    Scores[Scorecard and hard gates]
  end
  subgraph Trusted
    Manifest[Trusted tool manifest]
  end
  Goal --> Model --> Schema --> Policy --> Generated --> Gates --> Scores --> Manifest
```

Model output is never trusted merely because it is well formatted. Tool inputs are schema-bound,
paths stay beneath a session workspace, sensitive names are blocked, writers have role ownership,
reviewers fail closed, and reusable status requires deterministic hard gates. Verification is also
machine-gated: QA and Security must emit explicit pass verdicts as their first non-empty lines. A
blocked or missing verdict enters a bounded remediation loop before final review. The loop sends
both reports to the implementation roles selected by the original plan, refreshes the release
contract, and reruns verification. It fails closed after two unsuccessful repair attempts.

For JavaScript frontends, runtime verification rejects floating `latest` versions, preserves a
generated lockfile when needed, installs with `npm ci --ignore-scripts`, and removes only transient
`node_modules` after execution. The same lockfile is reused by the preview build.

## Persistence

```mermaid
erDiagram
  SESSION ||--o{ EVENT : emits
  SESSION ||--|| WORKSPACE : owns
  SESSION ||--o| TOOL_VERSION : produces
  TOOL ||--o{ TOOL_VERSION : versions
  TOOL_VERSION ||--|| SCORECARD : has
  SESSION { string id PK string goal string state json result string error }
  EVENT { int id PK string kind string actor json payload datetime created_at }
  TOOL_VERSION { string version string status string source_session_id json contract }
```

SQLite is the PoC control-plane store. Files remain in isolated session workspaces. Published
templates live under `.factory/tools/<tool-id>/<version>/` with immutable provenance.

New roles require an English Markdown specification, narrow tool allowlist, and explicit stage.
New tools subclass `FactoryTool` and publish strict JSON schemas. New stages subclass
`WorkflowStage` and declare state, mode, agents, and gate.
