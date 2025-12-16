"""
Validator - Configuration and Structure Validation.

This module provides comprehensive validation for configuration files,
state machines, zip archives, Python code, and project structure.
"""

import os
import zipfile
import json
import hashlib
import re
import constants as CONSTANTS
from logger import logger
import io
import ast


# ==========================================
# 0. Digital Twin Name Validation
# ==========================================
def validate_digital_twin_name(name: str) -> None:
    """
    Validates the digital twin name for AWS resource naming compatibility.
    
    Constraints:
    - Maximum 20 characters (resource naming limits)
    - Only alphanumeric, hyphen, underscore allowed
    
    Args:
        name: The digital twin name to validate
        
    Raises:
        ValueError: If name exceeds length or contains invalid characters
    """
    max_length = 30
    if len(name) > max_length:
        raise ValueError(
            f"Digital twin name '{name}' exceeds {max_length} characters."
        )
    
    valid_pattern = r'^[A-Za-z0-9_-]+$'
    if not re.match(valid_pattern, name):
        raise ValueError(
            f"Digital twin name '{name}' contains invalid characters. "
            "Only alphanumeric, hyphen, and underscore allowed."
        )


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
        
        # General Case: Single Object (CONFIG, OPTIMIZATION)
        elif isinstance(content, dict):
             for key in required_keys:
                 if key not in content:
                     raise ValueError(f"Missing key '{key}' in {filename}.")
             
             # Validate digital_twin_name format in config.json
             if filename == CONSTANTS.CONFIG_FILE:
                 twin_name = content.get("digital_twin_name")
                 if twin_name:
                     validate_digital_twin_name(twin_name)
             
             # Special Case: Inter-Cloud Configuration
             if filename == CONSTANTS.CONFIG_INTER_CLOUD_FILE:
                 connections = content.get("connections", {})
                 if not isinstance(connections, dict):
                     raise ValueError("'connections' must be a dictionary.")
                 
                 for conn_id, details in connections.items():
                     if not all(k in details for k in ["provider", "token", "url"]):
                         raise ValueError(f"Connection '{conn_id}' missing required fields: provider, token, url")


# ==========================================
# 1.a. AWS Hierarchy Validation
# ==========================================
def validate_aws_hierarchy_content(content):
    """
    Validates AWS TwinMaker hierarchy format (entity/component structure).
    
    The AWS hierarchy is an array of entity objects, each with:
    - type: "entity" or "component"
    - id: Entity identifier (required for entities)
    - name: Display name (required for components)
    - children: Nested array of child entities/components (optional)
    - componentTypeId or iotDeviceId: Required for components
    
    Args:
        content: JSON string or parsed list/dict
        
    Raises:
        ValueError: If format is invalid (fail-fast)
    """
    if content is None:
        raise ValueError("AWS hierarchy content cannot be None")
    
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in AWS hierarchy: {e}")
    
    if not isinstance(content, list):
        raise ValueError("AWS hierarchy must be a JSON array")
    
    def _validate_item(item, path="root"):
        """Recursively validate hierarchy items."""
        if not isinstance(item, dict):
            raise ValueError(f"Hierarchy item at {path} must be a dictionary")
        
        if "type" not in item:
            raise ValueError(f"Hierarchy item at {path} missing required 'type' field")
        
        item_type = item["type"]
        if item_type not in ("entity", "component"):
            raise ValueError(f"Hierarchy item at {path} has invalid type '{item_type}'. Must be 'entity' or 'component'")
        
        if item_type == "entity":
            if "id" not in item:
                raise ValueError(f"Entity at {path} missing required 'id' field")
        elif item_type == "component":
            if "name" not in item:
                raise ValueError(f"Component at {path} missing required 'name' field")
            if "componentTypeId" not in item and "iotDeviceId" not in item:
                raise ValueError(f"Component '{item.get('name')}' at {path} must have 'componentTypeId' or 'iotDeviceId'")
        
        # Validate children recursively
        children = item.get("children", [])
        for i, child in enumerate(children):
            _validate_item(child, f"{path}.children[{i}]")
    
    for i, item in enumerate(content):
        _validate_item(item, f"[{i}]")
    
    logger.info(f"✓ AWS hierarchy validated: {len(content)} top-level items")


