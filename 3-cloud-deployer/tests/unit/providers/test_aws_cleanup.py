import pytest

from src.providers.aws import cleanup
from src.providers.cleanup_observability import ProviderCleanupError


def test_cleanup_session_preserves_temporary_session_token(monkeypatch):
    captured = {}

    class Session:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("boto3.Session", Session)

    cleanup._create_session(
        {
            "aws_access_key_id": "key",
            "aws_secret_access_key": "secret",
            "aws_session_token": "temporary-token",
        },
        "eu-central-1",
    )

    assert captured["aws_session_token"] == "temporary-token"
    assert captured["region_name"] == "eu-central-1"


def test_cleanup_list_helper_consumes_every_paginator_page():
    class Paginator:
        def paginate(self, **kwargs):
            assert kwargs == {"scope": "factory"}
            yield {"items": ["one"]}
            yield {"items": ["two", "three"]}

    class Client:
        def can_paginate(self, operation):
            assert operation == "list_resources"
            return True

        def get_paginator(self, operation):
            return Paginator()

    assert list(
        cleanup._items(
            Client(),
            "list_resources",
            "items",
            scope="factory",
        )
    ) == ["one", "two", "three"]


def test_cleanup_list_helper_supports_non_paginated_operations():
    class Client:
        def can_paginate(self, operation):
            return False

        def list_resources(self, **kwargs):
            return {"items": [kwargs["scope"]]}

    assert list(
        cleanup._items(
            Client(),
            "list_resources",
            "items",
            scope="factory",
        )
    ) == ["factory"]


def test_cleanup_runs_every_independent_step_and_raises_aggregate(monkeypatch):
    calls = []

    class Session:
        pass

    def failed_step(context):
        calls.append("failed")
        raise RuntimeError("aws_secret_access_key=must-not-leak")

    def successful_step(context):
        calls.append("successful")

    monkeypatch.setattr(cleanup, "_create_session", lambda *_args: Session())
    monkeypatch.setattr(
        cleanup,
        "_CLEANUP_STEPS",
        (("failed", failed_step), ("successful", successful_step)),
    )

    with pytest.raises(ProviderCleanupError) as exc_info:
        cleanup.cleanup_aws_resources(
            {
                "aws": {
                    "aws_access_key_id": "key",
                    "aws_secret_access_key": "secret",
                }
            },
            "factory-twin",
        )

    assert calls == ["failed", "successful"]
    assert exc_info.value.failures[0].step == "failed"
    assert "must-not-leak" not in str(exc_info.value)


def test_delete_helper_never_mutates_resources_during_dry_run():
    deleted = []
    context = cleanup._AwsCleanupContext(
        session=object(),
        prefix="factory-twin",
        dry_run=True,
        run=cleanup.CleanupRun("AWS", cleanup.logger),
    )

    cleanup._delete_or_log(
        context,
        "S3",
        "factory-twin-bucket",
        lambda: deleted.append(True),
    )

    assert deleted == []
    assert context.run.failures == ()
