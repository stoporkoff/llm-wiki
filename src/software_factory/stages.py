from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from software_factory.domain import (
    AgentRunResult,
    ExecutionMode,
    ExecutionPlan,
    FactorySession,
    StageDefinition,
    WorkflowState,
)
from software_factory.planning import ExecutionPlanParser

AgentInvoker = Callable[[str, str], Awaitable[AgentRunResult]]


@dataclass
class WorkflowContext:
    session: FactorySession
    invoke: AgentInvoker
    discovery: str = ""
    architecture: str = ""
    plan: ExecutionPlan | None = None
    implementation: dict[str, str] = field(default_factory=dict)
    release: str = ""
    verification: dict[str, str] = field(default_factory=dict)
    review: str = ""
    tool_contract: dict[str, object] | None = None
    preview_url: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "discovery": self.discovery,
            "architecture": self.architecture,
            "plan": {
                "summary": self.plan.summary,
                "tasks": [
                    {
                        "role": item.role,
                        "objective": item.objective,
                        "acceptance_criteria": list(item.acceptance_criteria),
                    }
                    for item in self.plan.tasks
                ],
            }
            if self.plan
            else None,
            "implementation": self.implementation,
            "release": self.release,
            "verification": self.verification,
            "review": self.review,
            "tool_contract": self.tool_contract,
            "preview_url": self.preview_url,
        }


class WorkflowStage(ABC):
    definition: StageDefinition

    @abstractmethod
    async def execute(self, context: WorkflowContext) -> None: ...


class DiscoveryStage(WorkflowStage):
    definition = StageDefinition(
        state=WorkflowState.DISCOVERY,
        display_name="Discovery",
        description="Turn the request and wiki evidence into a bounded delivery brief.",
        mode=ExecutionMode.SEQUENTIAL,
        agents=("requirements-analyst",),
        gate=(
            "A testable brief exists with assumptions, exclusions, risks, and acceptance criteria."
        ),
    )

    async def execute(self, context: WorkflowContext) -> None:
        result = await context.invoke(
            "requirements-analyst",
            (
                f"User goal:\n{context.session.goal}\n\n"
                "Produce the authoritative discovery brief for this delivery session."
            ),
        )
        context.discovery = result.output


class PlanningStage(WorkflowStage):
    definition = StageDefinition(
        state=WorkflowState.PLANNING,
        display_name="Planning",
        description="Design the solution, then convert it into parallel specialist work.",
        mode=ExecutionMode.SEQUENTIAL,
        agents=("solution-architect", "team-lead"),
        gate="The plan is valid JSON, uses supported roles, and assigns non-overlapping ownership.",
    )

    def __init__(self, parser: ExecutionPlanParser | None = None) -> None:
        self._parser = parser or ExecutionPlanParser()

    async def execute(self, context: WorkflowContext) -> None:
        architecture = await context.invoke(
            "solution-architect",
            (
                f"User goal:\n{context.session.goal}\n\n"
                f"Discovery brief:\n{context.discovery}\n\n"
                "Propose the smallest coherent local architecture."
            ),
        )
        context.architecture = architecture.output
        planning = await context.invoke(
            "team-lead",
            (
                f"User goal:\n{context.session.goal}\n\n"
                f"Discovery brief:\n{context.discovery}\n\n"
                f"Architecture note:\n{context.architecture}\n\n"
                "Create the smallest complete implementation plan."
            ),
        )
        context.plan = self._parser.parse(planning.output)


class ImplementationStage(WorkflowStage):
    definition = StageDefinition(
        state=WorkflowState.IMPLEMENTING,
        display_name="Implementation",
        description="Run the specialists selected by the Team Lead in isolated ownership areas.",
        mode=ExecutionMode.DYNAMIC,
        agents=("frontend-developer", "backend-developer", "database-engineer"),
        gate="Every planned specialist reports completion and writes only inside its owned path.",
    )

    async def execute(self, context: WorkflowContext) -> None:
        if context.plan is None:
            raise RuntimeError("Implementation stage requires a validated execution plan")

        async def run_item(role: str, instruction: str) -> tuple[str, str]:
            result = await context.invoke(role, instruction)
            return role, result.output

        results = await asyncio.gather(
            *(
                run_item(
                    item.role,
                    (
                        f"User goal:\n{context.session.goal}\n\n"
                        f"Discovery brief:\n{context.discovery}\n\n"
                        f"Architecture note:\n{context.architecture}\n\n"
                        f"Assigned objective:\n{item.objective}\n\n"
                        "Acceptance criteria:\n- "
                        + "\n- ".join(item.acceptance_criteria or ("Deliver the objective",))
                    ),
                )
                for item in context.plan.tasks
            )
        )
        context.implementation = dict(results)


class VerificationStage(WorkflowStage):
    definition = StageDefinition(
        state=WorkflowState.TESTING,
        display_name="Verification",
        description="Run functional QA and defensive security review concurrently.",
        mode=ExecutionMode.PARALLEL,
        agents=("qa-engineer", "security-reviewer"),
        gate=(
            "Runtime evidence exists and both QA PASSED and SECURITY PASSED verdicts "
            "are present."
        ),
    )

    async def execute(self, context: WorkflowContext) -> None:
        common = (
            f"User goal:\n{context.session.goal}\n\n"
            f"Discovery brief:\n{context.discovery}\n\n"
            f"Architecture note:\n{context.architecture}\n\n"
            f"Implementation reports:\n{context.implementation}\n\n"
            f"Release report:\n{context.release}\n\n"
            "Inspect the actual workspace and report evidence. Follow the verdict contract in "
            "your agent specification exactly."
        )
        qa, security = await asyncio.gather(
            context.invoke("qa-engineer", common),
            context.invoke("security-reviewer", common),
        )
        context.verification = {"qa": qa.output, "security": security.output}
        self._require_verdict(qa.output, "QA PASSED", "QA BLOCKED")
        self._require_verdict(
            security.output, "SECURITY PASSED", "SECURITY BLOCKED"
        )

    @staticmethod
    def _require_verdict(output: str, passed: str, blocked: str) -> None:
        first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
        normalized = first_line.lstrip("#* ").rstrip("* ").upper()
        if normalized.startswith(passed):
            return
        if normalized.startswith(blocked):
            raise RuntimeError(f"Verification gate blocked: {first_line}")
        raise RuntimeError(
            f"Verification gate received no valid verdict; expected {passed} or {blocked}"
        )


