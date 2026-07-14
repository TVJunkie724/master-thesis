"""Characterization and security tests for the Functions API domains."""

import io
import json
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import rest_api
from api import function_artifacts, function_discovery, function_routes, function_upload
from api.function_build import MAX_FUNCTION_SOURCE_BYTES
from api.function_errors import FunctionProviderError
from src.core.paths import resolve_deployment_paths


client = TestClient(rest_api.app)


@pytest.mark.parametrize(
    ("provider", "source", "expected_files"),
    [
        ("aws", b"def lambda_handler(event, context):\n    return event\n", {"lambda_function.py"}),
        ("azure", b"def main(request):\n    return request\n", {"function_app.py", "host.json", "requirements.txt"}),
        ("google", b"def main(request):\n    return request\n", {"main.py", "requirements.txt"}),
        ("gcp", b"def main(request):\n    return request\n", {"main.py", "requirements.txt"}),
    ],
)
def test_build_function_zip_preserves_provider_contract(provider, source, expected_files):
    response = client.post(
        "/functions/build",
        params={"provider": provider},
        files={"function_file": ("handler.py", source, "text/x-python")},
    )

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert expected_files.issubset(set(archive.namelist()))


def test_build_function_zip_rejects_invalid_python():
    response = client.post(
        "/functions/build",
        params={"provider": "aws"},
        files={"function_file": ("handler.py", b"def broken(:\n", "text/x-python")},
    )

    assert response.status_code == 400
    assert "Python syntax error" in response.json()["detail"]


def test_build_function_zip_rejects_oversized_source():
    response = client.post(
        "/functions/build",
        params={"provider": "aws"},
        files={
            "function_file": (
                "handler.py",
                b"x" * (MAX_FUNCTION_SOURCE_BYTES + 1),
                "text/x-python",
            )
        },
    )

    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]


