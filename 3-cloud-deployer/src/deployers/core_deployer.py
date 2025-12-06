import globals
import aws.core_deployer_aws as core_aws
from botocore.exceptions import ClientError

from logger import logger

def deploy_l1(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      logger.info("Deploying L1 for AWS...")
      logger.info("Creating dispatcher IAM role...")
      core_aws.create_dispatcher_iam_role()
      logger.info("Creating dispatcher lambda function...")
      core_aws.create_dispatcher_lambda_function()
      logger.info("Creating dispatcher IoT rule...")
      core_aws.create_dispatcher_iot_rule()
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
      logger.info("Destroying L1 for AWS...")
      logger.info("Destroying dispatcher IoT rule...")
      core_aws.destroy_dispatcher_iot_rule()
      logger.info("Destroying dispatcher lambda function...")
      core_aws.destroy_dispatcher_lambda_function()
      logger.info("Destroying dispatcher IAM role...")
      core_aws.destroy_dispatcher_iam_role()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def redeploy_l2_event_checker(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.redeploy_event_checker_lambda_function
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
      core_aws.create_persister_iam_role()
      core_aws.create_persister_lambda_function()
      
      # Optional: Event Checker and its dependencies
      if globals.is_optimization_enabled("useEventChecking"):
          # Optional: Notification Workflow (Dependent on Event Checker)
          if globals.is_optimization_enabled("triggerNotificationWorkflow"):
              core_aws.create_lambda_chain_iam_role()
              core_aws.create_lambda_chain_step_function()
          
          # Optional: Feedback Loop (Dependent on Event Checker)
          if globals.is_optimization_enabled("returnFeedbackToDevice"):
              core_aws.create_event_feedback_iam_role()
              core_aws.create_event_feedback_lambda_function()
          
          # Create Event Checker LAST so it can access ARNs of dependencies
          core_aws.create_event_checker_iam_role()
          core_aws.create_event_checker_lambda_function()

      # Deploy Event Actions (Lambda Actions for Events)
      # These are dynamically defined in config_events.json and are part of L2 logic
      logger.info("Deploying Event Actions (L2)...")
      import deployers.event_action_deployer as event_action_deployer
      event_action_deployer.deploy(provider)

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
      # Destroy Optional Resources (Safe even if not created)
      core_aws.destroy_event_feedback_lambda_function()
      core_aws.destroy_event_feedback_iam_role()
      core_aws.destroy_lambda_chain_step_function()
      core_aws.destroy_lambda_chain_iam_role()
      
      core_aws.destroy_event_checker_lambda_function()
      core_aws.destroy_event_checker_iam_role()
      core_aws.destroy_persister_lambda_function()
      core_aws.destroy_persister_iam_role()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def deploy_l3_hot(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.create_hot_dynamodb_table()
      core_aws.create_hot_cold_mover_iam_role()
      core_aws.create_hot_cold_mover_lambda_function()
      core_aws.create_hot_cold_mover_event_rule()
      core_aws.create_hot_reader_iam_role()
      core_aws.create_hot_reader_lambda_function()
      core_aws.create_hot_reader_last_entry_iam_role()
      core_aws.create_hot_reader_last_entry_lambda_function()
      
      # Conditional: API Gateway
      if globals.should_deploy_api_gateway(provider):
          core_aws.create_api()
          core_aws.create_api_hot_reader_integration()

    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def destroy_l3_hot(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")  
  match provider:
    case "aws":
      core_aws.destroy_api_hot_reader_integration()
      core_aws.destroy_api()
      core_aws.destroy_hot_reader_last_entry_lambda_function()
      core_aws.destroy_hot_reader_last_entry_iam_role()
      core_aws.destroy_hot_reader_lambda_function()
      core_aws.destroy_hot_reader_iam_role()
      core_aws.destroy_hot_cold_mover_event_rule()
      core_aws.destroy_hot_cold_mover_lambda_function()
      core_aws.destroy_hot_cold_mover_iam_role()
      core_aws.destroy_hot_dynamodb_table()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def deploy_l3_cold(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.create_cold_s3_bucket()
      core_aws.create_cold_archive_mover_iam_role()
      core_aws.create_cold_archive_mover_lambda_function()
      core_aws.create_cold_archive_mover_event_rule()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def destroy_l3_cold(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.destroy_cold_archive_mover_event_rule()
      core_aws.destroy_cold_archive_mover_lambda_function()
      core_aws.destroy_cold_archive_mover_iam_role()
      core_aws.destroy_cold_s3_bucket()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def deploy_l3_archive(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.create_archive_s3_bucket()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def destroy_l3_archive(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.destroy_archive_s3_bucket()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def deploy_l3(provider=None):
  """
  Deploy all L3 services (hot, cold, archive)

  Args:
      provider (_type_, optional): _description_. Defaults to None.

  Raises:
      ValueError: _description_
      NotImplementedError: _description_
      NotImplementedError: _description_
      ValueError: _description_
  """
  deploy_l3_hot(provider)
  deploy_l3_cold(provider)
  deploy_l3_archive(provider)
  
def destroy_l3(provider=None):
  destroy_l3_archive(provider)
  destroy_l3_cold(provider)
  destroy_l3_hot(provider)

def deploy_l4(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.create_twinmaker_s3_bucket()
      core_aws.create_twinmaker_iam_role()
      core_aws.create_twinmaker_workspace()
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
      core_aws.destroy_twinmaker_workspace()
      core_aws.destroy_twinmaker_iam_role()
      core_aws.destroy_twinmaker_s3_bucket()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")


def deploy_l5(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.create_grafana_iam_role()
      core_aws.create_grafana_workspace()
      core_aws.add_cors_to_twinmaker_s3_bucket()
    case "azure":
      raise NotImplementedError("Azure deployment not implemented yet.")
    case "google":
      raise NotImplementedError("Google deployment not implemented yet.")
    case _:
      raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: 'aws', 'azure', 'google'.")

def destroy_l5(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.remove_cors_from_twinmaker_s3_bucket()
      core_aws.destroy_grafana_workspace()
      core_aws.destroy_grafana_iam_role()
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
  deploy_l3(provider)
  deploy_l4(provider)
  deploy_l5(provider)

def destroy(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  
  destroy_l5(provider)
  destroy_l4(provider)
  destroy_l3(provider)
  destroy_l2(provider)
  destroy_l1(provider)