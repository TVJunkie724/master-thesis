import base64
import requests
import sys
from services.config_loader import load_config

def check_server(base_url: str):
    """Check if the server is reachable."""
    try:
        response = requests.get(base_url, timeout=5) 
        response.raise_for_status()
        print(f"✅ Server reachable at {base_url}")
    except requests.RequestException as e:
        print(f"❌ Server unreachable: {e}")
        sys.exit(1) 
        
def debug_write_to_file(file_content, file_name, overwrite=True):
    
    cfg = load_config()
    mode = cfg["mode"]
    
    if mode == "DEBUG":
        with open(f"debug/{file_name}.log", "w" if overwrite else "a") as f:
            f.write(f"\n{file_content}")