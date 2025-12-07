import json
import globals
import constants as CONSTANTS
import aws.globals_aws as globals_aws
import aws.lambda_manager as lambda_manager
import deployers.core_deployer as core_deployer
import deployers.iot_deployer as iot_deployer
import info
import deployers.additional_deployer as hierarchy_deployer
import deployers.event_action_deployer as event_action_deployer
import deployers.init_values_deployer as init_values_deployer

from logger import logger, print_stack_trace

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
  info_config_credentials     - Shows credentials configuration.
  info_config_hierarchy       - Shows provider configuration for layers.
  info_config_events          - Shows event actions configuration.

Lambda management:
  lambda_update <local_function_name> <o:environment>               
                              - Deploys a new version of the specified lambda function.
  lambda_logs <local_function_name> <o:n> <o:filter_system_logs>    
                              - Fetches the last n logged messages of the specified lambda function.
  lambda_invoke <local_function_name> <o:payload> <o:sync>          
                              - Invokes the specified lambda function.

Other commands:
  simulate <provider> [project] - Runs the IoT Device Simulator interactively.
  help                        - Show this help menu.
  exit                        - Exit the program.
""")
    

deployment_commands = {
    "deploy": lambda provider: (
        core_deployer.deploy(provider=provider), 
        iot_deployer.deploy(provider=provider),
        hierarchy_deployer.deploy(provider=provider),
        event_action_deployer.deploy(provider=provider),
        init_values_deployer.deploy(provider=provider)
      ),
    "destroy": lambda provider: (
        init_values_deployer.destroy(provider=provider),
        event_action_deployer.destroy(provider=provider),
        hierarchy_deployer.destroy(provider=provider),
        iot_deployer.destroy(provider=provider), 
        core_deployer.destroy(provider=provider)
      ),
    "recreate_updated_events": lambda provider: (
        event_action_deployer.redeploy(provider=provider),
        core_deployer.redeploy_l2_event_checker(provider=provider)
      ),
    
    # Individual layer deploys
    "deploy_l1": lambda provider: core_deployer.deploy_l1(provider=provider),
    "deploy_l2": lambda provider: core_deployer.deploy_l2(provider=provider),
    "deploy_l3": lambda provider: core_deployer.deploy_l3(provider=provider),
    "deploy_l4": lambda provider: core_deployer.deploy_l4(provider=provider),
    "deploy_l5": lambda provider: core_deployer.deploy_l5(provider=provider),

    "destroy_l1": lambda provider: core_deployer.destroy_l1(provider=provider),
    "destroy_l2": lambda provider: core_deployer.destroy_l2(provider=provider),
    "destroy_l3": lambda provider: core_deployer.destroy_l3(provider=provider),
    "destroy_l4": lambda provider: core_deployer.destroy_l4(provider=provider),
    "destroy_l5": lambda provider: core_deployer.destroy_l5(provider=provider),
}

info_commands = {
    "check": lambda provider: (
      info.check(provider=provider),
      hierarchy_deployer.info(provider=provider),
      event_action_deployer.info(provider=provider),
      init_values_deployer.info(provider=provider)
    ),

    # Individual layer checks
    "check_l1": lambda provider: info.check_l1(provider=provider),
    "check_l2": lambda provider: info.check_l2(provider=provider),
    "check_l3": lambda provider: info.check_l3(provider=provider),
    "check_l4": lambda provider: info.check_l4(provider=provider),
    "check_l5": lambda provider: info.check_l5(provider=provider),
}    
    
    
VALID_PROVIDERS = {"aws", "azure", "google"}
    
def main():
    globals.initialize_all()
    globals_aws.initialize_aws_clients()
    
    valid_providers = ("aws", "azure", "google")
    
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

      # Project Management Commands
      if command == "list_projects":
        import file_manager
        projects = file_manager.list_projects()
        print(f"Available projects: {projects}")
        print(f"Active project: {globals.CURRENT_PROJECT}")
        continue
      
      elif command == "set_project":
        if not args:
            print("Error: Project name required.")
            continue
        try:
            globals.set_active_project(args[0])
            print(f"Active project set to: {globals.CURRENT_PROJECT}")
        except ValueError as e:
            print(f"Error: {e}")
        continue

      elif command == "create_project":
          if len(args) < 2:
              print("Usage: create_project <zip_path> <project_name>")
              continue
          zip_path = args[0]
          project_name = args[1]
          import file_manager
          try:
              file_manager.create_project_from_zip(project_name, zip_path)
              print(f"Project '{project_name}' created successfully.")
          except Exception as e:
              print(f"Error creating project: {e}")
          continue

      # Common argument parsing for provider and project
      provider = None
      project = CONSTANTS.DEFAULT_PROJECT_NAME
      
      # Helper to parse [provider] [project] arguments
      # Strategy: first arg is provider (if valid), second is project
      # Or via named flags if we wanted, but sticking to positional for compatibility if possible,
      # but adding project makes it tricky.
      # Let's use simple logic:
      # If command in deployment_commands or info_commands:
      # args[0] = provider
      # args[1] = project (optional, default="template")
      
      if command in deployment_commands or command in info_commands:
          if not args:
              print(f"Error: Provider argument required for '{command}'. Valid: {', '.join(valid_providers)}")
              continue
          
          provider = args[0].lower()
          if provider not in VALID_PROVIDERS:
               print(f"Error: invalid provider '{provider}'. Valid: {', '.join(VALID_PROVIDERS)}")
               continue
          
          # Check for optional project argument
          if len(args) > 1:
              project = args[1]
          
          # SAFETY CHECK
          if project != globals.CURRENT_PROJECT:
              logger.error(f"SAFETY ERROR: Requested project '{project}' does not match active project '{globals.CURRENT_PROJECT}'.")
              logger.error(f"Please switch to '{project}' using 'set_project {project}' before executing this command.")
              continue

      # deployment commands
      if command in deployment_commands:
            try:
                logger.info(f"Executing '{command} {provider}' on project '{project}'...")
                deployment_commands[command](provider=provider)
            except Exception as e:
                print_stack_trace()
                logger.error(f"Error during '{command} {provider}': {e}")
            continue
          
      # info commands
      elif command in info_commands:
        try:
            logger.info(f"Executing '{command} {provider}' on project '{project}'...")
            info_commands[command](provider=provider)
        except Exception as e:
            print_stack_trace()
            logger.error(f"Error during '{command} {provider}': {str(e)}")
        continue

      # other commands
      # Lambda commands also need safety check? User didn't explicitly ask for CLI lambda safety but API.
      # But good to be consistent. Lambda commands take local_function_name.
      # If we add project param it breaks signature.
      # For now, let's assume lambda commands operate on active project context implicitly, 
      # but since they don't take a project arg, we can't cross-check.
      # We just trust CURRENT_PROJECT is what the user wants. 
      # EXCEPT if we want to force user to be aware.
      # "Safety check" implies verifying user INTENT vs STATE.
      # If user just types `lambda_update foo`, they imply "current state".
      # If user types `deploy aws other_project`, they imply "other_project".
      # So for lambda commands, we warn if they are ambiguous? No, just let them run on CURRENT_PROJECT.
      
      elif command in ("lambda_update", "lambda_logs", "lambda_invoke"):
          # Safety Check Logic for Lambda Commands
          # Check if the last argument is a valid project name
          # If so, validate it against CURRENT_PROJECT and remove it from args
          projects = []
          try:
              import file_manager
              projects = file_manager.list_projects()
          except ImportError:
              logger.warning("Could not import file_manager for project validation.")
          
          # We only consider the last arg a project if we have enough args
          # lambda_update needs at least 1 arg (name) -> if 2 provided, 2nd could be env (json) OR project.
          # lambda_invoke needs at least 1 arg (name) -> if 2 provided, 2nd could be payload OR project.
          # This ambiguity is solved by checking if the value is in the known projects list.
          # But what if a project is named "{}"? Project names are folders, usually safe.
          
          target_project = None
          
          if args and projects and args[-1] in projects:
               target_project = args[-1]
               args = args[:-1]
               
          if target_project and target_project != globals.CURRENT_PROJECT:
               logger.error(f"SAFETY ERROR: Requested project '{target_project}' does not match active project '{globals.CURRENT_PROJECT}'.")
               logger.error(f"Please switch to '{target_project}' using 'set_project {target_project}' before executing this command.")
               continue

          if command == "lambda_update":
            if len(args) > 1:
              lambda_manager.update_function(args[0], json.loads(args[1]))
            elif len(args) > 0:
              lambda_manager.update_function(args[0])
            else:
                print("Usage: lambda_update <local_function_name> <o:environment> [project_name]")

          elif command == "lambda_logs":
            if len(args) > 2:
              print("".join(lambda_manager.fetch_logs(args[0], int(args[1]), args[2].lower() in ("true", "1", "yes", "y"))))
            elif len(args) > 1:
              print("".join(lambda_manager.fetch_logs(args[0], int(args[1]))))
            elif len(args) > 0:
              print("".join(lambda_manager.fetch_logs(args[0])))
            else:
                print("Usage: lambda_logs <local_function_name> <o:n> <o:filter_system_logs> [project_name]")

          elif command == "lambda_invoke":
            if len(args) > 2:
              lambda_manager.invoke_function(args[0], json.loads(args[1]), args[2].lower() in ("true", "1", "yes", "y"))
            elif len(args) > 1:
              lambda_manager.invoke_function(args[0], json.loads(args[1]))
            elif len(args) > 0:
              lambda_manager.invoke_function(args[0])
            else:
                 print("Usage: lambda_invoke <local_function_name> <o:payload> <o:sync> [project_name]")

      elif command == "simulate":
          if not args:
              print("Usage: simulate <provider> [project_name]")
              continue
          
          provider = args[0].lower()
          project_name = args[1] if len(args) > 1 else globals.CURRENT_PROJECT
          
          if project_name != globals.CURRENT_PROJECT:
               logger.error(f"SAFETY ERROR: Requested project '{project_name}' does not match active project '{globals.CURRENT_PROJECT}'.")
               logger.error(f"Please switch to '{project_name}' using 'set_project {project_name}'.")
               continue

          if provider != "aws":
              print(f"Error: Provider '{provider}' not supported yet. Only 'aws'.")
              continue

          import os
          import util
          # Pre-flight checks
          # Path logic: currently running from project root
          config_path = f"upload/{project_name}/iot_device_simulator/{provider}/config_generated.json"
          payload_path = f"upload/{project_name}/iot_device_simulator/{provider}/payloads.json"
          
          if not os.path.exists(config_path):
              print(f"Error: Simulator config not found at '{config_path}'. Please deploy L1 first.")
              continue
          if not os.path.exists(payload_path):
              print(f"Error: Payloads file not found at '{payload_path}'. Please ensure it exists.")
              continue
          
          # Run
          import subprocess
          import sys
          sim_script = f"src/iot_device_simulator/{provider}/main.py"
          try:
              logger.info(f"Starting simulator for {provider} on {project_name}...")
              subprocess.call([sys.executable, sim_script, "--project", project_name])
          except KeyboardInterrupt:
              print("\nSimulator stopped.")
          except Exception as e:
              print(f"Error running simulator: {e}")

      elif command == "help":
        help_menu()
      elif command == "exit":
        print("Goodbye!")
        break
      else:
        print(f"Unknown command: {command}. Type 'help' for a list of commands.")

if __name__ == "__main__":
  main()
