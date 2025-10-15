import base64
from services.config_loader import load_config

def encode_id(aas_id: str) -> str:
    """Encode AAS ID for server: URL-safe Base64 without padding."""
    b = aas_id.encode("utf-8")
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def debug_write_to_file(file_content, file_name, overwrite=True):
    
    cfg = load_config()
    mode = cfg["mode"]
    
    if mode == "DEBUG":
        with open(f"debug/{file_name}.log", "w" if overwrite else "a") as f:
            f.write(f"\n{file_content}")
