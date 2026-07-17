import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "backend"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
)
CONTRACT_V1 = CONTRACT_ROOT / "v1"


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
    digest = hashlib.sha256()
    for path in sorted(
        path
        for path in CONTRACT_ROOT.rglob("*")
        if path.is_file() and path.name != ".contract-sha256"
    ):
        digest.update(path.relative_to(CONTRACT_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def test_generated_contract_copy_is_complete_and_self_consistent():
    Draft202012Validator.check_schema(_load(CONTRACT_V1 / "schema.json"))
    assert (CONTRACT_ROOT / ".contract-sha256").read_text().strip() == _tree_digest()
    assert len(list((CONTRACT_V1 / "fixtures" / "valid").glob("*.json"))) == 3
    assert len(list((CONTRACT_V1 / "fixtures" / "invalid").glob("*.json"))) == 17


@pytest.mark.parametrize(
    "fixture_path",
    sorted((CONTRACT_V1 / "fixtures" / "valid").glob("*.json")),
    ids=lambda path: path.stem,
)
def test_valid_contract_fixtures_match_schema_and_digest(fixture_path):
    specification = _load(fixture_path)
    Draft202012Validator(
        _load(CONTRACT_V1 / "schema.json"),
        format_checker=FormatChecker(),
    ).validate(specification)
    assert specification["digest"] == _canonical_digest(specification)
