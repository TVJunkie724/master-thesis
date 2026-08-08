"""Explicit GCP Grafana Viewer rotation through the existing GKE workload."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import tempfile
import time
from typing import Any, Callable
from urllib.parse import quote, urlsplit

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
import requests


class GcpViewerRotationError(RuntimeError):
    """Safe failure raised by the bounded GCP Viewer rotation adapter."""


@dataclass(frozen=True)
class PodIdentity:
    name: str
    uid: str


REQUIRED_ROTATION_KEYS = {
    "cluster_host",
    "cluster_ca_certificate",
    "namespace",
    "secret_name",
    "pod_label_selector",
    "viewer_username",
}
GCP_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class GcpKubernetesViewerClient:
    """Minimal Kubernetes REST adapter; no general cluster API is exposed."""

    def __init__(
        self,
        *,
        host: str,
        ca_certificate: bytes,
        bearer_token: str,
        session: requests.Session | None = None,
    ):
        parsed = urlsplit(host)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"}:
            raise GcpViewerRotationError("GKE control-plane host is invalid")
        if not ca_certificate.startswith(b"-----BEGIN CERTIFICATE-----"):
            raise GcpViewerRotationError("GKE CA certificate is invalid")
        if not bearer_token:
            raise GcpViewerRotationError("GKE access token is unavailable")
        self._host = host.rstrip("/")
        self._token = bearer_token
        self._session = session or requests.Session()
        handle = tempfile.NamedTemporaryFile(
            prefix="t2mc-gke-ca-",
            suffix=".pem",
            delete=False,
        )
        self._ca_path = Path(handle.name)
        try:
            handle.write(ca_certificate)
            handle.flush()
        finally:
            handle.close()
        self._ca_path.chmod(0o600)

    def close(self) -> None:
        self._ca_path.unlink(missing_ok=True)
        self._session.close()

    def __enter__(self) -> "GcpKubernetesViewerClient":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected: set[int],
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._session.request(
                method,
                f"{self._host}{path}",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/json",
                    "Content-Type": "application/merge-patch+json",
                },
                json=json_body,
                params=params,
                timeout=30,
                verify=str(self._ca_path),
            )
        except requests.RequestException as exc:
            raise GcpViewerRotationError("GKE rotation request failed") from exc
        if response.status_code not in expected:
            raise GcpViewerRotationError(
                f"GKE rotation request returned HTTP {response.status_code}"
            )
        if not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise GcpViewerRotationError("GKE rotation response was invalid") from exc
        if not isinstance(payload, dict):
            raise GcpViewerRotationError("GKE rotation response was invalid")
        return payload

    def list_pods(self, namespace: str, selector: str) -> list[PodIdentity]:
        payload = self._request(
            "GET",
            f"/api/v1/namespaces/{quote(namespace, safe='')}/pods",
            expected={200},
            params={"labelSelector": selector},
        )
        identities: list[PodIdentity] = []
        for item in payload.get("items", []):
            metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
            name = metadata.get("name")
            uid = metadata.get("uid")
            if isinstance(name, str) and name and isinstance(uid, str) and uid:
                identities.append(PodIdentity(name=name, uid=uid))
        return identities

    def patch_viewer_password(
        self,
        namespace: str,
        secret_name: str,
        password: str,
    ) -> None:
        encoded = base64.b64encode(password.encode("utf-8")).decode("ascii")
        self._request(
            "PATCH",
            f"/api/v1/namespaces/{quote(namespace, safe='')}/secrets/{quote(secret_name, safe='')}",
            expected={200},
            json_body={"data": {"viewer-password": encoded}},
        )

    def delete_pod(self, namespace: str, pod_name: str) -> None:
        self._request(
            "DELETE",
            f"/api/v1/namespaces/{quote(namespace, safe='')}/pods/{quote(pod_name, safe='')}",
            expected={200, 202},
            json_body={"gracePeriodSeconds": 0},
        )

    def replacement_is_ready(
        self,
        namespace: str,
        selector: str,
        previous_uids: set[str],
    ) -> bool:
        payload = self._request(
            "GET",
            f"/api/v1/namespaces/{quote(namespace, safe='')}/pods",
            expected={200},
            params={"labelSelector": selector},
        )
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata", {})
            status = item.get("status", {})
            uid = metadata.get("uid")
            conditions = status.get("conditions", [])
            ready = any(
                isinstance(condition, dict)
                and condition.get("type") == "Ready"
                and condition.get("status") == "True"
                for condition in conditions
            )
            if (
                isinstance(uid, str)
                and uid not in previous_uids
                and status.get("phase") == "Running"
                and ready
            ):
                return True
        return False


def _rotation_bundle(outputs: dict[str, Any]) -> dict[str, str]:
    bundle = outputs.get("gcp_grafana_rotation_secret")
    if not isinstance(bundle, dict) or set(bundle) != REQUIRED_ROTATION_KEYS:
        raise GcpViewerRotationError("GCP Grafana rotation evidence is unavailable")
    if any(not isinstance(bundle[key], str) or not bundle[key].strip() for key in bundle):
        raise GcpViewerRotationError("GCP Grafana rotation evidence is invalid")
    return bundle


def _service_account_info(context: Any) -> dict[str, Any]:
    credential = getattr(context, "credentials", {}).get("gcp", {})
    raw_path = credential.get("gcp_credentials_file")
    if not isinstance(raw_path, str) or not raw_path:
        raise GcpViewerRotationError("GCP deployment credential is unavailable")
    root = Path(context.project_path).resolve()
    candidate = Path(raw_path)
    path = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise GcpViewerRotationError("GCP deployment credential path is invalid")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GcpViewerRotationError("GCP deployment credential is unreadable") from exc
    if not isinstance(document, dict) or document.get("type") != "service_account":
        raise GcpViewerRotationError("GCP deployment credential is invalid")
    return document


def _bearer_token(context: Any) -> str:
    try:
        credentials = service_account.Credentials.from_service_account_info(
            _service_account_info(context),
            scopes=[GCP_SCOPE],
        )
        credentials.refresh(GoogleAuthRequest())
    except GcpViewerRotationError:
        raise
    except Exception as exc:
        raise GcpViewerRotationError("GCP rotation authorization failed") from exc
    if not credentials.token:
        raise GcpViewerRotationError("GCP rotation authorization failed")
    return credentials.token


def rotate_gcp_grafana_viewer(
    context: Any,
    outputs: dict[str, Any],
    *,
    client_factory: Callable[..., GcpKubernetesViewerClient] = GcpKubernetesViewerClient,
    password_factory: Callable[[], str] | None = None,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Rotate the Viewer password and reveal it only after the new pod is ready."""

    graph = getattr(context, "resolved_deployment_graph", None)
    profile = getattr(graph, "profile_ref", {}) if graph is not None else {}
    l5_provider = context.config.get_provider_for_layer("5")
    if (
        profile.get("id") != "five-layer-baseline"
        or str(profile.get("version")) != "2"
        or str(l5_provider).lower() not in {"gcp", "google"}
    ):
        raise GcpViewerRotationError("GCP Grafana rotation is not available")
    bundle = _rotation_bundle(outputs)
    try:
        ca_certificate = base64.b64decode(
            bundle["cluster_ca_certificate"], validate=True
        )
    except ValueError as exc:
        raise GcpViewerRotationError("GKE CA certificate is invalid") from exc
    password = (password_factory or (lambda: secrets.token_urlsafe(24)))()
    if not isinstance(password, str) or len(password) < 24:
        raise GcpViewerRotationError("Generated Viewer credential is invalid")
    with client_factory(
        host=bundle["cluster_host"],
        ca_certificate=ca_certificate,
        bearer_token=_bearer_token(context),
    ) as client:
        old_pods = client.list_pods(
            bundle["namespace"], bundle["pod_label_selector"]
        )
        if not old_pods:
            raise GcpViewerRotationError("GCP Grafana pod is unavailable")
        client.patch_viewer_password(
            bundle["namespace"], bundle["secret_name"], password
        )
        for pod in old_pods:
            client.delete_pod(bundle["namespace"], pod.name)
        deadline = time.monotonic() + timeout_seconds
        previous_uids = {pod.uid for pod in old_pods}
        while time.monotonic() < deadline:
            if client.replacement_is_ready(
                bundle["namespace"],
                bundle["pod_label_selector"],
                previous_uids,
            ):
                issued_at = (now or (lambda: datetime.now(timezone.utc)))()
                if issued_at.tzinfo is None:
                    issued_at = issued_at.replace(tzinfo=timezone.utc)
                return {
                    "schema_version": "deployment-access-credential.v1",
                    "layer": "l5",
                    "provider": "gcp",
                    "username": bundle["viewer_username"],
                    "password": password,
                    "issued_at": issued_at.astimezone(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            sleep(2)
    raise GcpViewerRotationError("GCP Grafana did not become ready after rotation")
