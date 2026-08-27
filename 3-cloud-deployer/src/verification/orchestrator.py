"""Three-phase Six-layer telemetry roundtrip orchestration."""

from __future__ import annotations

import asyncio
import math
import time
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone

from src.verification import probes
from src.verification.contracts import (
    PhaseEmission,
    PhaseOutcome,
    ProbeResult,
    VerificationContext,
    VerificationSummary,
)
from src.verification.events import display_timestamp, sse_event

PHASE_2_TIMEOUT = 600
PHASE_2_POLL_INTERVAL = 2
PHASE_3_TIMEOUT = 60
PHASE_3_POLL_INTERVAL = 2


class _PhaseRun:
    """Forward phase events immediately while retaining its final outcome."""

    def __init__(self, source: AsyncIterator[PhaseEmission]) -> None:
        self._source = source
        self.outcome: PhaseOutcome | None = None

    async def events(self) -> AsyncIterator[str]:
        async for emission in self._source:
            if emission.event is not None:
                yield emission.event
            if emission.outcome is not None:
                if self.outcome is not None:
                    raise RuntimeError("Verification phase emitted multiple outcomes")
                self.outcome = emission.outcome
        if self.outcome is None:
            raise RuntimeError("Verification phase completed without an outcome")

    def require_outcome(self) -> PhaseOutcome:
        if self.outcome is None:
            raise RuntimeError("Verification phase outcome requested before completion")
        return self.outcome


