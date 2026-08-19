# Architecture

LLM Wiki is a file-first, repository-scoped knowledge compiler operated by an agent. It converts
immutable source files into a persistent, evidence-linked Markdown wiki while keeping semantic
reasoning separate from deterministic file operations.

The architecture intentionally has no application server, database, vector store, or background
worker. Codex is the semantic control plane. The Python toolkit is the deterministic data plane.
The repository filesystem is the durable store.

## Architectural goals

- Compile source knowledge once and reuse it across agent sessions.
- Keep every factual claim traceable to an immutable source location.
- Route each file format through the smallest relevant specialist skill.
- Make every generated artifact readable, reviewable, and version-control friendly.
- Keep deterministic operations reproducible and independent from an LLM provider.
- Degrade visibly when extraction, evidence, or freshness is incomplete.

## System context

```mermaid
flowchart LR
    classDef person fill:#172554,stroke:#60a5fa,color:#eff6ff,stroke-width:2px
    classDef agent fill:#3b0764,stroke:#c084fc,color:#faf5ff,stroke-width:2px
    classDef skill fill:#0f3d3e,stroke:#5eead4,color:#f0fdfa,stroke-width:2px
    classDef tool fill:#422006,stroke:#fbbf24,color:#fffbeb,stroke-width:2px
    classDef store fill:#3f1d2e,stroke:#fb7185,color:#fff1f2,stroke-width:2px

    User([Human operator]):::person
    Codex[Codex agent runtime]:::agent
    Core[$llm-wiki<br/>orchestration skill]:::skill
    Adapters[Source adapter skills<br/>PDF · Office · Tabular]:::skill
    Toolkit[Python CLI<br/>inside Docker]:::tool
    Repository[(Repository filesystem<br/>raw · wiki · state · graph)]:::store

    User -->|ingest · query · review| Codex
    Codex --> Core
    Core -->|select by description| Adapters
    Core -->|deterministic commands| Toolkit
    Adapters -->|extract through CLI| Toolkit
    Toolkit <--> Repository
    Core <--> Repository
    Codex -->|cited answer or review result| User
```

## Architectural layers

```mermaid
flowchart TB
    classDef layer fill:#111827,stroke:#64748b,color:#f8fafc,stroke-width:1.5px
    classDef semantic fill:#312e81,stroke:#818cf8,color:#eef2ff,stroke-width:2px
    classDef deterministic fill:#064e3b,stroke:#34d399,color:#ecfdf5,stroke-width:2px
    classDef persistence fill:#7c2d12,stroke:#fb923c,color:#fff7ed,stroke-width:2px

    subgraph Experience[Interaction layer]
        Prompt[User request]
        Result[Cited answer or wiki change]
    end

    subgraph Control[Semantic control plane]
        Router[Skill selection]
        Workflow[Ingest · Query · Lint]
        Reconcile[Entity resolution<br/>claim reconciliation<br/>contradiction handling]
    end

    subgraph Data[Deterministic data plane]
        Register[Content-addressed registration]
        Extract[Format extraction]
        Search[Lexical search]
        Build[Index and graph builders]
        Validate[Deterministic lint]
    end

    subgraph Storage[Persistence layer]
        Raw[(raw/)]
        Wiki[(wiki/)]
        State[(.llm-wiki/)]
        Graph[(graph/)]
    end

    Prompt --> Router --> Workflow --> Reconcile --> Result
    Workflow --> Register
    Workflow --> Extract
    Workflow --> Search
    Workflow --> Build
    Workflow --> Validate
    Register --> Raw
    Register --> State
    Extract --> State
    Reconcile --> Wiki
    Search --> Wiki
    Build --> Wiki
    Build --> Graph
    Validate --> Raw
    Validate --> State
    Validate --> Wiki

    class Prompt,Result layer
    class Router,Workflow,Reconcile semantic
    class Register,Extract,Search,Build,Validate deterministic
    class Raw,Wiki,State,Graph persistence
```

### Responsibility boundaries

| Component | Owns | Must not own |
|---|---|---|
| Codex runtime | Skill discovery, instruction execution, user interaction | Durable project knowledge |
| `$llm-wiki` | Workflow choice, semantic synthesis, wiki mutations, evidence reconciliation | Format-specific parsing details |
| Source adapters | Format extraction, location mapping, extraction warnings | Entity resolution or final wiki pages |
| Python toolkit | Hashing, copying, extraction, search, index, graph, lint, status | Semantic truth or unsupported inference |
| Repository | Source records, compiled wiki, local state, generated graph | Hidden application state |
| Docker image | Reproducible Python runtime and converter dependencies | LLM credentials or long-running services |

