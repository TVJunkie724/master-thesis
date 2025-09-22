import requests
import base64

def fetch_aas(aas_id, aasx_server):
    """Fetch metadata of the Asset Administration Shell."""
    url = f"{aasx_server}/shells/{aas_id}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


def fetch_submodel_elements(aas_id, submodel_id, aasx_server):
    """Fetch all elements of a submodel."""
    url = f"{aasx_server}/shells/{aas_id}/submodels/{submodel_id}/submodel-elements"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("result", [])


def push_submodel_to_local(submodel_id, id_short, elements, local_basyx_url):
    payload = {
        "idShort": id_short,
        "id": submodel_id,
        "idType": "IRI",
        "submodelElements": []
    }

    for elem in elements:
        payload["submodelElements"].append({
            "idShort": elem.get("idShort", "unknown"),
            "modelType": elem.get("modelType", "Property"),
            "valueType": elem.get("valueType", "string"),
            "value": elem.get("value", "")
        })

    url = f"{local_basyx_url}/submodels"
    resp = requests.post(url, json=payload)

    if resp.status_code in [200, 201]:
        print(f"Submodel '{id_short}' created successfully.")
    elif resp.status_code == 409:
        print(f"Submodel '{id_short}' was already added.")
    else:
        print(f"Failed to push '{id_short}': {resp.status_code}, {resp.text}")


def encode_identifier(identifier: str) -> str:
    """Encodes an identifier for BaSyx using Base64 URL-safe encoding (without padding)."""
    return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")


def get_submodel_from_basyx(submodel_id, local_basyx_url):
    """Fetches a submodel and its elements from the BaSyx server."""
    encoded_id = encode_identifier(submodel_id)
    url = f"{local_basyx_url}/submodels/{encoded_id}/submodel-elements"
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"\nFailed to fetch submodel '{submodel_id}': {response.status_code}, {response.text}")
        return None


def parse_sensors_from_submodel(submodel_data: dict):
    """Extracts a clean list of sensors from a submodel JSON with full info."""
    sensors = []

    if not submodel_data or "submodelElements" not in submodel_data:
        return sensors

    for elem in submodel_data["submodelElements"]:
        id_short = elem.get("idShort", "Unknown")
        model_type = elem.get("modelType", "Unknown")
        value_type = elem.get("valueType", "Unknown")
        value = elem.get("value")
        unit = elem.get("unit")        # optional, if submodel includes
        range_val = elem.get("range")  # optional, if submodel includes
        subitems = elem.get("subitems", [])

        if model_type == "Property":
            sensors.append({
                "idShort": id_short,
                "valueType": value_type,
                "value": value,
                "unit": unit,
                "range": range_val,
                "subitems": subitems
            })

    return sensors
