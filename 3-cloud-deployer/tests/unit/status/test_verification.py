from types import SimpleNamespace

from src.status import verification


def _config():
    return SimpleNamespace(
        providers={
            "layer_1_provider": "aws",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "gcp",
            "layer_3_cold_provider": "azure",
            "layer_3_archive_provider": "aws",
            "layer_4_provider": "azure",
            "layer_5_provider": "none",
        },
        iot_devices=[{"id": "device-1"}],
    )


def _state(status="deployed"):
    deployed = status == "deployed"
    resource = ["resource"] if deployed else []
    return {
        "status": status,
        "total_resources": 8 if deployed else 0,
        "l1": {"deployed": deployed, "resources": resource},
        "l2": {"deployed": deployed, "resources": resource},
        "l3": {
            key: {"deployed": deployed, "resources": resource}
            for key in ("hot", "cold", "archive")
        },
        "l4": {"deployed": deployed, "resources": resource},
        "l5": {"deployed": False, "resources": []},
    }


def _sdk_status():
    return {
        "iot_devices": {"status": "deployed", "provider": "aws"},
        "twin_management": {"status": "deployed", "provider": "azure"},
        "visualization": {"status": "not_configured", "provider": "none"},
    }


def _install(monkeypatch, state):
    context = SimpleNamespace(config=_config())
    monkeypatch.setattr(verification, "create_context", lambda name: context)
    monkeypatch.setattr(verification, "check_terraform_state", lambda name: state)
    monkeypatch.setattr(
        verification,
        "check_sdk_managed",
        lambda name, context: _sdk_status(),
    )
    monkeypatch.setattr(
        verification,
        "check_function_artifacts",
        lambda name: {"status": "no_deployments", "functions": {}},
    )


def test_verification_combines_independent_evidence(monkeypatch):
    _install(monkeypatch, _state())

    result = verification.verify_infrastructure("factory")

    assert result["summary"]["healthy"] is True
    assert result["summary"]["fail_count"] == 0
    by_name = {check["name"]: check for check in result["checks"]}
    assert by_name["IoT infrastructure"]["status"] == "pass"
    assert by_name["Digital twin resources"]["status"] == "pass"
    assert by_name["Visualization infrastructure"]["status"] == "skip"


def test_state_failure_does_not_misreport_resources_as_absent(monkeypatch):
    state = _state("error")
    state["error"] = "api_key=sensitive-value"
    _install(monkeypatch, state)

    result = verification.verify_infrastructure("factory")

    by_name = {check["name"]: check for check in result["checks"]}
    assert result["summary"]["healthy"] is False
    assert by_name["Terraform state"]["status"] == "fail"
    assert "sensitive-value" not in by_name["Terraform state"]["detail"]
    assert by_name["Hot storage"]["status"] == "skip"


def test_outdated_user_package_fails_verification(monkeypatch):
    _install(monkeypatch, _state())
    monkeypatch.setattr(
        verification,
        "check_function_artifacts",
        lambda name: {
            "status": "built",
            "functions": {"processor": {"deployed": False}},
        },
    )

    result = verification.verify_infrastructure("factory")

    check = next(item for item in result["checks"] if item["name"] == "User functions")
    assert check["status"] == "fail"
    assert result["summary"]["healthy"] is False
