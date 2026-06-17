"""Secret-free provider access inventory for Flutter read models."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import cast

from sqlalchemy.orm import Session, joinedload

from src.models.cloud_connection import CloudConnection
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.schemas.cloud_access import (
    CloudAccessEntry,
    CloudAccessInventoryResponse,
    CloudAccessProvider,
    CloudAccessProviderInventory,
    CloudAccessStatus,
)
from src.services.permission_sets import compare_permission_set_version


SUPPORTED_PROVIDERS: tuple[CloudAccessProvider, ...] = ("aws", "azure", "gcp")


@dataclass(frozen=True)
class ConnectionBindingSummary:
    count: int
    labels: list[str]


class CloudAccessInventoryService:
    """Builds UI-ready cloud access inventory without exposing credentials."""

    def __init__(self, db: Session):
        self._db = db

    def build_inventory(self, user_id: str) -> CloudAccessInventoryResponse:
        connections = self._list_connections(user_id)
        bindings = self._build_binding_index(user_id)

        providers = {
            provider: CloudAccessProviderInventory(
                provider=provider,
                pricing=self._pricing_entry(provider),
                deployment=[
                    self._deployment_entry(connection, bindings.get(connection.id))
                    for connection in connections
                    if connection.provider == provider
                ],
            )
            for provider in SUPPORTED_PROVIDERS
        }

        return CloudAccessInventoryResponse(providers=providers)

    def _list_connections(self, user_id: str) -> list[CloudConnection]:
        return (
            self._db.query(CloudConnection)
            .filter(CloudConnection.user_id == user_id)
            .order_by(CloudConnection.provider.asc(), CloudConnection.created_at.desc())
            .all()
        )

    def _build_binding_index(self, user_id: str) -> dict[str, ConnectionBindingSummary]:
        configs = (
            self._db.query(TwinConfiguration)
            .join(DigitalTwin, TwinConfiguration.twin_id == DigitalTwin.id)
            .options(joinedload(TwinConfiguration.twin))
            .filter(
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .all()
        )

        labels_by_connection: dict[str, set[str]] = defaultdict(set)
        for config in configs:
            twin_name = config.twin.name if config.twin else config.twin_id
            for connection_id in (
                config.aws_cloud_connection_id,
                config.azure_cloud_connection_id,
                config.gcp_cloud_connection_id,
            ):
                if connection_id:
                    labels_by_connection[connection_id].add(twin_name)

        return {
            connection_id: ConnectionBindingSummary(
                count=len(labels),
                labels=sorted(labels),
            )
            for connection_id, labels in labels_by_connection.items()
        }

    def _pricing_entry(self, provider: CloudAccessProvider) -> CloudAccessEntry:
        if provider == "azure":
            return CloudAccessEntry(
                connection_id=None,
                provider="azure",
                purpose="pricing",
                scope="public",
                identity_label="Azure Retail Prices API",
                status="active",
                is_default_for_pricing=True,
                actions=[],
                primary_message="Azure pricing uses the public Retail Prices API.",
            )

        return CloudAccessEntry(
            connection_id=None,
            provider=provider,
            purpose="pricing",
            scope="user",
            identity_label=f"{provider.upper()} pricing access not configured",
            status="missing",
            is_default_for_pricing=False,
            actions=["create_pricing_connection"],
            primary_message=(
                "No user-scoped pricing credential is configured for this provider."
            ),
        )

    def _deployment_entry(
        self,
        connection: CloudConnection,
        binding: ConnectionBindingSummary | None,
    ) -> CloudAccessEntry:
        provider = _provider(connection.provider)
        cloud_scope = _safe_json_object(connection.cloud_scope)
        permission_set = compare_permission_set_version(
            provider,
            connection.permission_set_version,
        )

        return CloudAccessEntry(
            connection_id=connection.id,
            provider=provider,
            purpose="deployment",
            scope="twin" if binding and binding.count > 0 else "user",
            identity_label=connection.display_name,
            status=_status_from_validation(connection.validation_status),
            provider_account_id=_string_or_none(cloud_scope.get("account_id")),
            provider_project_id=_string_or_none(cloud_scope.get("project_id")),
            provider_subscription_id=_string_or_none(cloud_scope.get("subscription_id")),
            is_default_for_pricing=False,
            last_validated_at=connection.last_validated_at,
            permission_set_status=permission_set.status,
            bound_twin_count=binding.count if binding else 0,
            bound_twin_labels=binding.labels if binding else [],
            actions=_deployment_actions(connection.validation_status, binding),
            primary_message=_deployment_message(connection, binding, permission_set.status),
        )


def _provider(value: str) -> CloudAccessProvider:
    if value not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported cloud provider in inventory: {value}")
    return cast(CloudAccessProvider, value)


def _safe_json_object(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _status_from_validation(validation_status: str | None) -> CloudAccessStatus:
    if validation_status == "valid":
        return "active"
    if validation_status == "invalid":
        return "invalid"
    return "needs_validation"


def _deployment_actions(
    validation_status: str | None,
    binding: ConnectionBindingSummary | None,
) -> list[str]:
    actions = ["validate"]
    if binding and binding.count > 0:
        actions.append("delete_blocked")
    else:
        actions.append("delete")
    if validation_status != "valid":
        actions.append("review_validation")
    return actions


def _deployment_message(
    connection: CloudConnection,
    binding: ConnectionBindingSummary | None,
    permission_set_status: str,
) -> str:
    if permission_set_status != "matched":
        return "Deployment permission set needs review before use."
    if connection.validation_status == "valid":
        if binding and binding.count > 0:
            return "Deployment access is valid and bound to one or more twins."
        return "Deployment access is valid and available."
    if connection.validation_status == "invalid":
        return connection.validation_message or "Deployment access validation failed."
    return "Deployment access has not been validated yet."


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
