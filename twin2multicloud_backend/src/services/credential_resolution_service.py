"""Credential resolution for CloudConnection SSOT and legacy fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from typing import Any

from src.services.errors import CredentialResolutionFailed
from src.utils.crypto import decrypt, decrypt_scoped

logger = logging.getLogger(__name__)

ProviderName = str


@dataclass(frozen=True, repr=False)
class ProviderCredentials:
    provider: ProviderName
    source: str
    source_id: str | None
    optimizer_payload: dict[str, Any]
    deployer_validation_payload: dict[str, Any]
    deployer_config_payload: dict[str, Any]
    gcp_credentials_json: dict[str, Any] | None = None


@dataclass(frozen=True, repr=False)
class DeploymentCredentials:
    providers: tuple[ProviderName, ...]
    config_credentials: dict[str, dict[str, Any]]
    gcp_credentials_json: dict[str, Any] | None = None
    sources: dict[str, str] = field(default_factory=dict)


class CredentialResolutionService:
    """Resolves credentials from CloudConnections first, legacy encrypted fields second."""

    def resolve_plaintext_credentials(self, provider: str, credentials) -> ProviderCredentials:
        """Resolve request-body credentials without persisting or decrypting them."""
        provider = self._normalize_provider(provider)
        if provider not in {"aws", "azure", "gcp"}:
            raise self._failed(
                [],
                provider,
                "UNSUPPORTED_PROVIDER",
                "Unsupported cloud provider",
            )
        if credentials is None:
            raise self._failed(
                [],
                provider,
                "MISSING_CREDENTIALS",
                "No credentials provided for provider",
            )
        payload = self.build_plaintext_payload(provider, credentials)
        return self._build_provider_credentials(provider, payload, "plaintext", None)

    def resolve_provider_credentials(self, twin, user_id: str, provider: str) -> ProviderCredentials:
        provider = self._normalize_provider(provider)
        errors: list[dict[str, Any]] = []

        if not getattr(twin, "configuration", None):
            raise self._failed(errors, provider, "MISSING_CONFIGURATION", "Twin configuration is missing")

        config = twin.configuration
        connection_id = self._connection_id(config, provider)
        if connection_id:
            connection = getattr(config, f"{provider}_cloud_connection", None)
            if connection is None:
                raise self._failed(
                    errors,
                    provider,
                    "DANGLING_CLOUD_CONNECTION",
                    "Configured Cloud Connection is no longer available",
                    source_id=connection_id,
                )
            payload = self._decrypt_cloud_connection(connection, user_id, provider, errors)
            if errors:
                raise self._failed_from_errors(errors)
            return self._build_provider_credentials(provider, payload, "cloud_connection", connection_id)

        payload = self._legacy_payload(twin, user_id, provider, errors)
        if errors:
            raise self._failed_from_errors(errors)
        if not payload:
            raise self._failed(errors, provider, "MISSING_CREDENTIALS", "No credentials configured for provider")
        return self._build_provider_credentials(provider, payload, "legacy", None)

    def resolve_deployment_credentials(
        self,
        twin,
        user_id: str,
        required_providers: set[str] | None = None,
    ) -> DeploymentCredentials:
        providers = self._deployment_providers(twin, required_providers)
        if not providers:
            raise CredentialResolutionFailed(
                "Cannot resolve deployment credentials",
                [{
                    "code": "NO_DEPLOYMENT_PROVIDERS",
                    "field": "optimizer_config",
                    "message": "No deployment providers are selected",
                }],
            )

        resolved: dict[str, ProviderCredentials] = {}
        errors: list[dict[str, Any]] = []
        gcp_credentials_json = None
        for provider in providers:
            try:
                credentials = self.resolve_provider_credentials(twin, user_id, provider)
                resolved[provider] = credentials
                if credentials.gcp_credentials_json is not None:
                    gcp_credentials_json = credentials.gcp_credentials_json
            except CredentialResolutionFailed as exc:
                errors.extend(exc.errors)

        if errors:
            raise CredentialResolutionFailed("Cannot resolve deployment credentials", errors)

        return DeploymentCredentials(
            providers=tuple(providers),
            config_credentials={
                provider: credentials.deployer_config_payload
                for provider, credentials in resolved.items()
            },
            gcp_credentials_json=gcp_credentials_json,
            sources={
                provider: credentials.source
                for provider, credentials in resolved.items()
            },
        )

    @classmethod
    def build_plaintext_payload(cls, provider: str, credentials) -> dict[str, Any]:
        """Normalize request-body credential schemas into canonical provider payloads."""
        provider = cls._normalize_provider(provider)
        if provider == "aws":
            payload = {
                "aws_access_key_id": credentials.access_key_id,
                "aws_secret_access_key": credentials.secret_access_key,
                "aws_region": credentials.region,
            }
            if credentials.session_token:
                payload["aws_session_token"] = credentials.session_token
            if credentials.sso_region:
                payload["aws_sso_region"] = credentials.sso_region
            return payload

        if provider == "azure":
            azure_region = credentials.region
            return {
                "azure_subscription_id": credentials.subscription_id,
                "azure_client_id": credentials.client_id,
                "azure_client_secret": credentials.client_secret,
                "azure_tenant_id": credentials.tenant_id,
                "azure_region": azure_region,
                "azure_region_iothub": credentials.region_iothub or azure_region,
                "azure_region_digital_twin": credentials.region_digital_twin or azure_region,
            }

        if provider == "gcp":
            payload = {
                "gcp_project_id": credentials.project_id,
                "gcp_billing_account": credentials.billing_account,
                "gcp_region": credentials.region,
                "gcp_credentials_file": credentials.service_account_json,
            }
            return {key: value for key, value in payload.items() if value is not None}

        raise CredentialResolutionFailed(
            "Cannot resolve deployment credentials",
            [cls._error(provider, "UNSUPPORTED_PROVIDER", "Unsupported cloud provider")],
        )

    @classmethod
    def build_optimizer_payload(cls, provider: str, payload: dict[str, Any]) -> dict[str, Any]:
        provider = cls._normalize_provider(provider)
        if provider == "gcp":
            project_id = payload.get("gcp_project_id") or cls._gcp_project_id_from_service_account(payload)
            result = {
                "gcp_credentials_file": payload.get("gcp_credentials_file"),
                "gcp_project_id": project_id,
                "gcp_region": payload.get("gcp_region"),
            }
            if payload.get("gcp_billing_account"):
                result["gcp_billing_account"] = payload.get("gcp_billing_account")
            return {key: value for key, value in result.items() if value}
        return payload.copy()

    @classmethod
    def build_deployer_validation_payload(cls, provider: str, payload: dict[str, Any]) -> dict[str, Any]:
        if cls._normalize_provider(provider) == "gcp":
            return cls.build_optimizer_payload(provider, payload)
        return payload.copy()

    @classmethod
    def build_deployer_config_payload(
        cls,
        provider: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        provider = cls._normalize_provider(provider)
        if provider != "gcp":
            return payload.copy(), None

        service_account_raw = payload.get("gcp_credentials_file")
        service_account_json = cls._parse_gcp_service_account(service_account_raw)
        project_id = payload.get("gcp_project_id") or cls._gcp_project_id_from_service_account(payload)
        deployer_payload = {
            "gcp_project_id": project_id,
            "gcp_region": payload.get("gcp_region") or "europe-west1",
            "gcp_credentials_file": "gcp_credentials.json",
        }
        if payload.get("gcp_billing_account"):
            deployer_payload["gcp_billing_account"] = payload["gcp_billing_account"]
        return {key: value for key, value in deployer_payload.items() if value}, service_account_json

    @staticmethod
    def configured_providers(twin) -> set[str]:
        config = getattr(twin, "configuration", None)
        if not config:
            return set()
        providers = set()
        checks = {
            "aws": ("aws_cloud_connection_id", "aws_access_key_id"),
            "azure": ("azure_cloud_connection_id", "azure_subscription_id"),
            "gcp": ("gcp_cloud_connection_id", "gcp_project_id", "gcp_service_account_json"),
        }
        for provider, fields in checks.items():
            if any(getattr(config, field, None) for field in fields):
                providers.add(provider)
        return providers

    @classmethod
    def required_providers_from_optimizer(cls, optimizer_config) -> set[str]:
        if not optimizer_config:
            return set()
        fields = (
            "cheapest_l1",
            "cheapest_l2",
            "cheapest_l3_hot",
            "cheapest_l3_cool",
            "cheapest_l3_archive",
            "cheapest_l4",
            "cheapest_l5",
        )
        providers = {
            cls._normalize_provider(getattr(optimizer_config, field))
            for field in fields
            if getattr(optimizer_config, field, None)
        }
        return {provider for provider in providers if provider}

    def _build_provider_credentials(
        self,
        provider: str,
        payload: dict[str, Any],
        source: str,
        source_id: str | None,
    ) -> ProviderCredentials:
        errors = self._validate_payload(provider, payload)
        if errors:
            raise self._failed_from_errors(errors)

        deployer_config_payload, gcp_credentials_json = self.build_deployer_config_payload(provider, payload)
        return ProviderCredentials(
            provider=provider,
            source=source,
            source_id=source_id,
            optimizer_payload=self.build_optimizer_payload(provider, payload),
            deployer_validation_payload=self.build_deployer_validation_payload(provider, payload),
            deployer_config_payload=deployer_config_payload,
            gcp_credentials_json=gcp_credentials_json,
        )

    def _decrypt_cloud_connection(
        self,
        connection,
        user_id: str,
        provider: str,
        errors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            raw = decrypt_scoped(connection.encrypted_payload, user_id, connection.id)
            parsed = json.loads(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "CloudConnection payload resolution failed for provider %s: %s",
                provider,
                type(exc).__name__,
            )
            errors.append(
                self._error(
                    provider,
                    "INVALID_CLOUD_CONNECTION_PAYLOAD",
                    "Cloud Connection payload cannot be decrypted or parsed",
                    source_id=connection.id,
                )
            )
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _legacy_payload(self, twin, user_id: str, provider: str, errors: list[dict[str, Any]]) -> dict[str, Any]:
        config = twin.configuration
        try:
            if provider == "aws" and getattr(config, "aws_access_key_id", None):
                payload = {
                    "aws_access_key_id": decrypt(config.aws_access_key_id, user_id, twin.id),
                    "aws_secret_access_key": decrypt(config.aws_secret_access_key, user_id, twin.id),
                    "aws_region": config.aws_region or "eu-central-1",
                }
                if getattr(config, "aws_session_token", None):
                    payload["aws_session_token"] = decrypt(config.aws_session_token, user_id, twin.id)
                if getattr(config, "aws_sso_region", None):
                    payload["aws_sso_region"] = config.aws_sso_region
                return payload

            if provider == "azure" and getattr(config, "azure_subscription_id", None):
                azure_region = config.azure_region or "westeurope"
                return {
                    "azure_subscription_id": decrypt(config.azure_subscription_id, user_id, twin.id),
                    "azure_tenant_id": decrypt(config.azure_tenant_id, user_id, twin.id),
                    "azure_client_id": decrypt(config.azure_client_id, user_id, twin.id),
                    "azure_client_secret": decrypt(config.azure_client_secret, user_id, twin.id),
                    "azure_region": azure_region,
                    "azure_region_iothub": getattr(config, "azure_region_iothub", None) or azure_region,
                    "azure_region_digital_twin": getattr(config, "azure_region_digital_twin", None) or azure_region,
                }

            if provider == "gcp" and (
                getattr(config, "gcp_project_id", None)
                or getattr(config, "gcp_service_account_json", None)
                or getattr(config, "gcp_billing_account", None)
            ):
                payload = {
                    "gcp_project_id": config.gcp_project_id,
                    "gcp_region": config.gcp_region or "europe-west1",
                }
                if getattr(config, "gcp_billing_account", None):
                    payload["gcp_billing_account"] = decrypt(config.gcp_billing_account, user_id, twin.id)
                if getattr(config, "gcp_service_account_json", None):
                    payload["gcp_credentials_file"] = decrypt(config.gcp_service_account_json, user_id, twin.id)
                return {key: value for key, value in payload.items() if value}
        except ValueError as exc:
            logger.warning("Legacy credential resolution failed for provider %s: %s", provider, type(exc).__name__)
            errors.append(self._error(
                provider,
                "LEGACY_CREDENTIAL_DECRYPTION_FAILED",
                "Legacy credentials cannot be decrypted",
            ))
        return {}

    def _deployment_providers(self, twin, required_providers: set[str] | None) -> list[str]:
        selected_providers = required_providers or self.required_providers_from_optimizer(
            getattr(twin, "optimizer_config", None)
        )
        providers = {
            self._normalize_provider(provider)
            for provider in selected_providers
            if provider
        }
        if not providers:
            providers = self.configured_providers(twin)
        return sorted(providers)

    @classmethod
    def _validate_payload(cls, provider: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        required = {
            "aws": ("aws_access_key_id", "aws_secret_access_key", "aws_region"),
            "azure": (
                "azure_subscription_id",
                "azure_tenant_id",
                "azure_client_id",
                "azure_client_secret",
                "azure_region",
                "azure_region_iothub",
                "azure_region_digital_twin",
            ),
            "gcp": ("gcp_credentials_file", "gcp_region"),
        }[provider]
        missing = [field for field in required if not payload.get(field)]
        if provider == "gcp" and not (
            payload.get("gcp_project_id")
            or payload.get("gcp_billing_account")
            or cls._gcp_project_id_from_service_account(payload)
        ):
            missing.append("gcp_project_id_or_billing_account")
        return [
            cls._error(provider, "MISSING_CREDENTIAL_FIELD", f"Missing required credential field: {field}", field=field)
            for field in missing
        ]

    @staticmethod
    def _connection_id(config, provider: str) -> str | None:
        connection_id = getattr(config, f"{provider}_cloud_connection_id", None)
        return connection_id if isinstance(connection_id, str) and connection_id else None

    @staticmethod
    def _normalize_provider(provider: str | None) -> str:
        if not provider or not isinstance(provider, str):
            return ""
        normalized = provider.lower()
        return "gcp" if normalized == "google" else normalized

    @classmethod
    def _gcp_project_id_from_service_account(cls, payload: dict[str, Any]) -> str | None:
        service_account = cls._parse_gcp_service_account(payload.get("gcp_credentials_file"), allow_missing=True)
        if not service_account:
            return None
        project_id = service_account.get("project_id")
        return project_id if isinstance(project_id, str) and project_id else None

    @staticmethod
    def _parse_gcp_service_account(raw: Any, allow_missing: bool = False) -> dict[str, Any] | None:
        if not raw:
            if allow_missing:
                return None
            raise CredentialResolutionFailed(
                "Cannot resolve deployment credentials",
                [
                    CredentialResolutionService._error(
                        "gcp",
                        "MISSING_CREDENTIAL_FIELD",
                        "Missing required credential field: gcp_credentials_file",
                        field="gcp_credentials_file",
                    )
                ],
            )
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as exc:
            if allow_missing:
                return None
            raise CredentialResolutionFailed(
                "Cannot resolve deployment credentials",
                [
                    CredentialResolutionService._error(
                        "gcp",
                        "INVALID_GCP_SERVICE_ACCOUNT_JSON",
                        "GCP service account JSON is invalid",
                    )
                ],
            ) from exc
        if not isinstance(parsed, dict):
            if allow_missing:
                return None
            raise CredentialResolutionFailed(
                "Cannot resolve deployment credentials",
                [
                    CredentialResolutionService._error(
                        "gcp",
                        "INVALID_GCP_SERVICE_ACCOUNT_JSON",
                        "GCP service account JSON is invalid",
                    )
                ],
            )
        return parsed

    @staticmethod
    def _error(
        provider: str,
        code: str,
        message: str,
        *,
        field: str = "credentials",
        source_id: str | None = None,
    ) -> dict[str, Any]:
        error: dict[str, Any] = {
            "provider": provider,
            "code": code,
            "field": field,
            "message": message,
        }
        if source_id:
            error["source_id"] = source_id
        return error

    def _failed(
        self,
        errors: list[dict[str, Any]],
        provider: str,
        code: str,
        message: str,
        *,
        source_id: str | None = None,
    ) -> CredentialResolutionFailed:
        errors.append(self._error(provider, code, message, source_id=source_id))
        return self._failed_from_errors(errors)

    @staticmethod
    def _failed_from_errors(errors: list[dict[str, Any]]) -> CredentialResolutionFailed:
        return CredentialResolutionFailed("Cannot resolve deployment credentials", errors)