# ==========================================
# 1.b. Azure Hierarchy Validation
# ==========================================
def validate_azure_hierarchy_content(content):
    """
    Validates Azure Digital Twins DTDL hierarchy format.
    
    At deployment time (L4), this JSON is converted to NDJSON for the
    Azure Digital Twins Import Jobs API:
        {"Section": "Header"} + header object
        {"Section": "Models"} + one line per model
        {"Section": "Twins"} + one line per twin
        {"Section": "Relationships"} + one line per relationship
    
    See: https://learn.microsoft.com/en-us/azure/digital-twins/concepts-apis-sdks#format-data
    
    Args:
        content: JSON string or parsed dict
        
    Raises:
        ValueError: If format is invalid (fail-fast)
    """
    if content is None:
        raise ValueError("Azure hierarchy content cannot be None")
    
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in Azure hierarchy: {e}")
    
    if not isinstance(content, dict):
        raise ValueError("Azure hierarchy must be a JSON object")
    
    # Validate header (optional)
    header = content.get("header")
    if header is not None:
        if not isinstance(header, dict):
            raise ValueError("Azure hierarchy 'header' must be an object")
        if "fileVersion" not in header:
            raise ValueError("Azure hierarchy header missing 'fileVersion'")
    
    # Validate models
    models = content.get("models", [])
    if not isinstance(models, list):
        raise ValueError("Azure hierarchy 'models' must be an array")
    
    for i, model in enumerate(models):
        if not isinstance(model, dict):
            raise ValueError(f"Model at index {i} must be an object")
        if "@id" not in model:
            raise ValueError(f"Model at index {i} missing '@id'")
        if "@type" not in model:
            raise ValueError(f"Model at index {i} missing '@type'")
        if "@context" not in model:
            raise ValueError(f"Model at index {i} missing '@context'")
        if not model["@id"].startswith("dtmi:"):
            raise ValueError(f"Model @id '{model['@id']}' must start with 'dtmi:'")
    
    # Validate twins
    twins = content.get("twins", [])
    if not isinstance(twins, list):
        raise ValueError("Azure hierarchy 'twins' must be an array")
    
    for i, twin in enumerate(twins):
        if not isinstance(twin, dict):
            raise ValueError(f"Twin at index {i} must be an object")
        if "$dtId" not in twin:
            raise ValueError(f"Twin at index {i} missing '$dtId'")
        if "$metadata" not in twin:
            raise ValueError(f"Twin '{twin.get('$dtId')}' missing '$metadata'")
        if "$model" not in twin.get("$metadata", {}):
            raise ValueError(f"Twin '{twin.get('$dtId')}' metadata missing '$model'")
    
    # Validate relationships
    relationships = content.get("relationships", [])
    if not isinstance(relationships, list):
        raise ValueError("Azure hierarchy 'relationships' must be an array")
    
    for i, rel in enumerate(relationships):
        if not isinstance(rel, dict):
            raise ValueError(f"Relationship at index {i} must be an object")
        if "$dtId" not in rel:
            raise ValueError(f"Relationship at index {i} missing '$dtId'")
        if "$targetId" not in rel:
            raise ValueError(f"Relationship at index {i} missing '$targetId'")
        if "$relationshipName" not in rel:
            raise ValueError(f"Relationship at index {i} missing '$relationshipName'")
    
    logger.info(f"✓ Azure hierarchy validated: {len(models)} models, {len(twins)} twins, {len(relationships)} relationships")


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
             # Determine Expected Provider - REQUIRED when triggerNotificationWorkflow is enabled
             provider = prov_config.get("layer_2_provider")
             if not provider:
                 raise ValueError(
                     "Missing 'layer_2_provider' in config_providers.json. "
                     "Required when 'triggerNotificationWorkflow' is enabled."
                 )
             provider = provider.lower()
             
             # Explicit provider handling - no fallbacks
             if provider == "aws":
                 target_file = CONSTANTS.AWS_STATE_MACHINE_FILE
             elif provider == "azure":
                 target_file = CONSTANTS.AZURE_STATE_MACHINE_FILE
             elif provider == "google":
                 target_file = CONSTANTS.GOOGLE_STATE_MACHINE_FILE
             else:
                 raise ValueError(f"Invalid provider '{provider}' for state machine. Must be 'aws', 'azure', or 'google'.")
                 
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
def get_provider_for_function(project_name, function_name, project_path: str = None):
    """
    Determines the cloud provider for a specific function based on the project configuration.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        project_path: Root project path (REQUIRED)
    """
    if project_path is None:
        raise ValueError("project_path is required")
    
    upload_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name)
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
         raise ValueError(
             f"Unknown function '{function_name}'. Cannot determine provider layer. "
             "Function must be in FUNCTION_LAYER_MAPPING or end with '-processor'."
         )

    provider = config_providers.get(layer_key)
    if not provider:
         raise ValueError(f"Provider configuration missing for layer '{layer_key}'.")
         
    return provider.lower()

