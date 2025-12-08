"""
Validator - Configuration and Structure Validation.

This module provides comprehensive validation for configuration files,
state machines, zip archives, Python code, and project structure.

Migration Status:
    - Uses globals for project path resolution in some functions.
    - Future migration: Add optional project_path parameters.
    - Works correctly as-is - no immediate migration required.
"""

import os
import zipfile
import json
import globals
import constants as CONSTANTS
from logger import logger
import io
import ast

# ==========================================
# 1. Configuration Content Validation
# ==========================================
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
             
             # Special Case: Inter-Cloud Configuration
             if filename == CONSTANTS.CONFIG_INTER_CLOUD_FILE:
                 connections = content.get("connections", {})
                 if not isinstance(connections, dict):
                     raise ValueError("'connections' must be a dictionary.")
                 
                 for conn_id, details in connections.items():
                     if not all(k in details for k in ["provider", "token", "url"]):
                         raise ValueError(f"Connection '{conn_id}' missing required fields: provider, token, url")

# ==========================================
# 2. State Machine Validation
# ==========================================
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
        missing_keys = [k for k in required_keys if k not in json_content]
        
        # Special handling for Azure because $schema is sometimes inside definition
        if filename == CONSTANTS.AZURE_STATE_MACHINE_FILE:
             if "definition" in json_content:
                 pass
        
        if missing_keys:
             if filename == CONSTANTS.AZURE_STATE_MACHINE_FILE and "definition" in json_content:
                 pass 
             else:
                 raise ValueError(f"Invalid State Machine format for {filename}. Missing required keys: {missing_keys}")

# ==========================================
# 3. Zip Archive Validation
# ==========================================
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
            
            # 5. User Processor Logic Validation
            if filename.endswith("process.py") and f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/processors/" in filename:
                 try:
                    with zf.open(member) as f:
                        content = f.read().decode('utf-8')
                        # Syntax check is sufficient here, logic check comes later
                        ast.parse(content)
                 except SyntaxError as e:
                     raise ValueError(f"Syntax error in processor file {filename}: {e.msg} at line {e.lineno}")
                 except Exception as e:
                     raise ValueError(f"Validation failed for processor code {filename}: {e}")

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


        # 6. Dependency Validation (Optimization Flags)
        optimization = opt_config.get("result", {}).get("inputParamsUsed", {})
        
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

# ==========================================
# 4. Function Code Validation (Syntax & Structure)
# ==========================================
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
             args = [arg.arg for arg in node.args.args]
             if len(args) >= 1 and args[0] == "req":
                 return # Valid
    
    raise ValueError("Azure Function must have a 'main(req)' entry point.")

def validate_python_code_google(code_content):
    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        raise ValueError(f"Python Syntax Error at line {e.lineno}: {e.msg}")
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
             return # Has at least one function
    
    raise ValueError("Google Cloud Function must define at least one function.")

