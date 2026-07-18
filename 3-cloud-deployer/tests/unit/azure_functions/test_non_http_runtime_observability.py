"""Contracts for non-HTTP Azure Function runtime observability."""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import logging
import re
import sys
import uuid
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.providers.azure.layers.function_bundler import (
    bundle_l1_functions,
    bundle_l3_functions,
)


DEPLOYER_ROOT = Path(__file__).resolve().parents[3]
AZURE_FUNCTIONS_ROOT = (
    DEPLOYER_ROOT / "src/providers/azure/azure_functions"
)
NON_HTTP_RUNTIMES = {
    "dispatcher": ("dispatcher", "event_grid_trigger"),
    "hot-to-cold-mover": ("hot_to_cold_mover", "timer_trigger"),
    "cold-to-archive-mover": (
        "cold_to_archive_mover",
        "timer_trigger",
    ),
}
FORBIDDEN_LOG_NAMES = {
    "blob_name",
    "cutoff",
    "cutoff_iso",
    "data",
    "device_id",
    "error_body",
    "iot_device_id",
    "REMOTE_ARCHIVE_WRITER_URL",
    "REMOTE_COLD_WRITER_URL",
    "telemetry_body",
}


@pytest.fixture(autouse=True)
def _isolate_shared_modules():
    yield
    _clear_shared_modules()


def _clear_shared_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "_shared" or module_name.startswith("_shared."):
            del sys.modules[module_name]


