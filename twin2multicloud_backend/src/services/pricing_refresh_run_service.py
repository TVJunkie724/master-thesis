"""Pricing refresh run orchestration owned by the Management API."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, cast

from sqlalchemy.orm import Session

from src.clients.optimizer_client import OptimizerClient
from src.models.cloud_connection import CloudConnection
from src.models.pricing_refresh_run import PricingRefreshRun
from src.schemas.cloud_access import CloudAccessProvider
from src.schemas.pricing_refresh import (
    PricingRefreshCredentialSummary,
    PricingRefreshRunResponse,
    PricingRefreshStartRequest,
)
from src.services.cloud_connection_service import CloudConnectionService
from src.services.errors import (
    ExternalServiceError,
    ExternalServiceUnavailable,
    PricingRefreshConnectionNotFound,
    PricingRefreshRequestError,
    PricingRefreshRunNotFound,
)


PROVIDERS: set[str] = {"aws", "azure", "gcp"}
SENSITIVE_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "private_key",
    "credential",
    "credentials",
    "access_key",
)
MAX_RESULT_SUMMARY_ITEMS = 200
MAX_RESULT_SUMMARY_TEXT_LENGTH = 500


class PricingRefreshRunService:
    """Creates and reads typed pricing refresh runs without exposing secrets."""

    def __init__(self, db: Session, optimizer_client: OptimizerClient | None = None):
        self.db = db
        self.optimizer_client = optimizer_client or OptimizerClient()
        self.cloud_connections = CloudConnectionService(db)

    async def create_run(
        self,
        provider: str,
        user_id: str,
        request: PricingRefreshStartRequest,
    ) -> PricingRefreshRun:
        provider = _provider(provider)
        connection = self._resolve_connection(provider, user_id, request)
        credential_summary = self._credential_summary(provider, connection)
        now = datetime.now(timezone.utc)

        run = PricingRefreshRun(
            user_id=user_id,
            provider=provider,
            status="running",
            pricing_connection_id=connection.id if connection else None,
            force=request.force,
            credential_summary_json=_json_dumps(credential_summary.model_dump()),
            created_at=now,
            started_at=now,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            payload = self._optimizer_payload(provider, connection, user_id)
            result = await self.optimizer_client.refresh_pricing(
                provider,
                credentials=payload,
                force_fetch=request.force,
            )
            run.status = "succeeded"
            run.result_summary_json = _json_dumps(_safe_result_summary(result))
            if connection is not None:
                self.cloud_connections.record_successful_use(connection)
        except ExternalServiceUnavailable:
            run.status = "failed"
            run.error_code = "OPTIMIZER_UNAVAILABLE"
            run.error_message = "Optimizer service is unavailable."
        except ExternalServiceError:
            run.status = "failed"
            run.error_code = "OPTIMIZER_ERROR"
            run.error_message = "Optimizer service returned an error."
        except ValueError:
            run.status = "failed"
            run.error_code = "PRICING_CREDENTIAL_UNREADABLE"
            run.error_message = "Pricing credential payload cannot be read."

        run.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_run(self, refresh_run_id: str, user_id: str) -> PricingRefreshRun:
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

    def to_response(self, run: PricingRefreshRun) -> PricingRefreshRunResponse:
        return PricingRefreshRunResponse(
            refresh_run_id=run.id,
            provider=cast(CloudAccessProvider, run.provider),
            status=run.status,
            credential_summary=PricingRefreshCredentialSummary(
                **(_json_loads(run.credential_summary_json) or {})
            ),
            force=bool(run.force),
            sse_url=f"/optimizer/pricing-refresh/runs/{run.id}/stream",
            result_summary=_json_loads(run.result_summary_json),
            error_code=run.error_code,
            error_message=run.error_message,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )

    def _resolve_connection(
        self,
        provider: CloudAccessProvider,
        user_id: str,
        request: PricingRefreshStartRequest,
    ) -> CloudConnection | None:
        if provider == "azure":
            if request.pricing_connection_id:
                raise PricingRefreshRequestError(
                    "Azure pricing uses the public Retail Prices API; omit pricing_connection_id."
                )
            return None

        if not request.pricing_connection_id:
            raise PricingRefreshRequestError(
                f"{provider.upper()} pricing refresh requires an explicitly confirmed CloudConnection."
            )

        connection = self.cloud_connections.get_connection(
            request.pricing_connection_id,
            user_id,
        )
        if not connection:
            raise PricingRefreshConnectionNotFound("Cloud connection not found")
        if connection.provider != provider:
            raise PricingRefreshRequestError(
                "Selected CloudConnection provider does not match the requested pricing provider."
            )
        if connection.purpose != "pricing":
            raise PricingRefreshRequestError(
                "Selected CloudConnection is not configured for pricing access."
            )
        if connection.validation_status != "valid":
            raise PricingRefreshRequestError(
                "Selected pricing CloudConnection must be validated before refresh."
            )
        return connection

    def _credential_summary(
        self,
        provider: CloudAccessProvider,
        connection: CloudConnection | None,
    ) -> PricingRefreshCredentialSummary:
        if provider == "azure":
            return PricingRefreshCredentialSummary(
                connection_id=None,
                identity_label="Azure Retail Prices API",
                scope="public",
            )

        cloud_scope = _json_loads(connection.cloud_scope if connection else None) or {}
        return PricingRefreshCredentialSummary(
            connection_id=connection.id if connection else None,
            identity_label=connection.display_name if connection else f"{provider.upper()} pricing access",
            scope="user",
            provider_account_id=_string_or_none(cloud_scope.get("account_id")),
            provider_project_id=_string_or_none(cloud_scope.get("project_id")),
            provider_subscription_id=_string_or_none(cloud_scope.get("subscription_id")),
        )

    def _optimizer_payload(
        self,
        provider: CloudAccessProvider,
        connection: CloudConnection | None,
        user_id: str,
    ) -> dict[str, Any]:
        if provider == "azure":
            return {}
        if connection is None:
            raise PricingRefreshRequestError("Pricing CloudConnection is required.")

        payload = self.cloud_connections.build_optimizer_credentials(connection, user_id)
        if provider != "gcp":
            return payload
        return {
            key: value
            for key, value in {
                "gcp_service_account_json": payload.get("gcp_credentials_file"),
                "gcp_project_id": payload.get("gcp_project_id"),
                "gcp_billing_account": payload.get("gcp_billing_account"),
                "gcp_region": payload.get("gcp_region"),
            }.items()
            if value
        }


def _provider(value: str) -> CloudAccessProvider:
    normalized = value.lower().strip()
    if normalized == "google":
        normalized = "gcp"
    if normalized not in PROVIDERS:
        raise PricingRefreshRequestError("Invalid provider. Use: aws, azure, gcp.")
    return cast(CloudAccessProvider, normalized)


def _safe_result_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, Any] = {}
    for key, raw in list(value.items())[:MAX_RESULT_SUMMARY_ITEMS]:
        if _is_sensitive_key(str(key)):
            continue
        result[str(key)] = _safe_value(raw)
    return result


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _safe_result_summary(value)
    if isinstance(value, list):
        return [_safe_value(item) for item in value[:MAX_RESULT_SUMMARY_ITEMS]]
    if isinstance(value, str):
        if len(value) > MAX_RESULT_SUMMARY_TEXT_LENGTH:
            return value[:MAX_RESULT_SUMMARY_TEXT_LENGTH] + "..."
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _json_loads(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
