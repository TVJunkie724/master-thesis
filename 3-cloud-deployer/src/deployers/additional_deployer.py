"""
Additional Deployer - TwinMaker Hierarchy Management Wrapper.

DEPRECATED: Use aws.additional_deployer_aws directly or the new providers pattern.
"""
import warnings
warnings.warn(
    "deployers.additional_deployer is deprecated.",
    DeprecationWarning,
    stacklevel=2
)

from logger import logger
import aws.additional_deployer_aws as hierarchy_deployer_aws
from botocore.exceptions import ClientError

def deploy_l4(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      hierarchy_deployer_aws.create_twinmaker_hierarchy()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")
  

def destroy_l4(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      hierarchy_deployer_aws.destroy_twinmaker_hierarchy()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def info_l4(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      hierarchy_deployer_aws.info_twinmaker_hierarchy()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")
  


def deploy(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  
  deploy_l4(provider)

def destroy(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  
  destroy_l4(provider)

def info(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  
  info_l4()