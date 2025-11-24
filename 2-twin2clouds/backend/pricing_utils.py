import requests
from backend.logger import logger
from decimal import Decimal, getcontext
import backend.config_loader as config_loader
import backend.utils as utils
import backend.constants as CONSTANTS
import json
import time

getcontext().prec = 28  # Increase precision to avoid InvalidOperation

def get_currency_rates() -> dict:
    """
    Fetch currency rates (USD to EUR and EUR to USD) with caching.
    """
    # Check if we have a fresh local file
    if utils.is_file_fresh(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH, max_age_days=1):
        return config_loader.load_json_file(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)

    logger.info("Fetching fresh currency rates from API...")
    rates = {"usd_to_eur_rate": 0.92, "eur_to_usd_rate": 1.09} # Default fallback

    try:
        # Fetch USD -> EUR
        resp_usd = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        data_usd = resp_usd.json()
        if data_usd.get("result") == "success":
            rates["usd_to_eur_rate"] = float(data_usd["rates"]["EUR"])

        # Fetch EUR -> USD
        resp_eur = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=5)
        data_eur = resp_eur.json()
        if data_eur.get("result") == "success":
            rates["eur_to_usd_rate"] = float(data_eur["rates"]["USD"])
            
        # Save to file
        with open(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH, "w") as f:
            json.dump(rates, f, indent=2)
            
        logger.info(f"✅ Saved fresh currency rates to {CONSTANTS.CURRENCY_CONVERSION_FILE_PATH}")
        return rates

    except Exception as e:
        logger.warning(f"Failed to fetch currency rates: {e}")
        if utils.file_exists(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH):
             logger.warning("Using stale local currency file.")
             return config_loader.load_json_file(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)
        logger.error("No local currency file found. Using hardcoded defaults.")
        return rates


def usd_to_eur(amount_usd: float) -> float:
    """Convert USD to EUR with high precision."""
    try:
        rates = get_currency_rates()
        rate = Decimal(str(rates["usd_to_eur_rate"]))
        amount = Decimal(str(amount_usd)) * rate
        return float(amount.quantize(Decimal("0.000000000001")))
    except Exception as e:
        logger.error(f"Currency conversion error (USD->EUR): {e}")
        return amount_usd # Fallback: return original amount

    
def eur_to_usd(amount_eur: float) -> float:
    """Convert EUR to USD with high precision."""
    try:
        rates = get_currency_rates()
        rate = Decimal(str(rates["eur_to_usd_rate"]))
        amount = Decimal(str(amount_eur)) * rate
        return float(amount.quantize(Decimal("0.000000000001")))
    except Exception as e:
        logger.error(f"Currency conversion error (EUR->USD): {e}")
        return amount_eur # Fallback: return original amount