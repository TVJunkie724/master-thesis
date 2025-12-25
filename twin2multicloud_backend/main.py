import sys
import requests
from services.config_loader import load_config
from services.utils import check_server, debug_write_to_file
import json

def main():
    cfg = load_config()
    mode = cfg["mode"]
    twin2clouds_url = cfg["twin2clouds_url"]
    cloud_deployer_url = cfg["cloud_deployer_url"]

    print("\n----------------------------------------------------------------")
    print(f"Running in mode: {mode}")
    print("----------------------------------------------------------------")

    check_server(twin2clouds_url)
    check_server(cloud_deployer_url)
    
    
if __name__ == "__main__":
    main()
