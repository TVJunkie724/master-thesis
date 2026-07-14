from types import SimpleNamespace

from src.providers.azure import cleanup


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
