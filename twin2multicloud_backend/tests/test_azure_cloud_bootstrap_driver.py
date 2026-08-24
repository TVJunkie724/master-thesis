from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import pytest

from src.schemas.cloud_bootstrap import (
    AzureBootstrapCredential,
    AzureBootstrapTarget,
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
)
from src.services.azure_cloud_bootstrap_driver import AzureCloudBootstrapDriver
from src.services.cloud_bootstrap_adapters import (
    CloudBootstrapAdapterError,
    SupervisedLiveCloudBootstrapAdapter,
)


TENANT_ID = "11111111-1111-4111-8111-111111111111"
SUBSCRIPTION_ID = "22222222-2222-4222-8222-222222222222"
BOOTSTRAP_CLIENT_ID = "33333333-3333-4333-8333-333333333333"
BOOTSTRAP_APP_OBJECT_ID = "44444444-4444-4444-8444-444444444444"
GENERATED_APP_OBJECT_ID = "55555555-5555-4555-8555-555555555555"
GENERATED_CLIENT_ID = "66666666-6666-4666-8666-666666666666"
GENERATED_SP_OBJECT_ID = "77777777-7777-4777-8777-777777777777"
GENERATED_KEY_ID = "88888888-8888-4888-8888-888888888888"
BOOTSTRAP_KEY_ID = "99999999-9999-4999-8999-999999999999"


@dataclass
class FakeResponse:
    status_code: int
    document: dict | None = None

    def json(self):
        return self.document


