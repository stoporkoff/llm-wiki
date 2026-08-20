from __future__ import annotations

import asyncio
import os
from pathlib import Path
from time import monotonic
from typing import Any

from software_factory.domain import AgentRunResult, AgentSpec
from software_factory.tools import ToolContext, ToolRegistry


class OpenAIConfigurationError(RuntimeError):
    pass


class OpenAIResponsesAgentGateway:
    def __init__(
        self,
        tools: ToolRegistry,
        default_model: str,
        reasoning_effort: str,
        max_tool_rounds: int = 12,
    ) -> None:
        self._tools = tools
        self._default_model = default_model
        self._reasoning_effort = reasoning_effort
        self._max_tool_rounds = max_tool_rounds

    async def run(
        self,
        spec: AgentSpec,
        instruction: str,
        workspace: Path,
        session_id: str,
    ) -> AgentRunResult:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise OpenAIConfigurationError("OPENAI_API_KEY is not configured")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        started = monotonic()
        definitions = self._tools.definitions(spec.tools)
        context = ToolContext(workspace=workspace, role=spec.id, session_id=session_id)
        request: dict[str, Any] = {
            "model": spec.model or self._default_model,
            "instructions": spec.instructions,
            "input": instruction,
            "tools": definitions,
            "parallel_tool_calls": True,
            "reasoning": {"effort": self._reasoning_effort},
        }
        response = await client.responses.create(**request)
        tool_calls = 0

        for _ in range(self._max_tool_rounds):
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                usage = getattr(response, "usage", None)
                details = getattr(usage, "input_tokens_details", None)
                return AgentRunResult(
                    output=response.output_text,
                    tool_calls=tool_calls,
                    input_tokens=getattr(usage, "input_tokens", 0) or 0,
                    output_tokens=getattr(usage, "output_tokens", 0) or 0,
                    cached_tokens=getattr(details, "cached_tokens", 0) or 0,
                    duration_ms=round((monotonic() - started) * 1000),
                )
            tool_calls += len(calls)
            outputs = await asyncio.gather(
                *(
                    self._tools.execute(call.name, call.arguments, context)
                    for call in calls
                )
            )
            request = {
                "model": spec.model or self._default_model,
                "instructions": spec.instructions,
                "input": [
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": output,
                    }
                    for call, output in zip(calls, outputs, strict=True)
                ],
                "previous_response_id": response.id,
                "tools": definitions,
                "parallel_tool_calls": True,
                "reasoning": {"effort": self._reasoning_effort},
            }
            response = await client.responses.create(**request)

        raise RuntimeError(f"Agent {spec.id} exceeded the tool round limit")
