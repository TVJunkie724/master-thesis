"""
Digital Twin Manager - CLI Entry Point.

This module provides the interactive CLI for managing Digital Twin deployments.
It uses the new DeploymentContext/provider architecture.
"""

import json
import os
import sys
from pathlib import Path

import constants as CONSTANTS
from logger import logger, print_stack_trace

# New architecture imports
from core.config_loader import load_project_config, load_credentials, get_required_providers
from core.context import DeploymentContext
import providers.deployer as deployer
import providers.iot_deployer as iot_deployer


# ==========================================
# Configuration & Context Management
# ==========================================

# Current project state
_current_project: str = CONSTANTS.DEFAULT_PROJECT_NAME
_current_context: DeploymentContext = None


def get_project_path() -> Path:
    """Get the project root path."""
    return Path(__file__).parent.parent


def get_upload_path(project_name: str) -> Path:
    """Get the upload path for a project."""
    return get_project_path() / CONSTANTS.PROJECT_UPLOAD_DIR_NAME / project_name


def _create_context(project_name: str, provider_name: str = None) -> DeploymentContext:
    """
    Create a DeploymentContext for a project.
    
    Args:
        project_name: Name of the project
        provider_name: Optional provider to initialize (e.g., "aws")
        
    Returns:
        Initialized DeploymentContext
    """
    project_path = get_upload_path(project_name)
    
    # Load configuration
    config = load_project_config(project_path)
    credentials = load_credentials(project_path)
    
    # Create context
    context = DeploymentContext(
        project_name=project_name,
        project_path=project_path,
        config=config,
    )
    
    # Initialize required providers
    required = get_required_providers(config) if provider_name is None else {provider_name}
    
    from core.registry import ProviderRegistry
    for prov_name in required:
        try:
            provider = ProviderRegistry.get(prov_name)
            creds = credentials.get(prov_name, {})
            if creds or prov_name == "aws":  # AWS can use env vars
                provider.initialize_clients(creds, config.digital_twin_name)
                context.providers[prov_name] = provider
        except Exception as e:
            logger.warning(f"Could not initialize {prov_name} provider: {e}")
    
    return context


def set_active_project(project_name: str) -> None:
    """Set the currently active project."""
    global _current_project, _current_context
    
    # Validate project name - reject empty, dots-only, or path traversal
    if not project_name or project_name in (".", ".."):
        raise ValueError("Invalid project name.")
    
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")
    
    target_path = get_upload_path(project_name)
    if not target_path.exists():
        raise ValueError(f"Project '{project_name}' does not exist.")
    
    _current_project = project_name
    _current_context = None  # Lazy initialization


def get_context(provider_name: str = None) -> DeploymentContext:
    """Get the current deployment context, creating if needed."""
    global _current_context
    if _current_context is None:
        _current_context = _create_context(_current_project, provider_name)
    return _current_context


# ==========================================
# Command Helpers
# ==========================================

