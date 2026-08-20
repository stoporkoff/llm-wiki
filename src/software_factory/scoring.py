from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from software_factory.stages import WorkflowContext


@dataclass(frozen=True)
class ScoreDimension:
    name: str
    score: float
    weight: float
    evidence: str


@dataclass(frozen=True)
class DeliveryScorecard:
    total: float
    status: str
    hard_gates: dict[str, bool]
    dimensions: tuple[ScoreDimension, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "status": self.status,
            "hard_gates": self.hard_gates,
            "dimensions": [asdict(item) for item in self.dimensions],
        }


class DeliveryScorer:
    """Deterministic first-pass scorer; weights must be calibrated with eval data."""

    _trusted_threshold = 0.80

    def score(self, context: WorkflowContext, workspace: Path) -> DeliveryScorecard:
        files = [path for path in workspace.rglob("*") if path.is_file()]
        qa = context.verification.get("qa", "").casefold()
        security = context.verification.get("security", "").casefold()
        contract = context.tool_contract or {}
        approved = context.review.lstrip().upper().startswith("APPROVED")
        reusable = contract.get("reusable") is True
        no_critical = (
            "no critical findings" in security
            and "high-severity finding" not in security
            and "high severity finding" not in security
        )
        has_tests = any("test" in path.name.casefold() for path in files)
        test_success = any(term in qa for term in ("passed", "success", "exit code 0"))

        dimensions = (
            ScoreDimension("functional", 1.0 if test_success else 0.55 if files else 0.0, 0.30,
                           "QA report and generated artifacts"),
            ScoreDimension("acceptance", 1.0 if approved else 0.0, 0.20,
                           "Final reviewer verdict"),
            ScoreDimension("security", 1.0 if no_critical else 0.0, 0.20,
                           "Security reviewer report"),
            ScoreDimension("reproducibility", 1.0 if has_tests else 0.4, 0.15,
                           "Presence of executable test artifacts"),
            ScoreDimension("tool_contract", 1.0 if reusable else 0.0, 0.10,
                           "Tool curator contract"),
            ScoreDimension("provenance", 1.0, 0.05,
                           "Session, source workspace, and score are recorded in the manifest"),
        )
        total = round(sum(item.score * item.weight for item in dimensions), 3)
        hard_gates = {
            "review_approved": approved,
            "no_critical_security_findings": no_critical,
            "curator_marked_reusable": reusable,
            "tests_present_and_reported_passing": has_tests and test_success,
        }
        trusted = all(hard_gates.values()) and total >= self._trusted_threshold
        return DeliveryScorecard(
            total=total,
            status="trusted" if trusted else "candidate",
            hard_gates=hard_gates,
            dimensions=dimensions,
        )
