"""Four-phase data-flow verification orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
import time
import uuid

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
PHASE_4_TIMEOUT = 60
PHASE_4_POLL_INTERVAL = 5
EVENT_CHECKER_TRACE_MARKER = "T2MC_EVENT_CHECKER_RECEIVED"


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
        send_payload = {
            **payload,
            "trace_id": trace_id,
            "time": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
        }

        phase_one = _PhaseRun(self._phase_message_delivery(send_payload, trace_id))
        async for event in phase_one.events():
            yield event
        phase_one_outcome = phase_one.require_outcome()
        summary.include(phase_one_outcome)
        if phase_one_outcome.failed:
            async for event in self._terminal_skip(summary, started, (2, 3, 4)):
                yield event
            return

        phase_two = _PhaseRun(
            self._phase_hot_storage(payload["iotDeviceId"], trace_id)
        )
        async for event in phase_two.events():
            yield event
        phase_two_outcome = phase_two.require_outcome()
        summary.include(phase_two_outcome)
        if phase_two_outcome.failed:
            async for event in self._terminal_skip(summary, started, (3, 4)):
                yield event
            return

        phase_three = _PhaseRun(
            self._phase_digital_twin(payload["iotDeviceId"])
        )
        async for event in phase_three.events():
            yield event
        summary.include(phase_three.require_outcome())

        phase_four = _PhaseRun(self._phase_event_flow(trace_id))
        async for event in phase_four.events():
            yield event
        summary.include(phase_four.require_outcome())
        yield self._done_event(summary, started)

    async def _phase_message_delivery(
        self,
        payload: dict,
        trace_id: str,
    ) -> AsyncIterator[PhaseEmission]:
        provider = self.context.providers["layer_1_provider"]
        yield PhaseEmission(
            event=self._phase_event(1, "Message Delivery", "running")
        )
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
        )
        if success:
            yield PhaseEmission(
                event=self._log_event(
                    f"Message sent successfully (trace: {trace_id})",
                    status="pass",
                )
            )
            yield PhaseEmission(
                event=self._phase_event(1, "Message Delivery", "pass")
            )
            yield PhaseEmission(outcome=PhaseOutcome(status="pass", passed=1))
            return

        yield PhaseEmission(
            event=self._log_event("Failed to send test message", status="fail")
        )
        yield PhaseEmission(
            event=self._phase_event(1, "Message Delivery", "fail")
        )
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
        url = probes.hot_reader_url(provider, self.context.terraform_outputs)
        yield PhaseEmission(
            event=self._phase_event(
                2,
                "Pipeline to Hot Storage",
                "running",
                timeout=PHASE_2_TIMEOUT,
            )
        )
        if not url:
            yield PhaseEmission(
                event=self._log_event(
                    f"No hot-reader URL found for {provider}",
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
            return

        started = time.monotonic()
        result = ProbeResult(success=False, error="not started")
        while time.monotonic() - started < PHASE_2_TIMEOUT:
            remaining = PHASE_2_TIMEOUT - (time.monotonic() - started)
            result = await asyncio.to_thread(
                probes.poll_hot_reader,
                url,
                device_id,
                self.context.terraform_outputs.get("inter_cloud_token"),
                min(20, remaining),
                PHASE_2_POLL_INTERVAL,
                trace_id=trace_id,
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
            yield PhaseEmission(outcome=PhaseOutcome(status="pass", passed=1))
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
    ) -> AsyncIterator[PhaseEmission]:
        provider = self.context.providers.get("layer_4_provider")
        if not provider:
            yield PhaseEmission(
                event=self._phase_event(
                    3,
                    "Digital Twin Readiness",
                    "skip",
                    reason="L4 not configured",
                )
            )
            yield PhaseEmission(outcome=PhaseOutcome(status="skip", skipped=1))
            return

        yield PhaseEmission(
            event=self._phase_event(
                3,
                "Digital Twin Readiness",
                "running",
                timeout=PHASE_3_TIMEOUT,
            )
        )
        result = await asyncio.to_thread(
            self._probe_digital_twin,
            provider,
            device_id,
        )
        if result.success:
            detail = result.evidence.get("entity") or result.evidence.get("twin_id")
            yield PhaseEmission(
                event=self._log_event(
                    f"Digital twin is addressable ({result.elapsed}s)",
                    detail=detail,
                    status="pass",
                )
            )
            yield PhaseEmission(
                event=self._phase_event(
                    3,
                    "Digital Twin Readiness",
                    "pass",
                    elapsed=result.elapsed,
                    evidence_kind=result.evidence.get("kind"),
                )
            )
            yield PhaseEmission(outcome=PhaseOutcome(status="pass", passed=1))
            return

        yield PhaseEmission(
            event=self._log_event(
                "Digital twin readiness verification failed",
                detail=result.error,
                status="fail",
            )
        )
        yield PhaseEmission(
            event=self._phase_event(3, "Digital Twin Readiness", "fail")
        )
        yield PhaseEmission(
            outcome=PhaseOutcome(
                status="fail",
                failed=1,
                failed_phase="Phase 3 - Digital Twin Readiness",
            )
        )

    def _probe_digital_twin(self, provider: str, device_id: str) -> ProbeResult:
        outputs = self.context.terraform_outputs
        if provider == "aws":
            workspace_id = outputs.get("aws_twinmaker_workspace_id")
            if not workspace_id:
                return ProbeResult(success=False, error="TwinMaker workspace ID missing")
            return probes.check_twinmaker_entity(
                workspace_id,
                device_id,
                PHASE_3_TIMEOUT,
                PHASE_3_POLL_INTERVAL,
                aws_region=outputs.get("aws_region"),
                aws_credentials=self.context.credentials.get("aws", {}),
            )
        if provider == "azure":
            endpoint = outputs.get("azure_adt_endpoint")
            if not endpoint:
                return ProbeResult(success=False, error="ADT endpoint missing")
            return probes.check_adt_twin(
                endpoint,
                self.context.credentials.get("azure", {}),
                device_id,
                PHASE_3_TIMEOUT,
                PHASE_3_POLL_INTERVAL,
            )
        return ProbeResult(
            success=False,
            error=f"L4 provider {provider} is not supported for verification",
        )

    async def _phase_event_flow(
        self,
        trace_id: str,
    ) -> AsyncIterator[PhaseEmission]:
        if not self.context.optimization.get("useEventChecking", False):
            yield PhaseEmission(
                event=self._phase_event(
                    4,
                    "Event Flow",
                    "skip",
                    reason="Event checking not configured",
                )
            )
            yield PhaseEmission(outcome=PhaseOutcome(status="skip", skipped=1))
            return

        yield PhaseEmission(event=self._phase_event(4, "Event Flow", "running"))
        provider = self.context.providers.get("layer_2_provider", "aws")
        result = await asyncio.to_thread(
            probes.check_cloud_logs,
            provider,
            f"{EVENT_CHECKER_TRACE_MARKER} trace_id={trace_id}",
            "event_checker",
            self.context.terraform_outputs,
            self.context.credentials,
            self.context.project_path,
            PHASE_4_TIMEOUT,
            PHASE_4_POLL_INTERVAL,
        )
        downstream_steps = self._configured_downstream_steps()
        skipped = len(downstream_steps)
        for step in downstream_steps:
            yield PhaseEmission(
                event=self._log_event(
                    f"{step}: no trace-correlation contract; diagnostic check skipped",
                    status="skip",
                )
            )

        if result.success:
            yield PhaseEmission(
                event=self._log_event(
                    f"Event-Checker invocation observed ({result.elapsed}s)",
                    status="pass",
                )
            )
            yield PhaseEmission(
                event=self._phase_event(4, "Event Flow", "pass")
            )
            yield PhaseEmission(
                outcome=PhaseOutcome(
                    status="pass",
                    passed=1,
                    skipped=skipped,
                )
            )
            return

        yield PhaseEmission(
            event=self._log_event(
                "Event-Checker evidence unavailable",
                detail=result.error,
                status="fail",
            )
        )
        yield PhaseEmission(event=self._phase_event(4, "Event Flow", "fail"))
        yield PhaseEmission(
            outcome=PhaseOutcome(
                status="fail",
                failed=1,
                skipped=skipped,
                failed_phase="Phase 4 - Event-Checker",
            )
        )

    def _configured_downstream_steps(self) -> list[str]:
        steps = []
        action_types = {
            event.get("action", {}).get("type")
            for event in self.context.events
        }
        if action_types & {"lambda", "function", "cloud_function"}:
            steps.append("Action Function")
        if self.context.optimization.get("triggerNotificationWorkflow", False):
            steps.append("Workflow")
        if self.context.optimization.get("returnFeedbackToDevice", False):
            steps.append("Feedback")
        return steps

    async def _terminal_skip(
        self,
        summary: VerificationSummary,
        started: float,
        phases: tuple[int, ...],
    ) -> AsyncIterator[str]:
        names = {
            2: "Pipeline to Hot Storage",
            3: "Digital Twin Readiness",
            4: "Event Flow",
        }
        for phase in phases:
            summary.skipped += 1
            yield self._phase_event(
                phase,
                names[phase],
                "skip",
                reason="Previous required phase failed",
            )
        yield self._done_event(summary, started)

    def _done_event(self, summary: VerificationSummary, started: float) -> str:
        return sse_event(
            "done",
            {
                "pass_count": summary.passed,
                "fail_count": summary.failed,
                "skip_count": summary.skipped,
                "total_time": round(time.monotonic() - started, 1),
                "failed_phase": summary.failed_phase,
                "hints": (
                    probes.cloud_log_hints(self.context.providers)
                    if summary.failed
                    else []
                ),
            },
        )

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
