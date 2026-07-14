"""Tests for the one-shot simulator subprocess boundary."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

from src.iot_device_simulator import sender
from src.simulator.session import SimulatorSessionSpec


def _spec(tmp_path):
    return SimulatorSessionSpec(
        project_name="factory",
        internal_provider="aws",
        public_provider="aws",
        device_id="device-1",
        config_path=tmp_path / "config.json",
        repository_root=tmp_path,
        module="src.iot_device_simulator.aws.main",
        allowed_commands=frozenset({"send", "exit"}),
    )


def test_sender_passes_telemetry_over_stdin_not_process_arguments(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(sender, "resolve_simulator_session", lambda **kwargs: _spec(tmp_path))

    def run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return CompletedProcess(command, 0, stdout="sent", stderr="")

    monkeypatch.setattr(sender.subprocess, "run", run)

    assert sender.send_test_message(
        "aws",
        "factory",
        "TRACE-ABCDEF12",
        payload_override={"iotDeviceId": "device-1", "temperature": 21},
    )
    assert captured["command"][-1] == "--payload-stdin"
    assert "temperature" not in " ".join(captured["command"])
    assert '"temperature":21' in captured["input"]
    assert captured["cwd"] == Path(tmp_path)


def test_sender_rejects_invalid_trace_without_starting_process(monkeypatch):
    called = False

    def run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(sender.subprocess, "run", run)

    assert not sender.send_test_message(
        "aws",
        "factory",
        "invalid",
        payload_override={"iotDeviceId": "device-1"},
    )
    assert called is False


def test_sender_rejects_oversized_payload_before_starting_process(tmp_path, monkeypatch):
    called = False
    monkeypatch.setattr(sender, "resolve_simulator_session", lambda **kwargs: _spec(tmp_path))

    def run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(sender.subprocess, "run", run)

    assert not sender.send_test_message(
        "aws",
        "factory",
        "TRACE-ABCDEF12",
        payload_override={"iotDeviceId": "device-1", "value": "x" * (4 * 1024 * 1024)},
    )
    assert called is False
