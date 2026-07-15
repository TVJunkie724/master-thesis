import logging
import json

import pytest

from logger import RedactingColoredFormatter
from src.simulator.session import SimulatorSessionInvalid, resolve_simulator_session
from src.terraform_runner import TerraformRunner


def test_terraform_runner_rejects_unknown_or_multiline_commands(tmp_path):
    runner = TerraformRunner(str(tmp_path))

    with pytest.raises(ValueError, match="not allowed"):
        runner._build_command(["workspace", "list"])
    with pytest.raises(ValueError, match="single-line"):
        runner._build_command(["plan", "-var-file=safe.tfvars\nversion"])


def test_terraform_runner_builds_fixed_executable_command(tmp_path):
    runner = TerraformRunner(
        str(tmp_path),
        state_path=str(tmp_path / "runtime" / "terraform.tfstate"),
    )

    assert runner._build_command(["plan", "-input=false"]) == [
        "terraform",
        f"-chdir={tmp_path}",
        "plan",
        f"-state={tmp_path / 'runtime' / 'terraform.tfstate'}",
        "-input=false",
    ]


def test_terraform_runner_builds_isolated_state_list_command(tmp_path):
    state_path = tmp_path / "runtime" / "terraform.tfstate"
    runner = TerraformRunner(str(tmp_path), state_path=str(state_path))

    assert runner._build_command(["state", "list"]) == [
        "terraform",
        f"-chdir={tmp_path}",
        "state",
        "list",
        f"-state={state_path}",
    ]
    with pytest.raises(ValueError, match="state list"):
        runner._build_command(["state", "rm", "resource.name"])


def test_simulator_entrypoint_is_selected_from_fixed_module_allowlist(tmp_path):
    device = (
        tmp_path
        / "upload"
        / "factory"
        / "iot_device_simulator"
        / "aws"
        / "device-1"
    )
    device.mkdir(parents=True)
    (device / "config_generated.json").write_text(
        json.dumps({"device_id": "device-1"}),
        encoding="utf-8",
    )
    (device.parents[1] / "payloads.json").write_text("[]", encoding="utf-8")

    spec = resolve_simulator_session(
        project_name="factory",
        provider="aws",
        repository_root=tmp_path,
    )

    assert spec.module == "src.iot_device_simulator.aws.main"
    with pytest.raises(SimulatorSessionInvalid):
        resolve_simulator_session(
            project_name="factory",
            provider="../../outside",
            repository_root=tmp_path,
        )


def test_console_formatter_redacts_interpolated_secrets():
    record = logging.LogRecord(
        name="deployer",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Terraform failed with azure_client_secret=%s",
        args=("sensitive-value",),
        exc_info=None,
    )

    rendered = RedactingColoredFormatter("%(message)s").format(record)

    assert "sensitive-value" not in rendered
    assert "<redacted>" in rendered
