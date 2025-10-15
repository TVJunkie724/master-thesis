import re
import json
import mimetypes
import os
from datetime import datetime

DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d")
MIN_DATE = "0001-01-01"
MIN_DATETIME = "0001-01-01T00:00:00"

def normalize_aas_element(elem):
    """Recursively normalize an AAS element or submodel in place."""
    elem_id = elem.get('idShort', elem.get('id', 'unknown'))
    print(f"Normalizing element: {elem_id}")
    try:
        normalize_idshort(elem)
        normalize_semantic_ids(elem)
        normalize_languages(elem)
        normalize_dates(elem)
        normalize_content_type(elem)

    except Exception as e:
        print(f"Element with id '{elem_id}' is invalid: {json.dumps(elem)}")
        print(f"Error while normalizing: {e}")

def normalize_content_type(elem):
    """
    Recursively normalize contentType in File elements.
    If contentType is empty, guess from file extension or use a safe default.
    """
    if isinstance(elem, dict):
        if elem.get("modelType") == "File":
            if not elem.get("contentType"):
                guessed, _ = mimetypes.guess_type(elem.get("value", ""))
                elem["contentType"] = guessed or "application/octet-stream"


        # Recurse into child elements
        for key in ("submodelElements", "value"):
            if isinstance(elem.get(key), list):
                for child in elem[key]:
                    normalize_content_type(child)

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
    Recursively normalize reference-like fields in AAS/Submodel elements:
      - If value is URL/IRI → ExternalReference + GlobalReference
      - Else → ModelReference + ConceptDescription (for semanticId)
      - derivedFrom → ModelReference + AssetAdministrationShell
      - first/second (e.g., in RelationshipElement) normalized accordingly
    """
    def normalize_reference(ref, default_first_key_type=None):
        if not isinstance(ref, dict):
            return
        if "type" not in ref or "keys" not in ref:
            return

        keys = ref.get("keys", [])
        if not keys:
            return

        first_key = keys[0]
        val = first_key.get("value", "")

        # If value looks like a URL/IRI → ExternalReference
        if re.match(r"^(https?:|urn:|ftp:)", val, re.IGNORECASE):
            ref["type"] = "ExternalReference"
            first_key["type"] = "GlobalReference"
        else:
            # Otherwise internal reference
            if ref.get("type") in ("ExternalReference", "ModelReference"):
                ref["type"] = "ModelReference"
            if default_first_key_type:
                first_key["type"] = default_first_key_type

    # --- normalize semanticId
    sem = elem.get("semanticId")
    normalize_reference(sem, default_first_key_type="ConceptDescription")

    # --- normalize derivedFrom (AAS)
    derived = elem.get("derivedFrom")
    if derived:
        normalize_reference(derived, default_first_key_type="AssetAdministrationShell")
        derived["type"] = "ModelReference"

    # --- normalize relationship references (first/second)
    for rel_field in ("first", "second"):
        ref = elem.get(rel_field)
        if ref:
            normalize_reference(ref)

    # --- recurse into children
    children = []
    if isinstance(elem.get("submodelElements"), list):
        children.extend(elem["submodelElements"])
    if isinstance(elem.get("value"), list):
        children.extend(elem["value"])

    for child in children:
        normalize_semantic_ids(child)


def normalize_languages(elem):
    """
    Recursively:
    - lowercase all 'language' strings
    - remove objects where:
        * only keys are 'language' and 'text'
        * and both are empty/whitespace
    """
    if isinstance(elem, dict):
        # Lowercase if key == "language"
        if "language" in elem and isinstance(elem["language"], str):
            elem["language"] = elem["language"].strip().lower()

        # Clean nested values
        for k, v in list(elem.items()):
            if isinstance(v, (dict, list)):
                elem[k] = normalize_languages(v)

    elif isinstance(elem, list):
        cleaned = []
        for item in elem:
            item = normalize_languages(item)
            if isinstance(item, dict):
                keys = set(item.keys())
                lang = item.get("language", "").strip()
                text = item.get("text", "").strip()
                # Remove only if it's *exactly* a language/text pair and both empty
                if keys.issubset({"language", "text"}) and lang == "" and text == "":
                    continue
            cleaned.append(item)
        return cleaned

    return elem


def to_pascal_case(name: str) -> str:
    """Convert a string to PascalCase, keeping only letters/digits."""
    parts = re.split(r'[^A-Za-z0-9]+', name)
    return ''.join(p.capitalize() for p in parts if p)

def normalize_idshort(elem):
    """
    Recursively normalize idShort into PascalCase:
      - Split on spaces, hyphens, underscores, etc.
      - Capitalize each word
      - Remove invalid characters
      - If starts with a number, prefix with 'X'
    """
    idshort = elem.get("idShort")
    if isinstance(idshort, str):
        pascal = to_pascal_case(idshort)
        # Prefix with 'X' if first character is not a letter
        if not pascal or not pascal[0].isalpha():
            pascal = "X_" + pascal
        elem["idShort"] = pascal

    # Recurse into nested elements
    children = []
    if isinstance(elem.get("submodelElements"), list):
        children.extend(elem["submodelElements"])
    if isinstance(elem.get("value"), list):
        children.extend(elem["value"])

    for child in children:
        normalize_idshort(child)
