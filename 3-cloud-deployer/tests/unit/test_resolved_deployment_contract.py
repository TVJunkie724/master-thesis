import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
)
CONTRACT_V2 = CONTRACT_ROOT / "v2"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_digest(specification: dict) -> str:
    payload = dict(specification)
    payload.pop("digest", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _tree_digest() -> str:
    entries = [
        (
            path.relative_to(CONTRACT_ROOT).as_posix(),
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(
            path
            for path in CONTRACT_ROOT.rglob("*")
            if path.is_file() and path.name != ".contract-sha256"
        )
    ]
    encoded = json.dumps(
        entries,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def test_generated_contract_copy_is_complete_and_self_consistent():
    Draft202012Validator.check_schema(_load(CONTRACT_V2 / "schema.json"))
    assert (CONTRACT_ROOT / ".contract-sha256").read_text().strip() == _tree_digest()
    assert len(list((CONTRACT_V2 / "fixtures" / "valid").glob("*.json"))) == 1


@pytest.mark.parametrize(
    "fixture_path",
    sorted((CONTRACT_V2 / "fixtures" / "valid").glob("*.json")),
    ids=lambda path: f"v2-{path.stem}",
)
def test_valid_v2_contract_fixtures_are_accepted_by_runtime(fixture_path):
    from src.deployment_specification import (
        validate_resolved_deployment_specification,
    )

    specification = _load(fixture_path)
    validated = validate_resolved_deployment_specification(specification)

    assert validated.schema_version == "resolved-deployment-specification.v2"
    assert validated.digest == specification["digest"]


@pytest.mark.parametrize(
    "mutation, expected_code",
    (
        ("digest", "DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH"),
        ("component", "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"),
        ("binding", "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH"),
    ),
)
def test_v2_runtime_rejects_semantic_drift(mutation, expected_code):
    import copy

    from src.deployment_specification import (
        DeploymentSpecificationError,
        validate_resolved_deployment_specification,
    )

    specification = copy.deepcopy(
        _load(
            CONTRACT_V2
            / "fixtures"
            / "valid"
            / "six-layer-aws-azure-eventing-small.json"
        )
    )
    if mutation == "digest":
        specification["calculation_run_id"] = "420bd4ff-8700-5034-8313-334244c0d0b2"
    elif mutation == "component":
        specification["component_selections"][0]["implementation_component_digest"] = (
            "sha256:" + ("0" * 64)
        )
        specification["digest"] = _canonical_digest(specification)
    else:
        specification["bindings"][0]["destination_selection_id"] = specification[
            "component_selections"
        ][1]["selection_id"]
        specification["digest"] = _canonical_digest(specification)

    with pytest.raises(DeploymentSpecificationError) as exc_info:
        validate_resolved_deployment_specification(specification)
    assert exc_info.value.code == expected_code
