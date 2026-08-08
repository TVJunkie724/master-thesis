from __future__ import annotations

import base64
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.api.deployment_trace import sanitize_terraform_outputs
from src.deployment_access.gcp_rotation import (
    GcpViewerRotationError,
    PodIdentity,
    rotate_gcp_grafana_viewer,
)


CA = b"-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----\n"


class _Config:
    def __init__(self, provider: str = "gcp"):
        self.provider = provider

    def get_provider_for_layer(self, layer: str) -> str:
        assert layer == "5"
        return self.provider


def _context(provider: str = "gcp") -> SimpleNamespace:
    return SimpleNamespace(
        config=_Config(provider),
        resolved_deployment_graph=SimpleNamespace(
            profile_ref={"id": "five-layer-baseline", "version": "2"}
        ),
    )


def _outputs() -> dict:
    return {
        "gcp_grafana_rotation_secret": {
            "cluster_host": "https://203.0.113.10",
            "cluster_ca_certificate": base64.b64encode(CA).decode("ascii"),
            "namespace": "t2mc-grafana",
            "secret_name": "grafana-runtime",
            "pod_label_selector": "app=grafana",
            "viewer_username": "researcher@example.invalid",
        }
    }


class _FakeClient:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(("create", kwargs))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def list_pods(self, namespace, selector):
        self.calls.append(("list", namespace, selector))
        return [PodIdentity(name="grafana-old", uid="old-uid")]

    def patch_viewer_password(self, namespace, secret_name, password):
        self.calls.append(("patch", namespace, secret_name, password))

    def delete_pod(self, namespace, pod_name):
        self.calls.append(("delete", namespace, pod_name))

    def replacement_is_ready(self, namespace, selector, previous_uids):
        self.calls.append(("ready", namespace, selector, previous_uids))
        return True


def test_rotation_patches_only_viewer_secret_replaces_pod_and_reveals_once(
    monkeypatch,
) -> None:
    fake = _FakeClient()
    monkeypatch.setattr(
        "src.deployment_access.gcp_rotation._bearer_token", lambda _context: "token"
    )

    credential = rotate_gcp_grafana_viewer(
        _context(),
        _outputs(),
        client_factory=fake,
        password_factory=lambda: "fixture-viewer-password-123456",
        now=lambda: datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
        sleep=lambda _seconds: None,
    )

    assert credential == {
        "schema_version": "deployment-access-credential.v1",
        "layer": "l5",
        "provider": "gcp",
        "username": "researcher@example.invalid",
        "password": "fixture-viewer-password-123456",
        "issued_at": "2026-07-31T12:00:00Z",
    }
    assert ("patch", "t2mc-grafana", "grafana-runtime", credential["password"]) in fake.calls
    assert ("delete", "t2mc-grafana", "grafana-old") in fake.calls
    assert ("ready", "t2mc-grafana", "app=grafana", {"old-uid"}) in fake.calls


def test_rotation_rejects_non_gcp_l5_before_authorization(monkeypatch) -> None:
    called = False

    def bearer(_context):
        nonlocal called
        called = True
        return "token"

    monkeypatch.setattr("src.deployment_access.gcp_rotation._bearer_token", bearer)

    with pytest.raises(GcpViewerRotationError, match="not available"):
        rotate_gcp_grafana_viewer(_context("aws"), _outputs())

    assert called is False


def test_rotation_requires_exact_internal_bundle(monkeypatch) -> None:
    outputs = _outputs()
    outputs["gcp_grafana_rotation_secret"]["admin_password"] = "must-not-cross"
    monkeypatch.setattr(
        "src.deployment_access.gcp_rotation._bearer_token", lambda _context: "token"
    )

    with pytest.raises(GcpViewerRotationError, match="evidence is unavailable"):
        rotate_gcp_grafana_viewer(_context(), outputs)


def test_generic_terraform_projection_redacts_internal_rotation_bundle() -> None:
    outputs = _outputs()

    sanitized = sanitize_terraform_outputs(outputs)

    assert sanitized == {"gcp_grafana_rotation_secret": "[REDACTED]"}
    assert "cluster_ca_certificate" not in str(sanitized)
