from types import SimpleNamespace

import pytest

from src.providers.azure import cleanup
from src.providers.cleanup_observability import ProviderCleanupError


class Response:
    def __init__(self, payload=None):
        self.payload = payload or {}
        self.raise_calls = 0

    def raise_for_status(self):
        self.raise_calls += 1

    def json(self):
        return self.payload


class Session:
    def __init__(self, users):
        self.get_response = Response({"value": users})
        self.delete_response = Response()
        self.get_calls = []
        self.delete_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.get_response

    def delete(self, url, **kwargs):
        self.delete_calls.append((url, kwargs))
        return self.delete_response


def _credential():
    return SimpleNamespace(
        get_token=lambda scope: SimpleNamespace(token="access-token")
    )


def test_entra_cleanup_deletes_only_exact_principal_with_deadlines():
    session = Session(
        [
            {"id": "wrong", "userPrincipalName": "other@example.com"},
            {"id": "target-id", "userPrincipalName": "Owner@Example.com"},
        ]
    )

    found = cleanup._cleanup_entra_user(
        _credential(),
        "owner@example.com",
        dry_run=False,
        http_session=session,
    )

    assert found is True
    assert session.get_calls[0][1]["timeout"] == 30
    assert session.get_calls[0][1]["params"]["$filter"] == (
        "userPrincipalName eq 'owner@example.com'"
    )
    assert session.delete_calls == [
        (
            f"{cleanup.GRAPH_USERS_URL}/target-id",
            {
                "headers": {"Authorization": "Bearer access-token"},
                "timeout": 30,
            },
        )
    ]


def test_entra_cleanup_is_idempotent_when_user_is_absent():
    session = Session([])

    assert cleanup._cleanup_entra_user(
        _credential(),
        "owner@example.com",
        dry_run=False,
        http_session=session,
    ) is False
    assert session.delete_calls == []


def test_entra_cleanup_dry_run_does_not_delete():
    session = Session(
        [{"id": "target-id", "userPrincipalName": "owner@example.com"}]
    )

    assert cleanup._cleanup_entra_user(
        _credential(),
        "owner@example.com",
        dry_run=True,
        http_session=session,
    ) is True
    assert session.delete_calls == []


def test_cleanup_runs_every_independent_step_and_raises_aggregate(monkeypatch):
    calls = []

    def failed_step(context):
        calls.append("failed")
        raise RuntimeError("azure_client_secret=must-not-leak")

    def successful_step(context):
        calls.append("successful")

    monkeypatch.setattr(
        "azure.identity.ClientSecretCredential",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        "azure.mgmt.resource.resources.ResourceManagementClient",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        cleanup,
        "_CLEANUP_STEPS",
        (("failed", failed_step), ("successful", successful_step)),
    )

    with pytest.raises(ProviderCleanupError) as exc_info:
        cleanup.cleanup_azure_resources(
            {
                "azure": {
                    "azure_tenant_id": "tenant",
                    "azure_client_id": "client",
                    "azure_client_secret": "secret",
                    "azure_subscription_id": "subscription",
                }
            },
            "factory-twin",
        )

    assert calls == ["failed", "successful"]
    assert exc_info.value.failures[0].step == "failed"
    assert "must-not-leak" not in str(exc_info.value)


def test_delete_helper_never_mutates_resources_during_dry_run():
    deleted = []
    context = cleanup._AzureCleanupContext(
        credential=object(),
        subscription_id="subscription",
        resource_client=object(),
        prefix="factory-twin",
        dry_run=True,
        run=cleanup.CleanupRun("Azure", cleanup.logger),
    )

    cleanup._delete_or_log(
        context,
        "Storage Accounts",
        "factorytwinstorage",
        lambda: deleted.append(True),
    )

    assert deleted == []
    assert context.run.failures == ()


@pytest.mark.parametrize(
    ("resource_id", "expected"),
    [
        ("/subscriptions/sub/resourceGroups/factory/providers/x/y", "factory"),
        ("/subscriptions/sub/resourceGroups/Factory/providers/x/y", "Factory"),
    ],
)
def test_resource_group_is_parsed_from_azure_resource_id(resource_id, expected):
    assert cleanup._resource_group(resource_id) == expected


def test_invalid_azure_resource_id_fails_closed():
    with pytest.raises(ValueError, match="resource group"):
        cleanup._resource_group("/subscriptions/sub")


def test_pinned_resource_sdk_exposes_the_supported_client_namespace():
    from azure.mgmt.resource.resources import ResourceManagementClient

    assert ResourceManagementClient.__name__ == "ResourceManagementClient"