class DataFlowVerificationOrchestrator:
    """Run request-local verification without global mutable cloud state."""

    def __init__(
        self,
        context: VerificationContext,
        send_message: Callable[..., bool],
    ) -> None:
        self.context = context
        self.send_message = send_message

    async def stream(self, payload: dict) -> AsyncIterator[str]:
        started = time.monotonic()
        summary = VerificationSummary()
        trace_id = f"VERIFY-{uuid.uuid4().hex[:8].upper()}"
        sent_at = datetime.now(timezone.utc)
        metric, value = self._verification_measurement(payload)
        send_payload = {
            **payload,
            "trace_id": trace_id,
            "source_sequence": trace_id,
            "projection_candidate": True,
            "twin_id": payload.get("twin_id") or payload["iotDeviceId"],
            "metric": metric,
            "value": value,
            "time": sent_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }

        phase_one = _PhaseRun(self._phase_message_delivery(send_payload, trace_id))
        async for event in phase_one.events():
            yield event
        phase_one_outcome = phase_one.require_outcome()
        summary.include(phase_one_outcome)
        if phase_one_outcome.failed:
            async for event in self._terminal_skip(summary, started, trace_id, (2, 3)):
                yield event
            return

        phase_two = _PhaseRun(
            self._phase_hot_storage(
                payload["iotDeviceId"],
                trace_id,
            )
        )
        async for event in phase_two.events():
            yield event
        phase_two_outcome = phase_two.require_outcome()
        summary.include(phase_two_outcome)
        if phase_two_outcome.failed:
            async for event in self._terminal_skip(summary, started, trace_id, (3,)):
                yield event
            return

        phase_three = _PhaseRun(
            self._phase_digital_twin(
                payload["iotDeviceId"],
                trace_id,
                metric,
                value,
                sent_at,
            )
        )
        async for event in phase_three.events():
            yield event
        summary.include(phase_three.require_outcome())
        yield self._done_event(summary, started, trace_id)

    async def _phase_message_delivery(
        self,
        payload: dict,
        trace_id: str,
    ) -> AsyncIterator[PhaseEmission]:
        provider = self.context.providers["layer_1_provider"]
        yield PhaseEmission(event=self._phase_event(1, "Message Delivery", "running"))
        yield PhaseEmission(
            event=self._log_event(
                f"Sending test message to {provider.upper()} IoT",
                detail=f"Device: {payload['iotDeviceId']}",
            )
        )
        success = await asyncio.to_thread(
            self.send_message,
            provider,
            self.context.project_name,
            trace_id,
            payload_override=payload,
            project_path=self.context.project_path,
        )
        if success:
            yield PhaseEmission(
                event=self._log_event(
                    f"Message sent successfully (trace: {trace_id})",
                    status="pass",
                )
            )
            yield PhaseEmission(event=self._phase_event(1, "Message Delivery", "pass"))
            yield PhaseEmission(
                outcome=PhaseOutcome(
                    status="pass",
                    passed=1,
                    evidence={
                        "phase": 1,
                        "kind": "message_accepted",
                        "provider": provider,
                    },
                )
            )
            return

        yield PhaseEmission(
            event=self._log_event("Failed to send test message", status="fail")
        )
        yield PhaseEmission(event=self._phase_event(1, "Message Delivery", "fail"))
        yield PhaseEmission(
            outcome=PhaseOutcome(
                status="fail",
                failed=1,
                failed_phase="Phase 1 - Message Delivery",
            )
        )

    async def _phase_hot_storage(
        self,
        device_id: str,
        trace_id: str,
    ) -> AsyncIterator[PhaseEmission]:
        provider = self.context.providers.get("layer_3_hot_provider")
        yield PhaseEmission(
            event=self._phase_event(
                2,
                "Pipeline to Hot Storage",
                "running",
                timeout=PHASE_2_TIMEOUT,
            )
        )
        started = time.monotonic()
        result = ProbeResult(success=False, error="not started")
        while time.monotonic() - started < PHASE_2_TIMEOUT:
            remaining = PHASE_2_TIMEOUT - (time.monotonic() - started)
            result = await asyncio.to_thread(
                probes.check_hot_storage_trace,
                provider,
                device_id,
                trace_id,
                self.context.terraform_outputs,
                self.context.credentials,
                self.context.project_path,
                min(20, remaining),
                PHASE_2_POLL_INTERVAL,
            )
            if result.success:
                break
            yield PhaseEmission(
                event=self._log_event(
                    f"Still waiting for trace evidence ({time.monotonic() - started:.1f}s)"
                )
            )

        if result.success:
            elapsed = round(time.monotonic() - started, 1)
            yield PhaseEmission(
                event=self._log_event(
                    f"Trace reached L3-Hot storage ({elapsed}s)",
                    detail=f"{result.evidence.get('record_count', 0)} record(s)",
                    status="pass",
                )
            )
            yield PhaseEmission(
                event=self._phase_event(
                    2,
                    "Pipeline to Hot Storage",
                    "pass",
                    elapsed=elapsed,
                )
            )
            yield PhaseEmission(
                outcome=PhaseOutcome(
                    status="pass",
                    passed=1,
                    evidence={
                        "phase": 2,
                        "kind": "trace_correlated_hot_record",
                        "provider": provider,
                        "record_count": result.evidence.get("record_count", 1),
                    },
                )
            )
            return

        yield PhaseEmission(
            event=self._log_event(
                "Trace did not reach hot storage",
                detail=result.error,
                status="fail",
            )
        )
        yield PhaseEmission(
            event=self._phase_event(2, "Pipeline to Hot Storage", "fail")
        )
        yield PhaseEmission(
            outcome=PhaseOutcome(
                status="fail",
                failed=1,
                failed_phase="Phase 2 - Pipeline",
            )
        )

    async def _phase_digital_twin(
        self,
        device_id: str,
        trace_id: str,
        metric: str,
        value: float,
        sent_at: datetime,
    ) -> AsyncIterator[PhaseEmission]:
        provider = self.context.providers.get("layer_4_provider")
        if not provider:
            yield PhaseEmission(
                event=self._phase_event(
                    3,
                    "Twin Projection",
                    "skip",
                    reason="L4 not configured",
                )
            )
            yield PhaseEmission(outcome=PhaseOutcome(status="skip", skipped=1))
            return

        yield PhaseEmission(
            event=self._phase_event(
                3,
                "Twin Projection",
                "running",
                timeout=PHASE_3_TIMEOUT,
            )
        )
        result = await asyncio.to_thread(
            self._probe_digital_twin,
            provider,
            device_id,
            trace_id,
            metric,
            value,
            sent_at,
        )
        if result.success:
            detail = result.evidence.get("entity") or result.evidence.get("twin_id")
            yield PhaseEmission(
                event=self._log_event(
                    f"Telemetry projection reached the digital twin ({result.elapsed}s)",
                    detail=detail,
                    status="pass",
                )
            )
            yield PhaseEmission(
                event=self._phase_event(
                    3,
                    "Twin Projection",
                    "pass",
                    elapsed=result.elapsed,
                    evidence_kind=result.evidence.get("kind"),
                )
            )
            yield PhaseEmission(
                outcome=PhaseOutcome(
                    status="pass",
                    passed=1,
                    evidence={
                        "phase": 3,
                        "kind": result.evidence.get("kind", "twin_projection"),
                        "provider": provider,
                        "correlation": result.evidence.get("correlation"),
                    },
                )
            )
            return

        yield PhaseEmission(
            event=self._log_event(
                "Telemetry projection verification failed",
                detail=result.error,
                status="fail",
            )
        )
        yield PhaseEmission(event=self._phase_event(3, "Twin Projection", "fail"))
        yield PhaseEmission(
            outcome=PhaseOutcome(
                status="fail",
                failed=1,
                failed_phase="Phase 3 - Twin Projection",
            )
        )

    def _probe_digital_twin(
        self,
        provider: str,
        device_id: str,
        trace_id: str,
        metric: str,
        value: float,
        sent_at: datetime,
    ) -> ProbeResult:
        outputs = self.context.terraform_outputs
        if provider == "aws":
            bundle = outputs.get("aws_component_twin_state_output")
            workspace_id = (
                bundle.get("workspace_id") if isinstance(bundle, dict) else None
            )
            if not workspace_id:
                return ProbeResult(
                    success=False, error="TwinMaker workspace ID missing"
                )
            return probes.check_twinmaker_projection(
                workspace_id,
                device_id,
                metric,
                value,
                trace_id,
                sent_at,
                PHASE_3_TIMEOUT,
                PHASE_3_POLL_INTERVAL,
                aws_region=outputs.get("aws_region"),
                aws_credentials=self.context.credentials.get("aws", {}),
            )
        if provider == "azure":
            bundle = outputs.get("azure_component_twin_state_output")
            endpoint = bundle.get("endpoint") if isinstance(bundle, dict) else None
            if not endpoint:
                return ProbeResult(success=False, error="ADT endpoint missing")
            return probes.check_adt_twin(
                endpoint,
                self.context.credentials.get("azure", {}),
                device_id,
                PHASE_3_TIMEOUT,
                PHASE_3_POLL_INTERVAL,
                expected_source_sequence=trace_id,
            )
        if provider in {"google", "gcp"}:
            return probes.check_gcp_twin_projection(
                device_id,
                trace_id,
                self.context.terraform_outputs,
                self.context.credentials.get("gcp", {}),
                self.context.project_path,
                PHASE_3_TIMEOUT,
                PHASE_3_POLL_INTERVAL,
            )
        return ProbeResult(
            success=False,
            error=f"L4 provider {provider} is not supported for verification",
        )

    async def _terminal_skip(
        self,
        summary: VerificationSummary,
        started: float,
        trace_id: str,
        phases: tuple[int, ...],
    ) -> AsyncIterator[str]:
        names = {
            2: "Pipeline to Hot Storage",
            3: "Twin Projection",
        }
        for phase in phases:
            summary.skipped += 1
            yield self._phase_event(
                phase,
                names[phase],
                "skip",
                reason="Previous required phase failed",
            )
        yield self._done_event(summary, started, trace_id)

    def _done_event(
        self,
        summary: VerificationSummary,
        started: float,
        trace_id: str,
    ) -> str:
        return sse_event(
            "done",
            {
                "schema_version": "telemetry-verification.v1",
                "trace_id": trace_id,
                "status": "pass" if summary.failed == 0 else "fail",
                "pass_count": summary.passed,
                "fail_count": summary.failed,
                "skip_count": summary.skipped,
                "total_time": round(time.monotonic() - started, 1),
                "failed_phase": summary.failed_phase,
                "evidence": summary.evidence,
                "hints": [],
            },
        )

    @staticmethod
    def _verification_measurement(payload: dict) -> tuple[str, float]:
        raw_value = payload.get("value")
        if raw_value is None:
            raw_value = next(
                (
                    candidate
                    for key, candidate in payload.items()
                    if key not in {"iotDeviceId", "time"}
                    and isinstance(candidate, (int, float))
                    and not isinstance(candidate, bool)
                    and math.isfinite(float(candidate))
                ),
                21.0,
            )
        if (
            isinstance(raw_value, bool)
            or not isinstance(raw_value, (int, float))
            or not math.isfinite(float(raw_value))
        ):
            raw_value = 21.0
        return "value", float(raw_value)

    @staticmethod
    def _phase_event(
        phase: int,
        name: str,
        status: str,
        **details,
    ) -> str:
        return sse_event(
            "phase",
            {
                "phase": phase,
                "name": name,
                "status": status,
                "timestamp": display_timestamp(),
                **details,
            },
        )

    @staticmethod
    def _log_event(
        message: str,
        *,
        detail: str | None = None,
        status: str | None = None,
    ) -> str:
        payload = {"timestamp": display_timestamp(), "message": message}
        if detail:
            payload["detail"] = detail
        if status:
            payload["status"] = status
        return sse_event("log", payload)
