"""
Event Action Deployer - Lambda Event Actions Wrapper.

DEPRECATED: Use aws.event_action_deployer_aws directly or the new providers pattern.
"""
import warnings
warnings.warn(
    "deployers.event_action_deployer is deprecated.",
    DeprecationWarning,
    stacklevel=2
)

import aws.event_action_deployer_aws as event_action_deployer_aws
from botocore.exceptions import ClientError

def deploy(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for event action deployer.")
    match provider:
        case "aws":
            event_action_deployer_aws.deploy_lambda_actions()
        case "azure":
            raise NotImplementedError("Azure event action deployer not implemented yet.")
        case "google":
            raise NotImplementedError("Google event action deployer not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def destroy(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for event action deployer.")
    match provider:
        case "aws":
            event_action_deployer_aws.destroy_lambda_actions()
        case "azure":
            raise NotImplementedError("Azure event action deployer not implemented yet.")
        case "google":
            raise NotImplementedError("Google event action deployer not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")
  

def redeploy(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for event action deployer.")
    match provider:
        case "aws":
            event_action_deployer_aws.destroy_lambda_actions()
            event_action_deployer_aws.deploy_lambda_actions()
        case "azure":
            raise NotImplementedError("Azure event action deployer not implemented yet.")
        case "google":
            raise NotImplementedError("Google event action deployer not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")
  

def info(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for event action deployer.")
    match provider:
        case "aws":
            event_action_deployer_aws.info_lambda_actions()
        case "azure":
            raise NotImplementedError("Azure event action deployer not implemented yet.")
        case "google":
            raise NotImplementedError("Google event action deployer not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")
  