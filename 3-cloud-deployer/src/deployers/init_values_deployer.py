"""
Init Values Deployer - IoT Initial Values Wrapper.

DEPRECATED: Use aws.init_values_deployer_aws directly or the new providers pattern.
"""
import warnings
warnings.warn(
    "deployers.init_values_deployer is deprecated.",
    DeprecationWarning,
    stacklevel=2
)

import aws.init_values_deployer_aws as init_values_deployer_aws

def deploy(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for init values deployer.")
        
    match provider:
        case "aws":
            init_values_deployer_aws.deploy()
        case "azure":
            raise NotImplementedError("Azure init values deployer not implemented yet.")
        case "google":
            raise NotImplementedError("Google init values deployer not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def destroy(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for init values deployer.")
        
    match provider:
        case "aws":
            init_values_deployer_aws.destroy()
        case "azure":
            pass
        case "google":
            pass
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def info(provider=None):
    if provider is None:
        raise ValueError("Provider must be specified for init values deployer.")
        
    match provider:
        case "aws":
            init_values_deployer_aws.info()
        case "azure":
            pass
        case "google":
            pass
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")
