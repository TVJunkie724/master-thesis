"""Tests for TerraformRunner workspace path behavior."""

from src.terraform_runner import TerraformRunner


def test_plan_defaults_to_project_workspace_when_state_path_is_set(tmp_path, monkeypatch):
    terraform_dir = tmp_path / "src" / "terraform"
    terraform_dir.mkdir(parents=True)
    workspace_dir = tmp_path / "upload" / "factory-twin" / "terraform"
    state_path = workspace_dir / "terraform.tfstate"
    var_file = workspace_dir / "generated.tfvars.json"
    calls = []

    runner = TerraformRunner(
        terraform_dir=str(terraform_dir),
        state_path=str(state_path),
    )

    def fake_run_command(args, *_, **__):
        calls.append(args)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    result = runner.plan(var_file=str(var_file))

    assert result == str(workspace_dir / "tfplan")
    assert workspace_dir.exists()
    assert calls == [
        [
            "plan",
            f"-var-file={var_file}",
            f"-out={workspace_dir / 'tfplan'}",
        ]
    ]


def test_plan_keeps_legacy_default_when_state_path_is_absent(tmp_path, monkeypatch):
    terraform_dir = tmp_path / "src" / "terraform"
    terraform_dir.mkdir(parents=True)
    var_file = tmp_path / "generated.tfvars.json"
    calls = []

    runner = TerraformRunner(terraform_dir=str(terraform_dir))

    def fake_run_command(args, *_, **__):
        calls.append(args)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    result = runner.plan(var_file=str(var_file))

    assert result == str(terraform_dir / "tfplan")
    assert calls == [
        [
            "plan",
            f"-var-file={var_file}",
            f"-out={terraform_dir / 'tfplan'}",
        ]
    ]


def test_plan_accepts_explicit_out_file(tmp_path, monkeypatch):
    terraform_dir = tmp_path / "src" / "terraform"
    terraform_dir.mkdir(parents=True)
    explicit_plan = tmp_path / "custom" / "saved.tfplan"
    calls = []

    runner = TerraformRunner(terraform_dir=str(terraform_dir))

    def fake_run_command(args, *_, **__):
        calls.append(args)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    result = runner.plan(
        var_file=str(tmp_path / "vars.json"),
        out_file=str(explicit_plan),
    )

    assert result == str(explicit_plan)
    assert explicit_plan.parent.exists()
    assert calls[0][-1] == f"-out={explicit_plan}"
