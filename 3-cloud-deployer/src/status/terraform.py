"""Read-only Terraform state and drift status checks."""

from __future__ import annotations

from pathlib import Path
import re
import tempfile
from typing import Any

from logger import logger
from src.core.observability import redact_sensitive
from src.core.paths import resolve_project_context_path
from src.terraform_runner import TerraformRunner
from src.tfvars_generator import generate_tfvars
from src.architecture_profiles.catalog import DeploymentComponentCatalog


_STATUS_BY_LOGICAL_COMPONENT = {
    "component.ingestion": "l1",
    "component.eventing": "eventing",
    "component.processing": "l2",
    "component.hot-storage": "hot",
    "component.cool-storage": "cold",
    "component.archive-storage": "archive",
    "component.twin-state": "l4",
    "component.visualization": "l5",
}
_INSTANCE_SELECTOR = re.compile(r"\[[^\]]+\]")


def _empty_state(status: str, *, error: str | None = None) -> dict[str, Any]:
    result = {
        "status": status,
        "l1": {"deployed": False, "resources": []},
        "eventing": {"deployed": False, "resources": []},
        "l2": {"deployed": False, "resources": []},
        "l3": {
            "hot": {"deployed": False, "resources": []},
            "cold": {"deployed": False, "resources": []},
            "archive": {"deployed": False, "resources": []},
        },
        "l4": {"deployed": False, "resources": []},
        "l5": {"deployed": False, "resources": []},
        "total_resources": 0,
    }
    if error:
        result["error"] = error
    return result


def _runner(project_name: str, project_path: Path | None = None) -> TerraformRunner:
    project_path = project_path or resolve_project_context_path(project_name)
    terraform_dir = Path(__file__).resolve().parents[1] / "terraform"
    return TerraformRunner(
        str(terraform_dir),
        state_path=str(project_path / "terraform" / "terraform.tfstate"),
    )


def run_terraform_status_command(
    args: list[str],
    project_name: str,
    project_path: Path | None = None,
):
    """Execute one allowlisted read-only Terraform status operation."""
    runner = _runner(project_name, project_path)
    if args == ["state", "list"]:
        return runner.state_list()
    if args[:3] == ["plan", "-refresh-only", "-detailed-exitcode"] and len(args) == 4:
        prefix = "-var-file="
        if not args[3].startswith(prefix):
            raise ValueError("Drift plan requires an explicit var file")
        return runner.refresh_only_plan(args[3][len(prefix) :])
    raise ValueError("Unsupported Terraform status command")


def _canonical_state_address(resource: str) -> str:
    """Remove only Terraform instance and module addressing syntax."""
    normalized = _INSTANCE_SELECTOR.sub("", resource.strip())
    segments = normalized.split(".")
    while len(segments) >= 4 and segments[0] == "module":
        segments = segments[2:]
    return ".".join(segments)


def _exclusive_resource_ownership() -> dict[str, str]:
    """Map exact contract addresses that prove one logical responsibility."""
    owners: dict[str, set[str]] = {}
    for component in DeploymentComponentCatalog().components.values():
        status_keys = {
            _STATUS_BY_LOGICAL_COMPONENT[logical_id]
            for logical_id in component["logical_component_ids"]
            if logical_id in _STATUS_BY_LOGICAL_COMPONENT
        }
        for address in component["terraform_binding"]["resource_addresses"]:
            owners.setdefault(str(address), set()).update(status_keys)
    return {
        address: next(iter(status_keys))
        for address, status_keys in owners.items()
        if len(status_keys) == 1
    }


_RESOURCE_OWNERSHIP = _exclusive_resource_ownership()


def _classify_resources(resources: list[str]) -> dict[str, list[str]]:
    classified = {key: [] for key in _STATUS_BY_LOGICAL_COMPONENT.values()}
    for resource in resources:
        status_key = _RESOURCE_OWNERSHIP.get(_canonical_state_address(resource))
        if status_key is not None:
            classified[status_key].append(resource)
    return classified


def check_terraform_state(
    project_name: str,
    project_path: Path | None = None,
) -> dict[str, Any]:
    """Classify canonical Terraform addresses without calling cloud APIs."""
    try:
        result = run_terraform_status_command(
            ["state", "list"], project_name, project_path
        )
    except Exception as exc:
        diagnostic = redact_sensitive(exc)
        logger.warning("Terraform state check failed: %s", diagnostic)
        return _empty_state("error", error="Terraform state check failed")

    if result.returncode != 0:
        diagnostic = redact_sensitive(result.stderr or result.stdout)
        if (
            "no state file" in diagnostic.lower()
            or "does not exist" in diagnostic.lower()
        ):
            return _empty_state("not_deployed")
        logger.warning("Terraform state list failed: %s", diagnostic)
        return _empty_state("error", error="Terraform state list failed")

    resources = [line for line in result.stdout.splitlines() if line.strip()]
    if not resources:
        return _empty_state("not_deployed")

    classified = _classify_resources(resources)
    l1 = classified["l1"]
    eventing = classified["eventing"]
    l2 = classified["l2"]
    hot = classified["hot"]
    cold = classified["cold"]
    archive = classified["archive"]
    l4 = classified["l4"]
    l5 = classified["l5"]
    return {
        "status": "deployed",
        "l1": {"deployed": bool(l1), "resources": l1},
        "eventing": {"deployed": bool(eventing), "resources": eventing},
        "l2": {"deployed": bool(l2), "resources": l2},
        "l3": {
            "hot": {"deployed": bool(hot), "resources": hot},
            "cold": {"deployed": bool(cold), "resources": cold},
            "archive": {"deployed": bool(archive), "resources": archive},
        },
        "l4": {"deployed": bool(l4), "resources": l4},
        "l5": {"deployed": bool(l5), "resources": l5},
        "total_resources": len(resources),
    }


def check_terraform_drift(
    project_name: str,
    project_path: Path | None = None,
) -> dict[str, Any]:
    """Compare deployed resources to state using transient credential tfvars."""
    project_path = project_path or resolve_project_context_path(project_name)
    try:
        with tempfile.TemporaryDirectory(prefix="twin2multicloud-drift-") as temp_dir:
            var_file = Path(temp_dir) / "generated.tfvars.json"
            generate_tfvars(str(project_path), str(var_file))
            result = run_terraform_status_command(
                [
                    "plan",
                    "-refresh-only",
                    "-detailed-exitcode",
                    f"-var-file={var_file}",
                ],
                project_name,
                project_path,
            )
    except Exception as exc:
        logger.warning("Terraform drift check failed: %s", redact_sensitive(exc))
        return {"status": "error", "error": "Terraform drift check failed"}

    if result.returncode == 0:
        return {
            "status": "no_drift",
            "message": "Infrastructure matches Terraform state",
        }
    if result.returncode == 2:
        logger.info(
            "Terraform drift detected: %s",
            redact_sensitive(result.stdout),
        )
        return {
            "status": "drift_detected",
            "message": "Infrastructure has drifted from Terraform state",
            "details": "Terraform refresh-only plan reported changes",
        }
    logger.warning(
        "Terraform drift command failed: %s",
        redact_sensitive(result.stderr or result.stdout),
    )
    return {
        "status": "error",
        "error": "Terraform drift command failed",
    }
