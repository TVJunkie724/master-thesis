from __future__ import annotations

import json

import pytest

from src.schemas.cloud_bootstrap import (
    AWSBootstrapCredential,
    AWSBootstrapTarget,
    AzureBootstrapCredential,
    AzureBootstrapTarget,
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
    GCPBootstrapCredential,
    GCPExistingProjectBootstrapTarget,
)
from src.schemas.cloud_connection import CloudConnectionCreate
from src.schemas.twin_config import AWSCredentials, AzureCredentials, GCPCredentials
from src.services.cloud_bootstrap_adapters import (
    CloudBootstrapAdapterError,
    CloudBootstrapAdapterResult,
    CloudBootstrapRollbackReceipt,
    SupervisedLiveBootstrapPlan,
    SupervisedLiveCloudBootstrapAdapter,
)


class RecordingDriver:
    def __init__(self, *, invalid_result: bool = False) -> None:
        self.invalid_result = invalid_result
        self.plans: list[SupervisedLiveBootstrapPlan] = []
        self.rollback_receipts: list[CloudBootstrapRollbackReceipt] = []

    def provision(
        self,
        *,
        plan,
        display_name,
        target,
        credential_origin,
        credential,
    ):
        del credential_origin, credential
        self.plans.append(plan)
        connection = _connection(plan.provider, display_name, target)
        if self.invalid_result:
            connection.permission_set_version = "thesis-demo-v1"
        return CloudBootstrapAdapterResult(
            connection=connection,
            safe_credential_identifier=f"{plan.provider}-bootstrap-key",
            disposal_status=CloudBootstrapDisposalStatus.REVOKED,
            generated_credential_validated=True,
            rollback_receipt=_receipt(plan),
        )

    def rollback(self, *, receipt, target, credential):
        del target, credential
        self.rollback_receipts.append(receipt)


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
def test_supervised_adapter_uses_exact_materialized_plan_without_provider_io(provider):
    target, credential = _input(provider)
    driver = RecordingDriver()
    adapter = SupervisedLiveCloudBootstrapAdapter({provider: driver})

    result = adapter.execute(
        session_id=f"session-{provider}-001",
        display_name=f"{provider.upper()} deployment access",
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=credential,
    )

    assert result.connection.provider == provider
    assert result.connection.permission_set_version == "thesis-demo-v2"
    assert result.connection.cloud_scope["bootstrap_mode"] == "supervised_live"
    assert result.generated_credential_validated is True
    assert len(driver.plans) == 1
    plan = driver.plans[0]
    assert plan.provider == provider
    assert plan.run_id.startswith("twin2mc-e2e-")
    assert "secret" not in plan.deployment_document_json.lower()
    if provider == "gcp":
        assert plan.gcp_api_baseline()["owner"] == "bootstrap.gcp.admin-v3"
        assert len(plan.gcp_api_baseline()["services"]) == 19
    else:
        assert plan.gcp_api_baseline() is None