class ReleaseEngineeringStage(WorkflowStage):
    definition = StageDefinition(
        state=WorkflowState.RELEASING,
        display_name="Release Engineering",
        description="Create a portable Docker launch contract for the generated project.",
        mode=ExecutionMode.SEQUENTIAL,
        agents=("infrastructure-engineer",),
        gate="Deployment assets and a valid static preview manifest exist under deploy/.",
    )

    async def execute(self, context: WorkflowContext) -> None:
        result = await context.invoke(
            "infrastructure-engineer",
            (
                f"User goal:\n{context.session.goal}\n\n"
                f"Architecture note:\n{context.architecture}\n\n"
                f"Implementation reports:\n{context.implementation}\n\n"
                "Inspect the generated project and create its Docker delivery contract."
            ),
        )
        context.release = result.output


class ReviewStage(WorkflowStage):
    definition = StageDefinition(
        state=WorkflowState.REVIEWING,
        display_name="Final Review",
        description="Evaluate the complete delivery and issue the final trust verdict.",
        mode=ExecutionMode.SEQUENTIAL,
        agents=("reviewer",),
        gate="The reviewer returns APPROVED with evidence; otherwise the workflow fails closed.",
    )

    async def execute(self, context: WorkflowContext) -> None:
        result = await context.invoke(
            "reviewer",
            (
                f"User goal:\n{context.session.goal}\n\n"
                f"Discovery brief:\n{context.discovery}\n\n"
                f"Architecture note:\n{context.architecture}\n\n"
                f"Implementation reports:\n{context.implementation}\n\n"
                f"Release report:\n{context.release}\n\n"
                f"Verification reports:\n{context.verification}\n\n"
                "Inspect the workspace and return the required approval verdict."
            ),
        )
        context.review = result.output
        if not context.review.lstrip().upper().startswith("APPROVED"):
            raise RuntimeError(f"Delivery review rejected: {context.review}")


class PackagingStage(WorkflowStage):
    definition = StageDefinition(
        state=WorkflowState.PACKAGING,
        display_name="Tool Packaging",
        description="Describe the approved delivery as a versioned reusable capability.",
        mode=ExecutionMode.SEQUENTIAL,
        agents=("tool-curator",),
        gate=(
            "A strict reuse contract exists; deterministic scoring decides candidate "
            "or trusted status."
        ),
    )

    async def execute(self, context: WorkflowContext) -> None:
        result = await context.invoke(
            "tool-curator",
            (
                f"User goal:\n{context.session.goal}\n\n"
                f"Architecture note:\n{context.architecture}\n\n"
                f"Implementation reports:\n{context.implementation}\n\n"
                f"Release report:\n{context.release}\n\n"
                f"Verification reports:\n{context.verification}\n\n"
                f"Approval:\n{context.review}\n\n"
                "Inspect the workspace and return the required reusable-tool contract."
            ),
        )
        try:
            contract = json.loads(result.output)
        except json.JSONDecodeError as error:
            raise RuntimeError("Tool curator returned invalid JSON") from error
        required = {"name", "description", "kind", "entrypoint", "reusable"}
        if not isinstance(contract, dict) or not required.issubset(contract):
            raise RuntimeError("Tool curator contract is missing required fields")
        context.tool_contract = contract


class PreviewStage(WorkflowStage):
    definition = StageDefinition(
        state=WorkflowState.PREVIEWING,
        display_name="Local Preview",
        description="Validate the release manifest and expose the delivered frontend on localhost.",
        mode=ExecutionMode.SEQUENTIAL,
        agents=("release-manager",),
        gate="The release manager starts a verified local preview and returns its URL.",
    )

    async def execute(self, context: WorkflowContext) -> None:
        result = await context.invoke(
            "release-manager",
            (
                f"User goal:\n{context.session.goal}\n\n"
                f"Release report:\n{context.release}\n\n"
                "Inspect deployment assets, start the localhost preview, and report the URL."
            ),
        )
        context.preview_url = f"/previews/{context.session.id}/"
        if context.preview_url not in result.output:
            raise RuntimeError("Release manager did not confirm the required localhost preview URL")


class StagePipeline:
    def __init__(self, stages: tuple[WorkflowStage, ...]) -> None:
        self._stages = stages

    @classmethod
    def default(cls) -> StagePipeline:
        return cls(
            (
                DiscoveryStage(),
                PlanningStage(),
                ImplementationStage(),
                ReleaseEngineeringStage(),
                VerificationStage(),
                ReviewStage(),
                PackagingStage(),
                PreviewStage(),
            )
        )

    @property
    def stages(self) -> tuple[WorkflowStage, ...]:
        return self._stages

    def catalog(self) -> list[dict[str, object]]:
        return [stage.definition.to_dict() for stage in self._stages]
