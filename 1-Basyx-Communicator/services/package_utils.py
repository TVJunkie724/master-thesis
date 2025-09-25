import base64
from urllib.parse import quote
import requests

from aasx_utils import download_aasx  # re-use your existing helper
REQUEST_TIMEOUT = 30

def _safe_b64decode(s):
    """Try to base64-decode s, return decoded str or None."""
    try:
        # add required padding
        padding = (-len(s)) % 4
        return base64.b64decode(s + ("=" * padding)).decode("utf-8")
    except Exception:
        return None

def list_packages(aasx_base):
    """Return raw packages list (list of dicts)."""
    url = f"{aasx_base.rstrip('/')}/packages"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    return j.get("result", j)

def find_package_for_aas(aas_id, aasx_base):
    """
    Return a packageId for the given aas_id, or None.
    Tries:
      - direct equality with package['aasIds'] entries
      - URL-encoded aas_id
      - base64 encoded aas_id (no padding)
      - decode package aasId values if they look base64 and compare
    """
    packages = list_packages(aasx_base)
    if not packages:
        return None

    raw = aas_id
    urlenc = quote(aas_id, safe="")
    b64 = base64.b64encode(aas_id.encode("utf-8")).decode("utf-8").rstrip("=")
    b64_urlsafe = base64.urlsafe_b64encode(aas_id.encode("utf-8")).decode("utf-8").rstrip("=")

    for p in packages:
        pkg_id = p.get("packageId")
        for aid in p.get("aasIds", []):
            if not isinstance(aid, str):
                continue
            # direct matches
            if aid == raw or aid == urlenc or aid == b64 or aid == b64_urlsafe:
                return pkg_id
            # try decoding the package entry if it might be base64
            decoded = _safe_b64decode(aid)
            if decoded and decoded == aas_id:
                return pkg_id
    return None

def download_package_by_id(aasx_base, package_id):
    """Download the package binary (.aasx) for packageId and return BytesIO via download_aasx."""
    url = f"{aasx_base.rstrip('/')}/packages/{package_id}"
    return download_aasx(url)
