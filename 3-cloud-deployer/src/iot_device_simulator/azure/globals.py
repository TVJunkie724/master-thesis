"""
Azure IoT Device Simulator - Configuration Management.

This module loads configuration for the Azure IoT device simulator,
supporting both standalone mode (local config.json) and integrated mode
(via --project flag loading from upload/{project}/iot_device_simulator/azure/).

Azure uses connection strings for authentication (simpler than AWS certificates).
"""

import os
import json
import re

config = {}
configs_root = None
config_filename = None
_SAFE_DEVICE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def initialize_config(project_name=None, device_id=None, config_path=None):
    """
    Initialize the simulator configuration.
    
    Args:
        project_name: Optional project name for integrated mode.
                     If None, looks for local config.json (standalone mode).
        device_id: Optional device ID for device-specific config.
    
    Raises:
        ValueError: If no configuration source is found.
        FileNotFoundError: If the config file doesn't exist.
    """
    global config, configs_root, config_filename
    
    # Determine config file path
    # 1. Check for local config (standalone mode) in current directory
    # In standalone zip, config.json is at root, src/ is a subdir.
    # Executed as `python src/main.py` from root -> CWD is root.
    
    local_config_path = "config.json"
    
    if config_path:
        selected_config_path = os.path.abspath(config_path)
        print(f"Loading explicit config from: {selected_config_path}")
    elif os.path.exists(local_config_path):
        selected_config_path = os.path.abspath(local_config_path)
        print(f"Loading standalone config from: {selected_config_path}")
    elif project_name:
        # 2. Integrated mode: `upload/{project}/iot_device_simulator/azure/{device_id}/config_generated.json`
        repo_root = os.getcwd()
        azure_sim_dir = os.path.join(
            repo_root, "upload", project_name, "iot_device_simulator", "azure"
        )
        
        if device_id:
            # Device-specific config path
            selected_config_path = os.path.join(azure_sim_dir, device_id, "config_generated.json")
        else:
            # Fallback: find first device subdirectory
            if os.path.exists(azure_sim_dir):
                device_dirs = [d for d in os.listdir(azure_sim_dir) 
                              if os.path.isdir(os.path.join(azure_sim_dir, d))]
                if device_dirs:
                    selected_config_path = os.path.join(
                        azure_sim_dir,
                        sorted(device_dirs)[0],
                        "config_generated.json",
                    )
                else:
                    raise ValueError(f"No device configs found in {azure_sim_dir}")
            else:
                raise ValueError(f"Simulator directory not found: {azure_sim_dir}")
        
        print(f"Loading project config from: {selected_config_path}")
    else:
        raise ValueError(
            "Configuration not found. Provide --project or run from a standalone package with config.json."
        )

    if not os.path.exists(selected_config_path):
        raise FileNotFoundError(f"Config file not found at: {selected_config_path}")

    with open(selected_config_path, "r") as file:
        config_data = json.load(file)

    # Resolve paths relative to config file directory
    config_dir = os.path.dirname(selected_config_path)
    if os.path.basename(selected_config_path) == "config_generated.json":
        configs_root = os.path.dirname(config_dir)
        config_filename = "config_generated.json"
    else:
        configs_root = os.path.join(config_dir, "configs")
        config_filename = "config.json"
    
    def resolve(path):
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(config_dir, path))

    # Required fields for Azure
    config["connection_string"] = config_data["connection_string"]
    config["device_id"] = config_data["device_id"]
    config["digital_twin_name"] = config_data.get("digital_twin_name", "")
    
    # Resolve payload path
    config["payload_path"] = resolve(config_data.get("payload_path", "../payloads.json"))

    # Validate payload file exists
    if not os.path.exists(config["payload_path"]):
        print(f"WARNING: Payload file not found at {config['payload_path']}")


def get_device_config_path(device_id):
    if not isinstance(device_id, str) or not _SAFE_DEVICE_ID.fullmatch(device_id) or ".." in device_id:
        raise ValueError("Invalid simulator device ID")
    return os.path.join(configs_root, device_id, config_filename)
