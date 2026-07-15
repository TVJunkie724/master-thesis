import pytest

from src.providers.gcp import cleanup
from src.providers.cleanup_observability import ProviderCleanupError


def test_discovery_iterator_consumes_every_page():
    calls = []

    class Request:
        def __init__(self, response):
            self.response = response

        def execute(self):
            return self.response

    def list_method(**kwargs):
        calls.append(kwargs)
        if "pageToken" not in kwargs:
            return Request({"resources": ["one"], "nextPageToken": "next"})
        return Request({"resources": ["two"]})

    assert list(
        cleanup._discovery_items(
            list_method,
            "resources",
            parent="projects/demo",
        )
    ) == ["one", "two"]
    assert calls == [
        {"parent": "projects/demo"},
        {"parent": "projects/demo", "pageToken": "next"},
    ]


def test_discovery_iterator_handles_empty_result():
    class Request:
        def execute(self):
            return {}

    assert list(cleanup._discovery_items(lambda **kwargs: Request(), "items")) == []


def test_soft_deleted_custom_role_is_not_undeleted_or_deleted_again():
    class RolesApi:
        def delete(self, **kwargs):
            raise AssertionError("soft-deleted role must not be deleted again")

    deleted = cleanup._delete_custom_role(
        RolesApi(),
        {"name": "projects/demo/roles/factory", "deleted": True},
        dry_run=False,
    )

    assert deleted is False


def test_active_custom_role_is_deleted_once():
    calls = []

    class Request:
        def execute(self):
            calls.append("execute")

    class RolesApi:
        def delete(self, **kwargs):
            calls.append(kwargs)
            return Request()

    deleted = cleanup._delete_custom_role(
        RolesApi(),
        {"name": "projects/demo/roles/factory", "deleted": False},
        dry_run=False,
    )

    assert calls == [
        {"name": "projects/demo/roles/factory"},
        "execute",
    ]
    assert deleted is True


def test_bucket_drain_deletes_every_generation_without_page_tokens():
    list_calls = []
    delete_calls = []
    pages = [
        {
            "items": [
                {"name": "device.json", "generation": "2"},
                {"name": "device.json", "generation": "1"},
            ],
            "nextPageToken": "must-not-be-used-after-mutation",
        },
        {},
    ]

    class Request:
        def __init__(self, response=None, callback=None):
            self.response = response or {}
            self.callback = callback

        def execute(self):
            if self.callback:
                self.callback()
            return self.response

    class Objects:
        def list(self, **kwargs):
            list_calls.append(kwargs)
            return Request(pages.pop(0))

        def delete(self, **kwargs):
            return Request(callback=lambda: delete_calls.append(kwargs))

    class StorageClient:
        def objects(self):
            return Objects()

    cleanup._delete_all_bucket_objects(StorageClient(), "factory-bucket")

    assert list_calls == [
        {"bucket": "factory-bucket", "versions": True},
        {"bucket": "factory-bucket", "versions": True},
    ]
    assert delete_calls == [
        {"bucket": "factory-bucket", "object": "device.json", "generation": "2"},
        {"bucket": "factory-bucket", "object": "device.json", "generation": "1"},
    ]


def test_bucket_drain_fails_instead_of_looping_without_progress(monkeypatch):
    class Request:
        def __init__(self, response=None):
            self.response = response or {}

        def execute(self):
            return self.response

    class Objects:
        def list(self, **_kwargs):
            return Request({"items": [{"name": "stuck", "generation": "1"}]})

        def delete(self, **_kwargs):
            return Request()

    class StorageClient:
        def objects(self):
            return Objects()

    monkeypatch.setattr(cleanup.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="made no progress"):
        cleanup._delete_all_bucket_objects(
            StorageClient(),
            "factory-bucket",
            max_stalled_passes=2,
        )


def test_cleanup_runs_every_independent_step_and_raises_aggregate(monkeypatch):
    calls = []

    def failed_step(context):
        calls.append("failed")
        raise RuntimeError("private_key=must-not-leak")

    def successful_step(context):
        calls.append("successful")

    monkeypatch.setattr(
        "src.utils.gcp_utils.parse_gcp_service_account",
        lambda _value: ("project", "email", object()),
    )
    monkeypatch.setattr(
        cleanup,
        "_CLEANUP_STEPS",
        (("failed", failed_step), ("successful", successful_step)),
    )

    with pytest.raises(ProviderCleanupError) as exc_info:
        cleanup.cleanup_gcp_resources(
            {
                "gcp": {
                    "gcp_project_id": "project",
                    "gcp_service_account_key": "{}",
                }
            },
            "factory-twin",
        )

    assert calls == ["failed", "successful"]
    assert exc_info.value.failures[0].step == "failed"
    assert "must-not-leak" not in str(exc_info.value)


def test_delete_helper_never_mutates_resources_during_dry_run():
    deleted = []
    context = cleanup._GcpCleanupContext(
        credentials=object(),
        project_id="project",
        region="europe-west1",
        prefix="factory-twin",
        dry_run=True,
        run=cleanup.CleanupRun("GCP", cleanup.logger),
    )

    cleanup._delete_or_log(
        context,
        "Cloud Storage",
        "factory-twin-bucket",
        lambda: deleted.append(True),
    )

    assert deleted == []
    assert context.run.failures == ()


@pytest.mark.parametrize(
    "payload",
    [
        {"gcp": {"gcp_service_account_key": "{}"}},
        {"gcp": {"gcp_project_id": "project"}},
    ],
)
def test_cleanup_rejects_incomplete_gcp_context(payload):
    with pytest.raises(ValueError, match="GCP cleanup requires"):
        cleanup.cleanup_gcp_resources(payload, "factory-twin", dry_run=True)
