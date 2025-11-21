"""
calculate_up_to_date_pricing.py
--------------------------------
Generates up-to-date multi-cloud pricing JSON.
Uses dynamic AWS fetching and placeholders for Azure & Google.
"""

import json
import traceback
from pathlib import Path
import py.config_loader as config_loader
import py.constants as CONSTANTS
from py.logger import logger
from py.cloud_price_fetcher_aws import fetch_aws_price, STATIC_DEFAULTS
from py.cloud_price_fetcher_azure import fetch_azure_price, STATIC_DEFAULTS_AZURE
# Future:
# from py.cloud_price_fetcher_google import fetch_google_price


# ============================================================
# ENTRYPOINT
# ============================================================
def calculate_up_to_date_pricing(additional_debug = False):
    logger.info("🔄 Starting multi-cloud pricing update...")

    credentials = config_loader.load_credentials_file()
    providers_config = config_loader.load_json_file(CONSTANTS.SERVICE_CALC_PARAMS_FILE_PATH)

    output = {}
    
    service_mapping = config_loader.load_json_file(CONSTANTS.SERVICE_MAPPING_FILE_PATH)


    if "aws" in credentials:
        print("")
        logger.info("========================================================")
        logger.info("Fetching AWS pricing...")
        logger.info("========================================================")
        aws_credentials = credentials.get("aws", {})
        output["aws"] = fetch_aws_data(aws_credentials, service_mapping, providers_config.get("aws", {}), additional_debug)

    ## TODO - TESTING ONLY
    additional_debug = True
    if "azure" in credentials:
        print("")
        logger.info("========================================================")
        logger.info("Fetching Azure pricing...")
        logger.info("========================================================")
        azure_credentials = credentials.get("azure", {})
        output["azure"] = fetch_azure_data(azure_credentials, service_mapping, providers_config.get("azure", {}), additional_debug)

    if "gcp" in credentials:
        print("")
        logger.info("========================================================")
        logger.info("Fetching GCP pricing...")
        logger.info("========================================================")
        google_credentials = credentials.get("gcp", {})
        output["gcp"] = fetch_google_data(google_credentials, service_mapping, providers_config.get("gcp", {}), additional_debug)

    Path(CONSTANTS.DYNAMIC_PRICING_FILE_PATH).write_text(json.dumps(output, indent=2))
    print("")
    logger.info("✅ Wrote pricing_dynamic.json successfully!")
    return output


from py.cloud_price_fetcher_aws import STATIC_DEFAULTS
from py.logger import logger

def _get_or_warn(neutral_service, provider_service, key, fetched_dict, default_value):
    """
    Returns a fetched value or default.
    - Logs info if the value is static (in STATIC_DEFAULTS).
    - Logs warning if the value had to fall back.
    """
    if neutral_service in STATIC_DEFAULTS.keys() and key in STATIC_DEFAULTS[neutral_service]:
        logger.info(f"      ℹ️ Using static value for AWS.{provider_service}.{key}")
    if key in fetched_dict and fetched_dict[key] is not None:
        return fetched_dict[key]
    
    
    logger.warning(f"   ⚠️ Using fallback for AWS.{provider_service}.{key} (not returned by API)")
    return default_value


    