def test_update_function_short_circuits_when_hash_is_unchanged(monkeypatch, tmp_path):
    artifact = b"deployment artifact"
    artifact_hash = function_routes.hash_bytes(artifact)
    monkeypatch.setattr(
        function_routes,
        "_get_updatable_functions",
        lambda _project: {
            "processor": {
                "provider": "aws",
                "type": "processor",
                "exists": True,
                "path": "/runtime/processor",
            }
        },
    )
    monkeypatch.setattr(
        function_routes,
        "_compute_source_hash",
        lambda _path: "sha256:" + "a" * 64,
    )
    monkeypatch.setattr(function_routes, "_load_twin_name", lambda _project: "factory")
    monkeypatch.setattr(
        function_routes,
        "_build_provider_update_artifact",
        lambda *_args, **_kwargs: artifact,
    )
    monkeypatch.setattr(function_routes, "_get_upload_dir", lambda _project: str(tmp_path))
    monkeypatch.setattr(
        function_routes,
        "get_artifact_metadata",
        lambda *_args: {"deployed_artifact_hash": artifact_hash},
    )
    monkeypatch.setattr(
        function_routes,
        "_upload_aws_lambda",
        lambda *_args: pytest.fail("unchanged function must not be uploaded"),
    )

    response = client.post(
        "/functions/update_function/processor",
        params={"project_name": "runtime-project"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unchanged"
    assert response.json()["hash"] == artifact_hash


def test_update_function_does_not_skip_artifact_that_was_only_built(
    monkeypatch,
    tmp_path,
):
    artifact = b"deployment artifact"
    uploads = []
    monkeypatch.setattr(
        function_routes,
        "_get_updatable_functions",
        lambda _project: {
            "sensor-1": {
                "provider": "aws",
                "type": "processor",
                "exists": True,
                "path": "/runtime/processor",
            }
        },
    )
    monkeypatch.setattr(
        function_routes,
        "_compute_source_hash",
        lambda _path: "sha256:" + "a" * 64,
    )
    monkeypatch.setattr(function_routes, "_load_twin_name", lambda _project: "factory")
    monkeypatch.setattr(
        function_routes,
        "_build_provider_update_artifact",
        lambda *_args, **_kwargs: artifact,
    )
    monkeypatch.setattr(function_routes, "_get_upload_dir", lambda _project: str(tmp_path))
    monkeypatch.setattr(
        function_routes,
        "get_artifact_metadata",
        lambda *_args: {"artifact_hash": function_routes.hash_bytes(artifact)},
    )
    monkeypatch.setattr(
        function_routes,
        "_upload_aws_lambda",
        lambda name, content, project: uploads.append((name, content, project)) or {
            "success": True
        },
    )

    response = client.post(
        "/functions/update_function/sensor-1",
        params={"project_name": "runtime-project"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "updated"
    assert uploads == [("factory-sensor-1-processor", artifact, "runtime-project")]


def test_update_function_protects_template():
    response = client.post("/functions/update_function/processor")

    assert response.status_code == 400
    assert "protected system folder" in response.json()["detail"]


def test_function_discovery_maps_configured_function_domains(tmp_path, monkeypatch):
    (tmp_path / "lambda_functions" / "event_actions" / "notify").mkdir(parents=True)
    (tmp_path / "lambda_functions" / "processors" / "sensor-1").mkdir(parents=True)
    (tmp_path / "config_optimization.json").write_text(
        json.dumps({"result": {"inputParamsUsed": {
            "useEventChecking": True,
            "returnFeedbackToDevice": False,
        }}})
    )
    bundle = SimpleNamespace(
        project_path=tmp_path,
        config=SimpleNamespace(
            events=[{"action": {"functionName": "notify", "autoDeploy": True}}],
            iot_devices=[{"id": "sensor-1"}],
            providers={"layer_2_provider": "aws"},
        ),
    )
    monkeypatch.setattr(
        function_discovery,
        "ProjectConfigLoader",
        lambda: SimpleNamespace(load_bundle=lambda _project: bundle),
    )

    functions = function_discovery._get_updatable_functions("runtime-project")

    assert functions["notify"]["type"] == "event_action"
    assert functions["notify"]["exists"] is True
    assert functions["sensor-1"]["type"] == "processor"
    assert "event-feedback" not in functions


def test_function_discovery_accepts_canonical_google_provider(tmp_path, monkeypatch):
    (tmp_path / "cloud_functions" / "processors" / "sensor-1").mkdir(parents=True)
    bundle = SimpleNamespace(
        project_path=tmp_path,
        config=SimpleNamespace(
            events=[],
            iot_devices=[{"id": "sensor-1"}],
            providers={"layer_2_provider": "google"},
        ),
    )
    monkeypatch.setattr(
        function_discovery,
        "ProjectConfigLoader",
        lambda: SimpleNamespace(load_bundle=lambda _project: bundle),
    )

    functions = function_discovery._get_updatable_functions("runtime-project")

    assert functions["sensor-1"]["provider"] == "google"
    assert functions["sensor-1"]["exists"] is True


def test_directory_hash_is_deterministic_and_tracks_content(tmp_path):
    (tmp_path / "handler.py").write_text("value = 1\n")
    first = function_artifacts._compute_source_hash(str(tmp_path))
    second = function_artifacts._compute_source_hash(str(tmp_path))
    (tmp_path / "handler.py").write_text("value = 2\n")
    changed = function_artifacts._compute_source_hash(str(tmp_path))

    assert first == second
    assert changed != first
    assert first.startswith("sha256:")


@pytest.mark.parametrize(
    ("provider", "source_name"),
    [("aws", "lambda_function.py"), ("gcp", "main.py")],
)
def test_provider_update_artifact_includes_shared_runtime(
    tmp_path,
    monkeypatch,
    provider,
    source_name,
):
    function_dir = tmp_path / "function"
    function_dir.mkdir()
    (function_dir / source_name).write_text("VALUE = 1\n", encoding="utf-8")
    providers_root = tmp_path / "providers"
    shared_dir = providers_root / provider / (
        "lambda_functions" if provider == "aws" else "cloud_functions"
    ) / "_shared"
    shared_dir.mkdir(parents=True)
    (shared_dir / "runtime.py").write_text("SHARED = True\n", encoding="utf-8")
    monkeypatch.setattr(function_routes, "PROVIDERS_ROOT", providers_root)

    artifact = function_routes._build_provider_update_artifact(
        provider,
        str(function_dir),
        twin_name="factory",
        function_type="event_action",
        function_name="notify",
    )

    with zipfile.ZipFile(io.BytesIO(artifact)) as archive:
        names = set(archive.namelist())
    assert source_name in names
    assert "_shared/runtime.py" in names
    if provider == "gcp":
        assert "requirements.txt" in names


def test_function_artifacts_reject_symbolic_links(tmp_path):
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret")
    (tmp_path / "linked.txt").symlink_to(outside)

    with pytest.raises(ValueError, match="Symbolic links"):
        function_artifacts._compute_source_hash(str(tmp_path))
    with pytest.raises(ValueError, match="Symbolic links"):
        function_artifacts._build_function_zip(str(tmp_path))


@pytest.mark.parametrize(
    ("function_name", "provider"),
    [("../escape", "aws"), ("handler", "../escape"), (".", "aws")],
)
def test_hash_metadata_rejects_unsafe_path_components(function_name, provider):
    with pytest.raises(ValueError, match="Invalid"):
        function_artifacts._get_metadata_path("runtime-project", function_name, provider)


@pytest.mark.parametrize("project_name", ["../escape", ".", "/absolute", "nested/project"])
def test_deployment_paths_reject_unsafe_project_names(project_name):
    with pytest.raises(ValueError, match="Invalid project name"):
        resolve_deployment_paths(project_name)


def test_azure_token_failure_does_not_echo_downstream_body(tmp_path, monkeypatch):
    secret = "client-secret-that-must-not-leak"
    (tmp_path / "config_credentials.json").write_text(
        json.dumps(
            {"azure": {
                "azure_subscription_id": "subscription",
                "azure_tenant_id": "tenant",
                "azure_client_id": "client",
                "azure_client_secret": secret,
            }}
        )
    )
    monkeypatch.setattr(function_upload, "_get_upload_dir", lambda _project: str(tmp_path))
    monkeypatch.setattr(
        function_upload.requests,
        "post",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=401, text=secret),
    )

    with pytest.raises(FunctionProviderError) as exc_info:
        function_upload._upload_azure_function("app", b"zip", "runtime-project")

    assert "HTTP 401" in str(exc_info.value)
    assert secret not in str(exc_info.value)


def test_kudu_async_deployment_waits_for_terminal_success(monkeypatch):
    statuses = iter([1, 2, 4])
    calls = []
    monkeypatch.setattr(
        function_upload.requests,
        "get",
        lambda url, **kwargs: calls.append((url, kwargs))
        or SimpleNamespace(status_code=200, json=lambda: {"status": next(statuses)}),
    )
    monkeypatch.setattr(function_upload.time, "sleep", lambda _seconds: None)

    function_upload._wait_for_kudu_deployment(
        "https://app.scm.example/deployments/1",
        auth=("user", "password"),
    )

    assert len(calls) == 3
    assert all(call[1]["timeout"] == 30 for call in calls)


def test_kudu_async_deployment_fails_closed(monkeypatch):
    monkeypatch.setattr(
        function_upload.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {"status": 3},
        ),
    )

    with pytest.raises(FunctionProviderError, match="deployment failed"):
        function_upload._wait_for_kudu_deployment(
            "https://app.scm.example/deployments/1",
            auth=("user", "password"),
        )


def test_kudu_async_deployment_rejects_unknown_status(monkeypatch):
    monkeypatch.setattr(
        function_upload.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {"status": "complete"},
        ),
    )

    with pytest.raises(FunctionProviderError, match="unknown status"):
        function_upload._wait_for_kudu_deployment(
            "https://app.scm.example/deployments/1",
            auth=("user", "password"),
        )


@pytest.mark.parametrize(
    "location",
    [
        "http://app.scm.azurewebsites.net/api/deployments/1",
        "https://attacker.example/api/deployments/1",
    ],
)
def test_kudu_status_url_cannot_escape_expected_https_host(location):
    with pytest.raises(FunctionProviderError, match="expected host"):
        function_upload._resolve_kudu_status_url(
            location,
            "https://app.scm.azurewebsites.net/api/zipdeploy",
        )


def test_azure_async_deployment_requires_status_location(tmp_path, monkeypatch):
    (tmp_path / "config_credentials.json").write_text(
        json.dumps(
            {
                "azure": {
                    "azure_subscription_id": "subscription",
                    "azure_tenant_id": "tenant",
                    "azure_client_id": "client",
                    "azure_client_secret": "secret",
                }
            }
        )
    )
    (tmp_path / "config.json").write_text(
        json.dumps({"digital_twin_name": "factory"})
    )
    responses = iter(
        [
            SimpleNamespace(status_code=200, json=lambda: {"access_token": "token"}),
            SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "properties": {
                        "publishingUserName": "user",
                        "publishingPassword": "password",
                    }
                },
            ),
            SimpleNamespace(status_code=202, headers={}),
        ]
    )
    monkeypatch.setattr(function_upload, "_get_upload_dir", lambda _project: str(tmp_path))
    monkeypatch.setattr(
        function_upload.requests,
        "post",
        lambda *_args, **_kwargs: next(responses),
    )

    with pytest.raises(FunctionProviderError, match="without a status URL"):
        function_upload._upload_azure_function("app", b"zip", "runtime-project")


