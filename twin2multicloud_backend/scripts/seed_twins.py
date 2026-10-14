"""Seed one honest Six-layer draft for local PoC demonstrations.

The seed intentionally does not fabricate an Optimizer result, selected
architecture, or deployment-ready state. A live Optimizer run remains the only
way to create executable Six-layer architecture evidence.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

import httpx

from src.config import settings
from src.models.cloud_connection import CloudConnection
from src.models.database import SessionLocal
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.services.cloud_connection_service import CloudConnectionService
from src.utils.crypto import encrypt_scoped


SEED_USER_EMAIL = "seed@twin2multicloud.dev"
TWIN_DEFINITIONS = ({"name": "six-layer-poc-draft"},)
SIX_LAYER_SMALL_WORKLOAD = {
    "schemaVersion": "six-layer-workload.v1",
    "numberOfDevices": 100,
    "deviceSendingIntervalInMinutes": 2.0,
    "averageSizeOfMessageInKb": 0.25,
    "numberOfDeviceTypes": 1,
    "hotStorageDurationInMonths": 1,
    "coolStorageDurationInMonths": 3,
    "archiveStorageDurationInMonths": 12,
    "twinEntityCount": 100,
    "aggregateDashboardRefreshesPerHour": 12,
    "apiCallsPerAggregateDashboardRefresh": 1,
    "dashboardActiveHoursPerDay": 1,
    "monthlyEditorSeats": 2,
    "monthlyViewerSeats": 1,
    "twinStateMaterializationsPerSecond": 0.1,
    "twinGraphUpdatesPerSecond": 0.01,
    "eventingScenarioId": "eventing-small-v1",
    "currency": "USD",
}


def _or_none(value: str | None) -> str | None:
    return value or None


def _build_aws_payload(credentials: dict) -> dict | None:
    if not credentials.get("aws_access_key_id"):
        return None
    payload = {
        "aws_access_key_id": credentials["aws_access_key_id"],
        "aws_secret_access_key": credentials.get("aws_secret_access_key", ""),
        "aws_region": credentials.get("aws_region", "eu-central-1"),
    }
    if token := _or_none(credentials.get("aws_session_token")):
        payload["aws_session_token"] = token
    if region := _or_none(credentials.get("aws_sso_region")):
        payload["aws_sso_region"] = region
    return payload


def _build_azure_payload(credentials: dict) -> dict | None:
    if not credentials.get("azure_subscription_id"):
        return None
    region = credentials.get("azure_region", "westeurope")
    return {
        "azure_subscription_id": credentials["azure_subscription_id"],
        "azure_client_id": credentials.get("azure_client_id", ""),
        "azure_client_secret": credentials.get("azure_client_secret", ""),
        "azure_tenant_id": credentials.get("azure_tenant_id", ""),
        "azure_region": region,
        "azure_region_iothub": credentials.get("azure_region_iothub") or region,
        "azure_region_digital_twin": (
            credentials.get("azure_region_digital_twin") or region
        ),
    }


def _build_gcp_payload(credentials: dict, service_account: str | None) -> dict | None:
    if not service_account:
        return None
    payload = {
        "gcp_project_id": credentials.get("gcp_project_id", ""),
        "gcp_region": credentials.get("gcp_region", "europe-west1"),
        "gcp_credentials_file": service_account,
    }
    return {key: value for key, value in payload.items() if value}


def _cloud_scope(provider: str, payload: dict) -> dict:
    if provider == "aws":
        return {"region": payload.get("aws_region")}
    if provider == "azure":
        return {
            "subscription_configured": bool(payload.get("azure_subscription_id")),
            "region": payload.get("azure_region"),
            "iot_hub_region": payload.get("azure_region_iothub"),
            "digital_twin_region": payload.get("azure_region_digital_twin"),
        }
    return {
        "project_id": payload.get("gcp_project_id"),
        "region": payload.get("gcp_region"),
    }


def _create_seed_cloud_connections(
    db,
    user: User,
    payloads: dict[str, dict | None],
) -> dict[str, CloudConnection]:
    service = CloudConnectionService(db)
    auth_types = {
        "aws": "access_key",
        "azure": "service_principal",
        "gcp": "service_account_key",
    }
    connections: dict[str, CloudConnection] = {}
    for provider, payload in payloads.items():
        if not payload:
            continue
        connection_id = str(uuid.uuid4())
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        connection = CloudConnection(
            id=connection_id,
            user_id=user.id,
            provider=provider,
            display_name=f"Seed {provider.upper()} Cloud Connection",
            cloud_scope=json.dumps(_cloud_scope(provider, payload), sort_keys=True),
            auth_type=auth_types[provider],
            encrypted_payload=encrypt_scoped(payload_json, user.id, connection_id),
            payload_fingerprint=service.fingerprint_payload(provider, payload),
            validation_status="untested",
        )
        db.add(connection)
        connections[provider] = connection
    db.flush()
    return connections


def _bind_connections(
    config: TwinConfiguration,
    connections: dict[str, CloudConnection],
) -> None:
    for provider in ("aws", "azure", "gcp"):
        if connection := connections.get(provider):
            setattr(config, f"{provider}_cloud_connection_id", connection.id)


def _sync_non_secret_fields(
    config: TwinConfiguration,
    aws: dict,
    azure: dict,
    gcp: dict,
) -> None:
    config.aws_region = aws.get("aws_region", "eu-central-1")
    config.aws_sso_region = _or_none(aws.get("aws_sso_region"))
    config.azure_region = azure.get("azure_region", "westeurope")
    config.azure_region_iothub = _or_none(azure.get("azure_region_iothub"))
    config.azure_region_digital_twin = _or_none(azure.get("azure_region_digital_twin"))
    config.gcp_project_id = gcp.get("gcp_project_id", "")
    config.gcp_region = gcp.get("gcp_region", "europe-west1")


async def _validate_provider(provider: str, credentials: dict) -> tuple[bool, str]:
    """Verify one connection against both executable downstream services."""

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                responses = await asyncio.gather(
                    client.post(
                        f"{settings.OPTIMIZER_URL}/permissions/verify/{provider}",
                        json=credentials,
                    ),
                    client.post(
                        f"{settings.DEPLOYER_URL}/permissions/verify/{provider}",
                        json=credentials,
                    ),
                    return_exceptions=True,
                )
            messages: list[str] = []
            valid = True
            for name, response in zip(("Optimizer", "Deployer"), responses):
                if isinstance(response, Exception):
                    valid = False
                    messages.append(f"{name} unavailable")
                    continue
                data = response.json() if response.status_code == 200 else {}
                accepted = bool(data.get("valid") or data.get("status") == "valid")
                if not accepted:
                    valid = False
                    messages.append(f"{name} rejected credentials")
            return valid, "; ".join(messages) if messages else "Valid"
        except (httpx.ConnectError, httpx.RequestError):
            if attempt < 2:
                await asyncio.sleep(5)
                continue
            return False, "Credential verification services unavailable"
        except Exception:
            return False, "Credential verification failed"
    return False, "Credential verification failed"


async def seed_if_needed() -> None:
    """Create one non-executable Six-layer draft when seed data is enabled."""

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == SEED_USER_EMAIL).first():
            print("SEED: Seed data already exists, skipping.")
            return
        if settings.SEED_LEGACY_TWIN_CREDENTIALS:
            raise RuntimeError(
                "SEED_LEGACY_TWIN_CREDENTIALS is unsupported; use CloudConnections."
            )

        credentials_path = Path(settings.SEED_CREDENTIALS_FILE)
        if not credentials_path.exists():
            print(f"SEED: Credentials file not found at {credentials_path}; skipping.")
            return
        credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
        service_account_path = Path(settings.SEED_GCP_CREDENTIALS_FILE)
        service_account = (
            service_account_path.read_text(encoding="utf-8")
            if service_account_path.exists()
            else None
        )
        aws = credentials.get("aws", {})
        azure = credentials.get("azure", {})
        gcp = credentials.get("gcp", {})
        payloads = {
            "aws": _build_aws_payload(aws),
            "azure": _build_azure_payload(azure),
            "gcp": _build_gcp_payload(gcp, service_account),
        }

        user = User(
            id=str(uuid.uuid4()),
            email=SEED_USER_EMAIL,
            name="Seed User",
        )
        db.add(user)
        db.flush()
        connections = _create_seed_cloud_connections(db, user, payloads)

        twin_id = str(uuid.uuid4())
        twin = DigitalTwin(
            id=twin_id,
            user_id=user.id,
            name=TWIN_DEFINITIONS[0]["name"],
            state=TwinState.DRAFT,
        )
        config = TwinConfiguration(
            id=str(uuid.uuid4()),
            twin_id=twin_id,
            debug_mode=False,
            highest_step_reached=2,
        )
        _bind_connections(config, connections)
        _sync_non_secret_fields(config, aws, azure, gcp)
        db.add_all(
            [
                twin,
                config,
                OptimizerConfiguration(
                    id=str(uuid.uuid4()),
                    twin_id=twin_id,
                    params=json.dumps(SIX_LAYER_SMALL_WORKLOAD),
                ),
            ]
        )

        for provider, connection in connections.items():
            valid, message = await _validate_provider(
                provider, payloads[provider] or {}
            )
            connection.validation_status = "valid" if valid else "invalid"
            connection.validation_message = message
            connection.last_validated_at = datetime.now(timezone.utc)
            connection.updated_at = datetime.now(timezone.utc)
            setattr(config, f"{provider}_validated", valid)

        db.commit()
        print(
            "SEED: Created one Six-layer draft; run the Optimizer to make it executable."
        )
    except Exception as exc:
        print(f"SEED: Error during seeding: {exc}", flush=True)
        db.rollback()
    finally:
        db.close()
