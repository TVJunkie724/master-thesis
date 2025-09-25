import requests
import json
from copy import deepcopy
from urllib.parse import quote
from utils import encode_id
from basyx.aas import model
from basyx.aas.model import AssetAdministrationShell
from basyx.aas.adapter.json import AASToJsonEncoder, AASFromJsonDecoder
import json
import re
from normalize_aas import normalize_aas_element


REQUEST_TIMEOUT = 30

def list_all_shell_ids(aasx_server: str):
    """Return all shell IDs from server."""
    url = f"{aasx_server.rstrip('/')}/shells"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    items = data.get("result", data)

    ids = []
    for it in items:
        if isinstance(it, str):
            ids.append(it)
        elif isinstance(it, dict):
            ident = None
            if "identification" in it:
                if isinstance(it["identification"], dict):
                    ident = it["identification"].get("id")
                elif isinstance(it["identification"], str):
                    ident = it["identification"]
            if not ident:
                ident = it.get("id") or it.get("idShort")
            if ident:
                ids.append(ident)
    return ids

def fetch_aas(aas_id: str, aasx_server: str):
    """Fetch full AAS JSON by its shell ID (not asset ID)."""
    encoded_id = encode_id(aas_id)  # <--- encode the AAS ID
    url = f"{aasx_server.rstrip('/')}/shells/{encoded_id}"
    
    print(f" Fetching AAS from {url}")
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

def fetch_submodel_list(aas_id: str, aasx_server: str,  submodel_ids: list[str] = None) -> list[str]:
    """
    Fetch submodels from the shell itself instead of the registry.
    Returns a list of submodels
    """
    if submodel_ids is None:
        # Get all shells
        url = f"{aasx_server.rstrip('/')}/shells"
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        shells = r.json().get("result", r.json())

        # Find the shell matching aas_id
        shell = next((s for s in shells if s.get("id") == aas_id), None)
        if not shell:
            return []
        submodel_ids = shell.get("submodels", [])
        
    submodels = []
    for sm_id in submodel_ids:
        encoded_aas_id = encode_id(aas_id)
        encoded_submodel_id = encode_id(sm_id)
        shells_url = f"{aasx_server.rstrip('/')}/shells/{encoded_aas_id}/submodels/{encoded_submodel_id}"
        r = requests.get(shells_url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        submodel = r.json().get("result", r.json())
        submodels.append(submodel)
    return submodels

def fetch_asset_information(aas_id: str, aasx_server: str):
    """Fetch asset information of an AAS by its shell ID."""
    encoded_id = encode_id(aas_id)
    url = f"{aasx_server.rstrip('/')}/shells/{encoded_id}/asset-information"
    print(f" Fetching asset information from {url}")
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json().get("result", r.json())

# def fetch_submodel_elements(aas_id: str, submodel_id: str, aasx_server: str):
    # """
    # Fetch all elements of a submodel via the repository API.
    # """
    # encoded_aas = encode_id(aas_id)
    # encoded_sm  = encode_id(submodel_id)
    # url = f"{aasx_server.rstrip('/')}/shells/{encoded_aas}/submodels/{encoded_sm}/submodel-elements"
    # print(f" Fetching submodel elements from {url}")
    # r = requests.get(url, timeout=REQUEST_TIMEOUT)
    # r.raise_for_status()
    # return r.json().get("result", r.json())
    
def build_full_aas(aas_id: str, aasx_server: str) -> model.AssetAdministrationShell:
    
    encoded_aas_id = encode_id(aas_id)
    print(f"Fetching AAS '{aas_id}' as '{encoded_aas_id}' from {aasx_server}")
    shells_url = f"{aasx_server.rstrip('/')}/shells/{encoded_aas_id}"
    r = requests.get(shells_url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    shell_data = r.json().get("result", r.json())

    if not shell_data:
        raise ValueError(f"AAS '{aas_id}' not found on server")

    id_short = shell_data.get("idShort", aas_id)
    print(f"Building full AAS for '{id_short}' ({aas_id})")

    
    # Fetch submodels
    # submodel_ids = fetch_submodel_list(aas_id, aasx_server)
    submodel_ids = [sm.get("keys", [{}])[0].get("value") for sm in shell_data.get("submodels", []) if sm.get("keys")]
    print(f"  Found {len(submodel_ids)} submodels")
    
    submodels_list = fetch_submodel_list(aas_id, aasx_server, submodel_ids) or []

    asset_info_data = fetch_asset_information(aas_id, aasx_server) or []

    # ----------------------------------
    # Build aas environment class
    # ----------------------------------
    aas_shell = [deepcopy(shell_data)]
    if "submodels" in aas_shell:
        del aas_shell["submodels"]
        
    aas_submodels = deepcopy(submodels_list)
    aas_asset_information = [asset_info_data]

    for sh in aas_shell:
        normalize_aas_element(sh)
    
    for sm in aas_submodels:
        try:
            normalize_aas_element(sm)    
        except Exception as e:
            print(f"Error fixing semantic IDs in submodel {sm.get('id')}: {e}")
    
    
    env_dict = {
        "assetAdministrationShells": aas_shell,
        "submodels": aas_submodels,
        "conceptDescriptions": aas_asset_information
    }
    
    env = json.loads(json.dumps(env_dict), cls=AASFromJsonDecoder)

    # aas_json = json.dumps(env, cls=AASToJsonEncoder, indent=2)
    # print("Decoded environment:", aas_json)
    
    return env