## Skill routing

Codex first sees only skill names and descriptions. It loads the full instructions only after a
description matches the task. The core skill remains the workflow owner and delegates only source
extraction.

```mermaid
flowchart TD
    classDef decision fill:#1e293b,stroke:#94a3b8,color:#f8fafc,stroke-width:2px
    classDef selected fill:#064e3b,stroke:#34d399,color:#ecfdf5,stroke-width:2px
    classDef fallback fill:#78350f,stroke:#fbbf24,color:#fffbeb,stroke-width:2px
    classDef stop fill:#7f1d1d,stroke:#f87171,color:#fef2f2,stroke-width:2px

    Start([Registered source]) --> Type{Source type?}
    Type -->|PDF| PDF[$wiki-pdf-source]
    Type -->|DOCX or PPTX| Office[$wiki-office-source]
    Type -->|XLSX, CSV, or TSV| Table[$wiki-tabular-source]
    Type -->|Plain text or structured text| Direct[Core workflow reads source]
    Type -->|Other| Match{Matching installed skill?}
    Match -->|Yes| Specialist[Load smallest matching skill]
    Match -->|No| Supported{Toolkit supports format?}
    Supported -->|Yes| Fallback[Use deterministic extractor]
    Supported -->|No| Unprocessed[Report unprocessed source]

    PDF --> Handoff[Return cache path<br/>location map<br/>warnings<br/>status]
    Office --> Handoff
    Table --> Handoff
    Specialist --> Handoff
    Direct --> Compile[Compile evidence into wiki]
    Fallback --> Compile
    Handoff --> Compile

    class Type,Match,Supported decision
    class PDF,Office,Table,Specialist,Direct,Handoff,Compile selected
    class Fallback fallback
    class Unprocessed stop
```

The adapter contract prevents competing skills from editing the same page:

1. Receive a registered immutable source path.
2. Write temporary output only under `.llm-wiki/cache/`.
3. Preserve page, slide, sheet, cell, timestamp, path, or line provenance.
4. Return the output path, location mapping, warnings, and completion status.
5. Leave all semantic decisions and wiki writes to `$llm-wiki`.

## Ingestion lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Agent as Codex + $llm-wiki
    participant CLI as Python toolkit
    participant Adapter as Source adapter
    participant FS as Repository filesystem

    User->>Agent: Ingest source file
    Agent->>CLI: init, when state is absent
    CLI->>FS: Create workspace structure
    Agent->>CLI: register source
    CLI->>CLI: Compute SHA-256
    CLI->>FS: Copy immutable content-addressed source
    CLI->>FS: Update .llm-wiki/state.json
    CLI-->>Agent: Registered raw path and source hash
    Agent->>Adapter: Extract registered source
    Adapter->>CLI: extract raw path to cache
    CLI->>FS: Write temporary extracted text
    Adapter-->>Agent: Location map, warnings, status
    Agent->>FS: Read schema, index, overview, related pages
    Agent->>Agent: Resolve entities and reconcile claims
    Agent->>FS: Update source and knowledge pages
    Agent->>CLI: index, graph, lint
    CLI->>FS: Rebuild deterministic artifacts
    CLI-->>Agent: Validation issues
    Agent->>FS: Repair current-operation issues
    Agent->>CLI: log ingest operation
    Agent-->>User: Report changed pages and limitations
```

Registration happens before extraction. This ensures every downstream claim can cite the immutable,
content-addressed copy rather than a mutable input path or temporary cache artifact.

## Query lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Agent as Codex + $llm-wiki
    participant CLI as Python toolkit
    participant Wiki as Compiled Markdown wiki
    participant Raw as Immutable sources

    User->>Agent: Ask a knowledge question
    Agent->>Wiki: Read index and overview
    Agent->>CLI: search question terms
    CLI->>Wiki: Score compiled pages lexically
    CLI-->>Agent: Ranked paths and excerpts
    Agent->>Wiki: Follow relevant wikilinks and evidence blocks
    opt Important, disputed, or incomplete claim
        Agent->>Raw: Verify exact source location
    end
    Agent->>Agent: Reconcile evidence and expose uncertainty
    Agent-->>User: Answer with source anchors
    opt Reusable synthesis requested
        Agent->>Wiki: Save synthesis page
        Agent->>CLI: index, graph, lint, log
    end
```

