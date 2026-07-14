from src.providers.aws import cleanup


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