def verify_project_structure(project_name, project_path: str = None):
    """
    Verifies that the project structure is valid and consistent with its configuration.
    Enforces strict dependency checks for optimization flags.
    
    Args:
        project_name: Name of the project to verify
        project_path: Root project path (REQUIRED)
    """
    if project_path is None:
        raise ValueError("project_path is required")
    
    upload_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name)
    
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
             provider = None
             if os.path.exists(providers_file):
                 try:
                     with open(providers_file, 'r') as f:
                         prov_config = json.load(f)
                         provider = prov_config.get("layer_2_provider")
                 except Exception:
                     pass
             
             if not provider:
                 raise ValueError(
                     "Missing 'layer_2_provider' in config_providers.json. "
                     "Required when 'triggerNotificationWorkflow' is enabled."
                 )
             provider = provider.lower()
            
             # Explicit provider handling - no fallbacks
             if provider == "aws":
                 target_file = CONSTANTS.AWS_STATE_MACHINE_FILE
             elif provider == "azure":
                 target_file = CONSTANTS.AZURE_STATE_MACHINE_FILE
             elif provider == "google":
                 target_file = CONSTANTS.GOOGLE_STATE_MACHINE_FILE
             else:
                 raise ValueError(f"Invalid provider '{provider}' for state machine. Must be 'aws', 'azure', or 'google'.")
                 
             state_machine_path = os.path.join(upload_dir, CONSTANTS.STATE_MACHINES_DIR_NAME, target_file)
             
             if not os.path.exists(state_machine_path):
                 raise ValueError(f"Missing state machine definition for provider '{provider}'. Expected file: {CONSTANTS.STATE_MACHINES_DIR_NAME}/{target_file}")

             try:
                 with open(state_machine_path, 'r') as f:
                     sm_content = f.read()
                     validate_state_machine_content(target_file, sm_content)
             except Exception as e:
                 raise ValueError(f"Invalid state machine content for '{provider}': {e}")

    # 3. Processor Code Validation
    # Check that processor code exists for each device in config_iot_devices.json
    devices_file = os.path.join(upload_dir, CONSTANTS.CONFIG_IOT_DEVICES_FILE)
    providers_file = os.path.join(upload_dir, CONSTANTS.CONFIG_PROVIDERS_FILE)
    
    if os.path.exists(devices_file) and os.path.exists(providers_file):
        try:
            with open(devices_file, 'r') as f:
                devices_config = json.load(f)
            with open(providers_file, 'r') as f:
                prov_config = json.load(f)
        except Exception:
            devices_config = []
            prov_config = {}
        
        # Determine L2 provider for processor path
        l2_provider = prov_config.get("layer_2_provider")
        if l2_provider:
            l2_provider = l2_provider.lower()
            
            # Track unique processors to avoid duplicate checks
            processors_checked = set()
            
            for device in devices_config:
                if "id" not in device:
                    raise ValueError("Device config entry missing required 'id' field")
                
                # Get processor name (default_processor if not specified)
                processor_name = device.get("processor", "default_processor")
                
                if processor_name in processors_checked:
                    continue
                processors_checked.add(processor_name)
                
                # Determine processor directory path based on provider
                if l2_provider == "aws":
                    proc_dir = os.path.join(upload_dir, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "processors", processor_name)
                elif l2_provider == "azure":
                    proc_dir = os.path.join(upload_dir, "azure_functions", "processors", processor_name)
                elif l2_provider == "google":
                    proc_dir = os.path.join(upload_dir, "cloud_functions", "processors", processor_name)
                else:
                    raise ValueError(f"Unsupported layer_2_provider: {l2_provider}")
                
                if not os.path.exists(proc_dir):
                    raise ValueError(
                        f"Missing processor code for device '{device['id']}'. "
                        f"Expected directory: {proc_dir}"
                    )

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
    # Note: Project context verification requires project_path which is not available here
    # For full validation with project context, use a higher-level function that has access to project_path

    return True, [], warnings


