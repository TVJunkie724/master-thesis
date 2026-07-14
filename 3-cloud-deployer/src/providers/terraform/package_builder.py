"""Stable facade for provider-specific Terraform function package builders."""

import logging
from pathlib import Path
from typing import Dict

from src.function_registry import get_functions_for_provider_build as get_functions_for_provider_build
from src.providers.terraform.package_builders.aws import (
    _create_lambda_zip,
    build_aws_lambda_packages,
    get_lambda_zip_path,
)
from src.providers.terraform.package_builders.azure import (
    _add_azure_function_app_directly,
    _create_azure_function_zip,
    _discover_azure_user_functions,
    _generate_main_function_app,
    _rewrite_azure_function_names,
    build_azure_function_packages,
    build_azure_l0_bundle,
    build_azure_l1_bundle,
    build_azure_l2_bundle,
    build_azure_l3_bundle,
    build_azure_user_bundle,
    get_azure_zip_path,
)
from src.providers.terraform.package_builders.common import (
    _clean_old_versioned_zips,
    _compute_content_hash,
    _merge_requirements,
    _should_include_file,
)
from src.providers.terraform.package_builders.gcp import (
    _create_gcp_function_zip,
    _create_gcp_processor_zip,
    _rewrite_gcp_function_names,
    build_gcp_cloud_function_packages,
    get_gcp_zip_path,
)
from src.providers.terraform.package_builders.user import (
    _compute_directory_hash,
    _reconcile_user_hash_metadata,
    _save_user_hash_metadata,
    build_user_packages,
    get_user_package_path,
)

logger = logging.getLogger(__name__)
BUILD_DIR = ".build"


def build_all_packages(
    terraform_dir: Path,
    project_path: Path,
    providers_config: dict,
) -> Dict[str, Path]:
    """Build every provider and user-function package required by one deployment."""
    terraform_dir = Path(terraform_dir)
    project_path = Path(project_path)

    packages: Dict[str, Path] = {}
    packages.update(build_aws_lambda_packages(terraform_dir, project_path, providers_config))
    packages.update(build_azure_function_packages(terraform_dir, project_path, providers_config))
    packages.update(build_gcp_cloud_function_packages(terraform_dir, project_path, providers_config))
    packages.update(build_user_packages(project_path, providers_config))

    logger.info("Built %s function packages", len(packages))
    return packages


__all__ = [
    "BUILD_DIR",
    "_add_azure_function_app_directly",
    "_clean_old_versioned_zips",
    "_compute_content_hash",
    "_compute_directory_hash",
    "_create_azure_function_zip",
    "_create_gcp_function_zip",
    "_create_gcp_processor_zip",
    "_create_lambda_zip",
    "_discover_azure_user_functions",
    "_generate_main_function_app",
    "_merge_requirements",
    "_rewrite_azure_function_names",
    "_rewrite_gcp_function_names",
    "_reconcile_user_hash_metadata",
    "_save_user_hash_metadata",
    "_should_include_file",
    "build_all_packages",
    "build_aws_lambda_packages",
    "build_azure_function_packages",
    "build_azure_l0_bundle",
    "build_azure_l1_bundle",
    "build_azure_l2_bundle",
    "build_azure_l3_bundle",
    "build_azure_user_bundle",
    "build_gcp_cloud_function_packages",
    "build_user_packages",
    "get_azure_zip_path",
    "get_functions_for_provider_build",
    "get_gcp_zip_path",
    "get_lambda_zip_path",
    "get_user_package_path",
]
