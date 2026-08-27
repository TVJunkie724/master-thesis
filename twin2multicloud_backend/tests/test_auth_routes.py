"""Tests for the local single-user PoC identity surface."""


def test_me_requires_the_configured_poc_bearer(client):
    assert client.get("/auth/me").status_code == 401
    assert (
        client.get(
            "/auth/me", headers={"Authorization": "Bearer wrong-token"}
        ).status_code
        == 401
    )


def test_me_creates_and_returns_the_single_research_user(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "id": response.json()["id"],
        "email": "research-user@example.invalid",
        "name": "Research User",
        "theme_preference": "dark",
    }


def test_me_updates_only_the_supported_preference(client, auth_headers):
    updated = client.patch(
        "/auth/me",
        headers=auth_headers,
        json={"theme_preference": "light"},
    )
    rejected = client.patch(
        "/auth/me",
        headers=auth_headers,
        json={"role": "admin"},
    )

    assert updated.status_code == 200
    assert updated.json()["theme_preference"] == "light"
    assert rejected.status_code == 422


def test_product_authentication_routes_do_not_exist(client):
    assert client.get("/auth/providers").status_code == 404
    assert client.post("/auth/providers/google/login").status_code == 404
    assert client.post("/auth/session/exchange").status_code == 404
    assert client.get("/auth/uibk/metadata").status_code == 404
