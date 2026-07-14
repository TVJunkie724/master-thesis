"""Guardrail for the Management API authentication boundary."""

from fastapi.routing import APIRoute

from src.api.dependencies import get_current_user
from src.main import app


PUBLIC_ROUTE_KEYS = {
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/auth/google/login"),
    ("GET", "/auth/google/callback"),
    ("GET", "/auth/uibk/login"),
    ("POST", "/auth/uibk/callback"),
    ("GET", "/auth/uibk/metadata"),
    ("GET", "/auth/providers"),
}


def _included_api_routes() -> list[APIRoute]:
    routes: list[APIRoute] = []
    for route in app.routes:
        included_router = getattr(route, "original_router", None)
        candidates = included_router.routes if included_router is not None else [route]
        routes.extend(candidate for candidate in candidates if isinstance(candidate, APIRoute))
    return routes


def _depends_on(dependant, dependency) -> bool:
    return any(
        child.call is dependency or _depends_on(child, dependency)
        for child in dependant.dependencies
    )


def test_every_non_public_api_route_requires_current_user():
    missing_auth: list[str] = []
    discovered_public: set[tuple[str, str]] = set()

    for route in _included_api_routes():
        for method in route.methods:
            key = (method, route.path)
            if key in PUBLIC_ROUTE_KEYS:
                discovered_public.add(key)
            elif not _depends_on(route.dependant, get_current_user):
                missing_auth.append(f"{method} {route.path}")

    assert discovered_public == PUBLIC_ROUTE_KEYS
    assert missing_auth == []