def _load_runtime(
    monkeypatch: pytest.MonkeyPatch,
    directory: str,
):
    monkeypatch.setenv(
        "DIGITAL_TWIN_INFO",
        json.dumps(
            {
                "config": {
                    "hot_storage_size_in_days": 7,
                    "cold_storage_size_in_days": 30,
                },
                "config_iot_devices": [{"id": "sensor-1"}],
                "config_providers": {
                    "layer_3_hot_provider": "azure",
                    "layer_3_cold_provider": "azure",
                    "layer_3_archive_provider": "azure",
                },
            }
        ),
    )
    monkeypatch.setenv("FUNCTION_APP_BASE_URL", "https://app.example.test")
    monkeypatch.setenv("L2_FUNCTION_KEY", "test-function-key")
    path = AZURE_FUNCTIONS_ROOT / directory / "function_app.py"
    module_name = (
        f"test_non_http_{directory.replace('-', '_')}_{id(monkeypatch)}"
    )

    _clear_shared_modules()
    sys.path.insert(0, str(AZURE_FUNCTIONS_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(AZURE_FUNCTIONS_ROOT))


def _invoke_failure_boundary(
    module,
    directory: str,
    failure: BaseException,
) -> None:
    if directory == "dispatcher":
        event = MagicMock()
        event.get_json.side_effect = failure
        module.dispatcher(event)
    elif directory == "hot-to-cold-mover":
        module._is_multi_cloud_cold = MagicMock(side_effect=failure)
        module.hot_to_cold_mover(MagicMock(past_due=False))
    else:
        module._is_multi_cloud_archive = MagicMock(side_effect=failure)
        module.cold_to_archive_mover(MagicMock(past_due=False))


def _assert_one_safe_failure_log(
    caplog: pytest.LogCaptureFixture,
    component: str,
    forbidden_values: tuple[str, ...],
) -> None:
    failure_logs = [
        record.getMessage()
        for record in caplog.records
        if "correlation_id=" in record.getMessage()
    ]
    assert len(failure_logs) == 1
    failure_log = failure_logs[0]
    assert failure_log.startswith(f"{component} failed correlation_id=")
    match = re.search(r"correlation_id=([0-9a-f-]{36})", failure_log)
    assert match is not None
    uuid.UUID(match.group(1))
    assert "diagnostic=<suppressed>" in failure_log
    for forbidden in forbidden_values:
        assert forbidden not in caplog.text


@pytest.mark.parametrize(
    ("directory", "component"),
    (
        ("dispatcher", "azure.dispatcher.execution"),
        ("hot-to-cold-mover", "azure.hot-to-cold-mover.execution"),
        (
            "cold-to-archive-mover",
            "azure.cold-to-archive-mover.execution",
        ),
    ),
)
def test_runtime_failures_are_correlated_suppressed_and_propagated(
    monkeypatch,
    caplog,
    directory,
    component,
):
    secret = f"non-http-secret-{directory}"
    payload_marker = f"telemetry-payload-{directory}"
    signed_value = f"signed-value-{directory}"
    monkeypatch.setenv("AZURE_TEST_SECRET", secret)
    module = _load_runtime(monkeypatch, directory)
    failure = RuntimeError(
        f"{secret} {payload_marker} "
        f"https://provider.example.test/path?sig={signed_value} "
        f"/home/site/wwwroot/{directory}.py "
        rf"C:\home\site\wwwroot\{directory}.py"
    )

    with pytest.raises(RuntimeError) as raised:
        _invoke_failure_boundary(module, directory, failure)

    assert raised.value is failure
    _assert_one_safe_failure_log(
        caplog,
        component,
        (
            secret,
            payload_marker,
            signed_value,
            "provider.example.test",
            "/home/site/wwwroot",
            r"C:\home\site\wwwroot",
            "Traceback",
        ),
    )


@pytest.mark.parametrize(
    ("directory", "component"),
    (
        ("dispatcher", "azure.dispatcher.configuration"),
        (
            "hot-to-cold-mover",
            "azure.hot-to-cold-mover.configuration",
        ),
        (
            "cold-to-archive-mover",
            "azure.cold-to-archive-mover.configuration",
        ),
    ),
)
def test_configuration_failures_use_stable_component_context(
    monkeypatch,
    caplog,
    directory,
    component,
):
    module = _load_runtime(monkeypatch, directory)
    failure = module.MissingEnvironmentVariableError(
        "SENSITIVE_SETTING is missing"
    )

    with pytest.raises(module.MissingEnvironmentVariableError) as raised:
        _invoke_failure_boundary(module, directory, failure)

    assert raised.value is failure
    _assert_one_safe_failure_log(
        caplog,
        component,
        ("SENSITIVE_SETTING", "Traceback"),
    )


def test_suppressed_failure_logging_never_serializes_exception(
    monkeypatch,
    caplog,
):
    class NonSerializableDiagnostic(RuntimeError):
        def __str__(self) -> str:
            raise AssertionError("exception text must not be evaluated")

    sys.path.insert(0, str(AZURE_FUNCTIONS_ROOT))
    _clear_shared_modules()
    try:
        from _shared.http_errors import log_runtime_failure

        correlation_id = log_runtime_failure(
            "azure.test.non-http",
            NonSerializableDiagnostic(),
            include_diagnostic=False,
        )
    finally:
        sys.path.remove(str(AZURE_FUNCTIONS_ROOT))
        _clear_shared_modules()

    uuid.UUID(correlation_id)
    assert correlation_id in caplog.text
    assert "diagnostic=<suppressed>" in caplog.text


def test_dispatcher_forwards_normalized_payload_without_logging_it(
    monkeypatch,
    caplog,
):
    caplog.set_level(logging.INFO)
    module = _load_runtime(monkeypatch, "dispatcher")
    payload_marker = "normalized-payload-must-not-be-logged"
    normalized = {
        "device_id": "sensor-1",
        "temperature": payload_marker,
    }
    module.normalize_telemetry = MagicMock(return_value=normalized)
    module._invoke_function = MagicMock()
    event = MagicMock()
    event.get_json.return_value = {
        "systemProperties": {
            "iothub-connection-device-id": "sensor-1",
        },
        "body": {"temperature": payload_marker},
    }

    module.dispatcher(event)

    module.normalize_telemetry.assert_called_once_with(
        {"temperature": payload_marker}
    )
    module._invoke_function.assert_called_once_with("processor", normalized)
    assert payload_marker not in caplog.text
    assert "sensor-1" not in caplog.text


def test_dispatcher_preserves_no_device_no_op(monkeypatch):
    module = _load_runtime(monkeypatch, "dispatcher")
    module._invoke_function = MagicMock()
    event = MagicMock()
    event.get_json.return_value = {"body": {"temperature": 20}}

    assert module.dispatcher(event) is None

    module._invoke_function.assert_not_called()


def test_non_http_trigger_inventory_is_closed_and_source_safe():
    discovered: set[tuple[str, str, str]] = set()
    for path in AZURE_FUNCTIONS_ROOT.glob("*/function_app.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            for decorator in function.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr.endswith("_trigger")
                ):
                    discovered.add(
                        (
                            path.parent.name,
                            function.name,
                            decorator.func.attr,
                        )
                    )

    expected = {
        (directory, function_name, trigger)
        for directory, (function_name, trigger) in NON_HTTP_RUNTIMES.items()
    }
    assert discovered == expected

    for directory in NON_HTTP_RUNTIMES:
        path = AZURE_FUNCTIONS_ROOT / directory / "function_app.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for forbidden in (
            "logging.exception",
            "logger.exception",
            "read_http_error_body",
        ):
            assert forbidden not in source

        failure_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "log_runtime_failure"
        ]
        assert len(failure_calls) == 2
        for call in failure_calls:
            include_diagnostic = next(
                (
                    keyword.value
                    for keyword in call.keywords
                    if keyword.arg == "include_diagnostic"
                ),
                None,
            )
            assert (
                isinstance(include_diagnostic, ast.Constant)
                and include_diagnostic.value is False
            )

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Raise)
                and isinstance(node.exc, ast.Name)
                and node.exc.id in {"e", "ex", "exc", "error", "exception"}
            ):
                pytest.fail(f"{path} re-raises a named exception explicitly")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr
                in {"debug", "info", "warning", "error", "exception"}
            ):
                logged_names = {
                    child.id
                    for child in ast.walk(node)
                    if isinstance(child, ast.Name)
                }
                assert not (logged_names & FORBIDDEN_LOG_NAMES), (
                    f"{path} logs forbidden runtime values: "
                    f"{sorted(logged_names & FORBIDDEN_LOG_NAMES)}"
                )
                assert not any(
                    isinstance(child, ast.Attribute)
                    and child.attr == "reason"
                    for child in ast.walk(node)
                ), f"{path} logs a provider/network reason"


@pytest.mark.parametrize(
    ("builder", "expected_functions"),
    (
        (bundle_l1_functions, ("dispatcher",)),
        (
            bundle_l3_functions,
            ("hot-to-cold-mover", "cold-to-archive-mover"),
        ),
    ),
)
def test_real_packages_include_non_http_observability_contract(
    builder,
    expected_functions,
):
    archive = builder(str(DEPLOYER_ROOT))

    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        names = set(package.namelist())
        assert "_shared/http_errors.py" in names
        sources = {
            name: package.read(name).decode("utf-8")
            for name in names
            if name.endswith("/function_app.py")
        }

    for function_name in expected_functions:
        module_name = function_name.replace("-", "_")
        source_name = f"{module_name}/function_app.py"
        assert source_name in sources
        source = sources[source_name]
        assert (
            "from _shared.http_errors import log_runtime_failure"
            in source
        )
        assert source.count(
            f'function_name(name="{function_name}")'
        ) == 1
        ast.parse(source)
