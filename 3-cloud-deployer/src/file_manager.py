import os
import zipfile
import json
import shutil
import globals
import constants as CONSTANTS
from logger import logger

import io

import ast

def validate_config_content(filename, content):
    """
    Validates the content of a configuration file against defined schemas.
    """
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON content for {filename}: {e}")
    
    # 1. Schema Key Validation
    if filename in CONSTANTS.CONFIG_SCHEMAS:
        required_keys = CONSTANTS.CONFIG_SCHEMAS[filename]
        
        # Special Case: Credentials (dynamic keys based on provider)
        if filename == CONSTANTS.CONFIG_CREDENTIALS_FILE:
            for provider, keys in CONSTANTS.REQUIRED_CREDENTIALS_FIELDS.items():
                if provider in content:
                    for key in keys:
                        if key not in content[provider]:
                            raise ValueError(f"Missing required credential field '{key}' for provider '{provider}' in {filename}.")
        
        # General Case: List of objects (IOT, EVENTS, HIERARCHY)
        elif isinstance(content, list):
             if not isinstance(required_keys, list):
                 pass # Should not happen based on constant definition
             
             for index, item in enumerate(content):
                 for key in required_keys:
                     if key not in item:
                         raise ValueError(f"Missing key '{key}' in {filename} at index {index}.")
                 
                 # Nested Checks for specific files
                 if filename == CONSTANTS.CONFIG_EVENTS_FILE:
                     # Check action structure
                     if "action" in item:
                         action = item["action"]
                         if "type" not in action or "functionName" not in action:
                             raise ValueError(f"Event action at index {index} missing 'type' or 'functionName'.")
                         
                         if action["type"] == "lambda" and "feedback" in action:
                             feedback = action["feedback"]
                             if "iotDeviceId" not in feedback or "payload" not in feedback:
                                 raise ValueError(f"Event feedback at index {index} missing 'iotDeviceId' or 'payload'.")

                 elif filename == CONSTANTS.CONFIG_HIERARCHY_FILE:
                     # Check component requirements
                     if item.get("type") == "component":
                         if "componentTypeId" not in item and "iotDeviceId" not in item:
                             raise ValueError(f"Component at index {index} ('{item.get('name')}') must have either 'componentTypeId' or 'iotDeviceId'.")
        
        # General Case: Single Object (CONFIG, OPTIMIZATION)
        elif isinstance(content, dict):
             for key in required_keys:
                 if key not in content:
                     raise ValueError(f"Missing key '{key}' in {filename}.")

