import json
import requests
import sys
from basyx_utils import (
    fetch_submodel_elements,
    get_submodel_from_basyx,
    parse_sensors_from_submodel
)
from iodd_parser import parse_iodd_zip_combined 

def load_config(file_path="config.json"):
    """Load configuration from JSON file."""
    with open(file_path, "r") as f:
        return json.load(f)

def check_server(base_url: str):
    """Check if the AAS server is reachable."""
    try:
        response = requests.get(base_url, timeout=5) 
        response.raise_for_status()
        
        print(f"✅ AAS Server reachable at {base_url}\n")
    except requests.RequestException as e:
        print(f"❌ AAS server unreachable: {e}")
        sys.exit(1) 
        
def enrich_zip_with_aas(zip_file, aas_id, submodel_id, aas_server_url):
    # First, parse all devices from the IODD zip
    zip_devices = parse_iodd_zip_combined(zip_file)

    try:
        # Try to fetch submodel elements from AAS server
        elements = fetch_submodel_elements(aas_id, submodel_id, aas_server_url)
        submodel_elements = elements.get("result", [])

        # Map submodel info to devices
        for device in zip_devices:
            # Example: enrich device with submodel info
            for elem in submodel_elements:
                if elem.get("idShort") == device.get("device_id"):
                    device["aas_info"] = elem

    except requests.RequestException as e:
        # Fallback: AAS server unreachable
        print(f"❌ Could not reach AAS server: \n{e}")
        sys.exit(1)
        

    return zip_devices


def main():
    config = load_config()

    AASX_SERVER = config["AASX_SERVER"]
    ZIP_FILE = "./_aasx_Software_Festo-SPAE-kPa-20171025-IODD1.1.zip"
    AAS_ID = config["AAS_ID"]
    SUBMODEL_ID = config["SUBMODEL_ID"]

    check_server(AASX_SERVER)

    # Enrich IODD ZIP data with AAS submodel info
    combined_devices = enrich_zip_with_aas(ZIP_FILE, AAS_ID, SUBMODEL_ID, AASX_SERVER)

    # Print JSON result
    print(json.dumps({"result": combined_devices}, indent=2))


if __name__ == "__main__":
    main()
