"""Async process lifecycle tests for simulator WebSocket sessions."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.simulator.session import (
    SimulatorSessionBusy,
    SimulatorSessionRegistry,
    SimulatorSessionRunner,
    SimulatorSessionSpec,
)


class _Sink:
    def __init__(self, commands=None):
        self.events = []
        self.commands = list(commands or [])
        self.wait_forever = asyncio.Event()

    async def send_json(self, data):
        self.events.append(data)

    async def receive_json(self):
        if self.commands:
            return self.commands.pop(0)
        await self.wait_forever.wait()


class _Reader:
    def __init__(self, lines):
        self.lines = list(lines)

    async def readline(self):
        return self.lines.pop(0) if self.lines else b""


class _Writer:
    def __init__(self):
        self.writes = []

    def write(self, value):
        self.writes.append(value)

    async def drain(self):
        return None


class _Process:
    def __init__(self, lines=(), returncode=0):
        self.stdout = _Reader(lines)
        self.stdin = _Writer()
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    async def wait(self):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


def _spec():
    return SimulatorSessionSpec(
        project_name="factory",
        internal_provider="aws",
        public_provider="aws",
        device_id="device-1",
        config_path=Path("/project/config.json"),
        repository_root=Path("/project"),
        module="src.iot_device_simulator.aws.main",
        allowed_commands=frozenset({"send", "help", "exit"}),
    )


def test_runner_emits_redacted_logs_and_terminal_status(monkeypatch):
    process = _Process(
        lines=[b"client_secret=do-not-leak\n", b"sent\n"],
        returncode=0,
    )

    async def create_process(*args, **kwargs):
        assert args[1:4] == ("-u", "-m", "src.iot_device_simulator.aws.main")
        assert kwargs["stderr"] == asyncio.subprocess.STDOUT
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    sink = _Sink()

    asyncio.run(SimulatorSessionRunner(_spec()).run(sink))

    assert sink.events[0]["status"] == "started"
    assert sink.events[1] == {"type": "log", "data": "client_secret=<redacted>"}
    assert sink.events[-1] == {"type": "status", "status": "completed", "exit_code": 0}


def test_command_relay_rejects_unknown_commands_and_forwards_exit():
    process = _Process(returncode=None)
    runner = SimulatorSessionRunner(_spec())
    runner._process = process
    sink = _Sink([{"command": "destroy"}, {"command": "EXIT"}])

    asyncio.run(runner._relay_commands(sink))

    assert sink.events == [{"type": "error", "data": "Unsupported simulator command."}]
    assert process.stdin.writes == [b"exit\n"]


def test_registry_rejects_duplicate_and_capacity_then_releases():
    registry = SimulatorSessionRegistry(max_sessions=1)

    async def exercise():
        async with registry.claim(("a", "aws", "one")):
            with pytest.raises(SimulatorSessionBusy, match="already active"):
                async with registry.claim(("a", "aws", "one")):
                    pass
            with pytest.raises(SimulatorSessionBusy, match="capacity"):
                async with registry.claim(("b", "aws", "two")):
                    pass
        async with registry.claim(("b", "aws", "two")):
            pass

    asyncio.run(exercise())


def test_stop_terminates_running_process():
    process = _Process(returncode=None)
    runner = SimulatorSessionRunner(_spec())
    runner._process = process

    asyncio.run(runner.stop())

    assert process.terminated is True
    assert process.returncode == -15
