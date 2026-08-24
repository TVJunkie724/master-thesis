from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from urllib.parse import unquote, urlparse

import pytest

from src.schemas.cloud_bootstrap import (
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
    GCPBootstrapCredential,
    GCPExistingProjectBootstrapTarget,
)
from src.services.cloud_bootstrap_adapters import (
    CloudBootstrapAdapterError,
    CloudBootstrapRollbackReceipt,
    SupervisedLiveCloudBootstrapAdapter,
)
from src.services.gcp_cloud_bootstrap_driver import (
    GCPCloudBootstrapDriver,
    verify_private_key_matches_x509,
)


PROJECT_ID = "twin2mc-test-project"
PROJECT_NUMBER = "123456789012"
BOOTSTRAP_EMAIL = f"bootstrap@{PROJECT_ID}.iam.gserviceaccount.com"
BOOTSTRAP_KEY_ID = "bootstrap-key-id"
GENERATED_KEY_ID = "generated-key-id"


@dataclass
class FakeResponse:
    status_code: int
    document: dict | None = None

    def json(self):
        return self.document


class FakeGCPEnvironment:
    def __init__(
        self,
        *,
        billing_enabled: bool = True,
        unexpected_role_member: bool = False,
        fail_generated_validation: bool = False,
        fail_first_policy_update: bool = False,
        key_creation_forbidden: bool = False,
        missing_prerequisite: bool = False,
        service_account_visibility_failures: int = 0,
        generated_key_visibility_failures: int = 0,
        generated_client_id_override: str | None = None,
    ) -> None:
        self.billing_enabled = billing_enabled
        self.unexpected_role_member = unexpected_role_member
        self.fail_generated_validation = fail_generated_validation
        self.fail_first_policy_update = fail_first_policy_update
        self.key_creation_forbidden = key_creation_forbidden
        self.service_account_visibility_failures = service_account_visibility_failures
        self.generated_key_visibility_failures = generated_key_visibility_failures
        self.generated_client_id_override = generated_client_id_override
        self.key_pair_matches = True
        self.enabled_services = {
            "cloudresourcemanager.googleapis.com",
            "iam.googleapis.com",
            "serviceusage.googleapis.com",
        }
        if missing_prerequisite:
            self.enabled_services.remove("iam.googleapis.com")
        self.bootstrap_key_present = True
        self.service_account = None
        self.role = None
        self.policy = {"version": 3, "etag": "etag-1", "bindings": []}
        self.generated_key = None
        self.operation_counter = 0
        self.operations: list[str] = []

    def factory(self, credential_info):
        key_id = credential_info.get("private_key_id")
        if key_id == BOOTSTRAP_KEY_ID and self.bootstrap_key_present:
            identity = "bootstrap"
        elif key_id == GENERATED_KEY_ID and self.generated_key is not None:
            identity = "generated"
        else:
            raise RuntimeError("unknown fake GCP credential")
        return FakeGCPTransport(self, identity)


