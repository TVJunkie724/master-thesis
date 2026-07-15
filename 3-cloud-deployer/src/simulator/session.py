"""Bounded, asynchronous process lifecycle for integrated simulator sessions."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import re
import stat
import sys
from typing import AsyncIterator, Protocol

from src.core.observability import redact_sensitive
from src.core.paths import resolve_project_context_path
from src.core.simulator_package import (
    SimulatorPackageInvalid,
    normalize_simulator_provider,
)
import constants as CONSTANTS


MAX_ACTIVE_SESSIONS = 16
MAX_COMMAND_BYTES = 32
MAX_CONFIG_BYTES = 256 * 1024
MAX_LOG_LINE_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024
SESSION_TIMEOUT_SECONDS = 30 * 60
SHUTDOWN_TIMEOUT_SECONDS = 3

_SAFE_DEVICE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PUBLIC_PROVIDER = {"aws": "aws", "azure": "azure", "google": "gcp"}
_MODULES = {
    "aws": "src.iot_device_simulator.aws.main",
    "azure": "src.iot_device_simulator.azure.main",
    "google": "src.iot_device_simulator.google.main",
}
_COMMANDS = {
    "aws": frozenset({"send", "help", "exit"}),
    "azure": frozenset({"send", "help", "exit"}),
    "google": frozenset({"1", "2", "3", "4", "exit"}),
}


class SimulatorSessionError(RuntimeError):
    """Base error for simulator stream setup and execution."""


class SimulatorSessionNotFound(SimulatorSessionError):
    """Required project output for a simulator session is absent."""


class SimulatorSessionInvalid(SimulatorSessionError):
    """Simulator session input or generated output violates its contract."""


class SimulatorSessionBusy(SimulatorSessionError):
    """The bounded simulator runtime cannot accept another session."""


class SimulatorEventSink(Protocol):
    """Minimal event/command boundary implemented by FastAPI WebSocket."""

    async def send_json(self, data: dict) -> None: ...

    async def receive_json(self) -> object: ...


@dataclass(frozen=True)
class SimulatorSessionSpec:
    """Validated immutable inputs used to launch one simulator process."""

    project_name: str
    internal_provider: str
    public_provider: str
    device_id: str
    config_path: Path
    repository_root: Path
    module: str
    allowed_commands: frozenset[str]

    @property
    def key(self) -> tuple[str, str, str]:
        return self.project_name, self.internal_provider, self.device_id


def resolve_simulator_session(
    *,
    project_name: str,
    provider: str,
    device_id: str | None = None,
    repository_root: Path | None = None,
    project_path: Path | None = None,
) -> SimulatorSessionSpec:
    """Resolve one deterministic, regular-file simulator configuration."""
    try:
        internal_provider = normalize_simulator_provider(provider)
    except SimulatorPackageInvalid as exc:
        raise SimulatorSessionInvalid(str(exc)) from exc

    if project_name == CONSTANTS.DEFAULT_PROJECT_NAME:
        raise SimulatorSessionInvalid(
            "The protected template project cannot run simulations."
        )
    project_path = project_path or resolve_project_context_path(
        project_name, repository_root
    )
    if not project_path.exists():
        raise SimulatorSessionNotFound(f"Project '{project_name}' not found.")
    if project_path.is_symlink() or not project_path.is_dir():
        raise SimulatorSessionInvalid("Project path is not a regular directory.")

    provider_dir = project_path / "iot_device_simulator" / internal_provider
    if not provider_dir.exists():
        raise SimulatorSessionNotFound("Simulator config not found. Deploy L1 first.")
    if provider_dir.is_symlink() or not provider_dir.is_dir():
        raise SimulatorSessionInvalid(
            "Simulator provider path is not a regular directory."
        )

    selected_device = _select_device(provider_dir, device_id)
    config_path = selected_device / "config_generated.json"
    _validate_config(config_path, selected_device.name, internal_provider)
    _validate_payload(project_path, provider_dir)

    resolved_root = (repository_root or Path(__file__).resolve().parents[2]).resolve()
    return SimulatorSessionSpec(
        project_name=project_name,
        internal_provider=internal_provider,
        public_provider=_PUBLIC_PROVIDER[internal_provider],
        device_id=selected_device.name,
        config_path=config_path.resolve(),
        repository_root=resolved_root,
        module=_MODULES[internal_provider],
        allowed_commands=_COMMANDS[internal_provider],
    )


def _select_device(provider_dir: Path, requested_device: str | None) -> Path:
    if requested_device is not None:
        if not _SAFE_DEVICE_ID.fullmatch(requested_device) or ".." in requested_device:
            raise SimulatorSessionInvalid("Simulator device ID is invalid.")
        selected = provider_dir / requested_device
        if not selected.exists():
            raise SimulatorSessionNotFound(
                f"Simulator device '{requested_device}' not found."
            )
        candidates = [selected]
    else:
        candidates = sorted(
            child
            for child in provider_dir.iterdir()
            if child.name != "_runtime" and child.is_dir() and not child.is_symlink()
        )
        if not candidates:
            raise SimulatorSessionNotFound("No device configs found. Deploy L1 first.")

    selected = candidates[0]
    if selected.is_symlink() or not selected.is_dir():
        raise SimulatorSessionInvalid(
            "Simulator device path is not a regular directory."
        )
    return selected


def _validate_config(config_path: Path, device_id: str, provider: str) -> None:
    if not config_path.exists():
        raise SimulatorSessionNotFound("Simulator config not found. Deploy L1 first.")
    if config_path.is_symlink() or not config_path.is_file():
        raise SimulatorSessionInvalid("Simulator config path is not a regular file.")
    if config_path.stat().st_size > MAX_CONFIG_BYTES:
        raise SimulatorSessionInvalid("Simulator config exceeds its size limit.")
    if provider == "azure" and stat.S_IMODE(config_path.stat().st_mode) & 0o077:
        raise SimulatorSessionInvalid(
            "Azure simulator config permissions are too broad."
        )
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SimulatorSessionInvalid("Simulator config is not valid JSON.") from exc
    if not isinstance(config, dict) or config.get("device_id") != device_id:
        raise SimulatorSessionInvalid(
            "Simulator config identity does not match its device directory."
        )


def _validate_payload(project_path: Path, provider_dir: Path) -> Path:
    for candidate in (
        project_path / "iot_device_simulator" / "payloads.json",
        provider_dir / "payloads.json",
    ):
        if candidate.exists():
            if candidate.is_symlink() or not candidate.is_file():
                raise SimulatorSessionInvalid(
                    "Simulator payload path is not a regular file."
                )
            if candidate.stat().st_size > MAX_PAYLOAD_BYTES:
                raise SimulatorSessionInvalid(
                    "Simulator payload file exceeds its size limit."
                )
            try:
                payloads = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SimulatorSessionInvalid(
                    "Simulator payload file is not valid JSON."
                ) from exc
            if not isinstance(payloads, list):
                raise SimulatorSessionInvalid(
                    "Simulator payload file must contain a JSON array."
                )
            return candidate.resolve()
    raise SimulatorSessionNotFound(
        "Payloads file not found. Upload payloads.json first."
    )


class SimulatorSessionRegistry:
    """In-process guard against duplicate and unbounded simulator processes."""

    def __init__(self, max_sessions: int = MAX_ACTIVE_SESSIONS):
        self._max_sessions = max_sessions
        self._active: set[tuple[str, str, str]] = set()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def claim(self, key: tuple[str, str, str]) -> AsyncIterator[None]:
        async with self._lock:
            if key in self._active:
                raise SimulatorSessionBusy(
                    "A simulator session is already active for this device."
                )
            if len(self._active) >= self._max_sessions:
                raise SimulatorSessionBusy(
                    "The simulator session capacity is currently exhausted."
                )
            self._active.add(key)
        try:
            yield
        finally:
            async with self._lock:
                self._active.discard(key)


class SimulatorSessionRunner:
    """Launch, relay, and terminate one simulator subprocess."""

    def __init__(self, spec: SimulatorSessionSpec):
        self.spec = spec
        self._process: asyncio.subprocess.Process | None = None

    async def run(self, sink: SimulatorEventSink) -> None:
        try:
            self._process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                "-m",
                self.spec.module,
                "--config",
                str(self.spec.config_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.spec.repository_root,
                limit=MAX_LOG_LINE_BYTES,
            )
        except OSError as exc:
            raise SimulatorSessionError(
                "Simulator process could not be started."
            ) from exc
        await sink.send_json(
            {
                "type": "status",
                "status": "started",
                "provider": self.spec.public_provider,
                "device_id": self.spec.device_id,
            }
        )

        output_task = asyncio.create_task(self._relay_output(sink))
        command_task = asyncio.create_task(self._relay_commands(sink))
        try:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                done, pending = await asyncio.wait(
                    {output_task, command_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if output_task in done:
                    output_task.result()
                else:
                    command_task.result()
                    await self._wait_for_exit()
                    await output_task
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
        finally:
            output_task.cancel()
            command_task.cancel()
            await asyncio.gather(output_task, command_task, return_exceptions=True)
            await self.stop()

    async def _relay_output(self, sink: SimulatorEventSink) -> None:
        process = self._require_process()
        if process.stdout is None:
            raise SimulatorSessionError("Simulator stdout pipe is unavailable.")
        try:
            while line := await process.stdout.readline():
                text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                await sink.send_json({"type": "log", "data": redact_sensitive(text)})
        except ValueError as exc:
            raise SimulatorSessionInvalid(
                "Simulator emitted a log line above its size limit."
            ) from exc
        exit_code = await process.wait()
        await sink.send_json(
            {
                "type": "status",
                "status": "completed" if exit_code == 0 else "failed",
                "exit_code": exit_code,
            }
        )

    async def _relay_commands(self, sink: SimulatorEventSink) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise SimulatorSessionError("Simulator stdin pipe is unavailable.")
        while process.returncode is None:
            payload = await sink.receive_json()
            command = payload.get("command") if isinstance(payload, dict) else None
            if not isinstance(command, str):
                await sink.send_json(
                    {"type": "error", "data": "A simulator command is required."}
                )
                continue
            command = command.strip().lower()
            if (
                len(command.encode("utf-8")) > MAX_COMMAND_BYTES
                or command not in self.spec.allowed_commands
            ):
                await sink.send_json(
                    {"type": "error", "data": "Unsupported simulator command."}
                )
                continue
            process.stdin.write(f"{command}\n".encode())
            await process.stdin.drain()
            if command in {"exit", "4"}:
                return

    async def _wait_for_exit(self) -> None:
        process = self._require_process()
        try:
            await asyncio.wait_for(process.wait(), timeout=SHUTDOWN_TIMEOUT_SECONDS)
        except TimeoutError:
            process.terminate()
            await self._wait_or_kill(process)

    async def stop(self) -> None:
        process = self._process
        if process is None or process.returncode is not None:
            return
        process.terminate()
        await self._wait_or_kill(process)

    @staticmethod
    async def _wait_or_kill(process: asyncio.subprocess.Process) -> None:
        try:
            await asyncio.wait_for(process.wait(), timeout=SHUTDOWN_TIMEOUT_SECONDS)
        except TimeoutError:
            process.kill()
            await process.wait()

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None:
            raise SimulatorSessionError("Simulator process has not been started.")
        return self._process


session_registry = SimulatorSessionRegistry()
