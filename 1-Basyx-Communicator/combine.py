from iodd_parser import parse_iodd_zip_combined
from basyx_utils import fetch_submodel_elements, encode_identifier
import requests

def enrich_process_data_with_aas(zip_data, aas_id, submodel_id, aasx_server):
    """
    Merge IODD ZIP info with AAS human-readable data.
    zip_data: list of dicts from parse_iodd_zip_combined()
    aas_id: the Asset Administration Shell ID
    submodel_id: submodel containing sensor/process data
    aasx_server: base URL of your AAS server
    """
    # Fetch all submodel elements from AAS
    aas_elements = fetch_submodel_elements(aas_id, submodel_id, aasx_server)
    human_data_map = {elem["idShort"]: elem for elem in aas_elements}

    enriched = []
    for device in zip_data:
        enriched_device = device.copy()
        enriched_process_data = []

        for pd in device["process_data"]:
            pd_id = pd.get("id")
            aas_info = human_data_map.get(pd_id, {})

            enriched_process_data.append({
                "id": pd_id,
                "pd_type": pd.get("pd_type"),
                "name": aas_info.get("idShort") or pd_id,
                "type": aas_info.get("valueType"),
                "unit": aas_info.get("unit"),      # if available in AAS
                "range": aas_info.get("range"),    # if available in AAS
                "subitems": aas_info.get("subitems", [])
            })

        enriched_device["process_data"] = enriched_process_data
        enriched.append(enriched_device)

    return {"result": enriched}