class FakeGCPTransport:
    def __init__(self, environment: FakeGCPEnvironment, identity: str) -> None:
        self.environment = environment
        self.identity = identity

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
        del headers, data
        path = unquote(urlparse(url).path)
        if "serviceusage.googleapis.com" in url:
            return self._service_usage(method, path, json)
        if "cloudresourcemanager.googleapis.com" in url:
            return self._resource_manager(method, path, json)
        if "cloudbilling.googleapis.com" in url:
            return self._billing(method, path)
        if "iam.googleapis.com" in url:
            return self._iam(method, path, params, json)
        return FakeResponse(404)

    def _resource_manager(self, method, path, body):
        if path == f"/v1/projects/{PROJECT_ID}" and method == "GET":
            return FakeResponse(
                200,
                {
                    "projectId": PROJECT_ID,
                    "projectNumber": PROJECT_NUMBER,
                    "lifecycleState": "ACTIVE",
                },
            )
        if path == f"/v1/projects/{PROJECT_ID}:getIamPolicy" and method == "POST":
            return FakeResponse(200, self._copy(self.environment.policy))
        if path == f"/v1/projects/{PROJECT_ID}:setIamPolicy" and method == "POST":
            if self.identity != "bootstrap":
                return FakeResponse(403)
            if self.environment.fail_first_policy_update:
                self.environment.fail_first_policy_update = False
                return FakeResponse(500)
            self.environment.operations.append("set_project_policy")
            self.environment.policy = self._copy(body["policy"])
            self.environment.policy["etag"] = (
                f"etag-{len(self.environment.operations) + 1}"
            )
            return FakeResponse(200, self._copy(self.environment.policy))
        if path == f"/v1/projects/{PROJECT_ID}:testIamPermissions" and method == "POST":
            permissions = list(body["permissions"])
            if (
                self.identity == "generated"
                and self.environment.fail_generated_validation
            ):
                permissions = permissions[:-1]
            return FakeResponse(200, {"permissions": permissions})
        return FakeResponse(404)

    def _service_usage(self, method, path, body):
        prefix = f"/v1/projects/{PROJECT_NUMBER}/services/"
        if path.startswith(prefix) and method == "GET":
            service = path.removeprefix(prefix)
            return FakeResponse(
                200,
                {
                    "name": f"projects/{PROJECT_NUMBER}/services/{service}",
                    "state": (
                        "ENABLED"
                        if service in self.environment.enabled_services
                        else "DISABLED"
                    ),
                },
            )
        if (
            path == f"/v1/projects/{PROJECT_NUMBER}/services:batchEnable"
            and method == "POST"
        ):
            if self.identity != "bootstrap":
                return FakeResponse(403)
            self.environment.operations.append("batch_enable")
            self.environment.enabled_services.update(body["serviceIds"])
            self.environment.operation_counter += 1
            return FakeResponse(
                200,
                {"name": f"operations/enable-{self.environment.operation_counter}"},
            )
        if path.startswith("/v1/operations/enable-") and method == "GET":
            return FakeResponse(200, {"name": path.removeprefix("/v1/"), "done": True})
        return FakeResponse(404)

    def _billing(self, method, path):
        if path == f"/v1/projects/{PROJECT_ID}/billingInfo" and method == "GET":
            return FakeResponse(
                200,
                {
                    "name": f"projects/{PROJECT_ID}/billingInfo",
                    "projectId": PROJECT_ID,
                    "billingAccountName": (
                        "billingAccounts/ABCDEF-123456-ABCDEF"
                        if self.environment.billing_enabled
                        else ""
                    ),
                    "billingEnabled": self.environment.billing_enabled,
                },
            )
        return FakeResponse(404)

    def _iam(self, method, path, params, body):
        account_path = f"/v1/projects/{PROJECT_ID}/serviceAccounts/"
        expected_email = None
        if self.environment.service_account:
            expected_email = self.environment.service_account["email"]

        if path == f"/v1/projects/{PROJECT_ID}/serviceAccounts" and method == "POST":
            if self.identity != "bootstrap":
                return FakeResponse(403)
            self.environment.operations.append("create_service_account")
            email = f"{body['accountId']}@{PROJECT_ID}.iam.gserviceaccount.com"
            self.environment.service_account = {
                "name": f"projects/{PROJECT_ID}/serviceAccounts/{email}",
                "projectId": PROJECT_ID,
                "uniqueId": "111111111111111111111",
                "email": email,
                "displayName": body["serviceAccount"]["displayName"],
                "description": body["serviceAccount"]["description"],
                "oauth2ClientId": "222222222222222222222",
                "disabled": False,
            }
            return FakeResponse(200, self._copy(self.environment.service_account))

        if path.startswith(account_path):
            suffix = path.removeprefix(account_path)
            email, separator, remainder = suffix.partition("/keys")
            if separator:
                return self._keys(method, email, remainder, params, body)
            if self.environment.service_account is None or email != expected_email:
                return FakeResponse(404)
            if method == "GET":
                if self.environment.service_account_visibility_failures:
                    self.environment.service_account_visibility_failures -= 1
                    return FakeResponse(404)
                return FakeResponse(200, self._copy(self.environment.service_account))
            if method == "DELETE":
                if self.identity != "bootstrap":
                    return FakeResponse(403)
                self.environment.operations.append("delete_service_account")
                self.environment.service_account = None
                self.environment.generated_key = None
                return FakeResponse(200, {})

        role_collection = f"/v1/projects/{PROJECT_ID}/roles"
        if path == role_collection and method == "POST":
            if self.identity != "bootstrap":
                return FakeResponse(403)
            self.environment.operations.append("create_role")
            self.environment.role = {
                "name": f"projects/{PROJECT_ID}/roles/{body['roleId']}",
                **self._copy(body["role"]),
                "deleted": False,
                "etag": "role-etag-1",
            }
            if self.environment.unexpected_role_member:
                self.environment.policy["bindings"].append(
                    {
                        "role": self.environment.role["name"],
                        "members": ["user:external@example.com"],
                    }
                )
            return FakeResponse(200, self._copy(self.environment.role))
        if path.startswith(f"{role_collection}/"):
            if (
                self.environment.role is None
                or path != f"/v1/{self.environment.role['name']}"
            ):
                return FakeResponse(404)
            if method == "GET":
                return FakeResponse(200, self._copy(self.environment.role))
            if method == "DELETE":
                if self.identity != "bootstrap":
                    return FakeResponse(403)
                self.environment.operations.append("delete_role")
                self.environment.role["deleted"] = True
                return FakeResponse(200, self._copy(self.environment.role))
        return FakeResponse(404)

    def _keys(self, method, email, remainder, params, body):
        if email == BOOTSTRAP_EMAIL:
            if method == "GET" and remainder == "":
                assert params == {"keyTypes": "USER_MANAGED"}
                keys = []
                if self.environment.bootstrap_key_present:
                    keys.append(
                        {
                            "name": (
                                f"projects/{PROJECT_ID}/serviceAccounts/"
                                f"{BOOTSTRAP_EMAIL}/keys/{BOOTSTRAP_KEY_ID}"
                            ),
                            "keyType": "USER_MANAGED",
                        }
                    )
                return FakeResponse(200, {"keys": keys})
            if method == "GET" and remainder == f"/{BOOTSTRAP_KEY_ID}":
                assert params == {"publicKeyType": "TYPE_X509_PEM_FILE"}
                return FakeResponse(
                    200,
                    {
                        "name": (
                            f"projects/{PROJECT_ID}/serviceAccounts/"
                            f"{BOOTSTRAP_EMAIL}/keys/{BOOTSTRAP_KEY_ID}"
                        ),
                        "keyType": "USER_MANAGED",
                        "keyAlgorithm": "KEY_ALG_RSA_2048",
                        "publicKeyData": "fake-bootstrap-x509",
                    },
                )
            if method == "DELETE" and remainder == f"/{BOOTSTRAP_KEY_ID}":
                self.environment.operations.append("delete_bootstrap_key")
                self.environment.bootstrap_key_present = False
                return FakeResponse(200, {})
            return FakeResponse(404)

        if (
            self.environment.service_account is None
            or email != self.environment.service_account["email"]
        ):
            return FakeResponse(404)
        if method == "GET" and remainder == "":
            assert params == {"keyTypes": "USER_MANAGED"}
            keys = []
            if self.environment.generated_key:
                keys.append(
                    {
                        "name": self.environment.generated_key["name"],
                        "keyType": "USER_MANAGED",
                    }
                )
            return FakeResponse(200, {"keys": keys})
        if method == "GET" and remainder == f"/{GENERATED_KEY_ID}":
            assert params == {"publicKeyType": "TYPE_X509_PEM_FILE"}
            if self.environment.generated_key_visibility_failures:
                self.environment.generated_key_visibility_failures -= 1
                return FakeResponse(404)
            return FakeResponse(
                200,
                {
                    "name": self.environment.generated_key["name"],
                    "keyType": "USER_MANAGED",
                    "keyAlgorithm": "KEY_ALG_RSA_2048",
                    "publicKeyData": "fake-generated-x509",
                },
            )
        if method == "POST" and remainder == "":
            if self.identity != "bootstrap":
                return FakeResponse(403)
            if self.environment.key_creation_forbidden:
                return FakeResponse(403)
            assert body == {
                "keyAlgorithm": "KEY_ALG_RSA_2048",
                "privateKeyType": "TYPE_GOOGLE_CREDENTIALS_FILE",
            }
            self.environment.operations.append("create_generated_key")
            document = {
                "type": "service_account",
                "project_id": PROJECT_ID,
                "private_key_id": GENERATED_KEY_ID,
                "private_key": "generated-gcp-private-key-material",
                "client_email": email,
                "client_id": (
                    self.environment.generated_client_id_override
                    or self.environment.service_account["oauth2ClientId"]
                ),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/generated",
                "universe_domain": "googleapis.com",
            }
            name = (
                f"projects/{PROJECT_ID}/serviceAccounts/{email}/keys/{GENERATED_KEY_ID}"
            )
            self.environment.generated_key = {
                "name": name,
                "keyType": "USER_MANAGED",
                "privateKeyType": "TYPE_GOOGLE_CREDENTIALS_FILE",
                "keyAlgorithm": "KEY_ALG_RSA_2048",
                "privateKeyData": base64.b64encode(
                    json.dumps(document).encode("utf-8")
                ).decode("ascii"),
            }
            return FakeResponse(200, self._copy(self.environment.generated_key))
        if method == "DELETE" and remainder == f"/{GENERATED_KEY_ID}":
            if self.identity != "bootstrap":
                return FakeResponse(403)
            self.environment.operations.append("delete_generated_key")
            self.environment.generated_key = None
            return FakeResponse(200, {})
        return FakeResponse(404)

    @staticmethod
    def _copy(value):
        return json.loads(json.dumps(value))