def validate_project_zip(zip_source):
    """
    Validates that a zip file contains all required configuration files 
    AND validates their content against defined schemas.
    
    Args:
        zip_source (str | BytesIO): Path to the zip file or a file-like object.
        
    Raises:
        ValueError: If required files are missing, if file paths are malicious (Zip Slip),
                    or if any configuration file has invalid content/schema.
    """
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)

    with zipfile.ZipFile(zip_source, 'r') as zf:
        file_list = zf.namelist()
        
        # 1. Check for Missing Required Files (Basic Check)
        zip_files = zf.namelist()
        
        # Identify project root prefix if any (e.g. project_folder/config.json)
        project_root = ""
        for f in zip_files:
            if f.endswith(CONSTANTS.CONFIG_FILE):
                project_root = f.replace(CONSTANTS.CONFIG_FILE, "")
                break
        
        for required_file in CONSTANTS.REQUIRED_CONFIG_FILES:
            expected_path = project_root + required_file
            if expected_path not in zip_files:
                 raise ValueError(f"Missing required configuration file in zip: {required_file}")

        # Capture configs for dependency check
        opt_config = {}
        prov_config = {}
        events_config = []
        
        # Track existence of code directories
        seen_event_actions = set()
        seen_state_machines = set()
        seen_feedback_func = False

        for member in zf.infolist():
            # Skip directories themselves
            if member.is_dir():
                continue
                
            # 2. Zip Slip Prevention
            if ".." in member.filename or os.path.isabs(member.filename):
                 raise ValueError("Malicious file path detected in zip (Zip Slip Prevention).")

            filename = member.filename
            
            # 3. Validate Content + Capture Configs
            basename = os.path.basename(filename)
            
            if basename in CONSTANTS.CONFIG_SCHEMAS:
                try:
                    with zf.open(member) as f:
                        content = f.read().decode('utf-8')
                        validate_config_content(basename, content)
                        
                        # Capture for Logic Check
                        if basename == CONSTANTS.CONFIG_OPTIMIZATION_FILE:
                            opt_config = json.loads(content)
                        elif basename == CONSTANTS.CONFIG_PROVIDERS_FILE:
                            prov_config = json.loads(content)
                        elif basename == CONSTANTS.CONFIG_EVENTS_FILE:
                             events_config = json.loads(content)
                             
                except Exception as e:
                     raise ValueError(f"Validation failed for {basename} inside zip: {e}")

            # 4. State Machine Content Validation
            if basename in CONSTANTS.STATE_MACHINE_SIGNATURES:
                 try:
                    with zf.open(member) as f:
                        content = f.read().decode('utf-8')
                        validate_state_machine_content(basename, content)
                        seen_state_machines.add(basename)
                 except Exception as e:
                     raise ValueError(f"State Machine validation failed for {basename} inside zip: {e}")
            
            # Track Directories (using file paths)
            # Check for event-feedback
            if f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/event-feedback/" in filename:
                seen_feedback_func = True
            
            # Check for event actions
            if f"{CONSTANTS.EVENT_ACTIONS_DIR_NAME}/" in filename:
                # Extract function name: .../event_actions/<func_name>/...
                parts = filename.split(f"{CONSTANTS.EVENT_ACTIONS_DIR_NAME}/")
                if len(parts) > 1:
                    sub = parts[1]
                    func_name = sub.split('/')[0]
                    if func_name:
                        seen_event_actions.add(func_name)


        # 5. Dependency Validation (Optimization Flags)
        optimization = opt_config.get("result", {}).get("optimization", {})
        
        if optimization.get("useEventChecking", False):
            # Check Event Actions
            for event in events_config:
                 action = event.get("action", {})
                 if action.get("type") == "lambda":
                     func_name = action.get("functionName")
                     if func_name and func_name not in seen_event_actions:
                         raise ValueError(f"Missing code for event action in zip: {func_name}")
                         
        if optimization.get("returnFeedbackToDevice", False):
            if not seen_feedback_func:
                 raise ValueError("Missing event-feedback function in zip (required by returnFeedbackToDevice).")
                 
        if optimization.get("triggerNotificationWorkflow", False):
             # Determine Expected Provider
             # Default to AWS if not specified or config missing
             provider = prov_config.get("layer_2_provider", "aws").lower()
             
             target_file = CONSTANTS.AWS_STATE_MACHINE_FILE
             if provider == "azure":
                 target_file = CONSTANTS.AZURE_STATE_MACHINE_FILE
             elif provider == "google":
                 target_file = CONSTANTS.GOOGLE_STATE_MACHINE_FILE
                 
             if target_file not in seen_state_machines:
                  raise ValueError(f"Missing state machine definition '{target_file}' in zip for provider '{provider}' (required by triggerNotificationWorkflow).")

def create_project_from_zip(project_name, zip_source):
    """
    Creates a new project from a validated zip file.
    
    Args:
        project_name (str): Name of the project to create.
        zip_source (str | BytesIO): Zip file source.
        
    Raises:
        ValueError: If project name is invalid, project already exists, or zip is invalid.
    """
    # Simple validation using os.path to prevent directory traversal
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")
    
    # If bytes, convert to BytesIO for multiple reads (validate + extract)
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)

    # Validate before extraction (Universal Validation)
    validate_project_zip(zip_source)
    
    target_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    if os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' already exists.")
        
    os.makedirs(target_dir)
    
    # Extract only after validation passed
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)
        
    logger.info(f"Created project '{project_name}' from zip.")

