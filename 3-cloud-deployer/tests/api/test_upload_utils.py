"""Contract tests for bounded multipart and Base64 upload parsing."""

import base64
import sys

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import rest_api
from src.api import projects
from src.api.utils import extract_file_content


app = FastAPI()


@app.post("/upload")
async def upload(request: Request):
    content = await extract_file_content(request, max_bytes=4)
    return {"content": content.decode("ascii")}


client = TestClient(app)
project_client = TestClient(rest_api.app)


def test_multipart_upload_is_bounded():
    response = client.post(
        "/upload",
        files={"file": ("payload.txt", b"12345", "text/plain")},
    )

    assert response.status_code == 413
    assert "4 bytes" in response.json()["detail"]


def test_rest_api_uses_one_canonical_api_module_namespace():
    assert rest_api.projects is projects
    assert rest_api.projects.__name__ == "src.api.projects"
    forbidden_roots = {"api", "core", "providers"}
    assert not any(
        name.split(".", 1)[0] in forbidden_roots
        for name in sys.modules
    )


def test_json_base64_upload_is_strict_and_bounded():
    valid = client.post(
        "/upload",
        json={"file_base64": base64.b64encode(b"1234").decode("ascii")},
    )
    malformed = client.post("/upload", json={"file_base64": "!!!!"})
    oversized = client.post(
        "/upload",
        json={"file_base64": base64.b64encode(b"12345").decode("ascii")},
    )

    assert valid.status_code == 200
    assert valid.json() == {"content": "1234"}
    assert malformed.status_code == 400
    assert malformed.json()["detail"] == "Invalid Base64 string."
    assert oversized.status_code == 413


def test_json_envelope_is_bounded_before_parsing():
    response = client.post(
        "/upload",
        content=b'{"padding":"' + b"x" * (70 * 1024) + b'"}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert "4 bytes" in response.json()["detail"]


def test_upload_rejects_missing_file_and_unsupported_media_type():
    missing = client.post("/upload", json={"other": "value"})
    unsupported = client.post(
        "/upload",
        content=b"1234",
        headers={"content-type": "text/plain"},
    )

    assert missing.status_code == 400
    assert unsupported.status_code == 415


def test_config_route_preserves_payload_too_large_status(monkeypatch):
    monkeypatch.setattr(projects, "MAX_CONFIG_UPLOAD_BYTES", 4)

    response = project_client.put(
        "/projects/runtime/config/config",
        files={"file": ("config.json", b"12345", "application/json")},
    )

    assert response.status_code == 413


def test_simulator_payload_route_preserves_payload_too_large_status(monkeypatch):
    monkeypatch.setattr(projects, "MAX_SIMULATOR_PAYLOAD_UPLOAD_BYTES", 4)

    response = project_client.put(
        "/projects/runtime/simulator/payloads",
        files={"file": ("payloads.json", b"12345", "application/json")},
    )

    assert response.status_code == 413