@dataclass
class FakeAzureEnvironment:
    tenant_id: str = TENANT_ID
    subscription_id: str = SUBSCRIPTION_ID
    bootstrap_client_id: str = BOOTSTRAP_CLIENT_ID
    bootstrap_secret: str = "submitted-azure-bootstrap-secret"
    generated_region_visible: bool = True
    external_assignment: bool = False

    def __post_init__(self):
        self.bootstrap_key_present = True
        self.application = None
        self.service_principal = None
        self.role = None
        self.assignment = None
        self.generated_secret = None
        self.generated_key_id = None
        self.key_counter = 0
        self.operations: list[str] = []

    def factory(self):
        return self

    def close(self):
        return None

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        params=None,
        data=None,
        json=None,
    ):
        del params
        path = urlparse(url).path
        if "login.microsoftonline.com" in url:
            return self._token(path, data)
        token = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
        if "graph.microsoft.com" in url:
            return self._graph(method, path.removeprefix("/v1.0"), token, json)
        if "management.azure.com" in url:
            return self._arm(method, path, token, json)
        return FakeResponse(404)

    def _token(self, path, data):
        if path != f"/{self.tenant_id}/oauth2/v2.0/token":
            return FakeResponse(401)
        client_id = data.get("client_id")
        secret = data.get("client_secret")
        scope = data.get("scope")
        if client_id == self.bootstrap_client_id and secret == self.bootstrap_secret:
            identity = "bootstrap"
        elif client_id == GENERATED_CLIENT_ID and secret == self.generated_secret:
            identity = "generated"
        else:
            return FakeResponse(401)
        if identity == "generated" and "graph.microsoft.com" in scope:
            return FakeResponse(403)
        audience = "graph" if "graph.microsoft.com" in scope else "arm"
        return FakeResponse(200, {"access_token": f"{identity}-{audience}"})

    def _graph(self, method, path, token, body):
        if token != "bootstrap-graph":
            return FakeResponse(403)
        if path == f"/applications(appId='{self.bootstrap_client_id}')" and method == "GET":
            credentials = (
                [{"keyId": BOOTSTRAP_KEY_ID, "displayName": "bootstrap"}]
                if self.bootstrap_key_present
                else []
            )
            return FakeResponse(
                200,
                {
                    "id": BOOTSTRAP_APP_OBJECT_ID,
                    "appId": self.bootstrap_client_id,
                    "displayName": "bootstrap-admin",
                    "tags": [],
                    "passwordCredentials": credentials,
                },
            )
        if path == "/applications" and method == "GET":
            return FakeResponse(200, {"value": [self.application] if self.application else []})
        if path == "/applications" and method == "POST":
            self.operations.append("create_application")
            self.application = {
                "id": GENERATED_APP_OBJECT_ID,
                "appId": GENERATED_CLIENT_ID,
                "displayName": body["displayName"],
                "tags": list(body["tags"]),
                "passwordCredentials": [],
                "keyCredentials": [],
            }
            return FakeResponse(201, dict(self.application))
        if path == "/servicePrincipals" and method == "GET":
            return FakeResponse(
                200,
                {"value": [self.service_principal] if self.service_principal else []},
            )
        if path == "/servicePrincipals" and method == "POST":
            self.operations.append("create_service_principal")
            self.service_principal = {
                "id": GENERATED_SP_OBJECT_ID,
                "appId": body["appId"],
                "displayName": self.application["displayName"],
                "tags": list(body["tags"]),
                "accountEnabled": True,
                "servicePrincipalType": "Application",
                "passwordCredentials": [],
                "keyCredentials": [],
            }
            return FakeResponse(201, dict(self.service_principal))
        if path.startswith("/applications/"):
            object_id, operation = self._object_and_operation(path, "/applications/")
            if object_id == BOOTSTRAP_APP_OBJECT_ID and operation == "removePassword":
                if method != "POST" or body.get("keyId") != BOOTSTRAP_KEY_ID:
                    return FakeResponse(400)
                self.operations.append("remove_bootstrap_password")
                self.bootstrap_key_present = False
                return FakeResponse(204)
            if object_id != GENERATED_APP_OBJECT_ID or self.application is None:
                return FakeResponse(404)
            if method == "GET" and operation is None:
                return FakeResponse(200, dict(self.application))
            if method == "POST" and operation == "addPassword":
                self.operations.append("add_generated_password")
                self.key_counter += 1
                self.generated_key_id = GENERATED_KEY_ID[:-1] + str(self.key_counter)
                self.generated_secret = f"generated-azure-secret-{self.key_counter}"
                credential = {
                    "keyId": self.generated_key_id,
                    "displayName": body["passwordCredential"]["displayName"],
                    "endDateTime": body["passwordCredential"]["endDateTime"],
                }
                self.application["passwordCredentials"] = [credential]
                return FakeResponse(200, {**credential, "secretText": self.generated_secret})
            if method == "POST" and operation == "removePassword":
                if body.get("keyId") != self.generated_key_id:
                    return FakeResponse(404)
                self.operations.append("remove_generated_password")
                self.application["passwordCredentials"] = []
                self.generated_key_id = None
                self.generated_secret = None
                return FakeResponse(204)
            if method == "DELETE" and operation is None:
                self.operations.append("delete_application")
                self.application = None
                return FakeResponse(204)
        if path.startswith("/servicePrincipals/"):
            object_id = path.removeprefix("/servicePrincipals/")
            if object_id != GENERATED_SP_OBJECT_ID or self.service_principal is None:
                return FakeResponse(404)
            if method == "GET":
                return FakeResponse(200, dict(self.service_principal))
            if method == "DELETE":
                self.operations.append("delete_service_principal")
                self.service_principal = None
                return FakeResponse(204)
        return FakeResponse(404)

    def _arm(self, method, path, token, body):
        if token not in {"bootstrap-arm", "generated-arm"}:
            return FakeResponse(403)
        if path == f"/subscriptions/{self.subscription_id}" and method == "GET":
            return FakeResponse(
                200,
                {
                    "id": path,
                    "subscriptionId": self.subscription_id,
                    "tenantId": self.tenant_id,
                    "state": "Enabled",
                },
            )
        if path == f"/subscriptions/{self.subscription_id}/locations" and method == "GET":
            values = [{"name": "westeurope"}] if self.generated_region_visible else []
            return FakeResponse(200, {"value": values})
        if "/roleDefinitions/" in path:
            if method == "GET":
                return FakeResponse(200, dict(self.role)) if self.role else FakeResponse(404)
            if token != "bootstrap-arm":
                return FakeResponse(403)
            if method == "PUT":
                self.operations.append("create_role_definition")
                role_id = path.rsplit("/", 1)[1]
                self.role = {
                    "id": path,
                    "name": role_id,
                    "properties": body["properties"],
                }
                return FakeResponse(201, dict(self.role))
            if method == "DELETE":
                self.operations.append("delete_role_definition")
                self.role = None
                return FakeResponse(204)
        if path.endswith("/providers/Microsoft.Authorization/roleAssignments"):
            if method != "GET":
                return FakeResponse(405)
            values = [dict(self.assignment)] if self.assignment else []
            if self.external_assignment:
                values.append(
                    {
                        "id": (
                            f"/subscriptions/{self.subscription_id}/providers/"
                            "Microsoft.Authorization/roleAssignments/"
                            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
                        ),
                        "name": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                        "properties": {
                            "principalId": GENERATED_SP_OBJECT_ID,
                            "principalType": "ServicePrincipal",
                            "roleDefinitionId": (
                                f"/subscriptions/{self.subscription_id}/providers/"
                                "Microsoft.Authorization/roleDefinitions/"
                                "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
                            ),
                            "scope": f"/subscriptions/{self.subscription_id}",
                        },
                    }
                )
            return FakeResponse(200, {"value": values})
        if "/roleAssignments/" in path:
            if method == "GET":
                return (
                    FakeResponse(200, dict(self.assignment))
                    if self.assignment
                    else FakeResponse(404)
                )
            if token != "bootstrap-arm":
                return FakeResponse(403)
            if method == "PUT":
                self.operations.append("create_role_assignment")
                assignment_id = path.rsplit("/", 1)[1]
                scope = path.split("/providers/Microsoft.Authorization", 1)[0]
                self.assignment = {
                    "id": path,
                    "name": assignment_id,
                    "properties": {**body["properties"], "scope": scope},
                }
                return FakeResponse(201, dict(self.assignment))
            if method == "DELETE":
                self.operations.append("delete_role_assignment")
                self.assignment = None
                return FakeResponse(204)
        return FakeResponse(404)

    @staticmethod
    def _object_and_operation(path, prefix):
        value = path.removeprefix(prefix)
        if "/" not in value:
            return value, None
        return tuple(value.split("/", 1))


