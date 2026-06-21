"""OpenAPI contract tests for Flutter-facing Management API responses."""

from __future__ import annotations

from src.main import app


def _response_ref(path: str, method: str = "get") -> str | None:
    operation = app.openapi()["paths"][path][method]
    response = operation["responses"]["200"]
    content = response.get("content", {}).get("application/json")
    if not content:
        return None
    return content["schema"].get("$ref")


def test_management_json_contracts_have_response_models():
    """Stable Flutter-facing JSON endpoints expose explicit OpenAPI schemas."""
    expected_refs = {
        ("/auth/google/login", "get"): "#/components/schemas/AuthUrlResponse",
        ("/auth/uibk/login", "get"): "#/components/schemas/AuthUrlResponse",
        ("/auth/me", "get"): "#/components/schemas/CurrentUserResponse",
        ("/auth/me", "patch"): "#/components/schemas/CurrentUserResponse",
        ("/auth/providers", "get"): "#/components/schemas/AuthProvidersResponse",
        ("/health", "get"): "#/components/schemas/HealthResponse",
        ("/twins/{twin_id}/can-redeploy", "get"): "#/components/schemas/RedeployReadinessResponse",
        ("/twins/{twin_id}/deploy", "post"): "#/components/schemas/OperationSessionResponse",
        ("/twins/{twin_id}/destroy", "post"): "#/components/schemas/OperationSessionResponse",
        ("/twins/{twin_id}/deployment-status", "get"): "#/components/schemas/DeploymentStatusResponse",
        ("/twins/{twin_id}/outputs", "get"): "#/components/schemas/DeploymentOutputsResponse",
        ("/twins/{twin_id}/deployments", "get"): "#/components/schemas/DeploymentHistoryResponse",
        ("/twins/{twin_id}/config/validate-stored/{provider}", "post"): (
            "#/components/schemas/DualCredentialValidationResponse"
        ),
        ("/config/validate-dual", "post"): "#/components/schemas/DualCredentialValidationResponse",
        ("/twins/{twin_id}/optimizer-config/cheapest-path", "get"): "#/components/schemas/CheapestPathResponse",
        ("/twins/{twin_id}/deployer/upload-glb", "post"): "#/components/schemas/SceneGlbUploadResponse",
        ("/twins/{twin_id}/deployer/upload-glb", "delete"): "#/components/schemas/MessageResponse",
    }

    for (path, method), expected_ref in expected_refs.items():
        assert _response_ref(path, method) == expected_ref


def test_documented_raw_payload_exceptions_remain_unmodeled():
    """Streaming, downloads, and dynamic downstream payloads stay explicitly raw."""
    raw_json_paths = [
        ("/twins/{twin_id}/deployer/upload-zip", "post"),
        ("/optimizer/calculate", "put"),
        ("/optimizer/pricing/export/{provider}", "get"),
        ("/optimizer/pricing-status", "get"),
        ("/optimizer/regions-status", "get"),
        ("/optimizer/refresh-pricing/{provider}", "post"),
    ]

    for path, method in raw_json_paths:
        assert _response_ref(path, method) is None
