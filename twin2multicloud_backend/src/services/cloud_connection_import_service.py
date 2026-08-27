"""Allowlisted provider credential-file imports for Cloud Connections."""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from src.schemas.cloud_connection import (
    CloudConnectionCreate,
    CloudConnectionImportMetadata,
)

_MAX_TEXT_CHARACTERS = 128 * 1024
_AWS_FIELDS = {
    "accesskeyid": "access_key_id",
    "awsaccesskeyid": "access_key_id",
    "secretaccesskey": "secret_access_key",
    "awssecretaccesskey": "secret_access_key",
    "sessiontoken": "session_token",
    "awssessiontoken": "session_token",
    "username": None,
}
_AZURE_FIELDS = {
    "appId",
    "clientId",
    "clientSecret",
    "displayName",
    "name",
    "password",
    "subscription",
    "subscriptionId",
    "tenant",
    "tenantId",
}
_GCP_FIELDS = {
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
    "auth_uri",
    "token_uri",
    "auth_provider_x509_cert_url",
    "client_x509_cert_url",
    "universe_domain",
}


def parse_cloud_connection_import(
    metadata: CloudConnectionImportMetadata,
    content: bytes,
) -> CloudConnectionCreate:
    """Parse exactly one supported provider export without retaining the file."""

    if not content or len(content) > _MAX_TEXT_CHARACTERS:
        raise ValueError("Credential file must be between 1 byte and 128 KiB")
    text = _decode_utf8(content)
    if metadata.provider == "aws":
        return _parse_aws(metadata, text)
    if metadata.provider == "azure":
        return _parse_azure(metadata, text)
    return _parse_gcp(metadata, text)


def _parse_aws(
    metadata: CloudConnectionImportMetadata,
    text: str,
) -> CloudConnectionCreate:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("AWS credential CSV requires a header row")
    normalized_headers = [_normalized_header(name) for name in reader.fieldnames]
    unknown = sorted(set(normalized_headers) - set(_AWS_FIELDS))
    if unknown:
        raise ValueError("AWS credential CSV contains unsupported columns")
    rows = [row for row in reader if any(str(value or "").strip() for value in row.values())]
    if len(rows) != 1:
        raise ValueError("AWS credential CSV must contain exactly one credential row")
    values: dict[str, str] = {}
    for original, normalized in zip(reader.fieldnames, normalized_headers, strict=True):
        target = _AWS_FIELDS[normalized]
        if target is not None:
            values[target] = str(rows[0].get(original) or "").strip()
    return CloudConnectionCreate.model_validate(
        {
            "provider": "aws",
            "purpose": metadata.purpose,
            "display_name": metadata.display_name,
            "cloud_scope": {
                **({"account_id": metadata.account_id} if metadata.account_id else {}),
                "region": metadata.region,
            },
            "aws": {
                "access_key_id": values.get("access_key_id"),
                "secret_access_key": values.get("secret_access_key"),
                "session_token": values.get("session_token") or None,
                "region": metadata.region,
                "sso_region": metadata.sso_region,
            },
        }
    )


def _parse_azure(
    metadata: CloudConnectionImportMetadata,
    text: str,
) -> CloudConnectionCreate:
    value = _json_object(text)
    if set(value) - _AZURE_FIELDS:
        raise ValueError("Azure Service Principal JSON contains unsupported fields")
    subscription = _first(value, "subscriptionId", "subscription")
    if subscription and subscription != metadata.target_scope_id:
        raise ValueError("Azure file subscription differs from target_scope_id")
    return CloudConnectionCreate.model_validate(
        {
            "provider": "azure",
            "purpose": metadata.purpose,
            "display_name": metadata.display_name,
            "cloud_scope": {"subscription_id": metadata.target_scope_id},
            "azure": {
                "subscription_id": metadata.target_scope_id,
                "client_id": _first(value, "clientId", "appId"),
                "client_secret": _first(value, "clientSecret", "password"),
                "tenant_id": _first(value, "tenantId", "tenant"),
                "region": metadata.region,
                "region_iothub": metadata.region_iothub,
                "region_digital_twin": metadata.region_digital_twin,
            },
        }
    )


def _parse_gcp(
    metadata: CloudConnectionImportMetadata,
    text: str,
) -> CloudConnectionCreate:
    value = _json_object(text)
    if set(value) - _GCP_FIELDS:
        raise ValueError("GCP Service Account JSON contains unsupported fields")
    if value.get("type") != "service_account":
        raise ValueError("GCP credential file must be a service account key")
    for field in ("project_id", "client_email", "private_key"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ValueError(f"GCP Service Account JSON is missing {field}")
    return CloudConnectionCreate.model_validate(
        {
            "provider": "gcp",
            "purpose": metadata.purpose,
            "display_name": metadata.display_name,
            "cloud_scope": {"project_id": metadata.target_scope_id},
            "gcp": {
                "project_id": metadata.target_scope_id,
                "region": metadata.region,
                "service_account_json": json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        }
    )


def _decode_utf8(content: bytes) -> str:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Credential file must be UTF-8 text") from exc
    if "\x00" in text:
        raise ValueError("Credential file contains binary data")
    return text


def _json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Credential JSON is invalid") from exc
    if not isinstance(value, dict):
        raise TypeError("Credential JSON must contain one object")
    return value


def _first(value: dict[str, Any], *names: str) -> str | None:
    for name in names:
        item = value.get(name)
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


__all__ = ["parse_cloud_connection_import"]