def _target():
    return GCPExistingProjectBootstrapTarget(
        provider="gcp",
        mode="existing_project",
        project_id=PROJECT_ID,
        region="europe-west1",
    )


def _credential():
    return GCPBootstrapCredential(
        provider="gcp",
        type="service_account",
        project_id=PROJECT_ID,
        private_key_id=BOOTSTRAP_KEY_ID,
        private_key="submitted-gcp-bootstrap-private-key",
        client_email=BOOTSTRAP_EMAIL,
        client_id="333333333333333333333",
        token_uri="https://oauth2.googleapis.com/token",
    )


def _adapter(environment):
    return SupervisedLiveCloudBootstrapAdapter(
        {
            "gcp": GCPCloudBootstrapDriver(
                transport_factory=environment.factory,
                sleeper=lambda _: None,
                key_pair_verifier=(
                    lambda _private, _public: environment.key_pair_matches
                ),
            )
        }
    )


def test_existing_project_bootstrap_enables_baseline_and_creates_bounded_identity():
    environment = FakeGCPEnvironment()
    adapter = _adapter(environment)

    result = adapter.execute(
        session_id="session-gcp-happy-path",
        display_name="GCP deployment access",
        target=_target(),
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=_credential(),
    )

    connection = result.connection
    generated = json.loads(connection.gcp.service_account_json)
    assert connection.cloud_scope == {
        "provider": "gcp",
        "mode": "existing_project",
        "project_id": PROJECT_ID,
        "region": "europe-west1",
        "bootstrap_mode": "supervised_live",
    }
    assert generated["client_email"].startswith("twin2mc-e2e-")
    assert generated["private_key_id"] == GENERATED_KEY_ID
    assert len(environment.enabled_services) == 19
    assert (
        result.disposal_status
        == CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
    )
    assert result.bootstrap_finalization_required is True
    assert dict(result.rollback_receipt.resource_ids) == {
        "key_id": GENERATED_KEY_ID,
        "role_name": environment.role["name"],
        "service_account_email": environment.service_account["email"],
    }
    assert environment.operations[:6] == [
        "batch_enable",
        "batch_enable",
        "create_service_account",
        "create_role",
        "set_project_policy",
        "create_generated_key",
    ]

    finalization = adapter.finalize_bootstrap(
        result=result,
        target=_target(),
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=_credential(),
    )
    assert finalization.disposal_status == CloudBootstrapDisposalStatus.REVOKED
    assert environment.bootstrap_key_present is False
    assert environment.service_account is not None
    assert environment.role is not None


