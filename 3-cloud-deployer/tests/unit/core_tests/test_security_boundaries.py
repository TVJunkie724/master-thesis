import logging
from unittest.mock import patch

import pytest

from src.api.simulator import _resolve_simulator_script_path
from src.logger import RedactingColoredFormatter
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


def test_simulator_entrypoint_stays_within_allowlisted_source_root(tmp_path):
    script = tmp_path / "src" / "iot_device_simulator" / "aws" / "main.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")

    with patch("src.api.simulator.state.get_project_base_path", return_value=str(tmp_path)):
        assert _resolve_simulator_script_path("aws") == script.resolve()
        with pytest.raises(ValueError):
            _resolve_simulator_script_path("../../outside")


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
