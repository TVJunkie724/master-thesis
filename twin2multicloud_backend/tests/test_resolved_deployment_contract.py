import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
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
        [
            path.relative_to(CONTRACT_ROOT).as_posix(),
            hashlib.sha256(path.read_bytes()).hexdigest(),
        ]
        for path in sorted(CONTRACT_ROOT.rglob("*"))
        if path.is_file()
        and path.name != ".contract-sha256"
        and "__pycache__" not in path.parts
    ]
    encoded = json.dumps(entries, separators=(",", ":"), sort_keys=True).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def test_generated_contract_copy_is_complete_and_self_consistent():
    Draft202012Validator.check_schema(_load(CONTRACT_V2 / "schema.json"))
    assert (CONTRACT_ROOT / ".contract-sha256").read_text().strip() == _tree_digest()
    assert len(list((CONTRACT_V2 / "fixtures" / "valid").glob("*.json"))) == 1
    assert len(list((CONTRACT_V2 / "fixtures" / "invalid").glob("*.json"))) == 0


@pytest.mark.parametrize(
    "fixture_path",
    sorted((CONTRACT_V2 / "fixtures" / "valid").glob("*.json")),
    ids=lambda path: path.stem,
)
def test_valid_contract_fixtures_match_schema_and_digest(fixture_path):
    specification = _load(fixture_path)
    Draft202012Validator(
        _load(CONTRACT_V2 / "schema.json"),
        format_checker=FormatChecker(),
    ).validate(specification)
    assert specification["digest"] == _canonical_digest(specification)