def update_project_from_zip(project_name, zip_source):
    """
    Updates an existing project from a zip file (Overwrites existing files).
    
    Args:
        project_name (str): Name of the project to update.
        zip_source (str | BytesIO): Zip file source.
        
    Raises:
        ValueError: If project name is invalid or zip is invalid.
    """
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")
    
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)
        
    # Validate entire zip content first (Universal Validation)
    validate_project_zip(zip_source)
        
    target_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    
    # Ensure project directory exists, create if not (auto-create behavior for update?) 
    # Usually update implies existence, but let's be robust.
    if not os.path.exists(target_dir):
         os.makedirs(target_dir)

    # Extract and Overwrite
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)
        
    logger.info(f"Updated project '{project_name}' from zip.")

def list_projects():
    """
    Returns a list of available project names.
    """
    upload_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME)
    projects = []
    if os.path.exists(upload_dir):
        for item in os.listdir(upload_dir):
            if os.path.isdir(os.path.join(upload_dir, item)):
                projects.append(item)
    return projects

def update_config_file(project_name, config_filename, config_content):
    """
    Updates a specific configuration file for a project.
    Hot-reloads if the project is currently active.
    """
    safe_name = os.path.basename(project_name)
    target_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    
    if not os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' does not exist.")
        
    target_file = os.path.join(target_dir, config_filename)
    
    # Verify content is valid JSON
    if isinstance(config_content, str):
        try:
             json_content = json.loads(config_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON content for {config_filename}: {e}")
    else:
        json_content = config_content

    # Validate Schema
    validate_config_content(config_filename, json_content)

    with open(target_file, 'w') as f:
        json.dump(json_content, f, indent=2)
        
    logger.info(f"Updated {config_filename} for project '{project_name}'.")
    
    # Hot Reload
    if project_name == globals.CURRENT_PROJECT:
        logger.info(f"Hot-reloading configuration for active project '{project_name}'...")
        if config_filename == CONSTANTS.CONFIG_FILE:
            globals.initialize_config()
        elif config_filename == CONSTANTS.CONFIG_IOT_DEVICES_FILE:
            globals.initialize_config_iot_devices()
        elif config_filename == CONSTANTS.CONFIG_EVENTS_FILE:
            globals.initialize_config_events()
        elif config_filename == CONSTANTS.CONFIG_HIERARCHY_FILE:
            globals.initialize_config_hierarchy()
        elif config_filename == CONSTANTS.CONFIG_CREDENTIALS_FILE:
            globals.initialize_config_credentials()
        elif config_filename == CONSTANTS.CONFIG_PROVIDERS_FILE:
            globals.initialize_config_providers()
# Provider-Specific Code Validators

def validate_state_machine_content(filename, content):
    """
    Validates that the state machine file content matches the expected provider format.
    """
    # 1. Parse JSON
    if isinstance(content, str):
        try:
            json_content = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON content for {filename}: {e}")
    else:
        json_content = content

    # 2. Check Signature
    if filename in CONSTANTS.STATE_MACHINE_SIGNATURES:
        required_keys = CONSTANTS.STATE_MACHINE_SIGNATURES[filename]
        # Check if root keys exist (top-level check)
        # For Azure, schema is inside definition, so we might need recursive check?
        # Let's keep it simple: Top level checks.
        
        # Azure special handling: check keys inside 'definition' if present?
        # Signatures defined in CONSTANTS:
        # AWS: ["StartAt", "States"] -> Top level
        # Azure: ["definition"] -> Top level. "$schema" is inside definition usually?
        # Wait, Azure sample has "definition" at root.
        
        # Google: ["main"] -> Top level.
        
        missing_keys = [k for k in required_keys if k not in json_content]
        
        # Special handling for Azure because $schema is sometimes inside definition
        if filename == CONSTANTS.AZURE_STATE_MACHINE_FILE:
             if "definition" in json_content:
                 # Check if schema is inside definition
                 if "$schema" in required_keys: # If we required it
                     # But $schema might be loosely checked.
                     # Let's trust "definition" presence as strong enough signal for now VS AWS/Google.
                     pass
        
        if missing_keys:
             # Refined check for Azure if we really want to check inside definition
             if filename == CONSTANTS.AZURE_STATE_MACHINE_FILE and "definition" in json_content:
                 pass # Accept it if definition is there
             else:
                 raise ValueError(f"Invalid State Machine format for {filename}. Missing required keys: {missing_keys}")

def verify_project_structure(project_name):
    """
    Verifies that the project structure is valid and consistent with its configuration.
    Enforces strict dependency checks for optimization flags.
    """
    upload_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name)
    
    if not os.path.exists(upload_dir):
        raise ValueError(f"Project '{project_name}' does not exist.")

    # 1. Basic Config Verification
    for config_file in CONSTANTS.REQUIRED_CONFIG_FILES:
        file_path = os.path.join(upload_dir, config_file)
        if not os.path.exists(file_path):
             raise ValueError(f"Missing required configuration file: {config_file}")
             
        # Validate Content
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                validate_config_content(config_file, content)
        except Exception as e:
            raise ValueError(f"Invalid content in {config_file}: {e}")

    # 2. Optimization Dependency Checks
    opt_file = os.path.join(upload_dir, CONSTANTS.CONFIG_OPTIMIZATION_FILE)
    try:
        with open(opt_file, 'r') as f:
            opt_config = json.load(f)
    except Exception:
        # Should be caught by basic verification above, but safe fallback
        opt_config = {}

    optimization = opt_config.get("result", {}).get("optimization", {})
    
    # Check Event Checking Dependencies
    if optimization.get("useEventChecking", False):
        # A. Verify Config Events Exists (Already checked by REQUIRED_CONFIG_FILES, but logic holds)
        events_file = os.path.join(upload_dir, CONSTANTS.CONFIG_EVENTS_FILE)
        try:
             with open(events_file, 'r') as f:
                 events_config = json.load(f)
        except Exception:
             events_config = []

        # B. Verify Event Actions Code
        for event in events_config:
            action = event.get("action", {})
            if action.get("type") == "lambda":
                func_name = action.get("functionName")
                if not func_name:
                    continue # Should be caught by schema validation
                
                # Check existences of upload/{project}/event_actions/{func_name}
                action_dir = os.path.join(upload_dir, CONSTANTS.EVENT_ACTIONS_DIR_NAME, func_name)
                if not os.path.exists(action_dir):
                    raise ValueError(f"Missing code for event action: {func_name}. Expected directory: {CONSTANTS.EVENT_ACTIONS_DIR_NAME}/{func_name}")

        # C. Verify Feedback Function
        if optimization.get("returnFeedbackToDevice", False):
            feedback_dir = os.path.join(upload_dir, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "event-feedback")
            if not os.path.exists(feedback_dir):
                raise ValueError("Missing event-feedback function. Required when 'returnFeedbackToDevice' is true. Expected directory: lambda_functions/event-feedback")

        # D. Verify Workflow Definition
        if optimization.get("triggerNotificationWorkflow", False):
             # Determine provider to expect specific file
             # Try to read providers config
             providers_file = os.path.join(upload_dir, CONSTANTS.CONFIG_PROVIDERS_FILE)
             provider = "aws" # Default
             if os.path.exists(providers_file):
                 try:
                     with open(providers_file, 'r') as f:
                         prov_config = json.load(f)
                         # Layer 2 is usually where event logic lives
                         provider = prov_config.get("layer_2_provider", "aws").lower() 
                 except:
                     pass
            
             target_file = CONSTANTS.AWS_STATE_MACHINE_FILE
             if provider == "azure":
                 target_file = CONSTANTS.AZURE_STATE_MACHINE_FILE
             elif provider == "google":
                 target_file = CONSTANTS.GOOGLE_STATE_MACHINE_FILE
                 
             state_machine_path = os.path.join(upload_dir, CONSTANTS.STATE_MACHINES_DIR_NAME, target_file)
             
             if not os.path.exists(state_machine_path):
                 raise ValueError(f"Missing state machine definition for provider '{provider}'. Expected file: {CONSTANTS.STATE_MACHINES_DIR_NAME}/{target_file}")

             # VALIDATE CONTENT (New Step)
             try:
                 with open(state_machine_path, 'r') as f:
                     sm_content = f.read()
                     validate_state_machine_content(target_file, sm_content)
             except Exception as e:
                 raise ValueError(f"Invalid state machine content for '{provider}': {e}")

    logger.info(f"Project structure verified for '{project_name}'.")