# ==========================================
# 5. Project Structure & Provider Resolution
# ==========================================
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
         logger.warning(f"Unknown function '{function_name}', defaulting to Layer 2 provider.")
         layer_key = "layer_2_provider"

    provider = config_providers.get(layer_key)
    if not provider:
         raise ValueError(f"Provider configuration missing for layer '{layer_key}'.")
         
    return provider.lower()

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
        opt_config = {}

    optimization = opt_config.get("result", {}).get("inputParamsUsed", {})
    
    # Check Event Checking Dependencies
    if optimization.get("useEventChecking", False):
        events_file = os.path.join(upload_dir, CONSTANTS.CONFIG_EVENTS_FILE)
        try:
             with open(events_file, 'r') as f:
                 events_config = json.load(f)
        except Exception:
             events_config = []

        for event in events_config:
            action = event.get("action", {})
            if action.get("type") == "lambda":
                func_name = action.get("functionName")
                if not func_name:
                    continue 
                
                action_dir = os.path.join(upload_dir, CONSTANTS.EVENT_ACTIONS_DIR_NAME, func_name)
                if not os.path.exists(action_dir):
                    raise ValueError(f"Missing code for event action: {func_name}. Expected directory: {CONSTANTS.EVENT_ACTIONS_DIR_NAME}/{func_name}")

        if optimization.get("returnFeedbackToDevice", False):
            feedback_dir = os.path.join(upload_dir, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "event-feedback")
            if not os.path.exists(feedback_dir):
                raise ValueError("Missing event-feedback function. Required when 'returnFeedbackToDevice' is true. Expected directory: lambda_functions/event-feedback")

        if optimization.get("triggerNotificationWorkflow", False):
             providers_file = os.path.join(upload_dir, CONSTANTS.CONFIG_PROVIDERS_FILE)
             provider = "aws"
             if os.path.exists(providers_file):
                 try:
                     with open(providers_file, 'r') as f:
                         prov_config = json.load(f)
                         provider = prov_config.get("layer_2_provider", "aws").lower() 
                 except Exception:
                     pass
            
             target_file = CONSTANTS.AWS_STATE_MACHINE_FILE
             if provider == "azure":
                 target_file = CONSTANTS.AZURE_STATE_MACHINE_FILE
             elif provider == "google":
                 target_file = CONSTANTS.GOOGLE_STATE_MACHINE_FILE
                 
             state_machine_path = os.path.join(upload_dir, CONSTANTS.STATE_MACHINES_DIR_NAME, target_file)
             
             if not os.path.exists(state_machine_path):
                 raise ValueError(f"Missing state machine definition for provider '{provider}'. Expected file: {CONSTANTS.STATE_MACHINES_DIR_NAME}/{target_file}")

             try:
                 with open(state_machine_path, 'r') as f:
                     sm_content = f.read()
                     validate_state_machine_content(target_file, sm_content)
             except Exception as e:
                 raise ValueError(f"Invalid state machine content for '{provider}': {e}")

    logger.info(f"Project structure verified for '{project_name}'.")

# ==========================================
# 6. Simulator Payload Validation
# ==========================================
def validate_simulator_payloads(content_str, project_name=None):
    """
    Validates the content of payloads.json.
    Args:
        content_str (str): JSON content string.
        project_name (str, optional): Project name to check iotDeviceId existence.
    Returns:
        (is_valid: bool, errors: list[str], warnings: list[str])
    """
    errors = []
    warnings = []
    
    try:
        data = json.loads(content_str)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"], []

    if not isinstance(data, list):
         return False, ["Payloads must be a JSON array (list)."], []

    if not data:
         warnings.append("Payloads list is empty.")

    # Check structure
    seen_ids = set()
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"Item at index {idx} is not a JSON object.")
            continue
            
        if "iotDeviceId" not in item:
            errors.append(f"Item at index {idx} missing required key 'iotDeviceId'.")
        else:
            seen_ids.add(item["iotDeviceId"])

    if errors:
        return False, errors, warnings
        
    # Optional Project Context Check
    if project_name:
        try:
             upload_dir = os.path.join(globals.project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name)
             iot_config_path = os.path.join(upload_dir, CONSTANTS.CONFIG_IOT_DEVICES_FILE)
             
             if not os.path.exists(iot_config_path):
                 warnings.append(f"Project '{project_name}' has no {CONSTANTS.CONFIG_IOT_DEVICES_FILE}. Cannot verify device IDs.")
             else:
                 with open(iot_config_path, 'r') as f:
                     iot_config = json.load(f)
                 
                 valid_ids = {d.get("id") for d in iot_config}
                 
                 for seen_id in seen_ids:
                     if seen_id not in valid_ids:
                         warnings.append(f"Device ID '{seen_id}' in payloads not found in project configuration.")
        except Exception as e:
            warnings.append(f"Could not verify device IDs against project: {e}")

    return True, [], warnings
