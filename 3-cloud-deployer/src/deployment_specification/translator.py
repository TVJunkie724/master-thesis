"""Pure translation from a validated specification to Terraform variables."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .contract import load_contract
from .errors import DeploymentSpecificationError
from .models import ValidatedResolvedDeploymentSpecification


def translate_deployment_tfvars(
    validated: ValidatedResolvedDeploymentSpecification,
) -> Mapping[str, str | int | bool]:
    """Return deterministic, allowlisted deployable selections only."""

    _, registry = load_contract()
    translated: dict[str, str | int | bool] = {}
    for component in validated.specification["components"]:
        component_id = component["component_id"]
        definitions = registry["components"][component_id]["dimensions"]
        for dimension in component["dimensions"]:
            definition = definitions[dimension["dimension_id"]]
            if definition["classification"] != "deployable_selection":
                continue
            target = definition["terraform_target"]
            value = dimension["value"]
            previous = translated.setdefault(target, value)
            if previous != value:
                raise DeploymentSpecificationError(
                    "DEPLOYMENT_SPECIFICATION_TARGET_CONFLICT",
                    target,
                    "Deployment dimensions contain contradictory Terraform targets",
                )
    return MappingProxyType(dict(sorted(translated.items())))
