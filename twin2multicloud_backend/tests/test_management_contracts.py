"""OpenAPI contract tests for Flutter-facing Management API responses."""

from __future__ import annotations

import inspect
from pathlib import Path

from src.clients.deployer_client import DeployerClient
from src.clients.optimizer_client import OptimizerClient
from src.main import app


def _response_ref(path: str, method: str = "get") -> str | None:
    operation = app.openapi()["paths"][path][method]
    success_status = next(
        status for status in operation["responses"] if status.startswith("2")
    )
    response = operation["responses"][success_status]
    content = response.get("content", {}).get("application/json")
    if not content:
        return None
    return content["schema"].get("$ref")


def test_management_json_contracts_have_response_models():
    """Stable Flutter-facing JSON endpoints expose explicit OpenAPI schemas."""
    expected_refs = {
        ("/auth/providers/{provider}/login", "post"): "#/components/schemas/AuthStartResponse",
        ("/auth/session/exchange", "post"): "#/components/schemas/AuthSessionExchangeResponse",
        ("/auth/session/cancel", "post"): "#/components/schemas/MessageResponse",
        ("/auth/logout", "post"): "#/components/schemas/MessageResponse",
        ("/auth/me", "get"): "#/components/schemas/CurrentUserResponse",
        ("/auth/me", "patch"): "#/components/schemas/CurrentUserResponse",
        ("/auth/providers", "get"): "#/components/schemas/AuthProvidersResponse",
        ("/health", "get"): "#/components/schemas/HealthResponse",
        (
            "/twins/{twin_id}/can-redeploy",
            "get",
        ): "#/components/schemas/RedeployReadinessResponse",
        (
            "/twins/{twin_id}/deploy",
            "post",
        ): "#/components/schemas/OperationSessionResponse",
        (
            "/twins/{twin_id}/destroy",
            "post",
        ): "#/components/schemas/OperationSessionResponse",
        (
            "/twins/{twin_id}/deployment-readiness",
            "get",
        ): "#/components/schemas/DeploymentReadinessResponse",
        (
            "/twins/{twin_id}/deployment-preflight",
            "post",
        ): "#/components/schemas/DeploymentPreflightResponse",
        (
            "/twins/{twin_id}/deployment-status",
            "get",
        ): "#/components/schemas/DeploymentStatusResponse",
        (
            "/twins/{twin_id}/outputs",
            "get",
        ): "#/components/schemas/DeploymentOutputsResponse",
        (
            "/twins/{twin_id}/deployments",
            "get",
        ): "#/components/schemas/DeploymentHistoryResponse",
        ("/twins/{twin_id}/config/validate-stored/{provider}", "post"): (
            "#/components/schemas/DualCredentialValidationResponse"
        ),
        (
            "/config/validate-dual",
            "post",
        ): "#/components/schemas/DualCredentialValidationResponse",
        (
            "/twins/{twin_id}/optimizer-config/cheapest-path",
            "get",
        ): "#/components/schemas/CheapestPathResponse",
        (
            "/twins/{twin_id}/deployer/upload-glb",
            "post",
        ): "#/components/schemas/SceneGlbUploadResponse",
        (
            "/twins/{twin_id}/deployer/upload-glb",
            "delete",
        ): "#/components/schemas/MessageResponse",
        (
            "/twins/{twin_id}/deployer/upload-zip",
            "post",
        ): "#/components/schemas/ProjectZipExtractionContract",
    }

    for (path, method), expected_ref in expected_refs.items():
        assert _response_ref(path, method) == expected_ref


def test_auth_response_secrets_are_not_misclassified_as_write_only():
    components = app.openapi()["components"]["schemas"]

    poll_verifier = components["AuthStartResponse"]["properties"]["poll_verifier"]
    access_token = components["AuthSessionExchangeResponse"]["properties"][
        "access_token"
    ]
    assert poll_verifier["x-sensitive"] is True
    assert access_token["x-sensitive"] is True
    assert "writeOnly" not in poll_verifier
    assert "writeOnly" not in access_token


