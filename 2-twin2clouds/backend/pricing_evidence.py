"""Pricing evidence validation for provider rows and publish gates."""
from __future__ import annotations

from typing import Any


EVIDENCE_SCHEMA_VERSION = "pricing-evidence.v1"

FETCHED = "fetched"
DERIVED = "derived"
OFFICIAL_CLOUD_EVIDENCE = "official_cloud_evidence"
NOT_APPLICABLE = "not_applicable"
FALLBACK_STATIC = "fallback_static"

ALLOWED_SOURCE_TYPES = {
    FETCHED,
    DERIVED,
    OFFICIAL_CLOUD_EVIDENCE,
    NOT_APPLICABLE,
    FALLBACK_STATIC,
}

REQUIRED_EVIDENCE_FIELDS = (
    "provider",
    "intent_id",
    "field_path",
    "source_type",
    "source_api",
    "request_scope",
    "normalization_rule",
    "normalized_value",
    "currency",
    "mapping_version",
    "registry_version",
    "fetched_at",
    "review_required",
)


def validate_evidence_record(record: dict[str, Any]) -> list[str]:
    """Validate one pricing evidence record."""
    errors: list[str] = []
    for field in REQUIRED_EVIDENCE_FIELDS:
        if field not in record:
            errors.append(f"Missing evidence field: {field}")

    source_type = record.get("source_type")
    if source_type not in ALLOWED_SOURCE_TYPES:
        errors.append(f"Unsupported source_type: {source_type!r}")

    if source_type == FETCHED and not record.get("selected_row"):
        errors.append("Fetched evidence requires selected_row")

    if source_type == DERIVED and not record.get("source_evidence_ids"):
        errors.append("Derived evidence requires source_evidence_ids")

    if source_type == OFFICIAL_CLOUD_EVIDENCE:
        source_reference = record.get("source_reference") or {}
        if not source_reference.get("url") and not source_reference.get("document_id"):
            errors.append("Official cloud evidence requires source_reference")
        if not record.get("reproducible"):
            errors.append("Official cloud evidence must be reproducible")

    if "candidate_rows" in record and not isinstance(record["candidate_rows"], list):
        errors.append("candidate_rows must be a list")
    if "rejected_rows" in record and not isinstance(record["rejected_rows"], list):
        errors.append("rejected_rows must be a list")

    return errors


def validate_evidence_report(
    records: list[dict[str, Any]],
    *,
    publishable: bool = False,
) -> list[str]:
    """Validate a collection of evidence records and optional publishability."""
    errors: list[str] = []
    if not records:
        errors.append("Evidence report must contain at least one record")
        return errors

    for index, record in enumerate(records):
        prefix = f"record[{index}]"
        for error in validate_evidence_record(record):
            errors.append(f"{prefix}: {error}")
        if publishable and record.get("source_type") == FALLBACK_STATIC:
            errors.append(f"{prefix}: fallback_static is not publishable")
        if publishable and record.get("review_required"):
            errors.append(f"{prefix}: review_required evidence is not publishable")

    return errors
