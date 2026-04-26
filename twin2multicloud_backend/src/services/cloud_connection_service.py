"""Cloud Connection lifecycle and credential payload handling."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from src.models.cloud_connection import CloudConnection
from src.repositories.cloud_connection_repository import CloudConnectionRepository
from src.schemas.cloud_connection import CloudConnectionCreate, CloudConnectionResponse, CloudConnectionUpdate
from src.utils.crypto import decrypt_scoped, encrypt_scoped


class CloudConnectionService:
    """Owns user-scoped Cloud Connection creation and secret-safe read models."""

    def __init__(self, db: Session):
        self._db = db
        self._repo = CloudConnectionRepository(db)

    def list_connections(self, user_id: str) -> list[CloudConnectionResponse]:
        return [self.to_response(connection, user_id) for connection in self._repo.list_for_user(user_id)]

    def get_connection(self, connection_id: str, user_id: str) -> CloudConnection | None:
        return self._repo.get_for_user(connection_id, user_id)

    def create_connection(self, user_id: str, request: CloudConnectionCreate) -> CloudConnectionResponse:
        connection_id = str(uuid.uuid4())
        payload = self._normalize_payload(request)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        fingerprint = self._fingerprint(request.provider, payload)

        connection = CloudConnection(
            id=connection_id,
            user_id=user_id,
            provider=request.provider,
            display_name=request.display_name,
            cloud_scope=json.dumps(request.cloud_scope, sort_keys=True),
            auth_type=request.auth_type or self._default_auth_type(request.provider),
            encrypted_payload=encrypt_scoped(payload_json, user_id, connection_id),
            payload_fingerprint=fingerprint,
            validation_status="untested",
        )
        self._repo.add(connection)
        self._db.commit()
        self._db.refresh(connection)
        return self.to_response(connection, user_id)

    def update_connection(
        self,
        connection: CloudConnection,
        user_id: str,
        request: CloudConnectionUpdate,
    ) -> CloudConnectionResponse:
        if request.display_name is not None:
            connection.display_name = request.display_name
        if request.cloud_scope is not None:
            connection.cloud_scope = json.dumps(request.cloud_scope, sort_keys=True)
        connection.updated_at = datetime.utcnow()

        self._db.commit()
        self._db.refresh(connection)
        return self.to_response(connection, user_id)

    def delete_connection(self, connection: CloudConnection) -> None:
        self._repo.delete(connection)
        self._db.commit()

    def record_validation_result(self, connection: CloudConnection, result: dict[str, Any]) -> None:
        connection.validation_status = "valid" if result.get("valid") else "invalid"
        connection.validation_message = self._validation_message(result)
        connection.last_validated_at = datetime.utcnow()
        connection.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(connection)

    def to_response(self, connection: CloudConnection, user_id: str) -> CloudConnectionResponse:
        payload = self.decrypt_payload(connection, user_id)
        return CloudConnectionResponse(
            id=connection.id,
            provider=connection.provider,
            display_name=connection.display_name,
            auth_type=connection.auth_type,
            cloud_scope=self._safe_json_dict(connection.cloud_scope),
            payload_fingerprint=connection.payload_fingerprint,
            payload_summary=self._payload_summary(connection.provider, payload),
            validation_status=connection.validation_status,
            validation_message=connection.validation_message,
            last_validated_at=connection.last_validated_at,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )

    def decrypt_payload(self, connection: CloudConnection, user_id: str) -> dict[str, Any]:
        payload = decrypt_scoped(connection.encrypted_payload, user_id, connection.id)
        return self._safe_json_dict(payload)

    def build_optimizer_credentials(self, connection: CloudConnection, user_id: str) -> dict[str, Any]:
        payload = self.decrypt_payload(connection, user_id)
        if connection.provider == "gcp":
            return {
                "gcp_project_id": payload.get("gcp_project_id") or "placeholder-project",
                "gcp_credentials_file": payload.get("gcp_credentials_file"),
                "gcp_region": payload.get("gcp_region"),
            }
        return payload.copy()

    def build_deployer_credentials(self, connection: CloudConnection, user_id: str) -> dict[str, Any]:
        return self.decrypt_payload(connection, user_id)

    def _normalize_payload(self, request: CloudConnectionCreate) -> dict[str, Any]:
        if request.provider == "aws" and request.aws:
            payload = {
                "aws_access_key_id": request.aws.access_key_id,
                "aws_secret_access_key": request.aws.secret_access_key,
                "aws_region": request.aws.region,
            }
            if request.aws.sso_region:
                payload["aws_sso_region"] = request.aws.sso_region
            if request.aws.session_token:
                payload["aws_session_token"] = request.aws.session_token
            return payload

        if request.provider == "azure" and request.azure:
            return {
                "azure_subscription_id": request.azure.subscription_id,
                "azure_client_id": request.azure.client_id,
                "azure_client_secret": request.azure.client_secret,
                "azure_tenant_id": request.azure.tenant_id,
                "azure_region": request.azure.region,
                "azure_region_iothub": request.azure.region_iothub or request.azure.region,
                "azure_region_digital_twin": request.azure.region_digital_twin or request.azure.region,
            }

        if request.provider == "gcp" and request.gcp:
            payload = {
                "gcp_project_id": request.gcp.project_id,
                "gcp_billing_account": request.gcp.billing_account,
                "gcp_region": request.gcp.region,
                "gcp_credentials_file": request.gcp.service_account_json,
            }
            return {key: value for key, value in payload.items() if value is not None}

        raise ValueError(f"Unsupported cloud connection provider: {request.provider}")

    def _payload_summary(self, provider: str, payload: dict[str, Any]) -> dict[str, Any]:
        if provider == "aws":
            return {
                "account_identity_configured": bool(payload.get("aws_access_key_id")),
                "region": payload.get("aws_region"),
                "uses_session_token": bool(payload.get("aws_session_token")),
            }
        if provider == "azure":
            return {
                "subscription_configured": bool(payload.get("azure_subscription_id")),
                "client_configured": bool(payload.get("azure_client_id")),
                "region": payload.get("azure_region"),
                "iot_hub_region": payload.get("azure_region_iothub"),
                "digital_twin_region": payload.get("azure_region_digital_twin"),
            }
        if provider == "gcp":
            return {
                "project_id": payload.get("gcp_project_id"),
                "billing_account_configured": bool(payload.get("gcp_billing_account")),
                "service_account_configured": bool(payload.get("gcp_credentials_file")),
                "service_account_email": self._gcp_service_account_email(payload),
                "region": payload.get("gcp_region"),
            }
        return {}

    def _fingerprint(self, provider: str, payload: dict[str, Any]) -> str:
        identity = self._payload_summary(provider, payload)
        fingerprint_input = json.dumps(
            {"provider": provider, "identity": identity},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(fingerprint_input.encode()).hexdigest()

    @staticmethod
    def _validation_message(result: dict[str, Any]) -> str:
        if result.get("valid"):
            return "Optimizer and Deployer validation passed"
        optimizer = result.get("optimizer") if isinstance(result.get("optimizer"), dict) else {}
        deployer = result.get("deployer") if isinstance(result.get("deployer"), dict) else {}
        messages = [
            message for message in [
                optimizer.get("message"),
                deployer.get("message"),
            ]
            if message
        ]
        return " | ".join(messages) or "Validation failed"

    @staticmethod
    def _default_auth_type(provider: str) -> str:
        return {
            "aws": "access_key",
            "azure": "service_principal",
            "gcp": "service_account_key",
        }[provider]

    @staticmethod
    def _safe_json_dict(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _gcp_service_account_email(payload: dict[str, Any]) -> str | None:
        raw = payload.get("gcp_credentials_file")
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        email = parsed.get("client_email")
        return email if isinstance(email, str) else None
