"""Durable, immutable repository for provider-region pricing catalogs."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import errno
import fcntl
from functools import lru_cache
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import re
from typing import Any, Iterator

from pydantic import ValidationError

from backend.pricing_catalog_models import (
    PricingCatalogBaselineManifest,
    PricingCatalogReference,
    PricingCatalogSnapshot,
    Provider,
    build_pricing_catalog_reference,
    canonical_json_bytes,
    canonicalize_pricing_region,
)


DEFAULT_MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_AGE_DAYS = 7
DEFAULT_BASELINE_ROOT = (
    Path(__file__).resolve().parents[1] / "json" / "pricing_catalog_baselines"
)
DEFAULT_RUNTIME_ROOT = Path(
    "/var/lib/twin2multicloud-optimizer/pricing-catalogs"
)
_FORBIDDEN_SECRET_KEY_FRAGMENTS = {
    "accesskey",
    "accesstoken",
    "apikey",
    "authorization",
    "clientsecret",
    "credential",
    "password",
    "privatekey",
    "secret",
    "sessiontoken",
    "token",
}
_SNAPSHOT_ID_PATTERN = re.compile(r"^pcs_[0-9a-f]{64}$")


class PricingCatalogRepositoryError(RuntimeError):
    """Base class for stable pricing catalog repository failures."""

    code = "PRICING_CATALOG_ERROR"


class PricingCatalogNotFoundError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_NOT_FOUND"


class PricingCatalogTamperedError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_TAMPERED"


class PricingCatalogStaleError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_STALE"


class PricingCatalogUnreviewedError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_UNREVIEWED"


class PricingCatalogRegionMismatchError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_REGION_MISMATCH"


class PricingCatalogRefreshInProgressError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_REFRESH_IN_PROGRESS"


class PricingCatalogStorageError(PricingCatalogRepositoryError):
    code = "PRICING_CATALOG_STORAGE_UNAVAILABLE"


class PricingCatalogRepository:
    """Single-writer filesystem repository with exact-reference reads."""

    def __init__(
        self,
        *,
        runtime_root: Path,
        baseline_root: Path,
        max_snapshot_bytes: int = DEFAULT_MAX_SNAPSHOT_BYTES,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ) -> None:
        self.runtime_root = _normalize_root(runtime_root)
        self.baseline_root = _normalize_root(baseline_root)
        if max_snapshot_bytes <= 0:
            raise ValueError("max_snapshot_bytes must be positive")
        if max_age_days <= 0:
            raise ValueError("max_age_days must be positive")
        self.max_snapshot_bytes = max_snapshot_bytes
        self.max_age = timedelta(days=max_age_days)
        self._thread_locks: dict[tuple[str, str], threading.Lock] = {}
        self._thread_locks_guard = threading.Lock()

    def initialize_from_baseline(self) -> PricingCatalogBaselineManifest:
        """Seed or migrate runtime state from an explicitly tracked baseline."""

        self._assert_safe_root(self.baseline_root, must_exist=True)
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self._assert_safe_root(self.runtime_root, must_exist=True)
        if not os.access(self.runtime_root, os.W_OK | os.R_OK):
            raise PricingCatalogStorageError("Pricing catalog storage is unavailable")

        baseline_payload = self._read_json(
            self.baseline_root / "baseline.json",
            not_found_message="Pricing catalog baseline manifest is missing",
        )
        manifest = self._parse_manifest(baseline_payload)
        runtime_manifest_path = self.runtime_root / "baseline.json"
        previous_manifest: PricingCatalogBaselineManifest | None = None
        if runtime_manifest_path.exists():
            runtime_payload = self._read_json(
                runtime_manifest_path,
                not_found_message="Runtime pricing catalog baseline is missing",
            )
            if canonical_json_bytes(runtime_payload) != canonical_json_bytes(
                baseline_payload
            ):
                if not self._is_tracked_predecessor(runtime_payload):
                    raise PricingCatalogTamperedError(
                        "Runtime pricing catalog baseline is not a tracked predecessor"
                    )
                previous_manifest = self._parse_manifest(runtime_payload)
                for old_reference in previous_manifest.catalogs.values():
                    self.resolve_exact(old_reference, require_fresh=False)
                    replacement = manifest.catalogs[old_reference.provider]
                    if (
                        old_reference.pricing_region
                        != replacement.pricing_region
                    ):
                        raise PricingCatalogTamperedError(
                            "Tracked baseline migration cannot change pricing regions"
                        )

        for reference in manifest.catalogs.values():
            source = self._snapshot_path(self.baseline_root, reference)
            payload = self._read_json(
                source,
                not_found_message="Pinned pricing catalog baseline is missing",
            )
            snapshot = self._parse_snapshot(payload, reference)
            target = self._snapshot_path(self.runtime_root, reference)
            self._write_immutable(target, snapshot.to_storage_dict())
            pointer = self._pointer_path(
                self.runtime_root,
                reference.provider,
                reference.pricing_region,
            )
            if not pointer.exists():
                self._write_json_atomically(pointer, reference.to_storage_dict())
            elif previous_manifest is not None:
                current_pointer = self._parse_reference(
                    self._read_json(
                        pointer,
                        not_found_message=(
                            "Published pricing catalog pointer is missing"
                        ),
                    )
                )
                old_reference = previous_manifest.catalogs[
                    reference.provider
                ]
                if current_pointer == old_reference:
                    self._write_json_atomically(
                        pointer,
                        reference.to_storage_dict(),
                    )

        if previous_manifest is None:
            self._write_immutable(
                runtime_manifest_path,
                manifest.to_storage_dict(),
            )
        else:
            self._write_json_atomically(
                runtime_manifest_path,
                manifest.to_storage_dict(),
            )
        self.verify_readiness()
        return manifest

    def _is_tracked_predecessor(self, runtime_payload: dict[str, Any]) -> bool:
        history_root = self.baseline_root / "history"
        if not history_root.exists() or history_root.is_symlink():
            return False
        for path in sorted(history_root.glob("baseline-*.json")):
            history_payload = self._read_json(
                path,
                not_found_message="Tracked pricing baseline predecessor is missing",
            )
            if canonical_json_bytes(history_payload) == canonical_json_bytes(
                runtime_payload
            ):
                return True
        return False

    def verify_readiness(self) -> None:
        """Fail closed when baseline or runtime catalog state is inconsistent."""

        runtime_payload = self._read_json(
            self.runtime_root / "baseline.json",
            not_found_message="Runtime pricing catalog baseline is missing",
        )
        source_payload = self._read_json(
            self.baseline_root / "baseline.json",
            not_found_message="Pricing catalog baseline manifest is missing",
        )
        if canonical_json_bytes(runtime_payload) != canonical_json_bytes(source_payload):
            raise PricingCatalogTamperedError(
                "Runtime pricing catalog baseline differs from its seed"
            )
        manifest = self._parse_manifest(runtime_payload)
        for reference in manifest.catalogs.values():
            self.resolve_exact(reference, require_fresh=False)
            self.resolve_published(
                reference.provider,
                reference.pricing_region,
                require_fresh=False,
            )

    def store_candidate(
        self,
        *,
        provider: Provider,
        pricing_region: str,
        pricing: dict[str, Any],
        provider_schema_version: str,
        contract_version: str,
        registry_version: str,
        mapping_versions: tuple[str, ...] | list[str],
        fetched_at: datetime,
        source: str,
        review_status: str,
        calculation_source: str,
    ) -> PricingCatalogSnapshot:
        """Store one new immutable candidate or reviewed observation."""

        sanitized_pricing = deepcopy(pricing)
        sanitized_pricing.pop("__account_pricing_context__", None)
        sanitized_pricing.pop("accountPricingContext", None)
        sanitized_pricing.pop("__publication__", None)
        _reject_secret_keys(sanitized_pricing)
        reference = build_pricing_catalog_reference(
            provider=provider,
            pricing_region=pricing_region,
            pricing=sanitized_pricing,
            provider_schema_version=provider_schema_version,
            contract_version=contract_version,
            registry_version=registry_version,
            mapping_versions=mapping_versions,
            fetched_at=fetched_at,
            source=source,
            review_status=review_status,
            calculation_source=calculation_source,
        )
        snapshot = PricingCatalogSnapshot(
            reference=reference,
            pricing=sanitized_pricing,
        )
        target = self._snapshot_path(self.runtime_root, reference)
        self._write_immutable(target, snapshot.to_storage_dict())
        return snapshot.detached_copy()

    def publish(
        self,
        reference: PricingCatalogReference,
    ) -> PricingCatalogReference:
        """Atomically point one provider-region pair at a reviewed snapshot."""

        if reference.review_status != "reviewed":
            raise PricingCatalogUnreviewedError(
                "Review-required pricing cannot be published"
            )
        if reference.publication_status != "published":
            raise PricingCatalogUnreviewedError(
                "Candidate pricing cannot become an active calculation catalog"
            )
        self.resolve_exact(reference, require_fresh=False)
        target = self._pointer_path(
            self.runtime_root,
            reference.provider,
            reference.pricing_region,
        )
        self._write_json_atomically(target, reference.to_storage_dict())
        return reference

    def resolve_exact(
        self,
        reference: PricingCatalogReference,
        *,
        require_fresh: bool = True,
        now: datetime | None = None,
    ) -> PricingCatalogSnapshot:
        """Resolve and verify the exact immutable document."""

        if reference.review_status != "reviewed":
            raise PricingCatalogUnreviewedError(
                "Review-required pricing cannot be used for calculation"
            )
        if reference.publication_status != "published":
            raise PricingCatalogUnreviewedError(
                "Unpublished pricing cannot be used for calculation"
            )
        path = self._snapshot_path(self.runtime_root, reference)
        payload = self._read_json(
            path,
            not_found_message="Exact pricing catalog snapshot is missing",
        )
        snapshot = self._parse_snapshot(payload, reference)
        if require_fresh and self.is_stale(reference, now=now):
            raise PricingCatalogStaleError("Pricing catalog snapshot is stale")
        return snapshot.detached_copy()

    def resolve_published(
        self,
        provider: Provider,
        pricing_region: str,
        *,
        require_fresh: bool = True,
        now: datetime | None = None,
    ) -> PricingCatalogSnapshot:
        canonical_region = canonicalize_pricing_region(provider, pricing_region)
        pointer = self._pointer_path(self.runtime_root, provider, canonical_region)
        payload = self._read_json(
            pointer,
            not_found_message="Published pricing catalog pointer is missing",
        )
        reference = self._parse_reference(payload)
        if (
            reference.provider != provider
            or reference.pricing_region != canonical_region
        ):
            raise PricingCatalogRegionMismatchError(
                "Published pricing catalog pointer has a region mismatch"
            )
        return self.resolve_exact(
            reference,
            require_fresh=require_fresh,
            now=now,
        )

    def resolve_snapshot(
        self,
        provider: Provider,
        pricing_region: str,
        snapshot_id: str,
        *,
        require_fresh: bool = False,
        now: datetime | None = None,
    ) -> PricingCatalogSnapshot:
        """Resolve one explicitly identified snapshot without trusting a pointer."""

        canonical_region = canonicalize_pricing_region(provider, pricing_region)
        if not isinstance(snapshot_id, str) or not _SNAPSHOT_ID_PATTERN.fullmatch(
            snapshot_id
        ):
            raise PricingCatalogNotFoundError(
                "Pricing catalog snapshot identity is invalid"
            )
        path = (
            self._region_root(self.runtime_root, provider, canonical_region)
            / "snapshots"
            / f"{snapshot_id}.json"
        )
        payload = self._read_json(
            path,
            not_found_message="Pricing catalog snapshot is missing",
        )
        reference_payload = payload.get("reference")
        if not isinstance(reference_payload, dict):
            raise PricingCatalogTamperedError(
                "Pricing catalog snapshot reference is invalid"
            )
        reference = self._parse_reference(reference_payload)
        if (
            reference.provider != provider
            or reference.pricing_region != canonical_region
            or reference.snapshot_id != snapshot_id
        ):
            raise PricingCatalogRegionMismatchError(
                "Pricing catalog snapshot identity does not match its path"
            )
        return self.resolve_exact(
            reference,
            require_fresh=require_fresh,
            now=now,
        )

    def resolve_baseline(
        self,
        provider: Provider,
        *,
        require_fresh: bool = True,
        now: datetime | None = None,
    ) -> PricingCatalogSnapshot:
        payload = self._read_json(
            self.runtime_root / "baseline.json",
            not_found_message="Runtime pricing catalog baseline is missing",
        )
        manifest = self._parse_manifest(payload)
        try:
            reference = manifest.catalogs[provider]
        except KeyError as exc:
            raise PricingCatalogNotFoundError(
                "Pinned provider pricing baseline is missing"
            ) from exc
        return self.resolve_exact(
            reference,
            require_fresh=require_fresh,
            now=now,
        )

    def is_stale(
        self,
        reference: PricingCatalogReference,
        *,
        now: datetime | None = None,
    ) -> bool:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        return current.astimezone(timezone.utc) - reference.fetched_at > self.max_age

    @contextmanager
    def refresh_guard(
        self,
        provider: Provider,
        pricing_region: str,
    ) -> Iterator[None]:
        """Reject duplicate provider-region refreshes across API workers."""

        canonical_region = canonicalize_pricing_region(provider, pricing_region)
        key = (provider, canonical_region)
        with self._thread_locks_guard:
            lock = self._thread_locks.setdefault(key, threading.Lock())
        if not lock.acquire(blocking=False):
            raise PricingCatalogRefreshInProgressError(
                "A pricing refresh is already active for this provider and region"
            )

        lock_path = self._region_root(
            self.runtime_root,
            provider,
            canonical_region,
        ) / "refresh.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor: int | None = None
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise PricingCatalogRefreshInProgressError(
                    "A pricing refresh is already active for this provider and region"
                ) from exc
            yield
        finally:
            if descriptor is not None:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)
            lock.release()

    def _parse_manifest(
        self,
        payload: dict[str, Any],
    ) -> PricingCatalogBaselineManifest:
        try:
            return PricingCatalogBaselineManifest.model_validate(payload)
        except ValidationError as exc:
            raise PricingCatalogTamperedError(
                "Pricing catalog baseline manifest is invalid"
            ) from exc

    def _parse_reference(self, payload: dict[str, Any]) -> PricingCatalogReference:
        try:
            return PricingCatalogReference.model_validate(payload)
        except ValidationError as exc:
            raise PricingCatalogTamperedError(
                "Pricing catalog reference is invalid"
            ) from exc

    def _parse_snapshot(
        self,
        payload: dict[str, Any],
        expected_reference: PricingCatalogReference,
    ) -> PricingCatalogSnapshot:
        try:
            snapshot = PricingCatalogSnapshot.model_validate(payload)
        except ValidationError as exc:
            raise PricingCatalogTamperedError(
                "Pricing catalog snapshot is invalid"
            ) from exc
        if snapshot.reference != expected_reference:
            raise PricingCatalogTamperedError(
                "Pricing catalog snapshot reference does not match"
            )
        return snapshot

    def _read_json(
        self,
        path: Path,
        *,
        not_found_message: str,
    ) -> dict[str, Any]:
        self._assert_descendant(path)
        try:
            descriptor = os.open(
                path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
        except FileNotFoundError as exc:
            raise PricingCatalogNotFoundError(not_found_message) from exc
        except OSError as exc:
            raise PricingCatalogTamperedError(
                "Pricing catalog path cannot be opened safely"
            ) from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise PricingCatalogTamperedError(
                    "Pricing catalog path is not a regular file"
                )
            if metadata.st_size > self.max_snapshot_bytes:
                raise PricingCatalogTamperedError(
                    "Pricing catalog document exceeds the size limit"
                )
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                descriptor = -1
                payload = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PricingCatalogTamperedError(
                "Pricing catalog document cannot be decoded"
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if not isinstance(payload, dict):
            raise PricingCatalogTamperedError(
                "Pricing catalog document must be a JSON object"
            )
        return payload

    def _write_immutable(self, target: Path, payload: dict[str, Any]) -> None:
        self._assert_descendant(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = canonical_json_bytes(payload)
        if len(encoded) > self.max_snapshot_bytes:
            raise PricingCatalogStorageError(
                "Pricing catalog document exceeds the size limit"
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags, 0o600)
        except FileExistsError:
            existing = self._read_raw_bytes(target)
            if existing != encoded:
                raise PricingCatalogTamperedError(
                    "Immutable pricing catalog identity collision"
                )
            return
        except OSError as exc:
            raise PricingCatalogStorageError(
                "Pricing catalog storage is unavailable"
            ) from exc
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            _fsync_directory(target.parent)
        except OSError as exc:
            target.unlink(missing_ok=True)
            raise PricingCatalogStorageError(
                "Pricing catalog storage is unavailable"
            ) from exc

    def _write_json_atomically(self, target: Path, payload: dict[str, Any]) -> None:
        self._assert_descendant(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = canonical_json_bytes(payload)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            _fsync_directory(target.parent)
        except OSError as exc:
            raise PricingCatalogStorageError(
                "Pricing catalog storage is unavailable"
            ) from exc
        finally:
            temporary.unlink(missing_ok=True)

    def _read_raw_bytes(self, path: Path) -> bytes:
        try:
            descriptor = os.open(
                path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise PricingCatalogTamperedError(
                    "Pricing catalog path is not a regular file"
                )
            if metadata.st_size > self.max_snapshot_bytes:
                raise PricingCatalogTamperedError(
                    "Pricing catalog document exceeds the size limit"
                )
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                return handle.read(self.max_snapshot_bytes + 1)
        except OSError as exc:
            raise PricingCatalogStorageError(
                "Pricing catalog storage is unavailable"
            ) from exc
        finally:
            if "descriptor" in locals() and descriptor >= 0:
                os.close(descriptor)

    def _snapshot_path(
        self,
        root: Path,
        reference: PricingCatalogReference,
    ) -> Path:
        return (
            self._region_root(
                root,
                reference.provider,
                reference.pricing_region,
            )
            / "snapshots"
            / f"{reference.snapshot_id}.json"
        )

    def _pointer_path(
        self,
        root: Path,
        provider: Provider,
        pricing_region: str,
    ) -> Path:
        return self._region_root(root, provider, pricing_region) / "published.json"

    def _region_root(
        self,
        root: Path,
        provider: Provider,
        pricing_region: str,
    ) -> Path:
        canonical_region = canonicalize_pricing_region(provider, pricing_region)
        path = root / provider / canonical_region
        self._assert_descendant(path)
        return path

    def _assert_descendant(self, path: Path) -> None:
        absolute = Path(os.path.abspath(path))
        roots = (self.runtime_root, self.baseline_root)
        if not any(absolute == root or root in absolute.parents for root in roots):
            raise PricingCatalogTamperedError(
                "Pricing catalog path escapes its configured root"
            )
        current = absolute.parent
        while any(current == root or root in current.parents for root in roots):
            if current.exists() and current.is_symlink():
                raise PricingCatalogTamperedError(
                    "Pricing catalog path contains a symbolic link"
                )
            if current in roots:
                break
            current = current.parent

    def _assert_safe_root(self, root: Path, *, must_exist: bool) -> None:
        if must_exist and not root.exists():
            raise PricingCatalogStorageError(
                "Pricing catalog storage root is unavailable"
            )
        if root.exists() and (root.is_symlink() or not root.is_dir()):
            raise PricingCatalogStorageError(
                "Pricing catalog storage root is invalid"
            )


@lru_cache(maxsize=1)
def get_pricing_catalog_repository() -> PricingCatalogRepository:
    """Return the configured process repository after verified initialization."""

    runtime_root = Path(
        os.getenv("PRICING_CATALOG_STORE_ROOT", str(DEFAULT_RUNTIME_ROOT))
    )
    baseline_root = Path(
        os.getenv("PRICING_CATALOG_BASELINE_ROOT", str(DEFAULT_BASELINE_ROOT))
    )
    repository = PricingCatalogRepository(
        runtime_root=runtime_root,
        baseline_root=baseline_root,
    )
    repository.initialize_from_baseline()
    return repository


def _normalize_root(path: Path) -> Path:
    if not isinstance(path, Path):
        path = Path(path)
    return Path(os.path.abspath(path))


def _reject_secret_keys(payload: Any, path: str = "$") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = "".join(character for character in str(key).lower() if character.isalnum())
            if any(
                fragment in normalized
                for fragment in _FORBIDDEN_SECRET_KEY_FRAGMENTS
            ):
                raise PricingCatalogStorageError(
                    f"Pricing catalog contains a forbidden secret field at {path}"
                )
            _reject_secret_keys(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _reject_secret_keys(value, f"{path}[{index}]")


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno in {errno.EINVAL, errno.ENOTSUP}:
            return
        raise
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