# ============================================================
# AWS FETCHING AND SCHEMA BUILD
# ============================================================
def fetch_aws_data(aws_credentials: dict, service_mapping: dict, aws_services_config: dict, additional_debug=False) -> dict:
    """
    Fetches all AWS service pricing using fetch_aws_price()
    and builds the canonical AWS pricing.json structure.
    Prints warnings for all fallback/default values or static defaults.
    """
    region = aws_credentials.get("aws_region", "eu-central-1")
    logger.info(f"🚀 Fetching AWS pricing for region: {region}")

    fetched = {}
    
    # for neutral_service in aws_services_config.keys():
    #     try:
    #         logger.info(f"--- Service: {neutral_service} ---")
    #         fetched[neutral_service] = fetch_aws_price(aws_credentials, service_mapping, neutral_service, region, additional_debug)
    #     except Exception as e:
    #         logger.debug(traceback.format_exc())
    #         logger.error(f"⚠️ Failed to fetch AWS service {neutral_service}: {e}")
    #         fetched[neutral_service] = {}

    logger.info("🧩 Building AWS pricing schema...")
    aws = {}

    neutral_service, provider_service = "transfer", "transfer"
    transfer = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "pricing_tiers": transfer.get("pricing_tiers", {
            "freeTier": {"limit": 100, "price": 0},
            "tier1": {"limit": 10240, "price": 0.09},
            "tier2": {"limit": 51200, "price": 0.085},
            "tier3": {"limit": 102400, "price": 0.07},
            "tier4": {"limit": "Infinity", "price": 0.05},
        }),
    }
    aws["egressPrice"] = _get_or_warn(neutral_service, provider_service, "egressPrice", transfer, 0.09)

    neutral_service, provider_service = "iot", "iotCore"
    iot = fetched.get(neutral_service, {})
    message_tiers = iot.get("messageTiers", {})
    aws[provider_service] = {
        "pricePerDeviceAndMonth": _get_or_warn(neutral_service, provider_service, "pricePerDeviceAndMonth", iot, 0.0035),
        "priceRulesTriggered": _get_or_warn(neutral_service, provider_service, "priceRulesTriggered", iot, 0.00000015),
        "pricing_tiers": {
            "tier1": {"limit": 1_000_000_000, "price": message_tiers.get("tier_first", 0.000001)},
            "tier2": {"limit": 5_000_000_000, "price": message_tiers.get("tier_next", 0.0000008)},
            "tier3": {"limit": "Infinity", "price": message_tiers.get("tier_over", 0.0000007)},
        },
    }

    neutral_service, provider_service = "functions", "lambda"
    fn = fetched.get(neutral_service, {})
    duration_tiers = fn.get("durationTiers", {})
    aws[provider_service] = {
        "requestPrice": _get_or_warn(neutral_service, provider_service, "requestPrice", fn, 0.0000002),
        "durationPrice": duration_tiers.get("tier1", 0.0000166667),
        "freeRequests": _get_or_warn(neutral_service, provider_service, "freeRequests", fn, 1_000_000),
        "freeComputeTime": _get_or_warn(neutral_service, provider_service, "freeComputeTime", fn, 400_000),
    }

    neutral_service, provider_service = "storage_hot", "dynamoDB"
    ddb = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "writePrice": _get_or_warn(neutral_service, provider_service, "writePrice", ddb, 0.000000625),
        "readPrice": _get_or_warn(neutral_service, provider_service, "readPrice", ddb, 0.000000125),
        "storagePrice": _get_or_warn(neutral_service, provider_service, "storagePrice", ddb, 0.25),
        "freeStorage": _get_or_warn(neutral_service, provider_service, "freeStorage", ddb, 25),
    }

    neutral_service, provider_service = "storage_cool", "s3InfrequentAccess"
    s3ia = fetched.get(neutral_service, {})
    egress_price = aws["egressPrice"]
    aws[provider_service] = {
        "storagePrice": _get_or_warn(neutral_service, provider_service, "storagePrice", s3ia, 0.0125),
        "upfrontPrice": _get_or_warn(neutral_service, provider_service, "upfrontPrice", s3ia, 0.0001),
        "requestPrice": _get_or_warn(neutral_service, provider_service, "requestPrice", s3ia, 0.00001),
        "dataRetrievalPrice": _get_or_warn(neutral_service, provider_service, "dataRetrievalPrice", s3ia, 0.01),
        "transferCostFromDynamoDB": round(egress_price * 1.1, 8),
        "transferCostFromCosmosDB": round(egress_price * 0.55, 8),
    }

    neutral_service, provider_service = "storage_archive", "s3GlacierDeepArchive"
    s3ga = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "storagePrice": _get_or_warn(neutral_service, provider_service, "storagePrice", s3ga, 0.00099),
        "lifecycleAndWritePrice": _get_or_warn(neutral_service, provider_service, "lifecycleAndWritePrice", s3ga, 0.00005),
        "dataRetrievalPrice": _get_or_warn(neutral_service, provider_service, "dataRetrievalPrice", s3ga, 0.0025),
    }

    neutral_service, provider_service = "twinmaker", "iotTwinMaker"
    tm = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "unifiedDataAccessAPICallsPrice": _get_or_warn(neutral_service, provider_service, "unifiedDataAccessAPICallsPrice", tm, 0.0000015),
        "entityPrice": _get_or_warn(neutral_service, provider_service, "entityPrice", tm, 0.05),
        "queryPrice": _get_or_warn(neutral_service, provider_service, "queryPrice", tm, 0.00005),
    }

    neutral_service, provider_service = "grafana", "awsManagedGrafana"
    gf = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "editorPrice": _get_or_warn(neutral_service, provider_service, "editorPrice", gf, 9.0),
        "viewerPrice": _get_or_warn(neutral_service, provider_service, "viewerPrice", gf, 5.0),
    }

    logger.info("✅ AWS pricing schema built successfully.")
    return aws