def test_azure_driver_provisions_validates_and_finalizes_exact_bootstrap_secret():
    environment = FakeAzureEnvironment()
    adapter = _adapter(environment)
    target, credential = _input(environment, bootstrap_key_id=BOOTSTRAP_KEY_ID)

    result = adapter.execute(
        session_id="azure-provider-driver-session",
        display_name="Azure deployment access",
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=credential,
    )

    assert result.connection.azure.client_id == GENERATED_CLIENT_ID
    assert result.connection.azure.client_secret == environment.generated_secret
    assert result.disposal_status == CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
    assert result.bootstrap_finalization_required is True
    assert environment.operations[:5] == [
        "create_application",
        "create_service_principal",
        "create_role_definition",
        "create_role_assignment",
        "add_generated_password",
    ]

    finalized = adapter.finalize_bootstrap(
        result=result,
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=credential,
    )
    assert finalized.disposal_status == CloudBootstrapDisposalStatus.REVOKED
    assert environment.bootstrap_key_present is False
    assert environment.generated_secret is not None


def test_azure_driver_reconciles_retry_and_rolls_back_only_gate_resources():
    environment = FakeAzureEnvironment()
    adapter = _adapter(environment)
    target, credential = _input(environment)
    first = adapter.execute(
        session_id="azure-reconcile-session",
        display_name="Azure deployment access",
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
        credential=credential,
    )
    first_secret = first.connection.azure.client_secret
    second = adapter.execute(
        session_id="azure-reconcile-session",
        display_name="Azure deployment access",
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
        credential=credential,
    )

    assert second.connection.azure.client_secret != first_secret
    assert environment.operations.count("create_application") == 1
    assert environment.operations.count("create_service_principal") == 1
    assert environment.operations.count("create_role_definition") == 1
    assert environment.operations.count("create_role_assignment") == 1
    assert environment.operations.count("remove_generated_password") == 1

    adapter.rollback(result=second, target=target, credential=credential)
    assert environment.application is None
    assert environment.service_principal is None
    assert environment.role is None
    assert environment.assignment is None
    assert environment.bootstrap_key_present is True


def test_azure_disposable_secret_without_key_id_remains_manual_revocation():
    environment = FakeAzureEnvironment()
    adapter = _adapter(environment)
    target, credential = _input(environment)
    result = adapter.execute(
        session_id="azure-manual-bootstrap-secret",
        display_name="Azure deployment access",
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=credential,
    )

    finalized = adapter.finalize_bootstrap(
        result=result,
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=credential,
    )

    assert finalized.disposal_status == (
        CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
    )
    assert environment.bootstrap_key_present is True
    assert "remove_bootstrap_password" not in environment.operations


def test_azure_generated_validation_failure_self_compensates_without_secret_output():
    environment = FakeAzureEnvironment(generated_region_visible=False)
    sleeps: list[float] = []
    adapter = SupervisedLiveCloudBootstrapAdapter(
        {
            "azure": AzureCloudBootstrapDriver(
                transport_factory=environment.factory,
                sleeper=sleeps.append,
                clock=lambda: datetime(2026, 8, 24, tzinfo=timezone.utc),
            )
        }
    )
    target, credential = _input(environment)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id="azure-validation-failure-session",
            display_name="Azure deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_CONNECTION_VALIDATION_FAILED"
    assert environment.application is None
    assert environment.service_principal is None
    assert environment.role is None
    assert environment.assignment is None
    assert sleeps == [1, 2, 4]
    assert environment.bootstrap_secret not in str(exc_info.value)


