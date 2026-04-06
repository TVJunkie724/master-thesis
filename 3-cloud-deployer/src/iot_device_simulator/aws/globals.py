import os
import json
import sys

config = {}

def initialize_config(project_name=None, device_id=None):
    global config
    
    # Determine config file path
    # 1. Check for local config (standalone mode) in current directory
    # In standalone zip, config.json is at root, src/ is a subdir. So main.py is in src/.
    # executed as `python src/main.py` from root -> CWD is root.
    # config.json should be in CWD.
    
    local_config_path = "config.json"
    
    if os.path.exists(local_config_path):
        config_path = os.path.abspath(local_config_path)
        print(f"Loading standalone config from: {config_path}")
    elif project_name:
        # 2. Integrated mode: `upload/{project}/iot_device_simulator/aws/{device_id}/config_generated.json`
        repo_root = os.getcwd()
        aws_sim_dir = os.path.join(repo_root, "upload", project_name, "iot_device_simulator", "aws")
        
        if device_id:
            # Device-specific config path
            config_path = os.path.join(aws_sim_dir, device_id, "config_generated.json")
        else:
            # Fallback: find first device subdirectory
            if os.path.exists(aws_sim_dir):
                device_dirs = [d for d in os.listdir(aws_sim_dir) 
                              if os.path.isdir(os.path.join(aws_sim_dir, d))]
                if device_dirs:
                    config_path = os.path.join(aws_sim_dir, device_dirs[0], "config_generated.json")
                else:
                    raise ValueError(f"No device configs found in {aws_sim_dir}")
            else:
                raise ValueError(f"Simulator directory not found: {aws_sim_dir}")
        
        print(f"Loading project config from: {config_path}")
    else:
        raise ValueError("Configuration not found. Provide --project or run from a standalone package with config.json.")

    if not os.path.exists(config_path):
         raise FileNotFoundError(f"Config file not found at: {config_path}")

    with open(config_path, "r") as file:
        config_data = json.load(file)

    # Resolve paths relative to config file directory
    config_dir = os.path.dirname(config_path)
    
    def resolve(path):
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(config_dir, path))

    config["endpoint"] = config_data["endpoint"]
    config["topic"] = config_data["topic"]
    config["device_id"] = config_data["device_id"]
    
    config["cert_path"] = resolve(config_data["cert_path"])
    config["key_path"] = resolve(config_data["key_path"])
    config["root_ca_path"] = resolve(config_data["root_ca_path"])
    config["payload_path"] = resolve(config_data["payload_path"])

    # Validate critical files exist
    for k in ["cert_path", "key_path", "root_ca_path", "payload_path"]:
        if not os.path.exists(config[k]):
            print(f"WARNING: File for {k} not found at {config[k]}")