def test_twin_routes_keep_openapi_summaries_and_descriptions():
    """Twin adapters must remain usable as developer/thesis API documentation after route splits."""
    expected_routes = [
        ("/twins/", "get"),
        ("/twins/", "post"),
        ("/twins/{twin_id}", "get"),
        ("/twins/{twin_id}", "put"),
        ("/twins/{twin_id}", "delete"),
        ("/twins/{twin_id}/can-redeploy", "get"),
        ("/twins/{twin_id}/deploy", "post"),
        ("/twins/{twin_id}/destroy", "post"),
        ("/twins/{twin_id}/deployment-readiness", "get"),
        ("/twins/{twin_id}/deployment-preflight", "post"),
        ("/twins/{twin_id}/deployment-status", "get"),
        ("/twins/{twin_id}/outputs", "get"),
        ("/twins/{twin_id}/deployments", "get"),
        ("/twins/{twin_id}/log-trace/start", "post"),
        ("/twins/{twin_id}/log-trace/stream/{trace_id}", "get"),
        ("/twins/{twin_id}/verify/infrastructure", "post"),
        ("/twins/{twin_id}/verify/dataflow", "post"),
        ("/twins/{twin_id}/simulator/download", "get"),
        ("/twins/{twin_id}/export", "get"),
    ]

    schema = app.openapi()
    missing = []
    for path, method in expected_routes:
        operation = schema["paths"][path][method]
        if not operation.get("summary") or not operation.get("description"):
            missing.append(f"{method.upper()} {path}")

    assert missing == []


def test_documented_raw_payload_exceptions_remain_unmodeled():
    """Streaming, downloads, and dynamic downstream payloads stay explicitly raw."""
    raw_json_paths = [
        ("/optimizer/calculate", "put"),
        ("/optimizer/pricing/export/{provider}", "get"),
        ("/optimizer/pricing-status", "get"),
        ("/optimizer/regions-status", "get"),
        ("/optimizer/refresh-pricing/{provider}", "post"),
    ]

    for path, method in raw_json_paths:
        assert _response_ref(path, method) is None


def _public_client_methods(client_cls) -> set[str]:
    return {
        name
        for name, value in inspect.getmembers(client_cls)
        if not name.startswith("_")
        and (inspect.iscoroutinefunction(value) or inspect.isfunction(value))
    }


def test_downstream_client_contract_surface_is_explicit():
    """Optimizer/Deployer calls used by Management API are intentional contract methods."""
    assert _public_client_methods(OptimizerClient) == {
        "calculate",
        "export_pricing_snapshot",
        "get_cache_status",
        "refresh_azure_pricing",
        "refresh_pricing_with_credentials",
        "stream_pricing_refresh",
        "validate_optimizer_config",
        "verify_permissions",
    }
    assert _public_client_methods(DeployerClient) == {
        "check_cooldown",
        "deploy_stream",
        "destroy_stream",
        "download_simulator",
        "extract_project_zip",
        "stage_operation_package",
        "start_log_trace",
        "stream_log_trace",
        "validate_config_file",
        "validate_deployer_complete",
        "verify_dataflow",
        "verify_infrastructure",
        "verify_permissions",
    }


def test_downstream_http_access_is_centralized_in_client_layer():
    """Service/route code must not bypass OptimizerClient or DeployerClient."""
    backend_root = Path(__file__).resolve().parents[1]
    allowed = {
        Path("src/clients/base.py"),
        Path("src/clients/deployer_client.py"),
        Path("src/clients/optimizer_client.py"),
    }
    forbidden_tokens = (
        "httpx.AsyncClient",
        "settings.OPTIMIZER_URL",
        "settings.DEPLOYER_URL",
        'os.getenv("OPTIMIZER_URL"',
        'os.getenv("DEPLOYER_URL"',
    )
    findings = []

    for path in (backend_root / "src").rglob("*.py"):
        relative = path.relative_to(backend_root)
        if relative in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                findings.append(f"{relative}: contains {token}")

    assert findings == []
