import zipfile
import json
import requests
from io import BytesIO

REQUEST_TIMEOUT = 30

def download_aasx(url):
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return BytesIO(resp.content)

def extract_aas_json(aasx_bytes):
    with zipfile.ZipFile(aasx_bytes) as zf:
        candidates = [n for n in zf.namelist() if n.lower().endswith(".json")]
        if not candidates:
            raise RuntimeError("No JSON file found in AASX package.")
        preferred = next((c for c in candidates if c.lower().endswith("aas.json")), candidates[0])
        with zf.open(preferred) as fh:
            return json.load(fh)
