"""Read-only repository for the three versioned thesis pricing snapshots."""

from __future__ import annotations

import json
import os
import stat
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.pricing_catalog_models import (
    PricingCatalogBaselineManifest,
    PricingCatalogReference,
    PricingCatalogSnapshot,
    Provider,
    canonicalize_pricing_region,
)

DEFAULT_MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
DEFAULT_BASELINE_ROOT = (
    Path(__file__).resolve().parents[1] / "json" / "pricing_catalog_baselines"
)


class PricingCatalogRepositoryError(RuntimeError):
    """Base class for stable pricing catalog failures."""

    code = "PRICING_CATALOG_ERROR"


class PricingCatalogNotFoundError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_NOT_FOUND"


class PricingCatalogTamperedError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_TAMPERED"


class PricingCatalogRegionMismatchError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_REGION_MISMATCH"


class PricingCatalogStorageError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_STORAGE_UNAVAILABLE"


class PricingCatalogRepository:
    """Resolve only the immutable snapshots pinned by ``baseline.json``."""

    def __init__(
        self,
        *,
        baseline_root: Path,
        max_snapshot_bytes: int = DEFAULT_MAX_SNAPSHOT_BYTES,
    ) -> None:
        self.baseline_root = Path(os.path.abspath(baseline_root))
        if max_snapshot_bytes <= 0:
            raise ValueError("max_snapshot_bytes must be positive")
        self.max_snapshot_bytes = max_snapshot_bytes

    def verify_readiness(self) -> None:
        """Verify the manifest plus all three pinned snapshot identities."""
        manifest = self._manifest()
        for reference in manifest.catalogs.values():
            self.resolve_exact(reference)

    def resolve_baseline(
        self,
        provider: Provider,
        *,
        require_fresh: bool = False,
        now=None,
    ) -> PricingCatalogSnapshot:
        """Return the single repository-pinned snapshot for ``provider``.

        ``require_fresh`` and ``now`` remain compatibility-only arguments. The
        thesis contract is version/digest based and deliberately has no wall-clock
        freshness gate.
        """
        del require_fresh, now
        try:
            reference = self._manifest().catalogs[provider]
        except KeyError as exc:
            raise PricingCatalogNotFoundError(
                "Pinned pricing catalog provider is missing"
            ) from exc
        return self.resolve_exact(reference)

    def resolve_exact(
        self,
        reference: PricingCatalogReference,
        *,
        require_fresh: bool = False,
        now=None,
    ) -> PricingCatalogSnapshot:
        """Resolve an exact reference only when it is the pinned baseline."""
        del require_fresh, now
        pinned = self._manifest().catalogs.get(reference.provider)
        if pinned != reference:
            raise PricingCatalogNotFoundError(
                "Pricing reference is not part of the pinned thesis baseline"
            )
        payload = self._read_json(self._snapshot_path(reference))
        try:
            snapshot = PricingCatalogSnapshot.model_validate(payload)
        except ValidationError as exc:
            raise PricingCatalogTamperedError(
                "Pinned pricing snapshot violates its contract"
            ) from exc
        if snapshot.reference != reference:
            raise PricingCatalogTamperedError(
                "Pinned pricing snapshot identity does not match its reference"
            )
        return snapshot.detached_copy()

    def resolve_snapshot(
        self,
        provider: Provider,
        pricing_region: str,
        snapshot_id: str,
        *,
        require_fresh: bool = False,
        now=None,
    ) -> PricingCatalogSnapshot:
        """Resolve the pinned snapshot by URL identity fields."""
        del require_fresh, now
        try:
            canonical_region = canonicalize_pricing_region(provider, pricing_region)
        except ValueError as exc:
            raise PricingCatalogRegionMismatchError("Pricing region is invalid") from exc
        try:
            reference = self._manifest().catalogs[provider]
        except KeyError as exc:
            raise PricingCatalogNotFoundError(
                "Pinned pricing catalog provider is missing"
            ) from exc
        if canonical_region != reference.pricing_region:
            raise PricingCatalogRegionMismatchError(
                "Pricing region does not match the pinned reference"
            )
        if snapshot_id != reference.snapshot_id:
            raise PricingCatalogNotFoundError(
                "Pricing snapshot is not part of the pinned thesis baseline"
            )
        return self.resolve_exact(reference)

    def _manifest(self) -> PricingCatalogBaselineManifest:
        payload = self._read_json(self.baseline_root / "baseline.json")
        try:
            return PricingCatalogBaselineManifest.model_validate(payload)
        except ValidationError as exc:
            raise PricingCatalogTamperedError(
                "Pinned pricing baseline manifest violates its contract"
            ) from exc

    def _snapshot_path(self, reference: PricingCatalogReference) -> Path:
        return (
            self.baseline_root
            / reference.provider
            / reference.pricing_region
            / "snapshots"
            / f"{reference.snapshot_id}.json"
        )

    def _read_json(self, path: Path) -> dict[str, Any]:
        self._assert_safe_path(path)
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError as exc:
            raise PricingCatalogNotFoundError(
                "Pinned pricing catalog document is missing"
            ) from exc
        except OSError as exc:
            raise PricingCatalogStorageError(
                "Pinned pricing catalog cannot be read"
            ) from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > self.max_snapshot_bytes:
                raise PricingCatalogTamperedError(
                    "Pinned pricing catalog path is not a bounded regular file"
                )
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                raw = handle.read(self.max_snapshot_bytes + 1)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if len(raw) > self.max_snapshot_bytes:
            raise PricingCatalogTamperedError(
                "Pinned pricing catalog exceeds the size limit"
            )
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PricingCatalogTamperedError(
                "Pinned pricing catalog is not valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise PricingCatalogTamperedError(
                "Pinned pricing catalog document must be an object"
            )
        return payload

    def _assert_safe_path(self, path: Path) -> None:
        if not self.baseline_root.is_dir() or self.baseline_root.is_symlink():
            raise PricingCatalogStorageError(
                "Pinned pricing baseline root is unavailable"
            )
        absolute = Path(os.path.abspath(path))
        if self.baseline_root not in absolute.parents:
            raise PricingCatalogTamperedError(
                "Pinned pricing catalog path escapes its repository root"
            )
        current = absolute.parent
        while current != self.baseline_root:
            if current.is_symlink():
                raise PricingCatalogTamperedError(
                    "Pinned pricing catalog path contains a symbolic link"
                )
            current = current.parent


@lru_cache(maxsize=1)
def get_pricing_catalog_repository() -> PricingCatalogRepository:
    """Return the read-only repository for the tracked thesis baseline."""
    baseline_root = Path(
        os.getenv("PRICING_CATALOG_BASELINE_ROOT", str(DEFAULT_BASELINE_ROOT))
    )
    repository = PricingCatalogRepository(baseline_root=baseline_root)
    repository.verify_readiness()
    return repository
