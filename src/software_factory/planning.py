from __future__ import annotations

import json
import re
from typing import Any

from software_factory.domain import ExecutionPlan, WorkItem


class PlanError(ValueError):
    pass


class ExecutionPlanParser:
    _allowed_roles = {
        "frontend-developer",
        "backend-developer",
        "database-engineer",
    }

    def parse(self, output: str) -> ExecutionPlan:
        normalized = output.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", normalized, re.DOTALL)
        if fenced:
            normalized = fenced.group(1)
        try:
            value = json.loads(normalized)
        except json.JSONDecodeError as error:
            raise PlanError("Team Lead did not return valid JSON") from error
        if not isinstance(value, dict) or not isinstance(value.get("tasks"), list):
            raise PlanError("Team Lead plan must contain a tasks list")
        tasks = tuple(self._parse_task(task) for task in value["tasks"])
        if not tasks:
            raise PlanError("Team Lead plan contains no implementation tasks")
        roles = [task.role for task in tasks]
        if len(roles) != len(set(roles)):
            raise PlanError("Team Lead assigned the same role more than once")
        return ExecutionPlan(summary=str(value.get("summary", "")), tasks=tasks)

    def _parse_task(self, value: Any) -> WorkItem:
        if not isinstance(value, dict):
            raise PlanError("Each planned task must be an object")
        role = str(value.get("role", ""))
        if role not in self._allowed_roles:
            raise PlanError(f"Unsupported implementation role: {role}")
        objective = str(value.get("objective", "")).strip()
        if not objective:
            raise PlanError(f"Task for {role} has no objective")
        criteria_value = value.get("acceptance_criteria", [])
        if not isinstance(criteria_value, list):
            raise PlanError(f"Acceptance criteria for {role} must be a list")
        return WorkItem(
            role=role,
            objective=objective,
            acceptance_criteria=tuple(str(item) for item in criteria_value),
        )