def help_menu():
    print("""
Available commands:

Deployment commands:
  deploy <provider>           - Deploys core and IoT services for the specified provider (aws, azure, google).
  destroy <provider>          - Destroys core and IoT services for the specified provider.
  recreate_updated_events     - Redeploys the events.

Individual core layer deployments:
  deploy_l1 <provider>        - Deploys core layer 1 services for the specified provider.
  deploy_l2 <provider>        - Deploys core layer 2 services for the specified provider.
  deploy_l3 <provider>        - Deploys core layer 3 services (hot, cold, archive).
  deploy_l4 <provider>        - Deploys core layer 4 services for the specified provider.
  deploy_l5 <provider>        - Deploys core layer 5 services for the specified provider.
  destroy_l1 <provider>       - Destroys core layer 1 services for the specified provider.
  destroy_l2 <provider>       - Destroys core layer 2 services for the specified provider.
  destroy_l3 <provider>       - Destroys core layer 3 services (hot, cold, archive).
  destroy_l4 <provider>       - Destroys core layer 4 services for the specified provider.
  destroy_l5 <provider>       - Destroys core layer 5 services for the specified provider.

Check/Info deployment status:
  check <provider>            - Runs all checks (L1 to L5) for the specified provider.

Individual layer deployment status checks:
  check_l1 <provider>         - Checks Level 1 (IoT Dispatcher Layer) for the specified provider.
  check_l2 <provider>         - Checks Level 2 (Persister & Processor Layer) for the specified provider.
  check_l3 <provider>         - Checks Level 3 (Hot, Cold, Archive) for the specified provider.
  check_l4 <provider>         - Checks Level 4 (TwinMaker) for the specified provider.
  check_l5 <provider>         - Checks Level 5 (Grafana/Visualization) for the specified provider.

Configuration & Info commands:
  info_config                 - Shows main configuration (config.json).
  info_config_iot_devices     - Shows IoT devices configuration.
  info_config_providers       - Shows cloud providers configuration.
  info_config_hierarchy       - Shows hierarchy configuration.
  info_config_events          - Shows event actions configuration.

Lambda management:
  lambda_update <local_function_name> <o:environment>               
                              - Deploys a new version of the specified lambda function.
  lambda_logs <local_function_name> <o:n> <o:filter_system_logs>    
                              - Fetches the last n logged messages of the specified lambda function.
  lambda_invoke <local_function_name> <o:payload> <o:sync>          
                              - Invokes the specified lambda function.

Credential validation:
  check_credentials <provider> - Validates credentials against required permissions for deployment.

Other commands:
  simulate <provider> [project] - Runs the IoT Device Simulator interactively.
  list_projects               - Lists available projects.
  set_project <name>          - Sets the active project.
  help                        - Show this help menu.
  exit                        - Exit the program.
""")


# ==========================================
# Command Handlers
# ==========================================

VALID_PROVIDERS = {"aws", "azure", "google"}


def handle_deploy(provider: str, context: DeploymentContext) -> None:
    """Handle full deployment."""
    deployer.deploy_all(context, provider)
    iot_deployer.deploy(context, provider)
    # Additional deployers
    import aws.additional_deployer_aws as additional
    import aws.event_action_deployer_aws as event_action
    import aws.init_values_deployer_aws as init_values
    
    if provider == "aws":
        aws_provider = context.providers.get("aws")
        if aws_provider:
            additional.create_twinmaker_hierarchy(provider=aws_provider, hierarchy=context.config.hierarchy)
            event_action.deploy_lambda_actions(
                provider=aws_provider, 
                events=context.config.events,
                project_path=str(context.project_path),
                digital_twin_info=context.config.get_digital_twin_info()
            )
            init_values.deploy(provider=aws_provider, iot_devices=context.config.iot_devices)


def handle_destroy(provider: str, context: DeploymentContext) -> None:
    """Handle full destruction."""
    import aws.additional_deployer_aws as additional
    import aws.event_action_deployer_aws as event_action
    
    if provider == "aws":
        aws_provider = context.providers.get("aws")
        if aws_provider:
            event_action.destroy_lambda_actions(provider=aws_provider, events=context.config.events)
            additional.destroy_twinmaker_hierarchy(provider=aws_provider, hierarchy=context.config.hierarchy)
    
    iot_deployer.destroy(context, provider)
    deployer.destroy_all(context, provider)


def handle_info_config(context: DeploymentContext) -> None:
    """Show configuration."""
    print(f"Digital Twin Name: {context.config.digital_twin_name}")
    print(f"Mode: {context.config.mode}")
    print(f"Hot Storage Days: {context.config.hot_storage_size_in_days}")
    print(f"Cold Storage Days: {context.config.cold_storage_size_in_days}")