# ==========================================
# 8. Duplicate Project Detection
# ==========================================
def _get_project_base_path():
    """Get the base path for projects. Uses PYTHONPATH or app detection."""
    app_path = "/app"
    if os.path.exists(app_path):
        return app_path
    # Fallback: go up from this file's directory
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _hash_credentials(creds: dict) -> str:
    """
    Creates a deterministic hash of credentials for comparison.
    Only hashes the keys that identify the account (not secrets).
    
    Args:
        creds: Credentials dictionary with provider keys.
        
    Returns:
        SHA256 hash string of identity-relevant fields.
    """
    # Use account-identifying fields only (not secrets)
    identity_fields = {
        "aws": ["aws_access_key_id", "aws_region"],
        "azure": ["azure_subscription_id", "azure_tenant_id", "azure_region", "azure_region_iothub", "azure_region_digital_twin"],
        "gcp": ["gcp_project_id", "gcp_region"]
    }
    
    hash_input = ""
    for provider, fields in identity_fields.items():
        if provider in creds:
            for field in fields:
                hash_input += str(creds[provider].get(field, ""))
    
    return hashlib.sha256(hash_input.encode()).hexdigest()


def check_duplicate_project(
    new_twin_name: str, 
    new_creds: dict, 
    exclude_project: str = None, 
    project_path: str = None
) -> str | None:
    """
    Checks if another project exists with the same digital_twin_name AND same credentials.
    
    This prevents deploying multiple projects that would create conflicting cloud resources
    (e.g., same IoT Thing names, same Lambda function names, same DynamoDB table prefixes).
    
    Args:
        new_twin_name: The digital_twin_name of the new/updated project.
        new_creds: The credentials config of the new/updated project.
        exclude_project: Project name to exclude from check (for updates).
        project_path: Base project path.
    
    Returns:
        Name of conflicting project if found, None otherwise.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    new_creds_hash = _hash_credentials(new_creds)
    upload_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME)
    
    if not os.path.exists(upload_dir):
        return None
    
    for project_name in os.listdir(upload_dir):
        if project_name == exclude_project:
            continue
        
        project_dir = os.path.join(upload_dir, project_name)
        if not os.path.isdir(project_dir):
            continue
        
        # Read config.json and credentials
        config_path = os.path.join(project_dir, CONSTANTS.CONFIG_FILE)
        creds_path = os.path.join(project_dir, CONSTANTS.CONFIG_CREDENTIALS_FILE)
        
        if not os.path.exists(config_path) or not os.path.exists(creds_path):
            continue
        
        try:
            with open(config_path, 'r') as f:
                existing_config = json.load(f)
            with open(creds_path, 'r') as f:
                existing_creds = json.load(f)
            
            existing_twin_name = existing_config.get("digital_twin_name")
            existing_creds_hash = _hash_credentials(existing_creds)
            
            if existing_twin_name == new_twin_name and existing_creds_hash == new_creds_hash:
                return project_name
        except Exception:
            # Skip corrupted or unreadable projects
            continue
    
    return None