def test_existing_user_owned_bootstrap_key_is_not_deleted():
    environment = FakeGCPEnvironment()
    result = _adapter(environment).execute(
        session_id="session-gcp-existing-owner",
        display_name="GCP deployment access",
        target=_target(),
        credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
        credential=_credential(),
    )

    assert (
        result.disposal_status == CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED
    )
    assert result.bootstrap_finalization_required is False
    assert environment.bootstrap_key_present is True


def test_unrecorded_generated_key_is_never_replaced_or_deleted():
    environment = FakeGCPEnvironment()
    adapter = _adapter(environment)
    adapter.execute(
        session_id="session-gcp-key-collision",
        display_name="GCP deployment access",
        target=_target(),
        credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
        credential=_credential(),
    )
    operations_before_retry = list(environment.operations)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id="session-gcp-key-collision",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_CLEANUP_FAILED"
    assert environment.generated_key is not None
    assert environment.service_account is not None
    assert environment.role["deleted"] is False
    assert "delete_generated_key" not in environment.operations[
        len(operations_before_retry) :
    ]
    assert "delete_service_account" not in environment.operations[
        len(operations_before_retry) :
    ]


def test_new_service_account_and_key_visibility_are_retried():
    environment = FakeGCPEnvironment(
        service_account_visibility_failures=2,
        generated_key_visibility_failures=2,
    )

    result = _adapter(environment).execute(
        session_id="session-gcp-eventual-consistency",
        display_name="GCP deployment access",
        target=_target(),
        credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
        credential=_credential(),
    )

    assert result.generated_credential_validated is True
    assert environment.service_account_visibility_failures == 0
    assert environment.generated_key_visibility_failures == 0