Queries normally search compiled knowledge first. Raw files are consulted when evidence is missing,
disputed, or important enough to require direct verification.

## Persistent information model

```mermaid
erDiagram
    SOURCE_RECORD ||--|| RAW_SOURCE : identifies
    RAW_SOURCE ||--|| SOURCE_PAGE : summarized_by
    SOURCE_PAGE }o--o{ ENTITY_PAGE : supports
    SOURCE_PAGE }o--o{ CONCEPT_PAGE : supports
    SOURCE_PAGE }o--o{ SYNTHESIS_PAGE : supports
    ENTITY_PAGE }o--o{ CONCEPT_PAGE : links
    ENTITY_PAGE }o--o{ SYNTHESIS_PAGE : informs
    CONCEPT_PAGE }o--o{ SYNTHESIS_PAGE : informs
    WIKI_PAGE ||--o{ WIKILINK : contains
    WIKI_PAGE ||--o{ EVIDENCE_ANCHOR : contains

    SOURCE_RECORD {
        string sha256 PK
        string path
        int size
        datetime registered_at
    }
    RAW_SOURCE {
        string content_addressed_path PK
        bytes immutable_content
    }
    WIKI_PAGE {
        string id PK
        string type
        string title
        string status
        string sources
        date updated
    }
    SOURCE_PAGE {
        string id PK
        string source_hash FK
    }
    ENTITY_PAGE {
        string id PK
        string canonical_name
    }
    CONCEPT_PAGE {
        string id PK
        string concept_name
    }
    SYNTHESIS_PAGE {
        string id PK
        string question_or_topic
    }
    WIKILINK {
        string source_page FK
        string target_page FK
    }
    EVIDENCE_ANCHOR {
        string raw_path FK
        string location
    }
```

The ER diagram is conceptual: records are JSON and Markdown files, not relational tables. The graph
is a materialized projection of Markdown wikilinks and can always be rebuilt.

## Filesystem topology

```mermaid
flowchart LR
    classDef source fill:#3f1d2e,stroke:#fb7185,color:#fff1f2
    classDef knowledge fill:#0f3d3e,stroke:#5eead4,color:#f0fdfa
    classDef generated fill:#422006,stroke:#fbbf24,color:#fffbeb
    classDef instruction fill:#312e81,stroke:#818cf8,color:#eef2ff

    Repo[Repository root]
    Repo --> Skills[.agents/skills/]
    Skills --> Core[llm-wiki/]
    Skills --> Sources[wiki-*-source/]
    Repo --> Raw[raw/{hash}-{name}]
    Repo --> Wiki[wiki/]
    Wiki --> SourcePages[sources/]
    Wiki --> Entities[entities/]
    Wiki --> Concepts[concepts/]
    Wiki --> Syntheses[syntheses/]
    Wiki --> Navigation[index.md · overview.md · log.md]
    Repo --> Local[.llm-wiki/]
    Local --> State[state.json · schema.md · cache/]
    Repo --> Graph[graph/graph.json]

    class Skills,Core,Sources instruction
    class Raw source
    class Wiki,SourcePages,Entities,Concepts,Syntheses,Navigation knowledge
    class Local,State,Graph generated
```

| Path | Lifecycle | Version-control intent |
|---|---|---|
| `.agents/skills/` | Maintained by developers | Tracked |
| `raw/` | Append-only through registration | Ignored by default |
| `wiki/` | Maintained by the agent and reviewed by humans | Tracked |
| `.llm-wiki/state.json` | Deterministic local registry | Ignored |
| `.llm-wiki/cache/` | Disposable extraction output | Ignored |
| `graph/graph.json` | Rebuildable wikilink projection | Ignored |

## Page state and knowledge evolution

```mermaid
stateDiagram-v2
    [*] --> Draft: New evidence discovered
    Draft --> Active: Evidence integrated and lint passes
    Active --> Active: Compatible evidence refreshes page
    Active --> Disputed: Sources conflict
    Disputed --> Active: Conflict resolved by evidence
    Active --> Stale: Source superseded or freshness concern
    Stale --> Active: Relevant evidence refreshed
    Draft --> Rejected: Insufficient or invalid evidence
    Disputed --> Rejected: Claim disproven
    Stale --> Archived: Knowledge no longer applicable
    Rejected --> [*]
    Archived --> [*]
```

The current toolkit validates structural invariants. The agent performs semantic state transitions
and must leave contradictions, uncertainty, and freshness limitations visible to reviewers.

## Trust boundaries

