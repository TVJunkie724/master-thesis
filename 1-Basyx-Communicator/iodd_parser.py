import zipfile
import xml.etree.ElementTree as ET

def parse_iodd_zip_combined(zip_path):
    results = []
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        for file in zipf.namelist():
            if not file.endswith(".xml"):
                continue
            xml_data = zipf.read(file)
            root = ET.fromstring(xml_data)

            # Safely get DeviceIdentity
            device_elem = root.find(".//DeviceIdentity")
            if device_elem is not None:
                vendor = device_elem.attrib.get("vendorName")
                device = device_elem.attrib.get("deviceId")
                device_id = device_elem.attrib.get("deviceId")
            else:
                vendor = None
                device = None
                device_id = None

            results.append({
                "file": file,
                "vendor": vendor,
                "device": device,
                "device_id": device_id,
                "process_data": []  # keep empty or parse as needed
            })
    return results


def parse_process_data(root):
    """Parse process data elements, minimal info (name/unit not in ZIP)."""
    pd_list = []
    for pd in root.findall(".//ProcessData/ProcessDataIn") + root.findall(".//ProcessData/ProcessDataOut"):
        pd_list.append({
            "id": pd.attrib.get("id"),
            "pd_type": pd.tag.split("}")[-1]
        })
    return pd_list

def enrich_zip_with_aas(zip_data, aas_elements):
    """Enrich process data with human-readable names from AAS elements."""
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
                "unit": aas_info.get("unit"),
                "range": aas_info.get("range"),
                "subitems": aas_info.get("subitems", [])
            })

        enriched_device["process_data"] = enriched_process_data
        enriched.append(enriched_device)

    return {"result": enriched}
