"""Frozen GCP Five-layer v2 Grafana image and dashboard contract tests."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "gcp"
    / "containers"
    / "five-layer-v2"
    / "grafana"
)


def test_image_uses_only_the_frozen_signed_artifacts():
    dockerfile = (ROOT / "Dockerfile").read_text("utf-8")

    assert (
        "grafana/grafana:12.4.2@sha256:"
        "83749231c3835e390a3144e5e940203e42b9589761f20ef3169c716e734ad505"
    ) in dockerfile
    assert (
        "ADD --checksum=sha256:"
        "39d1cac9bcd2f7f2e46607319cb27afb8592ab0fcbc57968dc9fb86f3ef69a59"
    ) in dockerfile
    assert "versions/3.10.1/download?os=linux&arch=amd64" in dockerfile
    assert 'test "${TARGETARCH}" = "amd64"' in dockerfile
    assert "MANIFEST.txt" in dockerfile
    assert "GF_INSTALL_PLUGINS" not in dockerfile
    assert "allow_loading_unsigned_plugins" not in dockerfile


def test_datasource_is_read_only_bounded_and_secret_backed():
    datasource = (
        ROOT / "provisioning" / "datasources" / "twin2multicloud.yaml"
    ).read_text("utf-8")

    assert "uid: twin2multicloud-raw-history" in datasource
    assert "type: yesoreyeram-infinity-datasource" in datasource
    assert "auth_method: apiKey" in datasource
    assert "apiKeyKey: x-twin2multicloud-reader-key" in datasource
    assert "apiKeyType: header" in datasource
    assert "allowedHosts:" in datasource
    assert "customHealthCheckUrl: ${RAW_HISTORY_READER_URL}/raw-history-health/v1" in datasource
    assert "allowDangerousHTTPMethods: false" in datasource
    assert "apiKeyValue: ${RAW_HISTORY_READER_KEY}" in datasource
    assert "ReaderKey123" not in datasource


def test_dashboard_has_exactly_the_two_reviewed_history_panels():
    dashboard = json.loads((ROOT / "dashboard.json.template").read_text("utf-8"))

    assert dashboard["uid"] == "twin2multicloud-raw-rollups"
    assert dashboard["title"] == "Twin2MultiCloud Raw & Rollups"
    assert dashboard["editable"] is False
    assert len(dashboard["panels"]) == 2
    assert dashboard["time"] == {"from": "now-30d", "to": "now"}

    expected_buckets = ("bucket_seconds=0", "bucket_seconds=3600")
    expected_times = ("stored_at", "bucket_start")
    for panel, bucket, time_column in zip(
        dashboard["panels"], expected_buckets, expected_times, strict=True
    ):
        assert panel["type"] == "timeseries"
        assert "No data" in panel["description"]
        assert len(panel["targets"]) == 1
        target = panel["targets"][0]
        assert target["type"] == "json"
        assert target["source"] == "url"
        assert target["format"] == "timeseries"
        assert target["parser"] == "backend"
        assert target["root_selector"] == "points"
        assert target["url_options"]["method"] == "GET"
        assert target["url"].startswith(
            "__RAW_HISTORY_READER_URL__/raw-history/v1?"
        )
        assert "device_id=${device}" in target["url"]
        assert "metric=${metric}" in target["url"]
        assert "from=${__from:date:iso}" in target["url"]
        assert "to=${__to:date:iso}" in target["url"]
        assert bucket in target["url"]
        assert target["columns"][0]["selector"] == time_column
        assert target["columns"][0]["type"] == "timestamp"

    assert dashboard["panels"][0]["timeFrom"] == "24h"
    variables = {item["name"]: item for item in dashboard["templating"]["list"]}
    assert set(variables) == {"provider", "deployment", "device", "metric"}
    assert variables["device"]["type"] == "textbox"
    assert variables["metric"]["type"] == "textbox"


def test_entrypoint_bootstraps_only_a_viewer_without_logging_secrets():
    entrypoint = (ROOT / "entrypoint.sh").read_text("utf-8")

    assert "/api/admin/users" in entrypoint
    assert "/api/org/users/${viewer_id}" in entrypoint
    assert "'{\"role\":\"Viewer\"}'" in entrypoint
    assert "GRAFANA_VIEWER_PASSWORD" in entrypoint
    assert "set -x" not in entrypoint
    assert all(
        "RAW_HISTORY_READER_KEY}" not in line
        for line in entrypoint.splitlines()
        if line.lstrip().startswith("echo ")
    )


def test_entrypoint_fails_closed_until_content_and_reader_probes_pass():
    entrypoint = (ROOT / "entrypoint.sh").read_text("utf-8")

    assert "probe_reader 0 '2026-01-01T00:00:00Z' '2026-01-02T00:00:00Z'" in entrypoint
    assert "probe_reader 3600 '2026-01-01T00:00:00Z' '2026-01-31T00:00:00Z'" in entrypoint
    assert "/api/datasources/uid/twin2multicloud-raw-history/health" in entrypoint
    assert '"status"[[:space:]]*:[[:space:]]*"OK"' in entrypoint
    assert "/api/dashboards/uid/twin2multicloud-raw-rollups" in entrypoint
    assert '"x-twin2multicloud-reader-key: ${RAW_HISTORY_READER_KEY}"' in entrypoint
