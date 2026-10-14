"""The Azure source bridge logs only stable failure classifications."""

import logging

import pytest

from runtime.six_layer_eventing.azure import runtime
from runtime.six_layer_eventing.bridge_core import RetryableBridgeError


@pytest.mark.parametrize(
    "error,expected",
    [
        (RetryableBridgeError("IDENTITY_EXCHANGE_RETRYABLE"), "IDENTITY_EXCHANGE_RETRYABLE"),
        (RuntimeError("token=private-test-token"), "RuntimeError"),
    ],
)
def test_destination_log_never_includes_raw_exception(caplog, error, expected):
    class FailingApplication:
        def publish(self, _route, _event):
            raise error

    with caplog.at_level(logging.WARNING), pytest.raises(type(error)):
        runtime._publish_observed(FailingApplication(), object(), {})

    assert expected in caplog.text
    assert "private-test-token" not in caplog.text


def test_setup_failure_log_never_includes_raw_exception(monkeypatch, caplog):
    def fail():
        raise RuntimeError("secret=private-test-secret")

    monkeypatch.setattr(runtime, "_application", fail)
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
        runtime.event_hub_batch([object()])

    assert "RuntimeError" in caplog.text
    assert "private-test-secret" not in caplog.text