def test_invalid_generated_connection_is_compensated_before_failure():
    target, credential = _input("aws")
    driver = RecordingDriver(invalid_result=True)
    adapter = SupervisedLiveCloudBootstrapAdapter({"aws": driver})

    with pytest.raises(
        CloudBootstrapAdapterError,
        match="generated deployment credential",
    ) as exc_info:
        adapter.execute(
            session_id="session-aws-invalid-result",
            display_name="AWS deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_CONNECTION_VALIDATION_FAILED"
    assert driver.rollback_receipts == [_receipt(driver.plans[0])]


def test_missing_driver_and_provider_mismatch_fail_before_mutation():
    aws_target, aws_credential = _input("aws")
    _, azure_credential = _input("azure")
    adapter = SupervisedLiveCloudBootstrapAdapter({})

    with pytest.raises(CloudBootstrapAdapterError) as missing:
        adapter.execute(
            session_id="session-aws-missing-driver",
            display_name="AWS deployment access",
            target=aws_target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=aws_credential,
        )
    assert missing.value.code == "BOOTSTRAP_IDENTITY_CREATION_FAILED"

    with pytest.raises(CloudBootstrapAdapterError) as mismatch:
        adapter.execute(
            session_id="session-provider-mismatch",
            display_name="AWS deployment access",
            target=aws_target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=azure_credential,
        )
    assert mismatch.value.code == "BOOTSTRAP_CREDENTIAL_INVALID"


def test_rollback_receipt_rejects_unknown_or_secret_shaped_data():
    with pytest.raises(ValueError, match="rollback receipt"):
        CloudBootstrapRollbackReceipt(
            provider="aws",
            run_id="twin2mc-e2e-a1b2c3d4",
            resource_ids=(("secret_access_key", "must-not-be-stored"),),
        )


def _receipt(plan: SupervisedLiveBootstrapPlan) -> CloudBootstrapRollbackReceipt:
    identifiers = {
        "aws": (("user_name", f"{plan.run_id}-deployer"),),
        "azure": (("application_object_id", "application-object-id"),),
        "gcp": (
            (
                "service_account_email",
                f"{plan.run_id}@example.iam.gserviceaccount.com",
            ),
        ),
    }[plan.provider]
    return CloudBootstrapRollbackReceipt(
        provider=plan.provider,
        run_id=plan.run_id,
        resource_ids=identifiers,
    )


def _input(provider: str):
    if provider == "aws":
        return (
            AWSBootstrapTarget(
                provider="aws",
                account_id="123456789012",
                region="eu-central-1",
            ),
            AWSBootstrapCredential(
                provider="aws",
                access_key_id="AKIAIOSFODNN7EXAMPLE",
                secret_access_key="submitted-aws-bootstrap-secret",
            ),
        )
    if provider == "azure":
        tenant = "11111111-1111-4111-8111-111111111111"
        subscription = "22222222-2222-4222-8222-222222222222"
        return (
            AzureBootstrapTarget(
                provider="azure",
                tenant_id=tenant,
                subscription_id=subscription,
                region="westeurope",
                bootstrap_credential_key_id="bootstrap-key-id",
            ),
            AzureBootstrapCredential(
                provider="azure",
                tenant_id=tenant,
                subscription_id=subscription,
                client_id="33333333-3333-4333-8333-333333333333",
                client_secret="submitted-azure-bootstrap-secret",
            ),
        )
    return (
        GCPExistingProjectBootstrapTarget(
            provider="gcp",
            mode="existing_project",
            project_id="twin2mc-test-project",
            region="europe-west1",
        ),
        GCPBootstrapCredential(
            provider="gcp",
            type="service_account",
            project_id="twin2mc-test-project",
            private_key_id="bootstrap-key-id",
            private_key="submitted-gcp-bootstrap-private-key",
            client_email=("bootstrap@twin2mc-test-project.iam.gserviceaccount.com"),
            client_id="12345678901234567890",
            token_uri="https://oauth2.googleapis.com/token",
        ),
    )


def _connection(provider: str, display_name: str, target):
    if provider == "aws":
        return CloudConnectionCreate(
            provider="aws",
            display_name=display_name,
            auth_type="access_key",
            permission_set_version="thesis-demo-v2",
            cloud_scope={
                "account_id": target.account_id,
                "region": target.region,
                "bootstrap_mode": "supervised_live",
            },
            aws=AWSCredentials(
                access_key_id="AKIAGENERATED0000001",
                secret_access_key="generated-aws-deployment-secret",
                region=target.region,
            ),
        )
    if provider == "azure":
        return CloudConnectionCreate(
            provider="azure",
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
                tenant_id=target.tenant_id,
                subscription_id=target.subscription_id,
                client_id="44444444-4444-4444-8444-444444444444",
                client_secret="generated-azure-deployment-secret",
                region=target.region,
            ),
        )
    service_account = {
        "type": "service_account",
        "project_id": target.project_id,
        "private_key_id": "generated-key-id",
        "private_key": "generated-gcp-deployment-private-key",
        "client_email": f"deployer@{target.project_id}.iam.gserviceaccount.com",
        "client_id": "98765432109876543210",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return CloudConnectionCreate(
        provider="gcp",
        display_name=display_name,
        auth_type="service_account_key",
        permission_set_version="thesis-demo-v2",
        cloud_scope={
            "provider": "gcp",
            "mode": "existing_project",
            "project_id": target.project_id,
            "region": target.region,
            "bootstrap_mode": "supervised_live",
        },
        gcp=GCPCredentials(
            project_id=target.project_id,
            service_account_json=json.dumps(service_account, sort_keys=True),
            region=target.region,
        ),
    )