def handle_lambda_command(command: str, args: list, context: DeploymentContext) -> None:
    """Handle Lambda management commands."""
    import aws.lambda_manager as lambda_manager
    
    aws_provider = context.providers.get("aws")
    if not aws_provider:
        print("Error: AWS provider not initialized.")
        return
    
    if command == "lambda_update":
        if len(args) > 1:
            lambda_manager.update_function(
                args[0], 
                json.loads(args[1]),
                provider=aws_provider,
                project_path=str(context.project_path),
                iot_devices=context.config.iot_devices
            )
        elif len(args) > 0:
            lambda_manager.update_function(
                args[0],
                provider=aws_provider,
                project_path=str(context.project_path),
                iot_devices=context.config.iot_devices
            )
        else:
            print("Usage: lambda_update <local_function_name> <o:environment>")
    
    elif command == "lambda_logs":
        if len(args) > 2:
            print("".join(lambda_manager.fetch_logs(
                args[0], 
                int(args[1]), 
                args[2].lower() in ("true", "1", "yes", "y"),
                provider=aws_provider
            )))
        elif len(args) > 1:
            print("".join(lambda_manager.fetch_logs(args[0], int(args[1]), provider=aws_provider)))
        elif len(args) > 0:
            print("".join(lambda_manager.fetch_logs(args[0], provider=aws_provider)))
        else:
            print("Usage: lambda_logs <local_function_name> <o:n> <o:filter_system_logs>")
    
    elif command == "lambda_invoke":
        if len(args) > 2:
            lambda_manager.invoke_function(
                args[0], 
                json.loads(args[1]), 
                args[2].lower() in ("true", "1", "yes", "y"),
                provider=aws_provider
            )
        elif len(args) > 1:
            lambda_manager.invoke_function(args[0], json.loads(args[1]), provider=aws_provider)
        elif len(args) > 0:
            lambda_manager.invoke_function(args[0], provider=aws_provider)
        else:
            print("Usage: lambda_invoke <local_function_name> <o:payload> <o:sync>")


# ==========================================
# Main Loop
# ==========================================

