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
from function_registry import get_function_by_name
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
    Returns all validation errors aggregated, not just the first one.
    """
    errors = []
    
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
                            errors.append(f"Missing credential field '{key}' for provider '{provider}'")
                    
                    # Azure-specific validation
                    if provider == "azure":
                        azure_region = content[provider].get("azure_region")
                        if azure_region:
                            try:
                                validate_azure_region_for_consumption_plan(azure_region)
                            except ValueError as e:
                                errors.append(str(e))
            
            if errors:
                raise ValueError(f"Config validation errors in {filename}:\n  ◦ " + "\n  ◦ ".join(errors))
            return

        
        # General Case: List of objects (IOT, EVENTS, HIERARCHY)
        elif isinstance(content, list):
             if not isinstance(required_keys, list):
                 pass # Should not happen based on constant definition
             
             for index, item in enumerate(content):
                 for key in required_keys:
                     if key not in item:
                         errors.append(f"Item at index {index}: missing key '{key}'")
                 
                 # Nested Checks for specific files
                 if filename == CONSTANTS.CONFIG_EVENTS_FILE:
                     # Check action structure
                     if "action" in item:
                         action = item["action"]
                         if "type" not in action:
                             errors.append(f"Event at index {index}: action missing 'type'")
                         if "functionName" not in action:
                             errors.append(f"Event at index {index}: action missing 'functionName'")
                         
                         if action.get("type") == "lambda" and "feedback" in action:
                             feedback = action["feedback"]
                             if "iotDeviceId" not in feedback:
                                 errors.append(f"Event at index {index}: feedback missing 'iotDeviceId'")
                             if "payload" not in feedback:
                                 errors.append(f"Event at index {index}: feedback missing 'payload'")
             
             if errors:
                 raise ValueError(f"Config validation errors in {filename}:\n  ◦ " + "\n  ◦ ".join(errors))
             return
        
        # General Case: Single Object (CONFIG, OPTIMIZATION)
        elif isinstance(content, dict):
             for key in required_keys:
                 if key not in content:
                     errors.append(f"Missing key '{key}'")
             
             # Validate digital_twin_name format in config.json
             if filename == CONSTANTS.CONFIG_FILE:
                 twin_name = content.get("digital_twin_name")
                 if twin_name:
                     try:
                         validate_digital_twin_name(twin_name)
                     except ValueError as e:
                         errors.append(str(e))
             
             # Special Case: Inter-Cloud Configuration
             if filename == CONSTANTS.CONFIG_INTER_CLOUD_FILE:
                 connections = content.get("connections", {})
                 if not isinstance(connections, dict):
                     errors.append("'connections' must be a dictionary")
                 else:
                     for conn_id, details in connections.items():
                         missing_conn_fields = [k for k in ["provider", "token", "url"] if k not in details]
                         if missing_conn_fields:
                             errors.append(f"Connection '{conn_id}': missing fields {missing_conn_fields}")
             
             if errors:
                 raise ValueError(f"Config validation errors in {filename}:\n  ◦ " + "\n  ◦ ".join(errors))


# ==========================================
# 0.a. Azure Region Validation
# ==========================================
def validate_azure_region_for_consumption_plan(azure_region: str) -> None:
    """
    Validates that the Azure region supports Consumption Plan (Y1) with Linux.
    
    Azure Functions Consumption Plan (Y1) with Linux OS is not supported in all regions.
    Some regions (like italynorth) only support the newer Flex Consumption plan (FC1).
    
    Note: There is no programmatic API to query Y1+Linux regional support.
    This validation is based on empirical testing (December 2025).
    
    Args:
        azure_region: The Azure region to validate
        
    Raises:
        ValueError: If region is known to not support Y1 + Linux
    """
    if azure_region in CONSTANTS.AZURE_UNSUPPORTED_REGIONS_Y1_LINUX:
        recommended = ", ".join(CONSTANTS.AZURE_RECOMMENDED_REGIONS_Y1_LINUX[:3])
        raise ValueError(
            f"Azure region '{azure_region}' does NOT support Consumption Plan (Y1) with Linux OS.\n"
            f"\n"
            f"This region only supports the Flex Consumption plan (FC1), which requires:\n"
            f"  - Different Terraform configuration\n"
            f"  - Different deployment mechanism (blob storage instead of zip_deploy_file)\n"
            f"  - Significant code changes\n"
            f"\n"
            f"Recommended regions for Consumption Plan (Y1) with Linux:\n"
            f"  - {recommended}\n"
            f"\n"
            f"To fix: Change 'azure_region' in config_credentials.json to one of the recommended regions.\n"
            f"\n"
            f"For more information, see: docs/azure_flex_consumption_migration.md"
        ) # TODO: Add link to docs when docs html is updated



# ==========================================
# 1.a. AWS Hierarchy Validation
# ==========================================
def validate_aws_hierarchy_content(content):
    """
    Validates AWS TwinMaker hierarchy format (entity/component structure).
    Returns all validation errors aggregated, not just the first one.
    
    The AWS hierarchy is an array of entity objects, each with:
    - type: "entity" or "component"
    - id: Entity identifier (required for entities)
    - name: Display name (required for components)
    - children: Nested array of child entities/components (optional)
    - componentTypeId: Required for components
    
    Args:
        content: JSON string or parsed list/dict
        
    Raises:
        ValueError: If format is invalid (aggregated errors)
    """
    errors = []
    
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
        """Recursively validate hierarchy items, collecting all errors."""
        if not isinstance(item, dict):
            errors.append(f"Item at {path}: must be a dictionary")
            return
        
        if "type" not in item:
            errors.append(f"Item at {path}: missing required 'type' field")
            return
        
        item_type = item["type"]
        if item_type not in ("entity", "component"):
            errors.append(f"Item at {path}: invalid type '{item_type}' (must be 'entity' or 'component')")
            return
        
        if item_type == "entity":
            if "id" not in item:
                errors.append(f"Entity at {path}: missing required 'id' field")
        elif item_type == "component":
            if "name" not in item:
                errors.append(f"Component at {path}: missing required 'name' field")
            
            # componentTypeId is MANDATORY for full deployment (3D scenes, data binding)
            if "componentTypeId" not in item:
                errors.append(
                    f"Component '{item.get('name', 'unnamed')}' at {path}: missing required 'componentTypeId'"
                )
            
            # Validate properties array if present
            properties = item.get("properties", [])
            if not isinstance(properties, list):
                errors.append(f"Component '{item.get('name')}' at {path}: 'properties' must be an array")
            else:
                valid_types = ["STRING", "DOUBLE", "INTEGER", "BOOLEAN", "LONG"]
                for i, prop in enumerate(properties):
                    if not isinstance(prop, dict):
                        errors.append(f"Property at {path}.properties[{i}]: must be an object")
                        continue
                    if "name" not in prop:
                        errors.append(f"Property at {path}.properties[{i}]: missing 'name'")
                    if "dataType" not in prop:
                        errors.append(f"Property at {path}.properties[{i}]: missing 'dataType'")
                    elif prop.get("dataType") not in valid_types:
                        errors.append(
                            f"Property '{prop.get('name')}' at {path}.properties[{i}]: invalid dataType "
                            f"'{prop.get('dataType')}' (must be one of: {valid_types})"
                        )
            
            # Validate constProperties array if present
            const_props = item.get("constProperties", [])
            if not isinstance(const_props, list):
                errors.append(f"Component '{item.get('name')}' at {path}: 'constProperties' must be an array")
            else:
                valid_types = ["STRING", "DOUBLE", "INTEGER", "BOOLEAN", "LONG"]
                for i, cprop in enumerate(const_props):
                    if not isinstance(cprop, dict):
                        errors.append(f"Const property at {path}.constProperties[{i}]: must be an object")
                        continue
                    if "name" not in cprop:
                        errors.append(f"Const property at {path}.constProperties[{i}]: missing 'name'")
                    if "value" not in cprop:
                        errors.append(f"Const property at {path}.constProperties[{i}]: missing 'value'")
                    if "dataType" not in cprop:
                        errors.append(f"Const property at {path}.constProperties[{i}]: missing 'dataType'")
                    elif cprop.get("dataType") not in valid_types:
                        errors.append(
                            f"Const property '{cprop.get('name')}' at {path}.constProperties[{i}]: invalid dataType "
                            f"'{cprop.get('dataType')}' (must be one of: {valid_types})"
                        )
            
            # Warning if no properties AND no constProperties (will be abstract)
            if not properties and not const_props:
                logger.warning(
                    f"Component '{item.get('name')}' at {path} has no properties or constProperties - "
                    "component type may be abstract and cannot be instantiated"
                )
        
        # Validate children recursively
        children = item.get("children", [])
        for i, child in enumerate(children):
            _validate_item(child, f"{path}.children[{i}]")
    
    for i, item in enumerate(content):
        _validate_item(item, f"[{i}]")
    
    if errors:
        raise ValueError(f"AWS hierarchy validation errors:\n  ◦ " + "\n  ◦ ".join(errors))
    
    logger.info(f"✓ AWS hierarchy validated: {len(content)} top-level items")


# ==========================================
# 1.b. Azure Hierarchy Validation
# ==========================================
def validate_azure_hierarchy_content(content):
    """
    Validates Azure Digital Twins DTDL hierarchy format.
    Returns all validation errors aggregated, not just the first one.
    
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
        ValueError: If format is invalid (aggregated errors)
    """
    errors = []
    
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
            errors.append("'header' must be an object")
        elif "fileVersion" not in header:
            errors.append("header missing 'fileVersion'")
    
    # Validate models
    models = content.get("models", [])
    if not isinstance(models, list):
        errors.append("'models' must be an array")
    else:
        for i, model in enumerate(models):
            if not isinstance(model, dict):
                errors.append(f"Model at index {i}: must be an object")
                continue
            if "@id" not in model:
                errors.append(f"Model at index {i}: missing '@id'")
            elif not model["@id"].startswith("dtmi:"):
                errors.append(f"Model at index {i}: @id '{model['@id']}' must start with 'dtmi:'")
            if "@type" not in model:
                errors.append(f"Model at index {i}: missing '@type'")
            if "@context" not in model:
                errors.append(f"Model at index {i}: missing '@context'")
    
    # Validate twins
    twins = content.get("twins", [])
    if not isinstance(twins, list):
        errors.append("'twins' must be an array")
    else:
        for i, twin in enumerate(twins):
            if not isinstance(twin, dict):
                errors.append(f"Twin at index {i}: must be an object")
                continue
            twin_id = twin.get('$dtId', f'index-{i}')
            if "$dtId" not in twin:
                errors.append(f"Twin at index {i}: missing '$dtId'")
            if "$metadata" not in twin:
                errors.append(f"Twin '{twin_id}': missing '$metadata'")
            elif "$model" not in twin.get("$metadata", {}):
                errors.append(f"Twin '{twin_id}': metadata missing '$model'")
    
    # Validate relationships
    relationships = content.get("relationships", [])
    if not isinstance(relationships, list):
        errors.append("'relationships' must be an array")
    else:
        for i, rel in enumerate(relationships):
            if not isinstance(rel, dict):
                errors.append(f"Relationship at index {i}: must be an object")
                continue
            if "$dtId" not in rel:
                errors.append(f"Relationship at index {i}: missing '$dtId'")
            if "$targetId" not in rel:
                errors.append(f"Relationship at index {i}: missing '$targetId'")
            if "$relationshipName" not in rel:
                errors.append(f"Relationship at index {i}: missing '$relationshipName'")
    
    # DTDL v3: Check for duplicate content names (error)
    for i, model in enumerate(models):
        contents = model.get("contents", [])
        names = [item.get("name") for item in contents if isinstance(item, dict) and item.get("name")]
        duplicates = [n for n in set(names) if names.count(n) > 1]
        if duplicates:
            model_id = model.get("@id", f"index-{i}")
            errors.append(f"Model '{model_id}': Duplicate content names {duplicates} - DTDL v3 requires unique names")
    
    if errors:
        raise ValueError(f"Azure hierarchy validation errors:\n  ◦ " + "\n  ◦ ".join(errors))
    
    # Semantic check: Telemetry without matching last{Name} Property
    for i, model in enumerate(models):
        contents = model.get("contents", [])
        telemetry_names = {
            item.get("name") for item in contents
            if isinstance(item, dict) and item.get("@type") == "Telemetry"
        }
        property_names = {
            item.get("name") for item in contents
            if isinstance(item, dict) and item.get("@type") == "Property"
        }
        
        # Expected pattern: Telemetry 'temperature' → Property 'lastTemperature'
        for tel_name in telemetry_names:
            if tel_name:
                expected_prop = f"last{tel_name[0].upper()}{tel_name[1:]}"
                if expected_prop not in property_names:
                    model_id = model.get("@id", f"index-{i}")
                    logger.warning(
                        f"Model '{model_id}': Telemetry '{tel_name}' has no Property "
                        f"'{expected_prop}'. Twin updates may not persist."
                    )
    
    logger.info(f"✓ Azure hierarchy validated: {len(models)} models, {len(twins)} twins, {len(relationships)} relationships")


# ==========================================
# 1.c. Scene Config Validation
# ==========================================
def validate_scene_config_content(provider: str, content: str, hierarchy_content: str = None):
    """
    Validates scene configuration JSON for 3D visualization.
    
    AWS (scene.json):
      - Basic JSON structure validation (must be an object)
    
    Azure (3DScenesConfiguration.json):
      - Valid JSON with configuration object
      - Allows {{STORAGE_URL}} placeholders in asset URLs
      - Cross-references primaryTwinID against hierarchy twins
    
    Args:
        provider: 'aws' or 'azure'
        content: Scene config JSON string
        hierarchy_content: Optional hierarchy JSON for cross-reference
        
    Raises:
        ValueError: If format is invalid
    """
    # Parse scene config
    if isinstance(content, str):
        try:
            scene_config = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in scene config: {e}")
    else:
        scene_config = content
    
    if not isinstance(scene_config, dict):
        raise ValueError("Scene config must be a JSON object")
    
    provider_lower = provider.lower()
    
    if provider_lower == "aws":
        # AWS scene.json: Basic structure validation
        # AWS TwinMaker scenes are simpler - just need a valid JSON object
        logger.info("✓ AWS scene.json validated: valid JSON object")
        
    elif provider_lower == "azure":
        # Azure 3DScenesConfiguration.json validation
        if "configuration" not in scene_config:
            raise ValueError("Azure scene config missing 'configuration' field")
        
        configuration = scene_config.get("configuration", {})
        
        if not isinstance(configuration, dict):
            raise ValueError("Azure scene config 'configuration' must be an object")
        
        # Check scenes array
        scenes = configuration.get("scenes", [])
        if not isinstance(scenes, list):
            raise ValueError("Azure scene config 'configuration.scenes' must be an array")
        
        # Cross-reference validation if hierarchy provided
        twin_ids_in_hierarchy = set()
        if hierarchy_content:
            try:
                if isinstance(hierarchy_content, str):
                    hierarchy = json.loads(hierarchy_content)
                else:
                    hierarchy = hierarchy_content
                
                # Extract twin IDs from hierarchy
                twins = hierarchy.get("twins", [])
                for twin in twins:
                    if isinstance(twin, dict) and "$dtId" in twin:
                        twin_ids_in_hierarchy.add(twin["$dtId"])
            except (json.JSONDecodeError, TypeError):
                # If hierarchy can't be parsed, skip cross-ref
                pass
        
        # Validate elements in each scene
        errors = []
        for scene_idx, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                continue
            
            elements = scene.get("elements", [])
            for elem_idx, element in enumerate(elements):
                if not isinstance(element, dict):
                    continue
                
                twin_url = element.get("primaryTwinID")
                if twin_url and twin_ids_in_hierarchy:
                    # primaryTwinID can be a URL with twin ID at the end
                    # e.g., "https://xxx.api.wcus.digitaltwins.azure.net/twins/room-1"
                    twin_id = twin_url.split("/")[-1] if "/" in twin_url else twin_url
                    
                    if twin_id and twin_id not in twin_ids_in_hierarchy:
                        elem_id = element.get("id", f"index-{elem_idx}")
                        errors.append(
                            f"Twin '{twin_id}' referenced in element '{elem_id}' (scene {scene_idx}) "
                            f"not found in hierarchy. Available twins: {sorted(list(twin_ids_in_hierarchy)[:5])}"
                        )
        
        if errors:
            raise ValueError("Scene config cross-reference errors:\n" + "\n".join(errors))
        
        logger.info(f"✓ Azure scene config validated: {len(scenes)} scenes")
    else:
        raise ValueError(f"Provider '{provider}' is not valid for scene config. Use 'aws' or 'azure'.")


# ==========================================
# 2. State Machine Validation
# ==========================================
def validate_state_machine_content(filename, content):
    """
    Validates that the state machine file content matches the expected provider format.
    Supports both JSON (.json) and YAML (.yaml/.yml) files.
    
    Returns all validation errors aggregated, not just the first one.
    
    Azure Logic Apps: Validates against official Microsoft schema requirements.
    See: https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-workflow-definition-language
    """
    errors = []
    
    # 1. Parse content based on file extension
    if isinstance(content, str):
        if filename.endswith(('.yaml', '.yml')):
            # Parse YAML
            try:
                import yaml
                parsed_content = yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML content for {filename}: {e}")
            except ImportError:
                raise ValueError(f"PyYAML is required to parse {filename}. Install with: pip install pyyaml")
        else:
            # Parse JSON
            try:
                parsed_content = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON content for {filename}: {e}")
    else:
        parsed_content = content

    # 2. Check Signature (top-level keys)
    if filename in CONSTANTS.STATE_MACHINE_SIGNATURES:
        required_keys = CONSTANTS.STATE_MACHINE_SIGNATURES[filename]
        missing_keys = [k for k in required_keys if k not in parsed_content]
        
        # 2a. Azure Logic App: Validate definition wrapper AND internal structure
        if filename == CONSTANTS.AZURE_STATE_MACHINE_FILE:
            if "definition" not in parsed_content:
                raise ValueError(
                    f"Invalid Azure Logic App format for {filename}. "
                    f"Missing required 'definition' wrapper. "
                    f"Expected structure: {{\"definition\": {{\"$schema\": ..., \"triggers\": ..., \"actions\": ...}}}}"
                )
            
            definition = parsed_content["definition"]
            if not isinstance(definition, dict):
                raise ValueError(
                    f"Azure Logic App 'definition' must be an object, got {type(definition).__name__}"
                )
            
            # Check required keys inside definition (aggregate all missing)
            for key in CONSTANTS.AZURE_DEFINITION_REQUIRED_KEYS:
                if key not in definition:
                    errors.append(f"Missing required key: '{key}'")
            
            # Check expected keys inside definition
            for key in CONSTANTS.AZURE_DEFINITION_EXPECTED_KEYS:
                if key not in definition:
                    errors.append(f"Missing expected key: '{key}'")
            
            # Validate $schema URL format (only if $schema exists)
            if "$schema" in definition:
                schema_url = definition.get("$schema", "")
                if not schema_url.startswith("https://schema.management.azure.com/"):
                    errors.append(
                        f"Invalid $schema URL: expected 'https://schema.management.azure.com/...', "
                        f"got '{schema_url}'"
                    )
            
            if errors:
                raise ValueError(f"Azure Logic App validation errors:\n  ◦ " + "\n  ◦ ".join(errors))
            return  # Azure validation complete
        
        # 2b. GCP Workflow: Special handling for 'main' structure
        if filename == CONSTANTS.GOOGLE_STATE_MACHINE_FILE:
            if "main" not in parsed_content:
                errors.append("Missing required 'main' block")
            else:
                main_block = parsed_content.get("main", {})
                
                # Extract steps list based on format
                steps_list = None
                if isinstance(main_block, list):
                    # Simplified format: main is directly a list of steps
                    steps_list = main_block
                elif isinstance(main_block, dict):
                    if "steps" not in main_block:
                        errors.append("'main' block missing required 'steps' array")
                    else:
                        steps_list = main_block.get("steps", [])
                
                # Validate step names are unique
                if steps_list and isinstance(steps_list, list):
                    step_names = []
                    for step in steps_list:
                        if isinstance(step, dict):
                            step_names.extend(step.keys())
                    
                    # Check for duplicates
                    seen = set()
                    duplicates = []
                    for name in step_names:
                        if name in seen:
                            duplicates.append(name)
                        seen.add(name)
                    
                    if duplicates:
                        errors.append(f"Duplicate step names: {duplicates}")
            
            if errors:
                raise ValueError(f"GCP Workflow validation errors:\n  ◦ " + "\n  ◦ ".join(errors))
            return  # Valid GCP workflow
        
        # 2c. AWS Step Function: Validate StartAt references existing state
        if filename == CONSTANTS.AWS_STATE_MACHINE_FILE:
            # Collect all missing keys
            for key in missing_keys:
                errors.append(f"Missing required key: '{key}'")
            
            start_at = parsed_content.get("StartAt")
            states = parsed_content.get("States", {})
            
            if "States" in parsed_content and not isinstance(states, dict):
                errors.append(f"'States' must be an object, got {type(states).__name__}")
            elif isinstance(states, dict):
                # Validate StartAt references an existing state
                if start_at and start_at not in states:
                    available_states = list(states.keys())[:5]
                    errors.append(
                        f"'StartAt' references non-existent state '{start_at}'. "
                        f"Available states: {available_states}"
                    )
            
            if errors:
                raise ValueError(f"AWS Step Function validation errors:\n  ◦ " + "\n  ◦ ".join(errors))
            return  # AWS validation complete
        
        # 2d. Other providers (fallback)
        if missing_keys:
            raise ValueError(f"Invalid State Machine format for {filename}. Missing required keys: {missing_keys}")

# ==========================================
# 3. Zip Archive Validation
# ==========================================
def validate_project_zip(zip_source):
    """
    Validates that a zip file contains all required configuration files 
    AND validates their content against defined schemas.
    
    This function delegates to src.validation.zip_validator which provides:
    - Required files check
    - Zip Slip prevention
    - Config schema validation
    - State machine validation
    - Processor syntax validation
    - Event action/feedback checks
    - NEW: Payloads vs IoT devices cross-validation
    - NEW: Credentials per provider check
    - NEW: Hierarchy provider match validation
    
    Args:
        zip_source (str | BytesIO | bytes): Path to the zip file, BytesIO, or raw bytes.
        
    Raises:
        ValueError: If required files are missing, if file paths are malicious (Zip Slip),
        or if any configuration file has invalid content/schema.
    """
    from src.validation.zip_validator import validate_project_zip as _validate_project_zip
    return _validate_project_zip(zip_source)

# ==========================================
# 4. Function Code Validation (Syntax & Structure)
# ==========================================
def validate_python_code_aws(code_content):
    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        raise ValueError(f"Python Syntax Error at line {e.lineno}: {e.msg}")

    # Find all lambda_handler definitions
    handlers = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "lambda_handler":
            handlers.append(node.lineno)
    
    if len(handlers) == 0:
        raise ValueError("AWS Lambda function must have a 'lambda_handler(event, context)' function.")
    
    if len(handlers) > 1:
        raise ValueError(f"Duplicate 'lambda_handler' definitions found at lines {handlers}. Only one entry point allowed.")
    
    # Validate signature
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "lambda_handler":
            args = [arg.arg for arg in node.args.args]
            if len(args) >= 2 and args[0] == "event" and args[1] == "context":
                return # Valid
            else:
                raise ValueError("AWS Lambda 'lambda_handler' must have signature: lambda_handler(event, context)")

def validate_python_code_azure(code_content):
    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        raise ValueError(f"Python Syntax Error at line {e.lineno}: {e.msg}")

    # Find all main definitions
    mains = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            mains.append(node.lineno)
    
    if len(mains) == 0:
        raise ValueError("Azure Function must have a 'main(req)' entry point.")
    
    if len(mains) > 1:
        raise ValueError(f"Duplicate 'main' definitions found at lines {mains}. Only one entry point allowed.")
    
    # Validate signature
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            args = [arg.arg for arg in node.args.args]
            if len(args) >= 1 and args[0] == "req":
                return # Valid
            else:
                raise ValueError("Azure Function 'main' must have signature: main(req)")

def validate_python_code_google(code_content):
    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        raise ValueError(f"Python Syntax Error at line {e.lineno}: {e.msg}")
    
    # Count top-level function definitions
    functions = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
    
    if len(functions) == 0:
        raise ValueError("Google Cloud Function must define at least one function.")
    
    # Check for duplicate function names
    seen = set()
    duplicates = []
    for name in functions:
        if name in seen:
            duplicates.append(name)
        seen.add(name)
    
    if duplicates:
        raise ValueError(f"Duplicate function definitions found: {duplicates}. Each function name must be unique.")

# Obsolete function removed - process.py pattern no longer used
# User functions now use provider-specific entry points (main, lambda_handler)


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
    # 1. Direct Mapping via Registry
    func = get_function_by_name(function_name)
    layer_key = func.layer_provider_key if func else None
    
    # 2. Implicit Mapping (Processors)
    if not layer_key and function_name.endswith("-processor"):
        layer_key = "layer_2_provider"
        
    if not layer_key:
         raise ValueError(
             f"Unknown function '{function_name}'. Cannot determine provider layer. "
             f"Function must exist in the registry or end with '-processor'."
         )

    provider = config_providers.get(layer_key)
    if not provider:
         raise ValueError(f"Provider configuration missing for layer '{layer_key}'.")
         
    return provider.lower()

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
        # GCP: project_id for private accounts, billing_account for org accounts
        "gcp": ["gcp_project_id", "gcp_billing_account", "gcp_region"]
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