def test_azure_wrong_subscription_fails_before_any_mutation():
    environment = FakeAzureEnvironment(subscription_id=SUBSCRIPTION_ID)
    adapter = _adapter(environment)
    target, credential = _input(
        environment,
        target_subscription="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id="azure-wrong-subscription-session",
            display_name="Azure deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_CREDENTIAL_INVALID"
    assert environment.operations == []


def test_azure_rejected_bootstrap_secret_is_a_safe_credential_error():
    environment = FakeAzureEnvironment()
    adapter = _adapter(environment)
    target, _ = _input(environment)
    credential = AzureBootstrapCredential(
        provider="azure",
        tenant_id=environment.tenant_id,
        subscription_id=environment.subscription_id,
        client_id=environment.bootstrap_client_id,
        client_secret="wrong-bootstrap-secret",
    )

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id="azure-rejected-secret-session",
            display_name="Azure deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_CREDENTIAL_INVALID"
    assert environment.operations == []
    assert "wrong-bootstrap-secret" not in str(exc_info.value)


def test_azure_unowned_application_collision_is_not_deleted():
    environment = FakeAzureEnvironment()
    session_id = "azure-unowned-application"
    run_id = SupervisedLiveCloudBootstrapAdapter._plan(
        session_id,
        _input(environment)[0],
    ).run_id
    environment.application = {
        "id": GENERATED_APP_OBJECT_ID,
        "appId": GENERATED_CLIENT_ID,
        "displayName": f"{run_id}-deployer",
        "tags": ["owner=someone-else"],
        "passwordCredentials": [],
    }
    adapter = _adapter(environment)
    target, credential = _input(environment)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id=session_id,
            display_name="Azure deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_IDENTITY_CREATION_FAILED"
    assert environment.application is not None
    assert "delete_application" not in environment.operations


def test_azure_owned_name_with_external_credential_is_not_deleted():
    environment = FakeAzureEnvironment()
    session_id = "azure-external-application-credential"
    run_id = SupervisedLiveCloudBootstrapAdapter._plan(
        session_id,
        _input(environment)[0],
    ).run_id
    environment.application = {
        "id": GENERATED_APP_OBJECT_ID,
        "appId": GENERATED_CLIENT_ID,
        "displayName": f"{run_id}-deployer",
        "tags": sorted(
            [
                "twin2mc:managed-by=setup-only",
                f"twin2mc:run-id={run_id}",
            ]
        ),
        "passwordCredentials": [
            {
                "keyId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "displayName": "external-credential",
            }
        ],
        "keyCredentials": [],
    }
    adapter = _adapter(environment)
    target, credential = _input(environment)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id=session_id,
            display_name="Azure deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_IDENTITY_CREATION_FAILED"
    assert environment.application is not None
    assert "delete_application" not in environment.operations


def test_azure_external_role_assignment_blocks_cleanup_without_deleting_identity():
    environment = FakeAzureEnvironment(external_assignment=True)
    adapter = _adapter(environment)
    target, credential = _input(environment)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id="azure-external-role-assignment",
            display_name="Azure deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_CLEANUP_FAILED"
    assert environment.application is not None
    assert environment.service_principal is not None
    assert environment.role is not None
    assert environment.assignment is not None
    assert not any(operation.startswith("delete_") for operation in environment.operations)


def _adapter(environment):
    return SupervisedLiveCloudBootstrapAdapter(
        {
            "azure": AzureCloudBootstrapDriver(
                transport_factory=environment.factory,
                sleeper=lambda _seconds: None,
                clock=lambda: datetime(2026, 8, 24, tzinfo=timezone.utc),
            )
        }
    )


def _input(
    environment,
    *,
    bootstrap_key_id=None,
    target_subscription=None,
):
    return (
        AzureBootstrapTarget(
            provider="azure",
            tenant_id=environment.tenant_id,
            subscription_id=target_subscription or environment.subscription_id,
            region="westeurope",
            bootstrap_credential_key_id=bootstrap_key_id,
        ),
        AzureBootstrapCredential(
            provider="azure",
            tenant_id=environment.tenant_id,
            subscription_id=environment.subscription_id,
            client_id=environment.bootstrap_client_id,
            client_secret=environment.bootstrap_secret,
        ),
    )
