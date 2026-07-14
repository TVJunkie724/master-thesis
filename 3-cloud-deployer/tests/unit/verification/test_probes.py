from pathlib import Path

from src.verification import probes


class _Response:
    status_code = 200

    @staticmethod
    def json():
        return {
            "items": [
                {"trace_id": "VERIFY-OTHER"},
                {"trace_id": "VERIFY-TARGET"},
            ]
        }


def test_hot_reader_rejects_non_https_endpoint(monkeypatch):
    called = False

    def get(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(probes.requests, "get", get)

    result = probes.poll_hot_reader(
        "http://example.test/reader",
        "device-1",
        None,
        1,
        0,
        trace_id="VERIFY-TARGET",
    )

    assert result.success is False
    assert "HTTPS" in result.error
    assert called is False


def test_hot_reader_only_accepts_current_trace(monkeypatch):
    monkeypatch.setattr(probes.requests, "get", lambda *args, **kwargs: _Response())

    result = probes.poll_hot_reader(
        "https://example.test/reader",
        "device-1",
        "token",
        1,
        0,
        trace_id="VERIFY-TARGET",
    )

    assert result.success is True
    assert result.evidence == {"record_count": 1}


def test_unknown_log_provider_fails_without_cloud_access():
    result = probes.check_cloud_logs(
        "unsupported",
        "marker",
        "event_checker",
        {},
        {},
        Path("/tmp/project"),
        1,
        0,
    )

    assert result.success is False
    assert result.error == "Unsupported provider: unsupported"
