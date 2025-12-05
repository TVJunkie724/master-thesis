import globals
from logger import logger
import aws.info_aws as info_aws
from botocore.exceptions import ClientError
import util

def check_l1(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    match provider:
        case "aws":
          info_aws.check_dispatcher_iam_role()
          info_aws.check_dispatcher_lambda_function()
          info_aws.check_dispatcher_iot_rule()

          for iot_device in globals.config_iot_devices:
            info_aws.check_iot_thing(iot_device)
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def check_l2(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    match provider:
        case "aws":
            info_aws.check_persister_iam_role()
            info_aws.check_persister_lambda_function()
            info_aws.check_event_checker_iam_role()
            info_aws.check_event_checker_lambda_function()
            for iot_device in globals.config_iot_devices:
                info_aws.check_processor_iam_role(iot_device)
                info_aws.check_processor_lambda_function(iot_device)
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def check_l3_hot(provider=None):
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

def check_l3_cold(provider=None):
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


def check_l3_archive(provider=None):
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

def check_l3(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    check_l3_hot(provider)
    check_l3_cold(provider)
    check_l3_archive(provider)

def check_l4(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    match provider:
        case "aws":
            info_aws.check_twinmaker_s3_bucket()
            info_aws.check_twinmaker_iam_role()
            info_aws.check_twinmaker_workspace()
            for iot_device in globals.config_iot_devices:
                info_aws.check_twinmaker_component_type(iot_device)
        case "azure":
            raise NotImplementedError("Azure info/check not implemented yet.")
        case "google":
            raise NotImplementedError("Google info/check not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def check_l5(provider=None):
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

def check(provider=None):
    """Run all checks for the specified provider"""
    if provider is None:
        raise ValueError("Provider must be specified for info/check.")
    
    try:
        check_l1(provider)
        check_l2(provider)
        check_l3(provider)
        check_l4(provider)
        check_l5(provider)
    except Exception as e:
        logger.error(f"Error during info/check: {str(e)}")
        raise