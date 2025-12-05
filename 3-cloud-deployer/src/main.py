import json
import globals
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


      # deployment commands
      if command in deployment_commands:
            if not args:
                valid_providers = VALID_PROVIDERS.copy()
                logger.error(
                    f"Error:\n"
                    f"   provider argument required for '{command}'.\n"
                    f"   Valid arguments are: '{', '.join(valid_providers)}'\n"
                    f"   Example: '{command} {valid_providers.pop()}'"
                )
                continue

            provider = args[0].lower()
            if provider not in VALID_PROVIDERS:
                logger.error(f"Error: invalid provider '{provider}'. Valid providers: {', '.join(VALID_PROVIDERS)}")
                continue

            try:
                logger.info(f"Executing '{command} {provider}'...")
                deployment_commands[command](provider=provider)
            except Exception as e:
                print_stack_trace()
                logger.error(f"Error during '{command} {provider}': {e}")
            continue
          
      # info commands
      elif command in info_commands:
        if not args:
            valid_providers = VALID_PROVIDERS.copy()
            logger.error(
                f"Error:\n"
                f"   provider argument required for '{command}'.\n"
                f"   Valid arguments are: '{', '.join(valid_providers)}'\n"
                f"   Example: '{command} {valid_providers.pop()}'"
            )
            continue

        provider = args[0].lower()
        if provider not in VALID_PROVIDERS:
            logger.error(f"Error: invalid provider '{provider}'. Valid providers: {', '.join(VALID_PROVIDERS)}")
            continue

        try:
            logger.info(f"Executing '{command} {provider}'...")
            info_commands[command](provider=provider)
        except Exception as e:
            print_stack_trace()
            logger.error(f"Error during '{command} {provider}': {str(e)}")
        continue

      # other commands
      elif command == "lambda_update":
        if len(args) > 1:
          lambda_manager.update_function(args[0], json.loads(args[1]))
        else:
          lambda_manager.update_function(args[0])
      elif command == "lambda_logs":
        if len(args) > 2:
          print("".join(lambda_manager.fetch_logs(args[0], int(args[1]), args[2].lower() in ("true", "1", "yes", "y"))))
        elif len(args) > 1:
          print("".join(lambda_manager.fetch_logs(args[0], int(args[1]))))
        else:
          print("".join(lambda_manager.fetch_logs(args[0])))
      elif command == "lambda_invoke":
        if len(args) > 2:
          lambda_manager.invoke_function(args[0], json.loads(args[1]), args[2].lower() in ("true", "1", "yes", "y"))
        elif len(args) > 1:
          lambda_manager.invoke_function(args[0], json.loads(args[1]))
        else:
          lambda_manager.invoke_function(args[0])

      elif command == "help":
        help_menu()
      elif command == "exit":
        print("Goodbye!")
        break
      else:
        print(f"Unknown command: {command}. Type 'help' for a list of commands.")

if __name__ == "__main__":
  main()
