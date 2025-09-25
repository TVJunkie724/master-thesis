import re
import json
from datetime import datetime

DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d")
MIN_DATE = "0001-01-01"
MIN_DATETIME = "0001-01-01T00:00:00"

def normalize_aas_element(elem):
    """Recursively normalize an AAS element in place."""
    elem_id = elem.get('idShort', elem.get('id', 'unknown'))
    print(f" Normalizing element: {elem_id}")
    try:
        normalize_semantic_ids(elem)
        normalize_languages(elem)
        normalize_dates(elem)
    except Exception as e:
        print(f"Element with id '{elem_id}' is invalid: {json.dumps(elem)}")
        print(f"Error while normalizing: {e}")

def normalize_dates(elem):
    """Recursively normalize dates, convert string dates to xs:date, and fix empty values."""
    val = elem.get("value")
    val_type = elem.get("valueType")

    def parse_date(s):
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    # Only handle string values
    if isinstance(val, str):
        dt = parse_date(val)
        if dt:
            if val_type == "xs:dateTime":
                elem["valueType"] = "xs:dateTime"
                elem["value"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
            else:  # xs:date or string
                elem["valueType"] = "xs:date"
                elem["value"] = dt.strftime("%Y-%m-%d")
        elif val_type in ("xs:date", "xs:dateTime"):
            # empty or unparseable → minimum date
            elem["value"] = MIN_DATETIME if val_type == "xs:dateTime" else MIN_DATE

    elif val_type in ("xs:date", "xs:dateTime") and not val:
        # empty value → minimum date
        elem["value"] = MIN_DATETIME if val_type == "xs:dateTime" else MIN_DATE

    # Recurse into children
    children = []
    for key in ("submodelElements", "value"):
        if isinstance(elem.get(key), list):
            children.extend([c for c in elem[key] if isinstance(c, dict)])
    for child in children:
        normalize_dates(child)

def normalize_semantic_ids(elem):
    """
    Recursively normalize semanticId types:
      - If value is URL/IRI → ExternalReference + GlobalReference
      - Else → ModelReference + ConceptDescription
    """
    sem = elem.get("semanticId")
    if sem and sem.get("type") in ("ExternalReference", "ModelReference"):
        keys = sem.get("keys", [])
        if keys:
            first_key = keys[0]
            val = first_key.get("value", "")
            # simple heuristic: does it look like a URL/IRI?
            if re.match(r"^(https?:|urn:|ftp:)", val, re.IGNORECASE):
                # external → GlobalReference
                sem["type"] = "ExternalReference"
                first_key["type"] = "GlobalReference"
            else:
                # internal → ModelReference
                sem["type"] = "ModelReference"
                first_key["type"] = "ConceptDescription"

    children = []
    if isinstance(elem.get("submodelElements"), list):
        children.extend(elem["submodelElements"])
    if isinstance(elem.get("value"), list):
        children.extend(elem["value"])

    for child in children:
        normalize_semantic_ids(child)     


def normalize_languages(elem):
    """
    Recursively lowercase all language tags in description fields.
    """
    # Fix current element's description language
    descriptions = elem.get("description", [])
    for desc in descriptions:
        lang = desc.get("language")
        if isinstance(lang, str):
            desc["language"] = lang.lower()

    # Recurse into possible children
    children = []
    if isinstance(elem.get("submodelElements"), list):
        children.extend(elem["submodelElements"])
    if isinstance(elem.get("value"), list):
        children.extend(elem["value"])

    for child in children:
        normalize_languages(child)