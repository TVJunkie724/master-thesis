"""Read-only access to the three pinned thesis pricing snapshots."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from backend.pricing_catalog_repository import (
    PricingCatalogNotFoundError,
    PricingCatalogRegionMismatchError,
    PricingCatalogStorageError,
    PricingCatalogTamperedError,
    get_pricing_catalog_repository,
)

router = APIRouter(prefix="/pricing/catalogs", tags=["Pricing Evidence"])
_PROVIDERS = frozenset({"aws", "azure", "gcp"})
_REGION_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_AWS_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$")


@router.get(
    "/baseline/{provider}",
    operation_id="getPricingCatalogBaseline",
    summary="Return one pinned reviewed thesis pricing reference",
)
def get_pricing_catalog_baseline(provider: str):
    provider = _provider(provider)
    try:
        snapshot = get_pricing_catalog_repository().resolve_baseline(
            provider,
            require_fresh=False,
        )
        return snapshot.reference.to_http_dict()
    except PricingCatalogNotFoundError as exc:
        raise _not_found() from exc
    except (PricingCatalogTamperedError, PricingCatalogStorageError) as exc:
        raise _integrity_error() from exc


@router.get(
    "/{provider}/{pricing_region}/snapshots/{snapshot_id}/reference",
    operation_id="getExactPricingCatalogReference",
    summary="Verify one exact pinned thesis pricing reference",
)
def get_exact_pricing_catalog_reference(
    provider: str,
    pricing_region: str,
    snapshot_id: str,
):
    snapshot = _resolve_exact(provider, pricing_region, snapshot_id)
    return {
        "reference": snapshot.reference.to_http_dict(),
        # Snapshot validity is identity-based; wall-clock freshness is not a
        # calculation gate for the reproducible thesis evaluation.
        "isFresh": True,
    }


@router.get(
    "/{provider}/{pricing_region}/snapshots/{snapshot_id}",
    operation_id="getExactPricingCatalogSnapshot",
    summary="Inspect one exact pinned thesis pricing snapshot",
)
def get_exact_pricing_catalog_snapshot(
    provider: str,
    pricing_region: str,
    snapshot_id: str,
):
    snapshot = _resolve_exact(provider, pricing_region, snapshot_id)
    return {
        "reference": snapshot.reference.to_http_dict(),
        "pricing": snapshot.pricing,
    }


def _resolve_exact(provider: str, pricing_region: str, snapshot_id: str):
    provider = _provider(provider)
    pricing_region = _region(provider, pricing_region)
    if not re.fullmatch(r"pcs_[0-9a-f]{64}", snapshot_id):
        raise _not_found()
    try:
        return get_pricing_catalog_repository().resolve_snapshot(
            provider,
            pricing_region,
            snapshot_id,
            require_fresh=False,
        )
    except (PricingCatalogNotFoundError, PricingCatalogRegionMismatchError) as exc:
        raise _not_found() from exc
    except (PricingCatalogTamperedError, PricingCatalogStorageError) as exc:
        raise _integrity_error() from exc


def _provider(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in _PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported pricing provider.")
    return normalized


def _region(provider: str, value: str) -> str:
    normalized = value.strip().lower()
    pattern = _AWS_REGION_PATTERN if provider == "aws" else _REGION_PATTERN
    if not pattern.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="Invalid pricing region.")
    return normalized


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Pinned pricing snapshot not found.")


def _integrity_error() -> HTTPException:
    return HTTPException(
        status_code=500,
        detail="Pinned pricing snapshot failed integrity validation.",
    )
