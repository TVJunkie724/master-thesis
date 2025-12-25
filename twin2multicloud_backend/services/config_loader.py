import json

def load_config(path="config.json"):
    """Load configuration from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
