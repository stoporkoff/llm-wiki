from __future__ import annotations

from software_factory.domain import WorkflowState


class InvalidTransitionError(ValueError):
    pass


class WorkflowStateMachine:
    _transitions: dict[WorkflowState, frozenset[WorkflowState]] = {
        WorkflowState.CREATED: frozenset({WorkflowState.DISCOVERY, WorkflowState.FAILED}),
        WorkflowState.DISCOVERY: frozenset({WorkflowState.PLANNING, WorkflowState.FAILED}),
        WorkflowState.PLANNING: frozenset({WorkflowState.IMPLEMENTING, WorkflowState.FAILED}),
        WorkflowState.IMPLEMENTING: frozenset({WorkflowState.RELEASING, WorkflowState.FAILED}),
        WorkflowState.RELEASING: frozenset({WorkflowState.TESTING, WorkflowState.FAILED}),
        WorkflowState.TESTING: frozenset({WorkflowState.REVIEWING, WorkflowState.FAILED}),
        WorkflowState.REVIEWING: frozenset({WorkflowState.PACKAGING, WorkflowState.FAILED}),
        WorkflowState.PACKAGING: frozenset({WorkflowState.PREVIEWING, WorkflowState.FAILED}),
        WorkflowState.PREVIEWING: frozenset({WorkflowState.COMPLETED, WorkflowState.FAILED}),
        WorkflowState.COMPLETED: frozenset(),
        WorkflowState.FAILED: frozenset(),
    }

    def can_transition(self, current: WorkflowState, target: WorkflowState) -> bool:
        return target in self._transitions[current]

    def transition(self, current: WorkflowState, target: WorkflowState) -> WorkflowState:
        if not self.can_transition(current, target):
            raise InvalidTransitionError(f"Invalid workflow transition: {current} -> {target}")
        return target