def validate_python_code_aws(code_content):
    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        raise ValueError(f"Python Syntax Error at line {e.lineno}: {e.msg}")

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "lambda_handler":
            # Check args: event, context
            args = [arg.arg for arg in node.args.args]
            if len(args) >= 2 and args[0] == "event" and args[1] == "context":
                return # Valid
    
    raise ValueError("AWS Lambda function must have a 'lambda_handler(event, context)' function.")

def validate_python_code_azure(code_content):
    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        raise ValueError(f"Python Syntax Error at line {e.lineno}: {e.msg}")

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
             # Basic signature check for Azure Functions
             # def main(req: func.HttpRequest) -> func.HttpResponse:
             # Just checking name 'main' and first arg 'req' for now as minimal validation
             args = [arg.arg for arg in node.args.args]
             if len(args) >= 1 and args[0] == "req":
                 return # Valid
    
    raise ValueError("Azure Function must have a 'main(req)' entry point.")

def validate_python_code_google(code_content):
    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        raise ValueError(f"Python Syntax Error at line {e.lineno}: {e.msg}")
    
    # Google functions often use 'main' or a custom entry point, but 'main' is standard for HTTP
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
             return # Has at least one function, simplified for GCP flexibility
    
    raise ValueError("Google Cloud Function must define at least one function.")

