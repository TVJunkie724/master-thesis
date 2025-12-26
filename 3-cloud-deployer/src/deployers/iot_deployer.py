import globals
import aws.iot_deployer_aws as iot_deployer_aws
from botocore.exceptions import ClientError

def deploy_l1(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      for iot_device in globals.config_iot_devices:
        iot_deployer_aws.create_iot_thing(iot_device)
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def destroy_l1(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      for iot_device in globals.config_iot_devices:
        iot_deployer_aws.destroy_iot_thing(iot_device)
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def deploy_l2(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      for iot_device in globals.config_iot_devices:
        iot_deployer_aws.create_processor_iam_role(iot_device)
        iot_deployer_aws.create_processor_lambda_function(iot_device)
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def destroy_l2(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      for iot_device in globals.config_iot_devices:
        iot_deployer_aws.destroy_processor_lambda_function(iot_device)
        iot_deployer_aws.destroy_processor_iam_role(iot_device)
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def deploy_l4(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      for iot_device in globals.config_iot_devices:
        iot_deployer_aws.create_twinmaker_component_type(iot_device)
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
      for iot_device in globals.config_iot_devices:
        iot_deployer_aws.destroy_twinmaker_component_type(iot_device)
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")



def deploy(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  
  deploy_l1(provider)
  deploy_l2(provider)
  deploy_l4(provider)

def destroy(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  
  destroy_l4(provider)
  destroy_l2(provider)
  destroy_l1(provider)