def test_service_account_visibility_timeout_uses_progressive_receipt_for_cleanup():
    environment = FakeGCPEnvironment(service_account_visibility_failures=7)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        _adapter(environment).execute(
            session_id="session-gcp-account-visibility-timeout",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_IDENTITY_CREATION_FAILED"
    assert environment.service_account is None
    assert environment.role is None
    assert len(environment.enabled_services) == 19


def test_generated_validation_failure_rolls_back_identity_but_retains_api_baseline():
    environment = FakeGCPEnvironment(fail_generated_validation=True)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        _adapter(environment).execute(
            session_id="session-gcp-invalid-generated",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_CONNECTION_VALIDATION_FAILED"
    assert environment.service_account is None
    assert environment.role["deleted"] is True
    assert environment.policy["bindings"] == []
    assert len(environment.enabled_services) == 19
    assert "delete_generated_key" in environment.operations
    assert "delete_service_account" in environment.operations
    assert "delete_role" in environment.operations


def test_generated_key_client_id_must_match_the_created_service_account():
    environment = FakeGCPEnvironment(generated_client_id_override="999999999999")

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        _adapter(environment).execute(
            session_id="session-gcp-generated-client-id-mismatch",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_IDENTITY_CREATION_FAILED"
    assert environment.service_account is None
    assert environment.role["deleted"] is True


def test_unbilled_project_fails_before_identity_creation_but_keeps_enabled_billing_api():
    environment = FakeGCPEnvironment(billing_enabled=False)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        _adapter(environment).execute(
            session_id="session-gcp-unbilled",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_SCOPE_UNSUPPORTED"
    assert "cloudbilling.googleapis.com" in environment.enabled_services
    assert environment.service_account is None


def test_missing_prerequisite_api_fails_before_any_setup_mutation():
    environment = FakeGCPEnvironment(missing_prerequisite=True)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        _adapter(environment).execute(
            session_id="session-gcp-missing-prerequisite",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_SCOPE_UNSUPPORTED"
    assert environment.operations == []


def test_key_creation_policy_block_fails_closed_and_removes_created_identity():
    environment = FakeGCPEnvironment(key_creation_forbidden=True)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        _adapter(environment).execute(
            session_id="session-gcp-key-policy-block",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_SCOPE_UNSUPPORTED"
    assert environment.service_account is None
    assert environment.role["deleted"] is True
    assert environment.policy["bindings"] == []
    assert len(environment.enabled_services) == 19


def test_partial_policy_failure_uses_progressive_receipt_for_clean_rollback():
    environment = FakeGCPEnvironment(fail_first_policy_update=True)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        _adapter(environment).execute(
            session_id="session-gcp-policy-failure",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_IDENTITY_CREATION_FAILED"
    assert environment.service_account is None
    assert environment.role["deleted"] is True
    assert environment.policy["bindings"] == []
    assert len(environment.enabled_services) == 19


def test_unowned_role_binding_collision_is_not_deleted_during_compensation():
    environment = FakeGCPEnvironment(unexpected_role_member=True)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        _adapter(environment).execute(
            session_id="session-gcp-external-role-binding",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_CLEANUP_FAILED"
    assert environment.service_account is not None
    assert environment.role["deleted"] is False
    assert environment.policy["bindings"][0]["members"] == ["user:external@example.com"]


def test_cleanup_refuses_role_binding_contaminated_by_external_member():
    environment = FakeGCPEnvironment()
    adapter = _adapter(environment)
    result = adapter.execute(
        session_id="session-gcp-contaminated-cleanup",
        display_name="GCP deployment access",
        target=_target(),
        credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
        credential=_credential(),
    )
    environment.policy["bindings"][0]["members"].append("user:external@example.com")

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.rollback(
            result=result,
            target=_target(),
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_CLEANUP_FAILED"
    assert environment.service_account is not None
    assert environment.generated_key is not None


def test_receipt_cannot_cross_project_scope():
    environment = FakeGCPEnvironment()
    driver = GCPCloudBootstrapDriver(
        transport_factory=environment.factory,
        sleeper=lambda _: None,
    )
    receipt = CloudBootstrapRollbackReceipt(
        provider="gcp",
        run_id="twin2mc-e2e-123456789012",
        resource_ids=(
            (
                "service_account_email",
                "twin2mc-e2e-123456789012@other-project.iam.gserviceaccount.com",
            ),
        ),
    )

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        driver.rollback(receipt=receipt, target=_target(), credential=_credential())

    assert exc_info.value.code == "BOOTSTRAP_CLEANUP_FAILED"


def test_gcp_target_and_submitted_key_must_match_exact_project_and_token_endpoint():
    credential = _credential().model_copy(
        update={"token_uri": "https://example.invalid/token"}
    )

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        _adapter(FakeGCPEnvironment()).execute(
            session_id="session-gcp-invalid-token-uri",
            display_name="GCP deployment access",
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_CREDENTIAL_INVALID"


def test_finalization_refuses_a_key_id_whose_public_key_does_not_match():
    environment = FakeGCPEnvironment()
    adapter = _adapter(environment)
    result = adapter.execute(
        session_id="session-gcp-bootstrap-key-mismatch",
        display_name="GCP deployment access",
        target=_target(),
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=_credential(),
    )
    environment.key_pair_matches = False

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.finalize_bootstrap(
            result=result,
            target=_target(),
            credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
            credential=_credential(),
        )

    assert exc_info.value.code == "BOOTSTRAP_CLEANUP_FAILED"
    assert environment.bootstrap_key_present is True


def test_private_key_match_uses_provider_x509_public_key():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    matching = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    different = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "twin2mc-test")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(matching.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(matching, hashes.SHA256())
    )
    encoded_certificate = base64.b64encode(
        certificate.public_bytes(serialization.Encoding.PEM)
    ).decode("ascii")

    def private_pem(key):
        return key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")

    assert verify_private_key_matches_x509(private_pem(matching), encoded_certificate)
    assert not verify_private_key_matches_x509(
        private_pem(different), encoded_certificate
    )
    assert not verify_private_key_matches_x509("invalid", encoded_certificate)
