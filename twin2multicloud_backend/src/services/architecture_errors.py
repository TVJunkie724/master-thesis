"""Stable, bounded architecture domain errors."""

from __future__ import annotations


class ArchitectureDomainError(ValueError):
    """Safe error contract shared by services and routes."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int,
        field: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.field = field
        super().__init__(message)


def architecture_error(
    code: str,
    message: str,
    *,
    field: str | None = None,
) -> ArchitectureDomainError:
    status = {
        "ARCH_PROFILE_NOT_FOUND": 404,
        "ARCH_PROFILE_VERSION_UNSUPPORTED": 404,
        "ARCH_RESOLUTION_NOT_SELECTED": 404,
        "ARCH_LEGACY_NOT_RESOLVABLE": 409,
        "ARCH_PROFILE_NOT_ACTIVE": 409,
        "ARCH_SELECTION_REVISION_CONFLICT": 409,
        "ARCH_SELECTION_INVALIDATION_STALE": 409,
        "ARCH_RESOLUTION_DUPLICATE": 409,
        "ARCH_LEGACY_PROJECTION_UNSUPPORTED": 409,
        "ARCH_SELECTION_FORBIDDEN": 403,
    }.get(code, 422)
    return ArchitectureDomainError(
        code,
        message,
        http_status=status,
        field=field,
    )
