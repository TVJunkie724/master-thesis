import os
import json
import re

config = {}
configs_root = None
config_filename = None
_SAFE_DEVICE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

def initialize_config(project_name=None, device_id=None, config_path=None):
    global config, configs_root, config_filename
    
    # Determine config file path
    # 1. Check for local config (standalone mode) in current directory
    # In standalone zip, config.json is at root, src/ is a subdir. So main.py is in src/.
    # executed as `python src/main.py` from root -> CWD is root.
    # config.json should be in CWD.
    
    local_config_path = "config.json"
    
    if config_path:
        selected_config_path = os.path.abspath(config_path)
        print(f"Loading explicit config from: {selected_config_path}")
    elif os.path.exists(local_config_path):
        selected_config_path = os.path.abspath(local_config_path)
        print(f"Loading standalone config from: {selected_config_path}")
    elif project_name:
        # 2. Integrated mode: `upload/{project}/iot_device_simulator/aws/{device_id}/config_generated.json`
        repo_root = os.getcwd()
        aws_sim_dir = os.path.join(repo_root, "upload", project_name, "iot_device_simulator", "aws")
        
        if device_id:
            # Device-specific config path
            selected_config_path = os.path.join(aws_sim_dir, device_id, "config_generated.json")
        else:
            # Fallback: find first device subdirectory
            if os.path.exists(aws_sim_dir):
                device_dirs = [d for d in os.listdir(aws_sim_dir) 
                              if os.path.isdir(os.path.join(aws_sim_dir, d))]
                if device_dirs:
                    selected_config_path = os.path.join(
                        aws_sim_dir,
                        sorted(device_dirs)[0],
                        "config_generated.json",
                    )
                else:
                    raise ValueError(f"No device configs found in {aws_sim_dir}")
            else:
                raise ValueError(f"Simulator directory not found: {aws_sim_dir}")
        
        print(f"Loading project config from: {selected_config_path}")
    else:
        raise ValueError("Configuration not found. Provide --project or run from a standalone package with config.json.")

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


def get_device_config_path(device_id):
    if not isinstance(device_id, str) or not _SAFE_DEVICE_ID.fullmatch(device_id) or ".." in device_id:
        raise ValueError("Invalid simulator device ID")
    return os.path.join(configs_root, device_id, config_filename)
