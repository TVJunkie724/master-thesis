import requests
from py.logger import logger
from decimal import Decimal, getcontext
from py.config_loader import load_currency_convertion_file

getcontext().prec = 12  # 12–18 digits is plenty for currency conversions

def usd_to_eur(amount_usd: float) -> float:
    """Convert USD to EUR with high precision."""
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        data = resp.json()
        if data.get("result") == "success":
            rate = Decimal(str(data["rates"]["EUR"]))
            amount = Decimal(str(amount_usd)) * rate
            return float(amount.quantize(Decimal("0.000000000001")))  # 12 decimal places
        else:
            raise ValueError("Failed to fetch conversion rate from API.")
    except Exception as e:
        logger.warning(f"Currency conversion error: {e}")
        logger.warning("Failed to fetch currency conversion rate, using fallback rate.")
        # Fallback conversion rate
        conversion_data = load_currency_convertion_file()
        rate = Decimal(str(conversion_data["usd_to_eur_rate"]))
        logger.warning(f"Using fallback USD to EUR rate: {rate}")
        amount = Decimal(str(amount_usd)) * Decimal(rate)
        return float(amount.quantize(Decimal("0.000000000001")))
    
    
def eur_to_usd(amount_eur: float) -> float:
    """Convert EUR to USD with high precision."""
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=5)
        data = resp.json()
        if data.get("result") == "success":
            rate = Decimal(str(data["rates"]["USD"]))
            amount = Decimal(str(amount_eur)) * rate
            return float(amount.quantize(Decimal("0.000000000001")))  # 12 decimal places
        else:
            raise ValueError("Failed to fetch conversion rate from API.")
    except Exception as e:
        logger.warning(f"Currency conversion error: {e}")
        logger.warning("Failed to fetch currency conversion rate, using fallback rate.")
        # Fallback conversion rate
        conversion_data = load_currency_convertion_file()
        rate = Decimal(str(conversion_data["eur_to_usd_rate"]))
        logger.warning(f"Using fallback EUR to USD rate: {rate}")
        amount = Decimal(str(amount_eur)) * Decimal(rate)
        return float(amount.quantize(Decimal("0.000000000001")))