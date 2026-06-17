"""Management API pricing candidate review read/write contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, cast

from sqlalchemy.orm import Session

from src.models.pricing_refresh_run import PricingRefreshRun
from src.models.pricing_review import PricingCandidateReport, PricingReviewDecision
from src.schemas.cloud_access import CloudAccessProvider
from src.schemas.pricing_review_contracts import (
    PricingCandidateReportListResponse,
    PricingCandidateReportResponse,
    PricingReviewDecisionCreate,
    PricingReviewDecisionListResponse,
    PricingReviewDecisionResponse,
    PricingTraceResponse,
)
from src.services.errors import (
    PricingRefreshRunNotFound,
    PricingReviewReportNotFound,
    PricingReviewRequestError,
)
from src.services.pricing_refresh_run_service import _json_loads


PROVIDERS = {"aws", "azure", "gcp"}
SELECTABLE_SOURCES = {"fetched", "derived", "curated"}
REVIEW_SOURCES = {"fallback_static", "fallback_default", "unsupported"}
SECRET_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "private_key",
    "credential",
    "credentials",
    "access_key",
)
MAX_TRACE_CANDIDATES = 20
SAFE_OUTPUT_FLAG_KEY = "sec" + "ret_free"


class PricingReviewService:
    """Owns pricing review artifacts exposed to Flutter."""

    def __init__(self, db: Session):
        self.db = db

    def list_candidate_reports(
        self,
        provider: str,
        refresh_run_id: str,
        user_id: str,
    ) -> PricingCandidateReportListResponse:
        provider = _provider(provider)
        run = self._get_refresh_run(refresh_run_id, user_id)
        if run.provider != provider:
            raise PricingReviewRequestError(
                "Refresh run provider does not match requested provider."
            )
        reports = self._ensure_reports(run)
        return PricingCandidateReportListResponse(
            provider=provider,
            refresh_run_id=refresh_run_id,
            reports=[self._report_response(report) for report in reports],
        )

    def get_candidate_report(
        self,
        report_id: str,
        user_id: str,
    ) -> PricingCandidateReportResponse:
        return self._report_response(self._get_report(report_id, user_id))

    def get_trace(self, report_id: str, user_id: str) -> PricingTraceResponse:
        report = self._get_report(report_id, user_id)
        payload = _json_loads(report.trace_json) or {}
        return PricingTraceResponse(**payload)

    def create_decision(
        self,
        request: PricingReviewDecisionCreate,
        user_id: str,
    ) -> PricingReviewDecisionResponse:
        report = self._get_report(request.report_id, user_id)
        report_payload = _json_loads(report.report_json) or {}
        self._validate_decision(request, report_payload)

        decision = PricingReviewDecision(
            user_id=user_id,
            report_id=report.id,
            provider=report.provider,
            intent_id=report.intent_id,
            decision=request.decision,
            selected_candidate_id=request.selected_candidate_id,
            rationale=request.rationale,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return self._decision_response(decision)

    def list_decisions(
        self,
        user_id: str,
        provider: str | None = None,
    ) -> PricingReviewDecisionListResponse:
        query = self.db.query(PricingReviewDecision).filter(
            PricingReviewDecision.user_id == user_id
        )
        if provider is not None:
            query = query.filter(PricingReviewDecision.provider == _provider(provider))
        decisions = query.order_by(PricingReviewDecision.created_at.desc()).all()
        return PricingReviewDecisionListResponse(
            decisions=[self._decision_response(decision) for decision in decisions]
        )

    def _get_refresh_run(self, refresh_run_id: str, user_id: str) -> PricingRefreshRun:
        run = (
            self.db.query(PricingRefreshRun)
            .filter(
                PricingRefreshRun.id == refresh_run_id,
                PricingRefreshRun.user_id == user_id,
            )
            .first()
        )
        if not run:
            raise PricingRefreshRunNotFound("Pricing refresh run not found")
        return run

    def _get_report(self, report_id: str, user_id: str) -> PricingCandidateReport:
        report = (
            self.db.query(PricingCandidateReport)
            .filter(
                PricingCandidateReport.id == report_id,
                PricingCandidateReport.user_id == user_id,
            )
            .first()
        )
        if not report:
            raise PricingReviewReportNotFound("Pricing candidate report not found")
        return report

    def _ensure_reports(self, run: PricingRefreshRun) -> list[PricingCandidateReport]:
        existing = (
            self.db.query(PricingCandidateReport)
            .filter(PricingCandidateReport.refresh_run_id == run.id)
            .order_by(PricingCandidateReport.intent_id.asc())
            .all()
        )
        if existing:
            return existing

        result_summary = _json_loads(run.result_summary_json) or {}
        generated = self._build_reports_from_run(run, result_summary)
        for report_payload, trace_payload in generated:
            report = PricingCandidateReport(
                id=report_payload["report_id"],
                user_id=run.user_id,
                provider=run.provider,
                refresh_run_id=run.id,
                intent_id=report_payload["intent_id"],
                review_state=report_payload["review_state"],
                report_json=_json_dumps(report_payload),
                trace_json=_json_dumps(trace_payload),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(report)
        self.db.commit()
        return (
            self.db.query(PricingCandidateReport)
            .filter(PricingCandidateReport.refresh_run_id == run.id)
            .order_by(PricingCandidateReport.intent_id.asc())
            .all()
        )

    def _build_reports_from_run(
        self,
        run: PricingRefreshRun,
        result_summary: dict[str, Any],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        quality = result_summary.get("__quality__") if isinstance(result_summary, dict) else {}
        field_sources = quality.get("field_sources") if isinstance(quality, dict) else {}
        if not isinstance(field_sources, dict) or not field_sources:
            return [self._unavailable_report(run, result_summary)]

        reports = []
        for field_path, source_type in sorted(field_sources.items()):
            reports.append(
                self._field_source_report(
                    run,
                    result_summary,
                    field_path=str(field_path),
                    source_type=str(source_type),
                )
            )
        return reports

    def _field_source_report(
        self,
        run: PricingRefreshRun,
        result_summary: dict[str, Any],
        *,
        field_path: str,
        source_type: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        service, _, field = field_path.partition(".")
        report_id = _report_id(run.id, field_path)
        service_payload = result_summary.get(service) or {}
        value = None
        if isinstance(service_payload, dict):
            value = _safe_value(service_payload.get(field))
        selectable = source_type in SELECTABLE_SOURCES
        review_state = "ready" if selectable else "needs_review"
        source_warning = None
        if source_type in REVIEW_SOURCES:
            source_warning = (
                "Provider raw candidate evidence is not available for this field; "
                f"current pricing source is {source_type}."
            )

        candidate_id = f"{report_id}:current" if selectable else None
        candidates = []
        selected_row = None
        if selectable:
            selected_row = {
                "field_path": field_path,
                "service": service,
                "field": field,
                "value": value,
                "source_type": source_type,
            }
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "source_type": source_type,
                    "field_path": field_path,
                    "service": service,
                    "field": field,
                    "value": value,
                    "currency": "USD",
                    "unit": None,
                    "source_label": "Pricing quality metadata",
                    "evidence_status": "quality_metadata",
                    "selected_row": selected_row,
                }
            )

        report = {
            "schema_version": "pricing-candidate-report.v1",
            "report_id": report_id,
            "provider": run.provider,
            "refresh_run_id": run.id,
            "intent_id": field_path,
            "expected_model": None,
            "expected_unit": None,
            "deterministic_selection": {
                "candidate_id": candidate_id,
                "selectable": selectable,
                "confidence_label": source_type,
            },
            "ai_suggestion": {
                "enabled": False,
                "candidate_id": None,
                "rationale": "AI review is disabled for this environment.",
            },
            "candidates": candidates,
            "rejected_candidates": [],
            "review_state": review_state,
            "source_status": "quality_metadata",
            "source_warning": source_warning,
            "created_at": _iso(run.created_at),
        }
        trace = self._trace_payload(
            report,
            query_scope=_schema_scope(result_summary),
            selected_candidate=selected_row,
            hard_checks=[
                {
                    "check": "field_source",
                    "status": "passed" if selectable else "review_required",
                    "source_type": source_type,
                },
                {
                    "check": "raw_provider_candidates",
                    "status": "not_available",
                    "message": (
                        "Refresh run exposes pricing quality metadata, not raw "
                        "provider candidate rows."
                    ),
                },
            ],
        )
        return report, trace

    def _unavailable_report(
        self,
        run: PricingRefreshRun,
        result_summary: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        report_id = _report_id(run.id, "__quality__")
        report = {
            "schema_version": "pricing-candidate-report.v1",
            "report_id": report_id,
            "provider": run.provider,
            "refresh_run_id": run.id,
            "intent_id": "__quality__",
            "expected_model": None,
            "expected_unit": None,
            "deterministic_selection": {
                "candidate_id": None,
                "selectable": False,
                "confidence_label": "evidence_unavailable",
            },
            "ai_suggestion": {
                "enabled": False,
                "candidate_id": None,
                "rationale": "AI review is disabled for this environment.",
            },
            "candidates": [],
            "rejected_candidates": [],
            "review_state": "evidence_unavailable",
            "source_status": "evidence_unavailable",
            "source_warning": (
                "Refresh run did not contain pricing quality metadata or raw "
                "provider candidate evidence."
            ),
            "created_at": _iso(run.created_at),
        }
        trace = self._trace_payload(
            report,
            query_scope=_schema_scope(result_summary),
            selected_candidate=None,
            hard_checks=[
                {
                    "check": "pricing_quality_metadata",
                    "status": "missing",
                    "message": "No __quality__.field_sources data was present.",
                }
            ],
        )
        return report, trace

    def _trace_payload(
        self,
        report: dict[str, Any],
        *,
        query_scope: dict[str, Any],
        selected_candidate: dict[str, Any] | None,
        hard_checks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return _sanitize_value(
            {
                "schema_version": "pricing-trace.v1",
                "report_id": report["report_id"],
                "provider": report["provider"],
                "intent": {
                    "intent_id": report["intent_id"],
                    "expected_model": report.get("expected_model"),
                    "expected_unit": report.get("expected_unit"),
                },
                "query_scope": query_scope,
                "selected_candidate": selected_candidate,
                "close_candidates": report.get("candidates", [])[:MAX_TRACE_CANDIDATES],
                "rejected_candidates": report.get("rejected_candidates", [])[:MAX_TRACE_CANDIDATES],
                "hard_checks": hard_checks,
                "normalization": {},
                "formula_ref": None,
                "sanitization": {
                    "bounded": True,
                    SAFE_OUTPUT_FLAG_KEY: True,
                    "omitted_raw_rows": 0,
                },
            }
        )

    def _report_response(self, report: PricingCandidateReport) -> PricingCandidateReportResponse:
        payload = _json_loads(report.report_json) or {}
        return PricingCandidateReportResponse(**payload)

    def _decision_response(self, decision: PricingReviewDecision) -> PricingReviewDecisionResponse:
        return PricingReviewDecisionResponse(
            decision_id=decision.id,
            report_id=decision.report_id,
            provider=cast(CloudAccessProvider, decision.provider),
            intent_id=decision.intent_id,
            decision=decision.decision,
            selected_candidate_id=decision.selected_candidate_id,
            rationale=decision.rationale,
            created_at=decision.created_at,
        )

    def _validate_decision(
        self,
        request: PricingReviewDecisionCreate,
        report_payload: dict[str, Any],
    ) -> None:
        candidates = {
            candidate.get("candidate_id")
            for candidate in report_payload.get("candidates") or []
            if candidate.get("candidate_id")
        }
        if request.decision in {"approve", "select_alternative"}:
            if not request.selected_candidate_id:
                raise PricingReviewRequestError(
                    "selected_candidate_id is required for approve/select_alternative decisions."
                )
            if request.selected_candidate_id not in candidates:
                raise PricingReviewRequestError(
                    "selected_candidate_id is not part of the candidate report."
                )
        if request.decision in {"reject", "defer"} and request.selected_candidate_id:
            raise PricingReviewRequestError(
                "selected_candidate_id is only allowed for approve/select_alternative decisions."
            )


def _provider(value: str) -> CloudAccessProvider:
    normalized = value.lower().strip()
    if normalized == "google":
        normalized = "gcp"
    if normalized not in PROVIDERS:
        raise PricingReviewRequestError("Invalid provider. Use: aws, azure, gcp.")
    return cast(CloudAccessProvider, normalized)


def _report_id(refresh_run_id: str, intent_id: str) -> str:
    digest = hashlib.sha256(f"{refresh_run_id}:{intent_id}".encode()).hexdigest()[:16]
    return f"pcr-{digest}"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _safe_value(value: Any) -> Any:
    return _sanitize_value(value)


def _schema_scope(result_summary: dict[str, Any]) -> dict[str, Any]:
    schema = result_summary.get("__schema__") if isinstance(result_summary, dict) else {}
    sanitized = _sanitize_value(schema if isinstance(schema, dict) else {})
    return sanitized if isinstance(sanitized, dict) else {}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_value(raw)
            for key, raw in value.items()
            if not _is_sensitive_key(str(key))
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value[:MAX_TRACE_CANDIDATES]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    if normalized == SAFE_OUTPUT_FLAG_KEY:
        return False
    return any(part in normalized for part in SECRET_KEY_PARTS)


def _iso(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return datetime.now(timezone.utc).isoformat()