```mermaid
flowchart LR
    classDef external fill:#7f1d1d,stroke:#fca5a5,color:#fef2f2,stroke-width:2px
    classDef boundary fill:#78350f,stroke:#fcd34d,color:#fffbeb,stroke-width:2px
    classDef trusted fill:#14532d,stroke:#86efac,color:#f0fdf4,stroke-width:2px

    Input[External source files]:::external
    Prompt[User instructions]:::external
    Register[Hash and register]:::boundary
    Extract[Constrained extraction]:::boundary
    Reconcile[Evidence reconciliation]:::boundary
    Lint[Deterministic lint]:::boundary
    Raw[(Immutable raw store)]:::trusted
    Wiki[(Reviewed Markdown wiki)]:::trusted

    Input --> Register --> Raw
    Raw --> Extract --> Reconcile
    Prompt --> Reconcile
    Reconcile --> Wiki
    Wiki --> Lint --> Wiki
```

Source text is untrusted data, even when it contains instructions that resemble prompts. Adapters
must not send files to external services, install capabilities, or mutate registered sources without
explicit authorization. Generated wiki text is useful but is not evidence by itself.

## Docker deployment model

```mermaid
flowchart LR
    classDef host fill:#172554,stroke:#60a5fa,color:#eff6ff,stroke-width:2px
    classDef container fill:#064e3b,stroke:#34d399,color:#ecfdf5,stroke-width:2px
    classDef volume fill:#3f1d2e,stroke:#fb7185,color:#fff1f2,stroke-width:2px

    subgraph Host[Developer workstation]
        Codex[Codex runtime]
        Repo[(Project repository)]:::volume
    end

    subgraph Container[Ephemeral llm-wiki:local container]
        CLI[llm-wiki CLI]
        Python[Python 3.12]
        Converters[pypdf · python-docx<br/>python-pptx · openpyxl]
        CLI --> Python
        CLI --> Converters
    end

    Codex -->|docker run| CLI
    Repo <-->|bind mount /workspace| CLI

    class Codex host
    class CLI,Python,Converters container
```

The container is stateless and disposable. All durable state remains in the bind-mounted repository.
No OpenAI API token is passed to the image because semantic work happens in the Codex session.

## Consistency model

LLM Wiki uses explicit, reviewable consistency rather than distributed transactions:

- A source registration is idempotent by SHA-256 digest.
- Raw source mutation is detected by deterministic lint.
- Wiki updates may span several Markdown pages and are completed by one agent workflow.
- `index.md` and `graph.json` are materialized projections rebuilt after mutations.
- `wiki/log.md` records meaningful operations but is not an event-sourcing authority.
- Interrupted ingestion can leave partial wiki changes; rerunning lint identifies structural damage,
  while semantic review identifies incomplete integration.

## Extension points

```mermaid
flowchart LR
    Core[$llm-wiki] --> AdapterContract{Source adapter contract}
    AdapterContract --> PDF[PDF]
    AdapterContract --> Office[Office]
    AdapterContract --> Tabular[Tabular]
    AdapterContract -.-> Image[Image and OCR]
    AdapterContract -.-> Media[Audio and video]
    AdapterContract -.-> Code[Source code]
    AdapterContract -.-> Archive[Archives]

    Toolkit[Python toolkit] --> ExtractorContract{Extractor function}
    ExtractorContract --> Existing[Current deterministic formats]
    ExtractorContract -.-> NewFormat[Additional local converter]

    Wiki[Markdown wiki] --> ProjectionContract{Rebuildable projection}
    ProjectionContract --> JSONGraph[JSON wikilink graph]
    ProjectionContract -.-> SearchIndex[Future search index]
    ProjectionContract -.-> Export[Future export formats]
```

New capabilities should preserve the existing boundaries. Add a focused source skill when agent
instructions are required. Add a Python extractor when conversion is deterministic and local. Add a
projection only when it can be rebuilt from tracked source and wiki artifacts.

## Current limitations

- Search is lexical term counting, not semantic or hybrid retrieval.
- The graph contains wikilinks only; it does not model typed claims or temporal relations.
- Freshness and contradiction review are agent workflows, not scheduled background jobs.
- PDF extraction does not include bundled OCR.
- DOCX, PPTX, and XLSX extraction preserves only the structure implemented by the current toolkit.
- Concurrent writers are not coordinated; one agent should mutate a workspace at a time.
- Human review remains necessary for consequential conclusions.

These constraints are deliberate for the PoC. They keep the system understandable and provide clear
interfaces for later storage, retrieval, review, and automation upgrades.
