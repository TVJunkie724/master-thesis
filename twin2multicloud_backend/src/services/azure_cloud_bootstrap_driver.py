"""Azure setup-only driver for the supervised guided-bootstrap transaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Callable, Protocol
from uuid import UUID, uuid5

from src.schemas.cloud_bootstrap import (
    AzureBootstrapCredential,
    AzureBootstrapTarget,
    CloudBootstrapCredential,
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
    CloudBootstrapTarget,
)
from src.schemas.cloud_connection import CloudConnectionCreate
from src.schemas.twin_config import AzureCredentials
from src.services.cloud_bootstrap_adapters import (
    CloudBootstrapAdapterError,
    CloudBootstrapAdapterResult,
    CloudBootstrapFinalizationResult,
    CloudBootstrapRollbackReceipt,
    SupervisedLiveBootstrapPlan,
)


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
ARM_ROOT = "https://management.azure.com"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
ARM_SCOPE = "https://management.azure.com/.default"
MANAGED_TAG = "twin2mc:managed-by=setup-only"
RUN_TAG_PREFIX = "twin2mc:run-id="
ROLE_ASSIGNMENT_NAMESPACE = UUID("00000000-0000-4000-8000-000000000154")
RESOURCE_API_VERSION = "2022-12-01"
AUTHORIZATION_API_VERSION = "2022-04-01"


class AzureHTTPResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class AzureTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> AzureHTTPResponse: ...


AzureTransportFactory = Callable[[], AzureTransport]


def default_azure_transport_factory() -> AzureTransport:
    """Create an explicit transport lazily; construction performs no network call."""

    import httpx

    return httpx.Client(
        timeout=httpx.Timeout(20.0),
        follow_redirects=False,
        trust_env=False,
    )


@dataclass(frozen=True)
class AzureTokens:
    graph: str
    arm: str


class _AzureRequestError(RuntimeError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__("Azure rejected the setup-only request.")


class AzureCloudBootstrapDriver:
    """Create and validate one gate-owned Entra/ARM deployment identity."""

    def __init__(
        self,
        *,
        transport_factory: AzureTransportFactory = default_azure_transport_factory,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._transport_factory = transport_factory
        self._sleep = sleeper
        self._clock = clock

    def provision(
        self,
        *,
        plan: SupervisedLiveBootstrapPlan,
        display_name: str,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult:
        if (
            plan.provider != "azure"
            or not isinstance(target, AzureBootstrapTarget)
            or not isinstance(credential, AzureBootstrapCredential)
        ):
            raise self._invalid_credential()
        tenant_id, subscription_id, client_id = self._canonical_input(
            target,
            credential,
        )
        bundle = plan.deployment_document()
        self._validate_bundle(bundle, plan, target, subscription_id)
        transport = self._transport_factory()
        receipt: CloudBootstrapRollbackReceipt | None = None
        try:
            tokens, _ = self._validated_bootstrap_tokens(
                transport,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                client_id=client_id,
                client_secret=credential.client_secret.get_secret_value(),
            )
            application = self._ensure_application(transport, tokens.graph, plan.run_id)
            application_object_id = self._required_uuid(application, "id")
            generated_client_id = self._required_uuid(application, "appId")
            receipt = self._receipt(
                plan.run_id,
                application_object_id=application_object_id,
            )
            service_principal = self._ensure_service_principal(
                transport,
                tokens.graph,
                plan.run_id,
                generated_client_id,
            )
            service_principal_object_id = self._required_uuid(
                service_principal,
                "id",
            )
            receipt = self._receipt(
                plan.run_id,
                application_object_id=application_object_id,
                service_principal_object_id=service_principal_object_id,
            )
            role_definition_id = self._ensure_role_definition(
                transport,
                tokens.arm,
                bundle,
            )
            receipt = self._receipt(
                plan.run_id,
                application_object_id=application_object_id,
                service_principal_object_id=service_principal_object_id,
                role_definition_id=role_definition_id,
            )
            role_assignment_id = self._ensure_role_assignment(
                transport,
                tokens.arm,
                bundle,
                service_principal_object_id,
                role_definition_id,
            )
            receipt = self._receipt(
                plan.run_id,
                application_object_id=application_object_id,
                service_principal_object_id=service_principal_object_id,
                role_definition_id=role_definition_id,
                role_assignment_id=role_assignment_id,
            )
            generated = self._replace_generated_password(
                transport,
                tokens.graph,
                application_object_id,
                plan.run_id,
            )
            credential_key_id = self._required_uuid(generated, "keyId")
            generated_secret = self._required_string(generated, "secretText")
            receipt = self._receipt(
                plan.run_id,
                application_object_id=application_object_id,
                credential_key_id=credential_key_id,
                role_assignment_id=role_assignment_id,
                role_definition_id=role_definition_id,
                service_principal_object_id=service_principal_object_id,
            )
            self._validate_generated_credential(
                transport,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                region=target.region,
                client_id=generated_client_id,
                client_secret=generated_secret,
                service_principal_object_id=service_principal_object_id,
                role_assignment_id=role_assignment_id,
                bundle=bundle,
            )
        except Exception as exc:
            try:
                if receipt is not None:
                    self._cleanup(
                        transport,
                        tokens,
                        receipt,
                        target,
                        bundle,
                    )
            except Exception as cleanup_exc:
                raise CloudBootstrapAdapterError(
                    "BOOTSTRAP_CLEANUP_FAILED",
                    f"Azure setup run {plan.run_id} requires manual cleanup.",
                ) from cleanup_exc
            if isinstance(exc, CloudBootstrapAdapterError):
                raise
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "Azure rejected the reviewed setup-only identity transaction.",
            ) from exc
        finally:
            self._close(transport)

        disposal_status, finalize = self._provisional_disposal(credential_origin)
        return CloudBootstrapAdapterResult(
            connection=CloudConnectionCreate(
                provider="azure",
                purpose="deployment",
                display_name=display_name,
                auth_type="service_principal",
                permission_set_version="thesis-demo-v2",
                cloud_scope={
                    "tenant_id": target.tenant_id,
                    "subscription_id": target.subscription_id,
                    "region": target.region,
                    "bootstrap_mode": "supervised_live",
                },
                azure=AzureCredentials(
                    subscription_id=target.subscription_id,
                    client_id=generated_client_id,
                    client_secret=generated_secret,
                    tenant_id=target.tenant_id,
                    region=target.region,
                ),
            ),
            safe_credential_identifier=(
                target.bootstrap_credential_key_id
                or credential.client_id.get_secret_value()
            ),
            disposal_status=disposal_status,
            generated_credential_validated=True,
            rollback_receipt=receipt,
            bootstrap_finalization_required=finalize,
        )

    def rollback(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        if (
            receipt.provider != "azure"
            or not isinstance(target, AzureBootstrapTarget)
            or not isinstance(credential, AzureBootstrapCredential)
        ):
            raise self._invalid_credential()
        tenant_id, subscription_id, client_id = self._canonical_input(
            target,
            credential,
        )
        bundle = self._bundle_for_receipt(receipt, target, subscription_id)
        transport = self._transport_factory()
        try:
            tokens, _ = self._validated_bootstrap_tokens(
                transport,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                client_id=client_id,
                client_secret=credential.client_secret.get_secret_value(),
            )
            self._validate_receipt_scope(receipt, target, bundle)
            self._cleanup(transport, tokens, receipt, target, bundle)
        finally:
            self._close(transport)

    def finalize_bootstrap(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        if (
            receipt.provider != "azure"
            or not isinstance(target, AzureBootstrapTarget)
            or not isinstance(credential, AzureBootstrapCredential)
        ):
            raise self._invalid_credential()
        if target.bootstrap_credential_key_id is None:
            return CloudBootstrapFinalizationResult(
                disposal_status=CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED,
            )
        tenant_id, subscription_id, client_id = self._canonical_input(
            target,
            credential,
        )
        bootstrap_key_id = self._canonical_uuid(target.bootstrap_credential_key_id)
        transport = self._transport_factory()
        try:
            tokens, application = self._validated_bootstrap_tokens(
                transport,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                client_id=client_id,
                client_secret=credential.client_secret.get_secret_value(),
            )
            application_object_id = self._required_uuid(application, "id")
            password_ids = {
                self._canonical_uuid(item.get("keyId"))
                for item in application.get("passwordCredentials", [])
                if isinstance(item, dict) and item.get("keyId")
            }
            if bootstrap_key_id not in password_ids:
                raise CloudBootstrapAdapterError(
                    "BOOTSTRAP_CLEANUP_FAILED",
                    "Azure bootstrap-secret ownership could not be proven for automatic deletion.",
                )
            self._graph_json(
                transport,
                tokens.graph,
                "POST",
                f"/applications/{application_object_id}/removePassword",
                expected={204},
                body={"keyId": bootstrap_key_id},
                allow_empty=True,
            )
            return CloudBootstrapFinalizationResult(
                disposal_status=CloudBootstrapDisposalStatus.REVOKED,
            )
        finally:
            self._close(transport)

    def _canonical_input(
        self,
        target: AzureBootstrapTarget,
        credential: AzureBootstrapCredential,
    ) -> tuple[str, str, str]:
        try:
            tenant_id = self._canonical_uuid(target.tenant_id)
            subscription_id = self._canonical_uuid(target.subscription_id)
            credential_tenant = self._canonical_uuid(
                credential.tenant_id.get_secret_value()
            )
            credential_subscription = self._canonical_uuid(
                credential.subscription_id.get_secret_value()
            )
            client_id = self._canonical_uuid(credential.client_id.get_secret_value())
            if target.bootstrap_credential_key_id is not None:
                self._canonical_uuid(target.bootstrap_credential_key_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise self._invalid_credential() from exc
        if (
            credential_tenant != tenant_id
            or credential_subscription != subscription_id
        ):
            raise self._invalid_credential()
        return tenant_id, subscription_id, client_id

    @staticmethod
    def _validate_bundle(
        bundle: dict[str, Any],
        plan: SupervisedLiveBootstrapPlan,
        target: AzureBootstrapTarget,
        subscription_id: str,
    ) -> None:
        scope = f"/subscriptions/{subscription_id}"
        properties = bundle.get("properties", {})
        if (
            bundle.get("schema_version") != "azure-deployment-identity-bundle.v1"
            or bundle.get("provider") != "azure"
            or bundle.get("region") != target.region
            or bundle.get("permission_set_version") != "thesis-demo-v2"
            or bundle.get("identity_binding_id")
            != "azure.thesis-demo-v2.service-principal-v1"
            or bundle.get("scope") != scope
            or properties.get("roleName")
            != f"Twin2MultiCloud {plan.run_id} deployment"
            or properties.get("assignableScopes") != [scope]
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The Azure provider bundle does not match the reviewed v2 contract.",
            )

    def _bootstrap_tokens(
        self,
        transport: AzureTransport,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> AzureTokens:
        return AzureTokens(
            graph=self._token(
                transport,
                tenant_id,
                client_id,
                client_secret,
                GRAPH_SCOPE,
            ),
            arm=self._token(
                transport,
                tenant_id,
                client_id,
                client_secret,
                ARM_SCOPE,
            ),
        )

    def _validated_bootstrap_tokens(
        self,
        transport: AzureTransport,
        *,
        tenant_id: str,
        subscription_id: str,
        client_id: str,
        client_secret: str,
    ) -> tuple[AzureTokens, dict[str, Any]]:
        try:
            tokens = self._bootstrap_tokens(
                transport,
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
            application = self._validate_bootstrap_identity(
                transport,
                tokens,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                client_id=client_id,
            )
            return tokens, application
        except Exception as exc:
            raise self._invalid_credential() from exc

    def _token(
        self,
        transport: AzureTransport,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        scope: str,
    ) -> str:
        response = transport.request(
            "POST",
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
                "scope": scope,
            },
        )
        document = self._response_json(response, expected={200})
        return self._required_string(document, "access_token")

    def _validate_bootstrap_identity(
        self,
        transport: AzureTransport,
        tokens: AzureTokens,
        *,
        tenant_id: str,
        subscription_id: str,
        client_id: str,
    ) -> dict[str, Any]:
        try:
            subscription = self._arm_json(
                transport,
                tokens.arm,
                "GET",
                f"/subscriptions/{subscription_id}",
                params={"api-version": RESOURCE_API_VERSION},
                expected={200},
            )
            application = self._graph_json(
                transport,
                tokens.graph,
                "GET",
                f"/applications(appId='{client_id}')",
                params={
                    "$select": "id,appId,displayName,tags,passwordCredentials"
                },
                expected={200},
            )
            if (
                self._canonical_uuid(subscription.get("subscriptionId"))
                != subscription_id
                or self._canonical_uuid(subscription.get("tenantId")) != tenant_id
                or self._canonical_uuid(application.get("appId")) != client_id
            ):
                raise ValueError("Azure bootstrap scope mismatch")
        except Exception as exc:
            raise self._invalid_credential() from exc
        return application

    def _ensure_application(
        self,
        transport: AzureTransport,
        graph_token: str,
        run_id: str,
    ) -> dict[str, Any]:
        display_name = f"{run_id}-deployer"
        response = self._graph_json(
            transport,
            graph_token,
            "GET",
            "/applications",
            params={
                "$filter": f"displayName eq '{display_name}'",
                "$select": "id,appId,displayName,tags,passwordCredentials,keyCredentials",
            },
            expected={200},
        )
        applications = response.get("value")
        if not isinstance(applications, list):
            raise _AzureRequestError(502)
        if response.get("@odata.nextLink"):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The Azure application ownership query is incomplete.",
            )
        if not applications:
            application = self._graph_json(
                transport,
                graph_token,
                "POST",
                "/applications",
                expected={201},
                body={
                    "displayName": display_name,
                    "signInAudience": "AzureADMyOrg",
                    "tags": self._tags(run_id),
                },
            )
        elif len(applications) == 1 and isinstance(applications[0], dict):
            application = applications[0]
        else:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "An Azure application name collision crosses the setup-run boundary.",
            )
        application_id = self._required_uuid(application, "id")
        self._required_uuid(application, "appId")
        application = self._graph_json(
            transport,
            graph_token,
            "GET",
            f"/applications/{application_id}",
            params={
                "$select": "id,appId,displayName,tags,passwordCredentials,keyCredentials"
            },
            expected={200},
        )
        try:
            self._validate_owned_application(application, run_id)
        except CloudBootstrapAdapterError as exc:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "An existing Azure application does not match the setup-run ownership boundary.",
            ) from exc
        return application

    def _ensure_service_principal(
        self,
        transport: AzureTransport,
        graph_token: str,
        run_id: str,
        app_id: str,
    ) -> dict[str, Any]:
        response = self._graph_json(
            transport,
            graph_token,
            "GET",
            "/servicePrincipals",
            params={
                "$filter": f"appId eq '{app_id}'",
                "$select": "id,appId,displayName,tags,accountEnabled,servicePrincipalType,passwordCredentials,keyCredentials",
            },
            expected={200},
        )
        principals = response.get("value")
        if not isinstance(principals, list):
            raise _AzureRequestError(502)
        if response.get("@odata.nextLink"):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The Azure service-principal ownership query is incomplete.",
            )
        if not principals:
            principal = self._graph_json(
                transport,
                graph_token,
                "POST",
                "/servicePrincipals",
                expected={201},
                body={"appId": app_id, "tags": self._tags(run_id)},
            )
        elif len(principals) == 1 and isinstance(principals[0], dict):
            principal = principals[0]
        else:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The Azure application has an ambiguous service-principal boundary.",
            )
        principal_id = self._required_uuid(principal, "id")
        principal = self._graph_json(
            transport,
            graph_token,
            "GET",
            f"/servicePrincipals/{principal_id}",
            params={
                "$select": "id,appId,displayName,tags,accountEnabled,servicePrincipalType,passwordCredentials,keyCredentials"
            },
            expected={200},
        )
        if (
            self._canonical_uuid(principal.get("appId")) != app_id
            or not isinstance(principal.get("tags"), list)
            or sorted(principal.get("tags", [])) != self._tags(run_id)
            or principal.get("accountEnabled", True) is not True
            or principal.get("servicePrincipalType", "Application") != "Application"
            or not isinstance(principal.get("passwordCredentials"), list)
            or not isinstance(principal.get("keyCredentials"), list)
            or principal.get("passwordCredentials")
            or principal.get("keyCredentials")
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "An existing Azure service principal is outside the setup-run boundary.",
            )
        return principal

    def _ensure_role_definition(
        self,
        transport: AzureTransport,
        arm_token: str,
        bundle: dict[str, Any],
    ) -> str:
        role_id = self._canonical_uuid(bundle.get("role_definition_id"))
        path = f"{bundle['scope']}/providers/Microsoft.Authorization/roleDefinitions/{role_id}"
        existing = self._arm_optional(
            transport,
            arm_token,
            "GET",
            path,
            params={"api-version": AUTHORIZATION_API_VERSION},
        )
        if existing is None:
            existing = self._arm_json(
                transport,
                arm_token,
                "PUT",
                path,
                params={"api-version": AUTHORIZATION_API_VERSION},
                expected={200, 201},
                body={"properties": bundle["properties"]},
            )
        self._validate_role_definition(existing, bundle, role_id)
        return role_id

    def _ensure_role_assignment(
        self,
        transport: AzureTransport,
        arm_token: str,
        bundle: dict[str, Any],
        principal_id: str,
        role_definition_id: str,
    ) -> str:
        assignment_id = str(
            uuid5(
                ROLE_ASSIGNMENT_NAMESPACE,
                f"{bundle['scope']}:{role_definition_id}:{principal_id}",
            )
        )
        path = f"{bundle['scope']}/providers/Microsoft.Authorization/roleAssignments/{assignment_id}"
        role_resource_id = self._role_resource_id(bundle["scope"], role_definition_id)
        existing = self._arm_optional(
            transport,
            arm_token,
            "GET",
            path,
            params={"api-version": AUTHORIZATION_API_VERSION},
        )
        if existing is None:
            existing = self._arm_json(
                transport,
                arm_token,
                "PUT",
                path,
                params={"api-version": AUTHORIZATION_API_VERSION},
                expected={200, 201},
                body={
                    "properties": {
                        "principalId": principal_id,
                        "principalType": "ServicePrincipal",
                        "roleDefinitionId": role_resource_id,
                    }
                },
            )
        self._validate_role_assignment(
            existing,
            bundle["scope"],
            assignment_id,
            principal_id,
            role_resource_id,
        )
        return assignment_id

    def _replace_generated_password(
        self,
        transport: AzureTransport,
        graph_token: str,
        application_object_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        display_name = f"{run_id}-deployment"
        application = self._graph_json(
            transport,
            graph_token,
            "GET",
            f"/applications/{application_object_id}",
            params={
                "$select": "id,appId,displayName,tags,passwordCredentials,keyCredentials"
            },
            expected={200},
        )
        self._validate_owned_application(application, run_id)
        for item in application.get("passwordCredentials", []):
            if isinstance(item, dict) and item.get("displayName") == display_name:
                key_id = self._canonical_uuid(item.get("keyId"))
                self._graph_json(
                    transport,
                    graph_token,
                    "POST",
                    f"/applications/{application_object_id}/removePassword",
                    expected={204},
                    body={"keyId": key_id},
                    allow_empty=True,
                )
        expiry = self._clock().astimezone(timezone.utc) + timedelta(hours=24)
        return self._graph_json(
            transport,
            graph_token,
            "POST",
            f"/applications/{application_object_id}/addPassword",
            expected={200},
            body={
                "passwordCredential": {
                    "displayName": display_name,
                    "endDateTime": expiry.isoformat().replace("+00:00", "Z"),
                }
            },
        )

    def _validate_generated_credential(
        self,
        transport: AzureTransport,
        *,
        tenant_id: str,
        subscription_id: str,
        region: str,
        client_id: str,
        client_secret: str,
        service_principal_object_id: str,
        role_assignment_id: str,
        bundle: dict[str, Any],
    ) -> None:
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                arm_token = self._token(
                    transport,
                    tenant_id,
                    client_id,
                    client_secret,
                    ARM_SCOPE,
                )
                subscription = self._arm_json(
                    transport,
                    arm_token,
                    "GET",
                    f"/subscriptions/{subscription_id}",
                    params={"api-version": RESOURCE_API_VERSION},
                    expected={200},
                )
                locations = self._arm_json(
                    transport,
                    arm_token,
                    "GET",
                    f"/subscriptions/{subscription_id}/locations",
                    params={"api-version": RESOURCE_API_VERSION},
                    expected={200},
                )
                role_id = self._canonical_uuid(bundle["role_definition_id"])
                role = self._arm_json(
                    transport,
                    arm_token,
                    "GET",
                    self._role_resource_id(bundle["scope"], role_id),
                    params={"api-version": AUTHORIZATION_API_VERSION},
                    expected={200},
                )
                assignment = self._arm_json(
                    transport,
                    arm_token,
                    "GET",
                    f"{bundle['scope']}/providers/Microsoft.Authorization/roleAssignments/{role_assignment_id}",
                    params={"api-version": AUTHORIZATION_API_VERSION},
                    expected={200},
                )
                assignments = self._arm_json(
                    transport,
                    arm_token,
                    "GET",
                    f"{bundle['scope']}/providers/Microsoft.Authorization/roleAssignments",
                    params={
                        "api-version": AUTHORIZATION_API_VERSION,
                        "$filter": (
                            f"principalId eq '{service_principal_object_id}'"
                        ),
                    },
                    expected={200},
                )
                self._validate_role_definition(role, bundle, role_id)
                self._validate_role_assignment(
                    assignment,
                    bundle["scope"],
                    role_assignment_id,
                    service_principal_object_id,
                    self._role_resource_id(bundle["scope"], role_id),
                )
                listed_assignments = assignments.get("value")
                if (
                    not isinstance(listed_assignments, list)
                    or assignments.get("nextLink")
                    or assignments.get("@odata.nextLink")
                    or len(listed_assignments) != 1
                ):
                    raise self._invalid_credential()
                self._validate_role_assignment(
                    listed_assignments[0],
                    bundle["scope"],
                    role_assignment_id,
                    service_principal_object_id,
                    self._role_resource_id(bundle["scope"], role_id),
                )
                available_regions = {
                    item.get("name")
                    for item in locations.get("value", [])
                    if isinstance(item, dict)
                }
                if (
                    self._canonical_uuid(subscription.get("subscriptionId"))
                    != subscription_id
                    or self._canonical_uuid(subscription.get("tenantId")) != tenant_id
                    or region not in available_regions
                ):
                    raise self._invalid_credential()
                return
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    self._sleep(2**attempt)
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_CONNECTION_VALIDATION_FAILED",
            "The generated Azure credential did not pass identity, authority, and region checks.",
        ) from last_error

    def _cleanup(
        self,
        transport: AzureTransport,
        tokens: AzureTokens,
        receipt: CloudBootstrapRollbackReceipt,
        target: AzureBootstrapTarget,
        bundle: dict[str, Any],
    ) -> None:
        identifiers = dict(receipt.resource_ids)
        application_id = identifiers.get("application_object_id")
        principal_id = identifiers.get("service_principal_object_id")
        role_id = identifiers.get("role_definition_id")
        assignment_id = identifiers.get("role_assignment_id")
        credential_key_id = identifiers.get("credential_key_id")
        application = None
        if application_id:
            application = self._graph_optional(
                transport,
                tokens.graph,
                "GET",
                f"/applications/{application_id}",
                params={
                    "$select": "id,appId,displayName,tags,passwordCredentials,keyCredentials"
                },
            )
            if application is not None:
                self._validate_owned_application(application, receipt.run_id)
        if principal_id:
            assignments = self._arm_json(
                transport,
                tokens.arm,
                "GET",
                f"{bundle['scope']}/providers/Microsoft.Authorization/roleAssignments",
                params={
                    "api-version": AUTHORIZATION_API_VERSION,
                    "$filter": f"principalId eq '{principal_id}'",
                },
                expected={200},
            )
            values = assignments.get("value")
            allowed_assignment_id = (
                f"{bundle['scope']}/providers/Microsoft.Authorization/roleAssignments/{assignment_id}"
                if assignment_id
                else None
            )
            if (
                not isinstance(values, list)
                or any(not isinstance(item, dict) for item in values)
                or assignments.get("nextLink")
                or assignments.get("@odata.nextLink")
                or len(values) > (1 if allowed_assignment_id else 0)
                or {
                    str(item.get("id", "")).lower()
                    for item in values
                    if isinstance(item, dict)
                }
                - ({allowed_assignment_id.lower()} if allowed_assignment_id else set())
            ):
                raise CloudBootstrapAdapterError(
                    "BOOTSTRAP_CLEANUP_FAILED",
                    "The Azure service principal has an assignment outside the setup run.",
                )
        if assignment_id:
            assignment_path = f"{bundle['scope']}/providers/Microsoft.Authorization/roleAssignments/{assignment_id}"
            assignment = self._arm_optional(
                transport,
                tokens.arm,
                "GET",
                assignment_path,
                params={"api-version": AUTHORIZATION_API_VERSION},
            )
            if assignment is not None:
                self._validate_role_assignment(
                    assignment,
                    bundle["scope"],
                    assignment_id,
                    principal_id,
                    self._role_resource_id(bundle["scope"], role_id),
                )
                self._arm_json(
                    transport,
                    tokens.arm,
                    "DELETE",
                    assignment_path,
                    params={"api-version": AUTHORIZATION_API_VERSION},
                    expected={200, 204},
                    allow_empty=True,
                )
        if role_id:
            role_path = self._role_resource_id(bundle["scope"], role_id)
            role = self._arm_optional(
                transport,
                tokens.arm,
                "GET",
                role_path,
                params={"api-version": AUTHORIZATION_API_VERSION},
            )
            if role is not None:
                self._validate_role_definition(role, bundle, role_id)
                self._arm_json(
                    transport,
                    tokens.arm,
                    "DELETE",
                    role_path,
                    params={"api-version": AUTHORIZATION_API_VERSION},
                    expected={200, 204},
                    allow_empty=True,
                )
        if application is not None and credential_key_id:
            owned_keys = {
                self._canonical_uuid(item.get("keyId"))
                for item in application.get("passwordCredentials", [])
                if isinstance(item, dict)
                and item.get("displayName") == f"{receipt.run_id}-deployment"
            }
            if owned_keys and owned_keys != {credential_key_id}:
                raise CloudBootstrapAdapterError(
                    "BOOTSTRAP_CLEANUP_FAILED",
                    "The generated Azure credential is outside the setup-run boundary.",
                )
            if owned_keys:
                self._graph_json(
                    transport,
                    tokens.graph,
                    "POST",
                    f"/applications/{application_id}/removePassword",
                    expected={204},
                    body={"keyId": credential_key_id},
                    allow_empty=True,
                )
        if principal_id:
            principal = self._graph_optional(
                transport,
                tokens.graph,
                "GET",
                f"/servicePrincipals/{principal_id}",
                params={
                    "$select": "id,appId,displayName,tags,accountEnabled,servicePrincipalType,passwordCredentials,keyCredentials"
                },
            )
            if principal is not None:
                if application is None or (
                    self._canonical_uuid(principal.get("appId"))
                    != self._canonical_uuid(application.get("appId"))
                    or sorted(principal.get("tags", [])) != self._tags(receipt.run_id)
                    or principal.get("passwordCredentials")
                    or principal.get("keyCredentials")
                ):
                    raise CloudBootstrapAdapterError(
                        "BOOTSTRAP_CLEANUP_FAILED",
                        "The Azure service principal is outside the setup-run boundary.",
                    )
                self._graph_json(
                    transport,
                    tokens.graph,
                    "DELETE",
                    f"/servicePrincipals/{principal_id}",
                    expected={204},
                    allow_empty=True,
                )
        if application is not None:
            self._graph_json(
                transport,
                tokens.graph,
                "DELETE",
                f"/applications/{application_id}",
                expected={204},
                allow_empty=True,
            )

    def _bundle_for_receipt(
        self,
        receipt: CloudBootstrapRollbackReceipt,
        target: AzureBootstrapTarget,
        subscription_id: str,
    ) -> dict[str, Any]:
        from src.services.deployment_policy_materializer import (
            materialize_azure_custom_role,
        )

        bundle = materialize_azure_custom_role(
            subscription_id=subscription_id,
            run_id=receipt.run_id,
        )
        self._validate_bundle(
            bundle,
            SupervisedLiveBootstrapPlan(
                provider="azure",
                run_id=receipt.run_id,
                deployment_document_json="{}",
            ),
            target,
            subscription_id,
        )
        return bundle

    def _validate_receipt_scope(
        self,
        receipt: CloudBootstrapRollbackReceipt,
        target: AzureBootstrapTarget,
        bundle: dict[str, Any],
    ) -> None:
        del target
        identifiers = dict(receipt.resource_ids)
        try:
            app_id = self._canonical_uuid(identifiers.get("application_object_id"))
            principal_id = (
                self._canonical_uuid(identifiers["service_principal_object_id"])
                if "service_principal_object_id" in identifiers
                else None
            )
            role_id = (
                self._canonical_uuid(identifiers["role_definition_id"])
                if "role_definition_id" in identifiers
                else None
            )
            assignment_id = (
                self._canonical_uuid(identifiers["role_assignment_id"])
                if "role_assignment_id" in identifiers
                else None
            )
            if "credential_key_id" in identifiers:
                self._canonical_uuid(identifiers["credential_key_id"])
        except Exception as exc:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The Azure rollback receipt has an invalid identifier boundary.",
            ) from exc
        expected_role = self._canonical_uuid(bundle["role_definition_id"])
        expected_assignment = (
            str(
                uuid5(
                    ROLE_ASSIGNMENT_NAMESPACE,
                    f"{bundle['scope']}:{expected_role}:{principal_id}",
                )
            )
            if principal_id is not None
            else None
        )
        if (
            not app_id
            or (role_id is not None and role_id != expected_role)
            or (assignment_id is not None and assignment_id != expected_assignment)
            or (assignment_id is not None and principal_id is None)
            or ("credential_key_id" in identifiers and not app_id)
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The Azure rollback receipt does not match its setup-run scope.",
            )

    @staticmethod
    def _validate_role_definition(
        document: dict[str, Any],
        bundle: dict[str, Any],
        role_id: str,
    ) -> None:
        expected_id = AzureCloudBootstrapDriver._role_resource_id(
            bundle["scope"], role_id
        )
        properties = document.get("properties", {})
        expected = bundle["properties"]
        if (
            str(document.get("id", "")).lower() != expected_id.lower()
            or AzureCloudBootstrapDriver._canonical_uuid(document.get("name"))
            != role_id
            or any(
                properties.get(key) != expected.get(key)
                for key in (
                    "roleName",
                    "description",
                    "type",
                    "permissions",
                    "assignableScopes",
                )
            )
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The Azure custom role differs from the reviewed v2 document.",
            )

    @staticmethod
    def _validate_role_assignment(
        document: dict[str, Any],
        scope: str,
        assignment_id: str,
        principal_id: str | None,
        role_resource_id: str,
    ) -> None:
        expected_id = (
            f"{scope}/providers/Microsoft.Authorization/roleAssignments/{assignment_id}"
        )
        properties = document.get("properties", {})
        if (
            str(document.get("id", "")).lower() != expected_id.lower()
            or AzureCloudBootstrapDriver._canonical_uuid(document.get("name"))
            != assignment_id
            or AzureCloudBootstrapDriver._canonical_uuid(
                properties.get("principalId")
            )
            != principal_id
            or str(properties.get("roleDefinitionId", "")).lower()
            != role_resource_id.lower()
            or str(properties.get("scope", scope)).lower() != scope.lower()
            or properties.get("principalType", "ServicePrincipal")
            != "ServicePrincipal"
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The Azure role assignment crosses the setup-run boundary.",
            )

    def _validate_owned_application(
        self,
        application: dict[str, Any],
        run_id: str,
    ) -> None:
        if (
            application.get("displayName") != f"{run_id}-deployer"
            or not isinstance(application.get("tags"), list)
            or sorted(application.get("tags", [])) != self._tags(run_id)
            or not isinstance(application.get("keyCredentials"), list)
            or not isinstance(application.get("passwordCredentials"), list)
            or application.get("keyCredentials")
            or any(
                not isinstance(item, dict)
                or item.get("displayName") != f"{run_id}-deployment"
                for item in application.get("passwordCredentials", [])
            )
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The Azure application is outside the setup-run boundary.",
            )

    def _graph_json(
        self,
        transport: AzureTransport,
        token: str,
        method: str,
        path: str,
        *,
        expected: set[int],
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        response = transport.request(
            method,
            f"{GRAPH_ROOT}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            json=body,
        )
        return self._response_json(response, expected=expected, allow_empty=allow_empty)

    def _arm_json(
        self,
        transport: AzureTransport,
        token: str,
        method: str,
        path: str,
        *,
        expected: set[int],
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        response = transport.request(
            method,
            f"{ARM_ROOT}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            json=body,
        )
        return self._response_json(response, expected=expected, allow_empty=allow_empty)

    def _graph_optional(
        self,
        transport: AzureTransport,
        token: str,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        response = transport.request(
            method,
            f"{GRAPH_ROOT}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        if response.status_code == 404:
            return None
        return self._response_json(response, expected={200})

    def _arm_optional(
        self,
        transport: AzureTransport,
        token: str,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        response = transport.request(
            method,
            f"{ARM_ROOT}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        if response.status_code == 404:
            return None
        return self._response_json(response, expected={200})

    @staticmethod
    def _response_json(
        response: AzureHTTPResponse,
        *,
        expected: set[int],
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        if response.status_code not in expected:
            raise _AzureRequestError(response.status_code)
        if allow_empty and response.status_code == 204:
            return {}
        document = response.json()
        if not isinstance(document, dict):
            raise _AzureRequestError(502)
        return document

    @staticmethod
    def _receipt(run_id: str, **identifiers: str) -> CloudBootstrapRollbackReceipt:
        return CloudBootstrapRollbackReceipt(
            provider="azure",
            run_id=run_id,
            resource_ids=tuple(sorted(identifiers.items())),
        )

    @staticmethod
    def _tags(run_id: str) -> list[str]:
        return sorted([MANAGED_TAG, f"{RUN_TAG_PREFIX}{run_id}"])

    @staticmethod
    def _role_resource_id(scope: str, role_id: str) -> str:
        return f"{scope}/providers/Microsoft.Authorization/roleDefinitions/{role_id}"

    @staticmethod
    def _canonical_uuid(value: Any) -> str:
        return str(UUID(str(value)))

    @staticmethod
    def _required_uuid(document: dict[str, Any], key: str) -> str:
        try:
            return AzureCloudBootstrapDriver._canonical_uuid(document.get(key))
        except (ValueError, TypeError, AttributeError) as exc:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "Azure returned an incomplete setup-only identifier.",
            ) from exc

    @staticmethod
    def _required_string(document: dict[str, Any], key: str) -> str:
        value = document.get(key)
        if not isinstance(value, str) or not value:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "Azure returned an incomplete setup-only response.",
            )
        return value

    @staticmethod
    def _provisional_disposal(
        origin: CloudBootstrapCredentialOrigin,
    ) -> tuple[CloudBootstrapDisposalStatus, bool]:
        if origin == CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED:
            return CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED, False
        return CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED, True

    @staticmethod
    def _close(transport: AzureTransport) -> None:
        close = getattr(transport, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _invalid_credential() -> CloudBootstrapAdapterError:
        return CloudBootstrapAdapterError(
            "BOOTSTRAP_CREDENTIAL_INVALID",
            "The Azure bootstrap credential does not match the selected tenant, subscription, or supported credential shape.",
        )
