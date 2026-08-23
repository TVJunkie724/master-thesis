import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    PROJECT_ROOT
    / "src"
    / "contracts"
    / "generated"
    / "cloud-bootstrap"
    / "v1"
    / "bootstrap-authority-pack.schema.json"
)
PACK_DIR = PROJECT_ROOT / "docs" / "references" / "permission_sets"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_bootstrap_authority_packs_are_strict_and_cover_all_providers():
    schema = _load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    packs = [
        _load(PACK_DIR / "aws_bootstrap_admin_v1.json"),
        _load(PACK_DIR / "azure_bootstrap_admin_v2.json"),
        _load(PACK_DIR / "gcp_bootstrap_admin_v1.json"),
    ]

    for pack in packs:
        validator.validate(pack)

    assert {pack["provider"] for pack in packs} == {"aws", "azure", "gcp"}
    assert {pack["contract_id"] for pack in packs} == {
        "bootstrap.aws.admin-v1",
        "bootstrap.azure.admin-v2",
        "bootstrap.gcp.admin-v1",
    }


def test_bootstrap_authority_packs_contain_no_secret_material_or_wildcards():
    forbidden_keys = {
        "access_key",
        "secret_access_key",
        "session_token",
        "client_secret",
        "private_key",
        "service_account_json",
    }
    for path in PACK_DIR.glob("*_bootstrap_admin_v*.json"):
        payload = _load(path)
        serialized = json.dumps(payload, sort_keys=True).lower()
        assert not forbidden_keys.intersection(payload)
        assert "-----begin private key-----" not in serialized
        permissions = [
            permission
            for group in payload["permission_groups"]
            for permission in group["permissions"]
        ]
        assert all("*" not in permission for permission in permissions)
