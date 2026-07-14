import requests
from backend.logger import logger
from decimal import Decimal, getcontext
import backend.config_loader as config_loader
import backend.utils as utils
import backend.constants as CONSTANTS
from datetime import datetime, timezone
from math import isfinite
from backend.pricing_schema import validate_pricing_payload
from backend.pricing_cache import write_json_atomically

getcontext().prec = 28  # Increase precision to avoid InvalidOperation

def get_currency_rates() -> dict:
    """
    Fetch currency rates (USD to EUR and EUR to USD) with caching.
    """
    # Check if we have a fresh local file
    if utils.is_file_fresh(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH, max_age_days=1):
        cached = config_loader.load_json_file(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)
        try:
            _validated_rate(cached.get("usd_to_eur_rate"))
            _validated_rate(cached.get("eur_to_usd_rate"))
            return cached
        except ValueError as exc:
            logger.warning("Fresh currency-rate snapshot is invalid: %s", exc)

    logger.info("Fetching fresh currency rates from API...")

    try:
        resp_usd = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        resp_usd.raise_for_status()
        data_usd = resp_usd.json()
        if data_usd.get("result") != "success":
            raise ValueError("Exchange-rate provider returned an unsuccessful response")
        usd_to_eur_rate = _validated_rate(data_usd.get("rates", {}).get("EUR"))
        rates = {
            "usd_to_eur_rate": usd_to_eur_rate,
            "eur_to_usd_rate": 1.0 / usd_to_eur_rate,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source": "open.er-api.com/v6/latest/USD",
        }
            
        write_json_atomically(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH, rates)
            
        logger.info(f"✅ Saved fresh currency rates to {CONSTANTS.CURRENCY_CONVERSION_FILE_PATH}")
        return rates

    except Exception as e:
        logger.warning(f"Failed to fetch currency rates: {e}")
        if utils.file_exists(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH):
            logger.warning("Using the last cached currency-rate snapshot.")
            cached = config_loader.load_json_file(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)
            try:
                _validated_rate(cached.get("usd_to_eur_rate"))
                _validated_rate(cached.get("eur_to_usd_rate"))
                return cached
            except ValueError as cache_error:
                raise RuntimeError(
                    "No valid currency-rate snapshot is available"
                ) from cache_error
        raise RuntimeError("No valid currency-rate snapshot is available") from e


def _validated_rate(value) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError("Exchange rate is missing or not numeric")
    rate = float(value)
    if not isfinite(rate) or rate <= 0:
        raise ValueError("Exchange rate must be finite and positive")
    return rate


def usd_to_eur(amount_usd: float) -> float:
    """Convert USD to EUR with high precision."""
    rates = get_currency_rates()
    rate = Decimal(str(_validated_rate(rates["usd_to_eur_rate"])))
    amount = Decimal(str(amount_usd)) * rate
    return float(amount.quantize(Decimal("0.000000000001")))

    
def eur_to_usd(amount_eur: float) -> float:
    """Convert EUR to USD with high precision."""
    rates = get_currency_rates()
    rate = Decimal(str(_validated_rate(rates["eur_to_usd_rate"])))
    amount = Decimal(str(amount_eur)) * rate
    return float(amount.quantize(Decimal("0.000000000001")))

def validate_pricing_schema(provider: str, data: dict) -> dict:
    """
    Validates that the pricing data contains all expected keys for the given provider.
    
    Args:
        provider (str): 'aws', 'azure', or 'gcp'
        data (dict): The loaded pricing JSON data
        
    Returns:
        dict: {
            "status": "valid" | "incomplete" | "missing",
            "missing_keys": [list of missing keys]
        }
    """
    return validate_pricing_payload(provider, data)
