"""Stable Functions API facade composed from focused function domains."""

from fastapi import APIRouter

from src.api.function_artifacts import (
    _build_function_zip,
    _compute_source_hash,
    _get_metadata_path,
    clear_all_function_metadata,
    get_artifact_metadata,
)
from src.api.function_build import (
    _build_aws_zip,
    _build_azure_zip,
    _build_gcp_zip,
    _validate_entry_point,
    _validate_python_syntax,
    build_function_zip,
    router as build_router,
)
from src.api.function_discovery import (
    CACHE_TTL_SECONDS,
    _get_cached_functions,
    _get_updatable_functions,
    _get_upload_dir,
    _invalidate_cache,
    _set_cache,
)
from src.api.function_routes import (
    get_updatable_functions,
    invalidate_function_cache,
    router as lifecycle_router,
    update_function,
)
from src.api.function_upload import (
    HAS_BOTO3,
    HAS_GCP_FUNCTIONS,
    HAS_REQUESTS,
    _upload_aws_lambda,
    _upload_azure_function,
    _upload_gcp_function,
)

router = APIRouter(prefix="/functions", tags=["Functions"])
router.include_router(lifecycle_router)
router.include_router(build_router)

__all__ = [
    "CACHE_TTL_SECONDS",
    "HAS_BOTO3",
    "HAS_GCP_FUNCTIONS",
    "HAS_REQUESTS",
    "_build_aws_zip",
    "_build_azure_zip",
    "_build_function_zip",
    "_build_gcp_zip",
    "_compute_source_hash",
    "_get_cached_functions",
    "_get_metadata_path",
    "_get_updatable_functions",
    "_get_upload_dir",
    "_invalidate_cache",
    "_set_cache",
    "_upload_aws_lambda",
    "_upload_azure_function",
    "_upload_gcp_function",
    "_validate_entry_point",
    "_validate_python_syntax",
    "build_function_zip",
    "clear_all_function_metadata",
    "get_artifact_metadata",
    "get_updatable_functions",
    "invalidate_function_cache",
    "router",
    "update_function",
]
