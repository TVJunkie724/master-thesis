"""Stable Functions API facade composed from focused function domains."""

from fastapi import APIRouter

from api.function_artifacts import (
    _build_function_zip,
    _compute_directory_hash,
    _delete_hash_metadata,
    _get_hash_metadata,
    _get_metadata_path,
    _save_hash_metadata,
    clear_all_hash_metadata,
)
from api.function_build import (
    _build_aws_zip,
    _build_azure_zip,
    _build_gcp_zip,
    _validate_entry_point,
    _validate_python_syntax,
    build_function_zip,
    router as build_router,
)
from api.function_discovery import (
    CACHE_TTL_SECONDS,
    _get_cached_functions,
    _get_updatable_functions,
    _get_upload_dir,
    _invalidate_cache,
    _set_cache,
)
from api.function_routes import (
    get_updatable_functions,
    invalidate_function_cache,
    router as lifecycle_router,
    update_function,
)
from api.function_upload import (
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
    "_compute_directory_hash",
    "_delete_hash_metadata",
    "_get_cached_functions",
    "_get_hash_metadata",
    "_get_metadata_path",
    "_get_updatable_functions",
    "_get_upload_dir",
    "_invalidate_cache",
    "_save_hash_metadata",
    "_set_cache",
    "_upload_aws_lambda",
    "_upload_azure_function",
    "_upload_gcp_function",
    "_validate_entry_point",
    "_validate_python_syntax",
    "build_function_zip",
    "clear_all_hash_metadata",
    "get_updatable_functions",
    "invalidate_function_cache",
    "router",
    "update_function",
]