def get_provider_for_function(project_name, function_name):
    """
    Determines the cloud provider for a specific function based on the project configuration.
    """
    upload_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name)
    providers_file = os.path.join(upload_dir, CONSTANTS.CONFIG_PROVIDERS_FILE)
    
    if not os.path.exists(providers_file):
        raise ValueError("Missing Project Configuration: config_providers.json must be uploaded before validating function code.")
        
    try:
        with open(providers_file, 'r') as f:
            config_providers = json.load(f)
    except json.JSONDecodeError:
        raise ValueError("Project configuration is corrupted. Please re-upload config_providers.json.")
        
    # logic to map function_name to layer
    # 1. Direct Mapping
    layer_key = CONSTANTS.FUNCTION_LAYER_MAPPING.get(function_name)
    
    # 2. Implicit Mapping (Processors)
    if not layer_key and function_name.endswith("-processor"):
        layer_key = "layer_2_provider"
        
    if not layer_key:
         # Fallback or error? For now assume L2 if unknown or strict error?
         # Guide implies strict mapping.
         logger.warning(f"Unknown function '{function_name}', defaulting to Layer 2 provider.")
         layer_key = "layer_2_provider"

    provider = config_providers.get(layer_key)
    if not provider:
         raise ValueError(f"Provider configuration missing for layer '{layer_key}'.")
         
    return provider.lower()

def update_function_code_file(project_name, function_name, file_name, code_content):
    """
    Updates the code file for a specific function, with provider-specific validation.
    target_filename is enforced by caller (rest_api) or file_name here to be 'lambda_function.py' typically.
    """
    safe_project_name = os.path.basename(project_name)
    target_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_project_name, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, function_name)
    
    if not os.path.exists(target_dir):
        # Allow creating directory if it doesn't exist? Usually project structure is created by zip.
        # But for 'upload function code', maybe we strictly require directory existence.
        # Let's try to create it if it's a valid function structure, but safer to fail if project structure is broken.
        raise ValueError(f"Function directory '{function_name}' does not exist in project '{project_name}'.")

    # Validate Python Code
    if file_name.endswith(".py"):
        provider = get_provider_for_function(project_name, function_name)
        if provider == "aws":
            validate_python_code_aws(code_content)
        elif provider == "azure":
            validate_python_code_azure(code_content)
        elif provider == "google":
            validate_python_code_google(code_content)
            
    # Write File
    target_file = os.path.join(target_dir, file_name)
    with open(target_file, 'w') as f:
        f.write(code_content)
        
    logger.info(f"Updated function code '{file_name}' for function '{function_name}' in project '{project_name}'.")