# ============================================================
# FETCHING AZURE DATA AND SCHEMA BUILD
# ============================================================
def fetch_azure_data(azure_credentials: dict, service_mapping: dict, azure_services_config: dict, additional_debug=False) -> dict:
    """
    Placeholder for Azure fetching — iterates through config like AWS,
    builds canonical structure, logs defaults (fetching not yet implemented).
    """
    region = azure_credentials.get("azure_region", "westeurope")
    logger.info(f"🚀 Fetching Azure pricing for region: {region}")
    
    fetched = {}

    for neutral_service_name in azure_services_config.keys():
        try:
            logger.info(f"--- Azure Service: {neutral_service_name} ---")
            fetched[neutral_service_name] = fetch_azure_price(service_mapping, neutral_service_name, region, additional_debug)
        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"⚠️ Failed to fetch Azure service {neutral_service_name}: {e}")
            fetched[neutral_service_name] = {}
        
    
    logger.info(f"🚀 Building Azure structure (region: {region})")
    print(json.dumps(fetched, indent=2))
    azure = {}

    # Transfer
    azure["transfer"] = {
        "pricing_tiers": {
            "freeTier": {"limit": 100, "price": 0},
            "tier1": {"limit": 10240, "price": 0.08},
            "tier2": {"limit": 40960, "price": 0.065},
            "tier3": {"limit": 102400, "price": 0.06},
            "tier4": {"limit": "Infinity", "price": 0.04},
        }
    }

    # IoT Hub
    azure["iotHub"] = {
        "pricing_tiers": {
            "tier1": {"limit": 120_000_000, "threshold": 12_000_000, "price": 25},
            "tier2": {"limit": 1_800_000_000, "threshold": 180_000_000, "price": 250},
            "tier3": {"limit": "Infinity", "threshold": 9_000_000_000, "price": 2500},
        }
    }

    # Azure Functions
    azure["functions"] = {
        "requestPrice": 0.0000002,
        "durationPrice": 0.0000166667,
        "freeRequests": 1_000_000,
        "freeComputeTime": 400_000,
    }

    # CosmosDB (storage_hot)
    azure["cosmosDB"] = {
        "storagePrice": 0.25,
        "requestPrice": 0.0584,
        "minimumRequestUnits": 400,
        "RUsPerWrite": 1,
        "RUsPerRead": 10,
    }

    # Blob Storage Cool (storage_cool)
    azure["blobStorageCool"] = {
        "storagePrice": 0.015,
        "writePrice": 0.00001,
        "readPrice": 0.000001,
        "dataRetrievalPrice": 0.01,
        "transferCostFromCosmosDB": 0.05,
    }

    # Blob Storage Archive (storage_archive)
    azure["blobStorageArchive"] = {
        "storagePrice": 0.00099,
        "writePrice": 0.000013,
        "dataRetrievalPrice": 0.02,
    }

    # Azure Digital Twins
    azure["azureDigitalTwins"] = {
        "messagePrice": 0.000001,
        "operationPrice": 0.0000025,
        "queryPrice": 0.0000005,
        "queryUnitTiers": [
            {"lower": 1, "upper": 99, "value": 15},
            {"lower": 100, "upper": 9999, "value": 1500},
            {"lower": 10000, "value": 4000},
        ],
    }

    # Managed Grafana
    azure["azureManagedGrafana"] = {"userPrice": 6.0, "hourlyPrice": 0.069}

    logger.info("✅ Azure placeholder schema built successfully.")
    return azure


# ============================================================
# GOOGLE PLACEHOLDER STRUCTURE
# ============================================================
def fetch_google_data(google_credentials: dict, service_mapping: dict, google_services_config: dict, additional_debug=False) -> dict:
    region = google_credentials.get("gcp_region", "europe-west1")
    logger.info(f"🚀 Fetching Google Cloud pricing for region: {region}")
    logger.warning(f"⚠️ Google Cloud fetching not implemented yet (region: {region}).")
    return {}