@pytest.mark.parametrize(
    ("provider", "function_type", "expected"),
    [
        ("aws", "event_action", "factory-alert"),
        ("aws", "processor", "factory-sensor-1-processor"),
        ("aws", "feedback", "factory-event-feedback"),
        ("google", "event_action", "factory-event-action-alert"),
        ("google", "processor", "factory-sensor-1-processor"),
        ("google", "feedback", "factory-event-feedback"),
    ],
)
def test_provider_function_names_match_terraform_contract(
    provider,
    function_type,
    expected,
):
    assert (
        function_routes._provider_function_name(
            provider,
            function_type,
            "factory",
            "sensor-1" if function_type == "processor" else "alert",
        )
        == expected
    )


def test_gcp_update_uses_v2_source_upload_contract(tmp_path, monkeypatch):
    credentials_file = tmp_path / "service-account.json"
    credentials_file.write_text("{}")
    (tmp_path / "config_credentials.json").write_text(
        json.dumps(
            {"gcp": {
                "gcp_project_id": "project-id",
                "gcp_region": "europe-west1",
                "gcp_credentials_file": credentials_file.name,
            }}
        )
    )
    monkeypatch.setattr(function_upload, "_get_upload_dir", lambda _project: str(tmp_path))
    fake_credentials = object()
    monkeypatch.setattr(
        function_upload.service_account.Credentials,
        "from_service_account_file",
        lambda _path: fake_credentials,
    )

    calls = {}
    source = function_upload.functions_v2.StorageSource(bucket="upload", object_="source.zip")
    cloud_function = function_upload.functions_v2.Function(
        name="projects/project-id/locations/europe-west1/functions/factory-alert",
        build_config=function_upload.functions_v2.BuildConfig(),
    )

    class FakeOperation:
        def result(self, timeout):
            calls["result_timeout"] = timeout
            return cloud_function

    class FakeClient:
        def generate_upload_url(self, request, timeout):
            calls["generate"] = (request, timeout)
            return SimpleNamespace(upload_url="https://upload.example", storage_source=source)

        def get_function(self, request, timeout):
            calls["get"] = (request, timeout)
            return cloud_function

        def update_function(self, request, timeout):
            calls["update"] = (request, timeout)
            return FakeOperation()

    monkeypatch.setattr(
        function_upload.functions_v2,
        "FunctionServiceClient",
        lambda credentials: FakeClient(),
    )
    monkeypatch.setattr(
        function_upload.requests,
        "put",
        lambda *_args, **kwargs: calls.setdefault(
            "put",
            SimpleNamespace(status_code=200, kwargs=kwargs),
        ),
    )

    result = function_upload._upload_gcp_function(
        "factory-alert",
        b"zip-content",
        "runtime-project",
    )

    assert result["success"] is True
    assert calls["generate"][0]["parent"] == "projects/project-id/locations/europe-west1"
    assert calls["update"][0]["update_mask"].paths == ["build_config.source"]
    assert calls["result_timeout"] == 900


def test_update_function_maps_provider_failure_to_bad_gateway(monkeypatch, tmp_path):
    monkeypatch.setattr(
        function_routes,
        "_get_updatable_functions",
        lambda _project: {
            "processor": {
                "provider": "aws",
                "type": "processor",
                "exists": True,
                "path": "/runtime/processor",
            }
        },
    )
    monkeypatch.setattr(
        function_routes,
        "_compute_source_hash",
        lambda _path: "sha256:" + "a" * 64,
    )
    monkeypatch.setattr(function_routes, "get_artifact_metadata", lambda *_args: None)
    monkeypatch.setattr(
        function_routes,
        "_build_provider_update_artifact",
        lambda *_args, **_kwargs: b"zip",
    )
    monkeypatch.setattr(function_routes, "_load_twin_name", lambda _project: "factory")
    monkeypatch.setattr(function_routes, "_get_upload_dir", lambda _project: str(tmp_path))
    monkeypatch.setattr(
        function_routes,
        "_upload_aws_lambda",
        lambda *_args: (_ for _ in ()).throw(FunctionProviderError("provider unavailable")),
    )

    response = client.post(
        "/functions/update_function/processor",
        params={"project_name": "runtime-project"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "provider unavailable"
