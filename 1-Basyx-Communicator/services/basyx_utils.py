import json
import requests

from services.utils import encode_id
from basyx.aas import model
from basyx.aas.adapter import json as aas_json
from basyx.aas.adapter import http
from basyx.aas.model.submodel import Submodel
from basyx.aas.model.aas import AssetAdministrationShell
from basyx.aas.adapter.json import AASToJsonEncoder, AASFromJsonDecoder

REQUEST_TIMEOUT = 30

def register_submodels(submodels, basyx_base):
    """Register all submodels to BaSyx, converting Submodel objects to dicts first."""
    headers = {"Content-Type": "application/json"}

    for sm in submodels:
        # Convert Submodel object to dict
        if isinstance(sm, Submodel):
            sm_payload = json.loads(json.dumps(sm, cls=AASToJsonEncoder))
        elif isinstance(sm, dict):
            sm_payload = sm
        else:
            print("Skipping unknown submodel type:", type(sm))
            continue

        sm_id = sm_payload.get("id")
        if not sm_id:
            print("Skipping submodel without id:", sm_payload)
            continue

        sm_id_encoded = encode_id(sm_id)
        print(f"Registering Submodel with ID:   {sm_id} ({sm_id_encoded})")
        url = f"{basyx_base.rstrip('/')}/submodels"
        resp = requests.post(url, json=sm_payload, headers=headers, timeout=REQUEST_TIMEOUT)

        if resp.status_code in (200, 201):
            print(f"   Submodel '{sm_id}' created successfully.")
        elif resp.status_code == 409:
            print(f"   Submodel '{sm_id}' already exists.")
        else:
            print(f"   Failed to create submodel '{sm_id}': {resp.status_code}, {resp.text}")
        print("\n")


def register_aas(shells, basyx_base):
    """Register AAS shells to BaSyx, converting AssetAdministrationShell objects to dicts."""
    headers = {"Content-Type": "application/json"}

    for shell in shells:
        if isinstance(shell, AssetAdministrationShell):
            shell_payload = json.loads(json.dumps(shell, cls=AASToJsonEncoder))
        elif isinstance(shell, dict):
            shell_payload = shell
        else:
            print("Skipping unknown shell type:", type(shell))
            continue

        shell_id = shell_payload.get("id")
        if not shell_id:
            print("Skipping AAS without id:", shell_payload)
            continue

        url = f"{basyx_base.rstrip('/')}/shells"
        # url = f"{basyx_base.rstrip('/')}/asset-administration-shells"
        
        print(f"Registering AAS with ID:   {shell_id} - {encode_id(shell_id)}")
        
        resp = requests.post(url, json=shell_payload, headers=headers, timeout=REQUEST_TIMEOUT)

        if resp.status_code in (200, 201):
            print(f"   AAS '{shell_id}' registered successfully.")
        elif resp.status_code == 409:
            print(f"   AAS model '{shell_id}' already exists.")
        else:
            print(f"   Failed to register AAS '{shell_id}': {resp.status_code}, {resp.reason}.")
        
        print("\n")


def upload_aas_environment(env_dict, basyx_base):
    """Upload submodels and AAS shells from env_dict to BaSyx."""
    submodels = env_dict.get("submodels", [])
    shells = env_dict.get("assetAdministrationShells", [])
    
    print("\n----------------------------")
    print("Registering AAS shells...")
    print("----------------------------")
    register_aas(shells, basyx_base)

    print("\n----------------------------")
    print("Registering submodels...")
    print("----------------------------")
    register_submodels(submodels, basyx_base)


    print("\n----------------------------")
    print("Upload completed.\n")
