from __future__ import annotations

import os
from contextlib import AbstractContextManager, nullcontext
from typing import Any, cast


class FactoryTelemetry:
    def __init__(self) -> None:
        self._tracer: Any = None
        self._meter: Any = None
        self._sessions: Any = None
        self._agent_duration: Any = None
        self._tool_calls: Any = None
        self._tokens: Any = None
        self._tool_duration: Any = None
        self._delivery_score: Any = None

    @classmethod
    def configure(cls) -> FactoryTelemetry:
        telemetry = cls()
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            return telemetry
        try:
            from opentelemetry import metrics, trace
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": "llm-wiki-factory"})
            trace_provider = TracerProvider(resource=resource)
            trace_provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces"))
            )
            trace.set_tracer_provider(trace_provider)
            metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=f"{endpoint.rstrip('/')}/v1/metrics")
            )
            metrics.set_meter_provider(
                MeterProvider(resource=resource, metric_readers=[metric_reader])
            )
            telemetry._tracer = trace.get_tracer("software_factory")
            telemetry._meter = metrics.get_meter("software_factory")
            telemetry._sessions = telemetry._meter.create_counter("factory.sessions")
            telemetry._agent_duration = telemetry._meter.create_histogram(
                "factory.agent.duration", unit="ms"
            )
            telemetry._tool_calls = telemetry._meter.create_counter("factory.tool.calls")
            telemetry._tokens = telemetry._meter.create_counter("factory.openai.tokens")
            telemetry._tool_duration = telemetry._meter.create_histogram(
                "factory.tool.duration", unit="ms"
            )
            telemetry._delivery_score = telemetry._meter.create_histogram("factory.delivery.score")
        except (ImportError, RuntimeError, ValueError):
            return cls()
        return telemetry

    def span(self, name: str, attributes: dict[str, Any]) -> AbstractContextManager[Any]:
        if self._tracer is None:
            return nullcontext()
        return cast(
            AbstractContextManager[Any],
            self._tracer.start_as_current_span(name, attributes=attributes),
        )

    def session_completed(self, state: str) -> None:
        if self._sessions is not None:
            self._sessions.add(1, {"state": state})

    def agent_completed(self, agent: str, duration_ms: int, tool_calls: int) -> None:
        if self._agent_duration is not None:
            self._agent_duration.record(duration_ms, {"agent": agent})
        if self._tool_calls is not None:
            self._tool_calls.add(tool_calls, {"agent": agent})

    def tokens(self, agent: str, input_tokens: int, output_tokens: int, cached_tokens: int) -> None:
        if self._tokens is None:
            return
        self._tokens.add(input_tokens, {"agent": agent, "type": "input"})
        self._tokens.add(output_tokens, {"agent": agent, "type": "output"})
        self._tokens.add(cached_tokens, {"agent": agent, "type": "cached"})

    def tool_completed(self, agent: str, tool: str, duration_ms: int, ok: bool) -> None:
        if self._tool_duration is not None:
            self._tool_duration.record(
                duration_ms, {"agent": agent, "tool": tool, "outcome": "ok" if ok else "error"}
            )

    def delivery_scored(self, status: str, score: float) -> None:
        if self._delivery_score is not None:
            self._delivery_score.record(score, {"status": status})
