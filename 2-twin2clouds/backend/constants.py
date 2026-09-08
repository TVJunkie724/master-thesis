"""Local settings and retained offline currency input; no pricing credentials."""

from pathlib import Path

CONFIG_FILE_PATH = Path("/config") / "config.json"

# Keep the historical path used by the offline five-layer currency converter.
# Active Six-layer currency rates are pinned inside the provider rate cards.
CURRENCY_CONVERSION_FILE_PATH = Path("json") / "fetched_data" / "currency.json"
