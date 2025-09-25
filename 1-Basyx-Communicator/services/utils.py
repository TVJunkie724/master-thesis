import base64

def encode_id(aas_id: str) -> str:
    """Encode AAS ID for server: URL-safe Base64 without padding."""
    b = aas_id.encode("utf-8")
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")
