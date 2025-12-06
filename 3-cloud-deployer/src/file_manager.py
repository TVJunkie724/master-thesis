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
        
        # 1. Check for Missing Required Files
        missing_files = []
        for required_file in CONSTANTS.REQUIRED_CONFIG_FILES:
            if required_file not in file_list:
                missing_files.append(required_file)
        
        if missing_files:
            raise ValueError(f"Invalid project zip. Missing required files: {', '.join(missing_files)}")
            
        # 2. Iterate through all files for Deep Validation & Safety Checks
        for member in zf.infolist():
            # SAFETY: Zip Slip Prevention
            # Check for '..' or absolute paths to prevent overwriting critical system files
            if ".." in member.filename or os.path.isabs(member.filename):
                 raise ValueError("Malicious file path detected in zip (Zip Slip Prevention).")
            
            # 3. Validate Content of Known Config Files
            if member.filename in CONSTANTS.CONFIG_SCHEMAS:
                try:
                    with zf.open(member) as f:
                        content = f.read().decode('utf-8')
                        validate_config_content(member.filename, content)
                except Exception as e:
                     raise ValueError(f"Validation failed for {member.filename} inside zip: {e}")

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
