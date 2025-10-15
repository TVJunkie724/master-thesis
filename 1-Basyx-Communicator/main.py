import sys
import requests
from services.config_loader import load_config
from services.aas_rest import list_all_shell_ids, fetch_and_build_full_aas
from services.basyx_utils import upload_aas_environment
from services.utils import encode_id, debug_write_to_file
import json

from basyx.aas.adapter.json import AASToJsonEncoder, AASFromJsonDecoder
from basyx.aas import model
from basyx.aas.adapter import json as aas_json


def check_server(base_url: str):
    """Check if the AAS server is reachable."""
    try:
        response = requests.get(base_url, timeout=5) 
        response.raise_for_status()
        print(f"✅ AAS Server reachable at {base_url}")
    except requests.RequestException as e:
        print(f"❌ AAS server unreachable: {e}")
        sys.exit(1) 

def main():
    cfg = load_config()
    mode = cfg["mode"]
    basyx_url = cfg["basyx_url"]
    aasx_base = cfg["aasx_base_url"]

    print("\n----------------------------------------------------------------")
    print(f"Running in mode: {mode}")
    print("----------------------------------------------------------------")

    check_server(basyx_url)
    check_server(aasx_base)
    
    shell_ids = [shell_ids[1]]  # Limit to first AAS for testing
    for aas_id in shell_ids:
        
        print("\n\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("----------------------------------------------------------------")
        print("Processing AAS ID:", aas_id)
        print("----------------------------------------------------------------")
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print(f"Source AASX server:         {aasx_base}")
        print(f"Target (local) AAS server:  {basyx_url}")
        
        
        try:
            aas = fetch_and_build_full_aas(aas_id, aasx_base)
            
            aas_json = json.dumps(aas, cls=AASToJsonEncoder, indent=2)
            
            debug_write_to_file(aas_json, "test_aas", False)
        
            upload_aas_environment(aas, basyx_url)
        except Exception as e:
            print(f"Error while building and uploading AAS: {e}")
        
if __name__ == "__main__":
    main()
