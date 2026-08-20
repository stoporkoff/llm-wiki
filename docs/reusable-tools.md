# Reusable Tool Lifecycle

A successful delivery is useful twice: first as user output, then as a candidate capability. The
PoC packages approved artifacts as versioned templates. It does not pretend arbitrary generated
applications have a safe executable function interface.

```mermaid
stateDiagram-v2
  [*] --> Generated
  Generated --> Reviewed
  Reviewed --> Candidate: contract or score incomplete
  Reviewed --> Trusted: hard gates and score >= 0.80
  Candidate --> Trusted: later evaluation and approval
  Candidate --> Rejected
  Trusted --> Deprecated
```

## Publication Flow

```mermaid
sequenceDiagram
  participant Reviewer
  participant Curator as Tool Curator
  participant Scorer
  participant Store as ReusableToolStore
  participant Future as Future Developer Agent
  Reviewer-->>Curator: APPROVED delivery
  Curator->>Curator: Inspect actual files
  Curator-->>Scorer: Strict JSON contract
  Scorer->>Scorer: Hard gates + weighted dimensions
  Scorer->>Store: Publish version and provenance
  Future->>Store: list_reusable_tools
  Store-->>Future: Trusted tools only
  Future->>Store: apply_reusable_tool(tool, component)
  Store-->>Future: Copy into owned workspace path
```

Each `.factory/tools/<id>/<version>/tool.json` contains schema version, stable id, derived version,
status, source session, curator contract, scorecard, and available components. `payload/` contains
only supported roots: `frontend`, `backend`, `database`, `deploy`, and `tests`.

## Reuse Safety

- Agents discover only `trusted` versions.
- Application copies only the component matching the caller's write boundary.
- Agents inspect existing files before applying a template.
- Secrets and `.git` cannot be accessed through file tools.
- Reuse preserves origin and score provenance.
- Production promotion should add human or offline evaluation approval.

## Future Executable Tools

```mermaid
flowchart LR
  Template[Template tool] --> Contract[Typed execution contract]
  Contract --> Sandbox[OCI or WASI sandbox]
  Sandbox --> Conformance[Contract tests]
  Conformance --> Signature[Signed artifact + SBOM]
  Signature --> Registry[Executable tool registry]
```

Executable generated tools require a separate sandbox, resource limits, dependency locking, SBOM,
signature, permissions, and conformance suite. Those controls are outside this PoC rather than
being simulated insecurely.
