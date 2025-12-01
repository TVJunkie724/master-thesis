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
    if not data:
        return {"status": "missing", "missing_keys": []}

    expected_schema = {
        "aws": {
            "transfer": ["pricing_tiers", "egressPrice"],
            "iotCore": ["pricePerDeviceAndMonth", "priceRulesTriggered", "pricing_tiers"],
            "lambda": ["requestPrice", "durationPrice", "freeRequests", "freeComputeTime"],
            "dynamoDB": ["writePrice", "readPrice", "storagePrice", "freeStorage"],
            "s3InfrequentAccess": ["storagePrice", "upfrontPrice", "requestPrice", "dataRetrievalPrice", "transferCostFromDynamoDB", "transferCostFromCosmosDB"],
            "s3GlacierDeepArchive": ["storagePrice", "lifecycleAndWritePrice", "dataRetrievalPrice"],
            "iotTwinMaker": ["unifiedDataAccessAPICallsPrice", "entityPrice", "queryPrice"],
            "awsManagedGrafana": ["editorPrice", "viewerPrice"],
            "stepFunctions": ["pricePer1kStateTransitions"],
            "eventBridge": ["pricePerMillionEvents"],
            "apiGateway": ["pricePerMillionCalls", "dataTransferOutPrice"]
        },
        "azure": {
            "transfer": ["pricing_tiers"],
            "iotHub": ["pricing_tiers"], # IoT Hub structure is complex, just check root
            "functions": ["requestPrice", "durationPrice", "freeRequests", "freeComputeTime"],
            "cosmosDB": ["requestPrice", "minimumRequestUnits", "RUsPerRead", "RUsPerWrite", "storagePrice"],
            "blobStorageCool": ["storagePrice", "upfrontPrice", "writePrice", "readPrice", "dataRetrievalPrice", "transferCostFromCosmosDB"],
            "blobStorageArchive": ["storagePrice", "writePrice", "dataRetrievalPrice"],
            "azureDigitalTwins": ["messagePrice", "operationPrice", "queryPrice", "queryUnitTiers"],
            "azureManagedGrafana": ["userPrice", "hourlyPrice"],
            "logicApps": ["pricePer1kStateTransitions"],
            "eventGrid": ["pricePerMillionEvents"],
            "apiManagement": ["pricePerMillionCalls"]
        },
        "gcp": {
            "transfer": ["pricing_tiers", "egressPrice"],
            "iot": ["pricePerGiB", "pricePerDeviceAndMonth"],
            "functions": ["requestPrice", "durationPrice", "freeRequests", "freeComputeTime"],
            "storage_hot": ["writePrice", "readPrice", "storagePrice", "freeStorage"],
            "storage_cool": ["storagePrice", "upfrontPrice", "requestPrice", "dataRetrievalPrice"],
            "storage_archive": ["storagePrice", "lifecycleAndWritePrice", "dataRetrievalPrice"],
            "twinmaker": ["e2MediumPrice", "storagePrice"],
            "grafana": ["e2MediumPrice", "storagePrice"],
            "apiGateway": ["pricePerMillionCalls", "dataTransferOutPrice"],
            "cloudWorkflows": ["stepPrice"],
            "cloudScheduler": ["jobPrice"]
        }
    }

    provider_schema = expected_schema.get(provider)
    if not provider_schema:
        return {"status": "unknown_provider", "missing_keys": []}

    missing_keys = []
    
    for service, keys in provider_schema.items():
        if service not in data:
            missing_keys.append(f"{service} (missing service)")
            continue
            
        service_data = data[service]
        if not isinstance(service_data, dict):
             # Some services might not be dicts if schema changed, but here we expect dicts
             continue

        for key in keys:
            if key not in service_data:
                missing_keys.append(f"{service}.{key}")

    if missing_keys:
        return {"status": "incomplete", "missing_keys": missing_keys}
    
    return {"status": "valid", "missing_keys": []}