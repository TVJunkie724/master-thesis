"""
Info - Infrastructure Status Checks.

This module provides status check functions to verify deployed resources
across all layers and providers.

All functions now REQUIRE the config parameter.
Legacy globals fallback has been removed.
"""

from logger import logger
import aws.info_aws as info_aws
from botocore.exceptions import ClientError
from typing import Union
from core.context import ProjectConfig


def check_l1(provider: str = None, config: Union[dict, ProjectConfig] = None):
    """Check Layer 1 (IoT) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    if config is None:
        raise ValueError("config is required - globals fallback has been removed")
    
    # Get iot_devices from config
    if hasattr(config, 'iot_devices'):
        iot_devices = config.iot_devices
    else:
        iot_devices = config.get('iot_devices', [])
    
    match provider:
        case "aws":
          info_aws.check_dispatcher_iam_role()
          info_aws.check_dispatcher_lambda_function()
          info_aws.check_dispatcher_iot_rule()

          for iot_device in iot_devices:
            info_aws.check_iot_thing(iot_device)
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def check_l2(provider: str = None, config: Union[dict, ProjectConfig] = None):
    """Check Layer 2 (Compute) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    if config is None:
        raise ValueError("config is required - globals fallback has been removed")
    
    if hasattr(config, 'iot_devices'):
        iot_devices = config.iot_devices
    else:
        iot_devices = config.get('iot_devices', [])
    
    match provider:
        case "aws":
            info_aws.check_persister_iam_role()
            info_aws.check_persister_lambda_function()
            info_aws.check_event_checker_iam_role()
            info_aws.check_event_checker_lambda_function()
            info_aws.check_lambda_chain_iam_role()
            info_aws.check_lambda_chain_step_function()
            info_aws.check_event_feedback_iam_role()
            info_aws.check_event_feedback_lambda_function()
            for iot_device in iot_devices:
                info_aws.check_processor_iam_role(iot_device)
                info_aws.check_processor_lambda_function(iot_device)
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def check_l3_hot(provider: str = None, config: Union[dict, ProjectConfig] = None):
    """Check Layer 3 Hot (Storage) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    match provider:
        case "aws":
            info_aws.check_hot_dynamodb_table()
            info_aws.check_hot_cold_mover_iam_role()
            info_aws.check_hot_cold_mover_lambda_function()
            info_aws.check_hot_cold_mover_event_rule()
            info_aws.check_hot_reader_iam_role()
            info_aws.check_hot_reader_lambda_function()
            info_aws.check_hot_reader_last_entry_iam_role()
            info_aws.check_hot_reader_last_entry_lambda_function()
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def check_l3_cold(provider: str = None, config: Union[dict, ProjectConfig] = None):
    """Check Layer 3 Cold (Storage) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    match provider:
        case "aws":
            info_aws.check_cold_s3_bucket()
            info_aws.check_cold_archive_mover_iam_role()
            info_aws.check_cold_archive_mover_lambda_function()
            info_aws.check_cold_archive_mover_event_rule()
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def check_l3_archive(provider: str = None, config: Union[dict, ProjectConfig] = None):
    """Check Layer 3 Archive (Storage) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    match provider:
        case "aws":
            info_aws.check_archive_s3_bucket()
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def check_l3(provider: str = None, config: Union[dict, ProjectConfig] = None):
    """Check all Layer 3 (Storage) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    check_l3_hot(provider, config)
    check_l3_cold(provider, config)
    check_l3_archive(provider, config)


def check_l4(provider: str = None, config: Union[dict, ProjectConfig] = None):
    """Check Layer 4 (TwinMaker) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    if config is None:
        raise ValueError("config is required - globals fallback has been removed")
    
    if hasattr(config, 'iot_devices'):
        iot_devices = config.iot_devices
    else:
        iot_devices = config.get('iot_devices', [])
    
    match provider:
        case "aws":
            info_aws.check_twinmaker_s3_bucket()
            info_aws.check_twinmaker_iam_role()
            info_aws.check_twinmaker_workspace()
            for iot_device in iot_devices:
                info_aws.check_twinmaker_component_type(iot_device)
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def check_l5(provider: str = None, config: Union[dict, ProjectConfig] = None):
    """Check Layer 5 (Grafana) resources."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    match provider:
        case "aws":
            info_aws.check_grafana_iam_role()
            info_aws.check_grafana_workspace()
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def check(provider: str = None, config: Union[dict, ProjectConfig] = None):
    """Run all checks for the specified provider."""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    if config is None:
        raise ValueError("config is required - globals fallback has been removed")
    
    try:
        check_l1(provider, config)
        check_l2(provider, config)
        check_l3(provider, config)
        check_l4(provider, config)
        check_l5(provider, config)
    except Exception as e:
        logger.error(f"Error during info/check: {str(e)}")
        raise