def main():
    global _current_project, _current_context
    
    logger.info("Welcome to the Digital Twin Manager. Type 'help' for commands.")
    
    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("Goodbye!")
            break
        
        if not user_input:
            continue
        
        parts = user_input.split()
        command = parts[0]
        args = parts[1:]
        
        # Project management commands (no provider needed)
        if command == "list_projects":
            import file_manager
            projects = file_manager.list_projects()
            print(f"Available projects: {projects}")
            print(f"Active project: {_current_project}")
            continue
        
        elif command == "set_project":
            if not args:
                print("Error: Project name required.")
                continue
            try:
                set_active_project(args[0])
                print(f"Active project set to: {_current_project}")
            except ValueError as e:
                print(f"Error: {e}")
            continue
        
        elif command == "create_project":
            if len(args) < 2:
                print("Usage: create_project <zip_path> <project_name>")
                continue
            import file_manager
            try:
                file_manager.create_project_from_zip(args[1], args[0])
                print(f"Project '{args[1]}' created successfully.")
            except Exception as e:
                print(f"Error creating project: {e}")
            continue
        
        # Help and exit
        elif command == "help":
            help_menu()
            continue
        
        elif command == "exit":
            print("Goodbye!")
            break
        
        # Info commands (no provider needed)
        elif command == "info_config":
            try:
                ctx = get_context()
                handle_info_config(ctx)
            except Exception as e:
                print(f"Error: {e}")
            continue
        
        elif command == "info_config_iot_devices":
            ctx = get_context()
            print(json.dumps(ctx.config.iot_devices, indent=2))
            continue
        
        elif command == "info_config_providers":
            ctx = get_context()
            print(json.dumps(ctx.config.providers, indent=2))
            continue
        
        elif command == "info_config_hierarchy":
            ctx = get_context()
            print(json.dumps(ctx.config.hierarchy, indent=2))
            continue
        
        elif command == "info_config_events":
            ctx = get_context()
            print(json.dumps(ctx.config.events, indent=2))
            continue
        
        # Commands that need provider
        deployment_commands = {
            "deploy", "destroy", "recreate_updated_events",
            "deploy_l1", "deploy_l2", "deploy_l3", "deploy_l4", "deploy_l5",
            "destroy_l1", "destroy_l2", "destroy_l3", "destroy_l4", "destroy_l5",
        }
        
        check_commands = {
            "check", "check_l1", "check_l2", "check_l3", "check_l4", "check_l5"
        }
        
        lambda_commands = {"lambda_update", "lambda_logs", "lambda_invoke"}
        
        if command in deployment_commands or command in check_commands:
            if not args:
                print(f"Error: Provider argument required. Valid: {', '.join(VALID_PROVIDERS)}")
                continue
            
            provider = args[0].lower()
            if provider not in VALID_PROVIDERS:
                print(f"Error: Invalid provider '{provider}'. Valid: {', '.join(VALID_PROVIDERS)}")
                continue
            
            try:
                context = get_context(provider)
                logger.info(f"Executing '{command} {provider}' on project '{_current_project}'...")
                
                if command == "deploy":
                    handle_deploy(provider, context)
                elif command == "destroy":
                    handle_destroy(provider, context)
                elif command == "deploy_l1":
                    deployer.deploy_l1(context, provider)
                elif command == "deploy_l2":
                    deployer.deploy_l2(context, provider)
                elif command == "deploy_l3":
                    deployer.deploy_l3(context, provider)
                elif command == "deploy_l4":
                    deployer.deploy_l4(context, provider)
                elif command == "deploy_l5":
                    deployer.deploy_l5(context, provider)
                elif command == "destroy_l1":
                    deployer.destroy_l1(context, provider)
                elif command == "destroy_l2":
                    deployer.destroy_l2(context, provider)
                elif command == "destroy_l3":
                    deployer.destroy_l3(context, provider)
                elif command == "destroy_l4":
                    deployer.destroy_l4(context, provider)
                elif command == "destroy_l5":
                    deployer.destroy_l5(context, provider)
                elif command == "check":
                    import info
                    info.check(provider=provider, config=context.config)
                elif command.startswith("check_l"):
                    import info
                    layer = command.replace("check_l", "")
                    getattr(info, f"check_l{layer}")(provider=provider, config=context.config)
                    
            except Exception as e:
                print_stack_trace()
                logger.error(f"Error during '{command} {provider}': {e}")
            continue
        
        elif command in lambda_commands:
            try:
                context = get_context("aws")
                handle_lambda_command(command, args, context)
            except Exception as e:
                print_stack_trace()
                logger.error(f"Error during '{command}': {e}")
            continue
        
        elif command == "simulate":
            if not args:
                print("Usage: simulate <provider> [project_name]")
                continue
            
            provider = args[0].lower()
            project_name = args[1] if len(args) > 1 else _current_project
            
            if provider != "aws":
                print(f"Error: Provider '{provider}' not supported yet. Only 'aws'.")
                continue
            
            config_path = f"upload/{project_name}/iot_device_simulator/{provider}/config_generated.json"
            payload_path = f"upload/{project_name}/iot_device_simulator/{provider}/payloads.json"
            
            if not os.path.exists(config_path):
                print(f"Error: Simulator config not found at '{config_path}'. Please deploy L1 first.")
                continue
            if not os.path.exists(payload_path):
                print(f"Error: Payloads file not found at '{payload_path}'.")
                continue
            
            import subprocess
            sim_script = f"src/iot_device_simulator/{provider}/main.py"
            try:
                logger.info(f"Starting simulator for {provider} on {project_name}...")
                subprocess.call([sys.executable, sim_script, "--project", project_name])
            except KeyboardInterrupt:
                print("\nSimulator stopped.")
            except Exception as e:
                print(f"Error running simulator: {e}")
            continue
        
        elif command == "check_credentials":
            if not args:
                print("Usage: check_credentials <provider>")
                continue
            
            provider = args[0].lower()
            if provider != "aws":
                print(f"Error: Provider '{provider}' not supported yet. Only 'aws'.")
                continue
            
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
            from credentials_checker import check_aws_credentials_from_config
            
            logger.info(f"Checking AWS credentials for project '{_current_project}'...")
            result = check_aws_credentials_from_config(_current_project)
            
            print(f"\n{'='*60}")
            print(f"Status: {result['status'].upper()}")
            print(f"Message: {result['message']}")
            print(f"{'='*60}")
            
            if result.get('caller_identity'):
                print(f"\nCaller Identity:")
                print(f"  Account: {result['caller_identity']['account']}")
                print(f"  ARN: {result['caller_identity']['arn']}")
            
            if result.get('summary', {}).get('total_required', 0) > 0:
                summary = result['summary']
                print(f"\nSummary:")
                print(f"  Total Required: {summary['total_required']}")
                print(f"  ✅ Valid: {summary['valid']}")
                print(f"  ❌ Missing: {summary['missing']}")
            print()
            continue
        
        else:
            print(f"Unknown command: {command}. Type 'help' for a list of commands.")


if __name__ == "__main__":
    main()
