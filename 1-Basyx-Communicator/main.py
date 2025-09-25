import sys
import requests
from config_loader import load_config
from aas_rest import list_all_shell_ids, build_full_aas
from basyx_utils import upload_aas_environment
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
    basyx_url = cfg["basyx_url"]
    aasx_base = cfg["aasx_base_url"]

    check_server(basyx_url)
    check_server(aasx_base)

    shell_ids = list_all_shell_ids(aasx_base)
    shell_ids = shell_ids[2]  # Limit to first 5 for testing
    for aas_id in [shell_ids]:
        print("\nProcessing:", aas_id)
        try:
            aas = build_full_aas(aas_id, aasx_base)
            
            aas_json = json.dumps(aas, cls=AASToJsonEncoder, indent=2)
            print("Decoded environment:", aas_json)
            
            upload_aas_environment(aas, basyx_url)
        except Exception as e:
            print(f"Error while building and uploading AAS: {e}")
        
if __name__ == "__main__":
    main()
