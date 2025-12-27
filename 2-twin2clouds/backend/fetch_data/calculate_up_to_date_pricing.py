import json
import traceback
from pathlib import Path
import backend.config_loader as config_loader
import backend.constants as CONSTANTS
from backend.logger import logger
from backend.fetch_data.cloud_price_fetcher_aws import STATIC_DEFAULTS
from backend.fetch_data.cloud_price_fetcher_azure import STATIC_DEFAULTS_AZURE
from backend.fetch_data.cloud_price_fetcher_google import STATIC_DEFAULTS_GCP
from google.cloud import billing_v1
from backend.config_loader import load_gcp_credentials

# Factory Pattern: Centralized creation of price fetcher instances
# All provider-specific fetching is done through the Factory
from backend.fetch_data.factory import PriceFetcherFactory


# ============================================================
# ENTRYPOINT
# ============================================================
def calculate_up_to_date_pricing(target_provider: str, additional_debug = False):
    """
    Fetches pricing for a specific provider and saves it to its dedicated file.
    target_provider must be one of: 'aws', 'azure', 'gcp'.
    """
    logger.info(f"🔄 Starting pricing update for provider: {target_provider}")

    valid_providers = ["aws", "azure", "gcp"]
    if target_provider not in valid_providers:
        raise ValueError(f"Invalid target_provider: {target_provider}. Must be one of {valid_providers}")

    credentials = config_loader.load_credentials_file()
    service_mapping = config_loader.load_service_mapping()
    
    output_data = {}
    target_file_path = None

    if target_provider == "aws":
        if "aws" in credentials:
            print("")
            logger.info("========================================================")
            logger.info("Fetching AWS pricing...")
            logger.info("========================================================")
            
            # Load Region Map
            try:
                region_map = config_loader.load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)
            except Exception as e:
                logger.error(f"Failed to load AWS region map: {e}. Need to fetch regions first.")
                raise e

            aws_credentials = credentials.get("aws", {})
            output_data = fetch_aws_data(aws_credentials, service_mapping, region_map, additional_debug)
            target_file_path = CONSTANTS.AWS_PRICING_FILE_PATH
        else:
            logger.warning("AWS credentials missing, skipping fetch.")

    elif target_provider == "azure":
        if "azure" in credentials:
            print("")
            logger.info("========================================================")
            logger.info("Fetching Azure pricing...")
            logger.info("========================================================")
            
            # Load Region Map
            try:
                region_map = config_loader.load_json_file(CONSTANTS.AZURE_REGIONS_FILE_PATH)
            except Exception as e:
                logger.error(f"Failed to load Azure region map: {e}. Need to fetch regions first.")
                raise e
                
            azure_credentials = credentials.get("azure", {})
            output_data = fetch_azure_data(azure_credentials, service_mapping, region_map, additional_debug)
            target_file_path = CONSTANTS.AZURE_PRICING_FILE_PATH
        else:
            logger.warning("Azure credentials missing, skipping fetch.")

    elif target_provider == "gcp":
        if "gcp" in credentials:
            print("")
            logger.info("========================================================")
            logger.info("Fetching GCP pricing...")
            logger.info("========================================================")
            
            # Load Region Map
            try:
                region_map = config_loader.load_json_file(CONSTANTS.GCP_REGIONS_FILE_PATH)
            except Exception as e:
                logger.error(f"Failed to load GCP region map: {e}. Need to fetch regions first.")
                raise e

            google_credentials = credentials.get("gcp", {})
            output_data = fetch_google_data(google_credentials, service_mapping, region_map, additional_debug)
            target_file_path = CONSTANTS.GCP_PRICING_FILE_PATH
        else:
            logger.warning("GCP credentials missing, skipping fetch.")

    if target_file_path and output_data:
        # Validate schema
        from backend.pricing_utils import validate_pricing_schema
        validation = validate_pricing_schema(target_provider, output_data)
        if validation["status"] != "valid":
            logger.warning(f"⚠️ Pricing data for {target_provider} is incomplete. Missing keys: {validation['missing_keys']}")
            
        Path(target_file_path).write_text(json.dumps(output_data, indent=2))
        print("")
        logger.info(f"✅ Wrote {target_file_path.name} successfully!")
        return output_data
    else:
        logger.warning(f"⚠️ No data fetched for {target_provider} or credentials missing.")
        return {}


def calculate_up_to_date_pricing_with_credentials(target_provider: str, credentials: dict, additional_debug=False):
    """
    Fetches pricing using provided credentials instead of loading from file.
    Used by Management API for credential-forward pricing refresh.
    
    Args:
        target_provider: 'aws' or 'gcp' (Azure uses public API, no credentials needed)
        credentials: Dict with provider-specific credentials
        additional_debug: Enable verbose logging
    
    Returns:
        dict: Pricing data for the provider
    """
    logger.info(f"🔄 Starting pricing update for provider: {target_provider} (with provided credentials)")

    if target_provider not in ["aws", "gcp"]:
        raise ValueError(f"This function only supports aws/gcp, not {target_provider}. Use regular endpoint for Azure.")

    service_mapping = config_loader.load_service_mapping()
    output_data = {}
    target_file_path = None

    if target_provider == "aws":
        logger.info("========================================================")
        logger.info("Fetching AWS pricing with provided credentials...")
        logger.info("========================================================")
        
        # Load Region Map
        try:
            region_map = config_loader.load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)
        except Exception as e:
            logger.error(f"Failed to load AWS region map: {e}")
            raise e

        # Build AWS credentials dict from request
        aws_credentials = {
            "aws_access_key_id": credentials.get("aws_access_key_id"),
            "aws_secret_access_key": credentials.get("aws_secret_access_key"),
            "aws_region": credentials.get("aws_region", "eu-central-1")
        }
        
        # Create boto3 credentials for AWS fetcher
        # IMPORTANT: Always use 'us-east-1' regardless of user's aws_region.
        # The Pricing API is ONLY available in us-east-1, so user's region is
        # irrelevant here. Using us-east-1 also prevents connection errors from
        # invalid region names (AWS STS endpoint URLs are region-based).
        import boto3
        try:
            session = boto3.Session(
                aws_access_key_id=aws_credentials["aws_access_key_id"],
                aws_secret_access_key=aws_credentials["aws_secret_access_key"],
                region_name="us-east-1"  # Pricing API only in us-east-1
            )
            client_credentials = session.get_credentials()
        except Exception as e:
            logger.error(f"Failed to create AWS session: {e}")
            client_credentials = None
        
        output_data = fetch_aws_data(aws_credentials, service_mapping, region_map, additional_debug)
        target_file_path = CONSTANTS.AWS_PRICING_FILE_PATH

    elif target_provider == "gcp":
        logger.info("========================================================")
        logger.info("Fetching GCP pricing with provided credentials...")
        logger.info("========================================================")
        
        # Load Region Map
        try:
            region_map = config_loader.load_json_file(CONSTANTS.GCP_REGIONS_FILE_PATH)
        except Exception as e:
            logger.error(f"Failed to load GCP region map: {e}")
            raise e

        # Parse service account JSON and create credentials
        from google.oauth2 import service_account as gcp_service_account
        
        sa_json = credentials.get("gcp_service_account_json", "{}")
        if isinstance(sa_json, str):
            try:
                sa_info = json.loads(sa_json)
            except json.JSONDecodeError:
                raise ValueError("Invalid GCP service account JSON")
        else:
            sa_info = sa_json
            
        gcp_creds = gcp_service_account.Credentials.from_service_account_info(sa_info)
        
        # Create billing client with provided credentials
        billing_client = billing_v1.CloudCatalogClient(credentials=gcp_creds)
        
        google_credentials = {
            "gcp_region": credentials.get("gcp_region", "europe-west1")
        }
        
        # Fetch with billing_client passed directly
        output_data = fetch_google_data(
            google_credentials, service_mapping, region_map, 
            additional_debug, billing_client
        )
        target_file_path = CONSTANTS.GCP_PRICING_FILE_PATH

    if target_file_path and output_data:
        from backend.pricing_utils import validate_pricing_schema
        validation = validate_pricing_schema(target_provider, output_data)
        if validation["status"] != "valid":
            logger.warning(f"⚠️ Pricing data incomplete. Missing: {validation['missing_keys']}")
            
        Path(target_file_path).write_text(json.dumps(output_data, indent=2))
        logger.info(f"✅ Wrote {target_file_path.name} successfully!")
        return output_data
    else:
        logger.warning(f"⚠️ No data fetched for {target_provider}")
        return {}

# ============================================================
# HELPER FUNCTION
# ============================================================
def _get_or_warn(provider_name, neutral_service, provider_service, key, fetched_dict, default_value, static_defaults):
    """
    Returns a fetched value or default.
    - Logs info if the value is static (in static_defaults).
    - Logs warning if the value had to fall back.
    """
    # Handle None case - if fetcher failed completely
    if fetched_dict is None:
        fetched_dict = {}
    
    is_in_static = neutral_service in static_defaults and key in static_defaults[neutral_service]
    is_in_fetched = key in fetched_dict and fetched_dict[key] is not None

    if is_in_fetched:
        return fetched_dict[key]

    if is_in_static:
        logger.info(f"      ℹ️ Using static value for {provider_name}.{provider_service}.{key}")
        default_value = static_defaults[neutral_service][key]
    else:
        logger.warning(f"   ⚠️ Using fallback for {provider_name}.{provider_service}.{key} (not returned by API)")
    return default_value

# ============================================================
# AWS FETCHING AND SCHEMA BUILD
# ============================================================
def fetch_aws_data(aws_credentials: dict, service_mapping: dict, region_map: dict, additional_debug=False) -> dict:
    """
    Fetches all AWS service pricing using the Factory Pattern
    and builds the canonical AWS pricing.json structure.
    Prints warnings for all fallback/default values or static defaults.
    """
    region = aws_credentials.get("aws_region", "eu-central-1")
    logger.info(f"🚀 Fetching AWS pricing for region: {region}")

    # Load AWS credentials once for all services
    try:
        client_credentials = config_loader.load_aws_credentials()
    except Exception as e:
        logger.error(f"Failed to load AWS credentials: {e}")
        client_credentials = None

    # Factory Pattern: Create AWS fetcher instance
    aws_fetcher = PriceFetcherFactory.create("aws")
    
    fetched = {}
    
    # Fetch AWS services using the Factory-created fetcher
    for neutral_service, service_codes_per_provider in service_mapping.items():
        try:
            service_code = service_codes_per_provider.get("aws", "")

            if not service_code:
                logger.debug(f"ℹ️ Service {neutral_service} has no AWS code, skipping (optional)")
                continue

            logger.info(f"--- Service: {neutral_service} ---")
            # Use Factory-created fetcher with provider-specific kwargs
            fetched[neutral_service] = aws_fetcher.fetch_price(
                service_name=neutral_service,
                region_code=region,
                region_map=region_map,
                debug=additional_debug,
                service_code=service_code,
                aws_credentials=client_credentials
            )
        except ValueError as e:
            logger.error(e)
            raise
        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"⚠️ Failed to fetch AWS service {neutral_service}: {e}")
            fetched[neutral_service] = {}

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
        "egressPrice": _get_or_warn("AWS", neutral_service, provider_service, "egressPrice", transfer, 0.09, STATIC_DEFAULTS)
    }

    neutral_service, provider_service = "iot", "iotCore"
    iot = fetched.get(neutral_service, {})
    message_tiers = iot.get("messageTiers", {})
    aws[provider_service] = {
        "pricePerDeviceAndMonth": _get_or_warn("AWS", neutral_service, provider_service, "pricePerDeviceAndMonth", iot, 0.0035, STATIC_DEFAULTS),
        "priceRulesTriggered": _get_or_warn("AWS", neutral_service, provider_service, "priceRulesTriggered", iot, 0.00000015, STATIC_DEFAULTS),
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
        "requestPrice": _get_or_warn("AWS", neutral_service, provider_service, "requestPrice", fn, 0.0000002, STATIC_DEFAULTS),
        "durationPrice": duration_tiers.get("tier1", 0.0000166667),
        "freeRequests": _get_or_warn("AWS", neutral_service, provider_service, "freeRequests", fn, 1_000_000, STATIC_DEFAULTS),
        "freeComputeTime": _get_or_warn("AWS", neutral_service, provider_service, "freeComputeTime", fn, 400_000, STATIC_DEFAULTS),
    }

    neutral_service, provider_service = "storage_hot", "dynamoDB"
    ddb = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "writePrice": _get_or_warn("AWS", neutral_service, provider_service, "writePrice", ddb, 0.000000625, STATIC_DEFAULTS),
        "readPrice": _get_or_warn("AWS", neutral_service, provider_service, "readPrice", ddb, 0.000000125, STATIC_DEFAULTS),
        "storagePrice": _get_or_warn("AWS", neutral_service, provider_service, "storagePrice", ddb, 0.25, STATIC_DEFAULTS),
        "freeStorage": _get_or_warn("AWS", neutral_service, provider_service, "freeStorage", ddb, 25, STATIC_DEFAULTS),
    }

    neutral_service, provider_service = "storage_cool", "s3InfrequentAccess"
    s3ia = fetched.get(neutral_service, {})
    egress_price = aws["transfer"]["egressPrice"]
    aws[provider_service] = {
        "storagePrice": _get_or_warn("AWS", neutral_service, provider_service, "storagePrice", s3ia, 0.0125, STATIC_DEFAULTS),
        "upfrontPrice": _get_or_warn("AWS", neutral_service, provider_service, "upfrontPrice", s3ia, 0.0001, STATIC_DEFAULTS),
        "requestPrice": _get_or_warn("AWS", neutral_service, provider_service, "requestPrice", s3ia, 0.00001, STATIC_DEFAULTS),
        "dataRetrievalPrice": _get_or_warn("AWS", neutral_service, provider_service, "dataRetrievalPrice", s3ia, 0.01, STATIC_DEFAULTS),
        "transferCostFromDynamoDB": round(egress_price * 1.1, 8),
        "transferCostFromCosmosDB": round(egress_price * 0.55, 8),
    }

    neutral_service, provider_service = "storage_archive", "s3GlacierDeepArchive"
    s3ga = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "storagePrice": _get_or_warn("AWS", neutral_service, provider_service, "storagePrice", s3ga, 0.00099, STATIC_DEFAULTS),
        "lifecycleAndWritePrice": _get_or_warn("AWS", neutral_service, provider_service, "lifecycleAndWritePrice", s3ga, 0.00005, STATIC_DEFAULTS),
        "dataRetrievalPrice": _get_or_warn("AWS", neutral_service, provider_service, "dataRetrievalPrice", s3ga, 0.0025, STATIC_DEFAULTS),
    }

    neutral_service, provider_service = "twinmaker", "iotTwinMaker"
    tm = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "unifiedDataAccessAPICallsPrice": _get_or_warn("AWS", neutral_service, provider_service, "unifiedDataAccessAPICallsPrice", tm, 0.0000015, STATIC_DEFAULTS),
        "entityPrice": _get_or_warn("AWS", neutral_service, provider_service, "entityPrice", tm, 0.05, STATIC_DEFAULTS),
        "queryPrice": _get_or_warn("AWS", neutral_service, provider_service, "queryPrice", tm, 0.00005, STATIC_DEFAULTS),
    }

    neutral_service, provider_service = "grafana", "awsManagedGrafana"
    gf = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "editorPrice": _get_or_warn("AWS", neutral_service, provider_service, "editorPrice", gf, 9.0, STATIC_DEFAULTS),
        "viewerPrice": _get_or_warn("AWS", neutral_service, provider_service, "viewerPrice", gf, 5.0, STATIC_DEFAULTS),
    }

    neutral_service, provider_service = "orchestration", "stepFunctions"
    sf = fetched.get(neutral_service, {})
    price_per_1k = _get_or_warn("AWS", neutral_service, provider_service, "pricePer1kStateTransitions", sf, 0.025, STATIC_DEFAULTS)
    
    # SANITY CHECK: The Pricing API often returns the price per *single* request (e.g. 0.000025) 
    # even when the dimension description says "Per 1,000 State Transitions".
    # If the value is suspiciously low (< 0.001), we assume it's the per-request price 
    # and multiply by 1,000 to normalize it to the expected "Per 1k" unit.
    if price_per_1k < 0.001:
        logger.info(f"   ⚠️ Detected per-request price for Step Functions ({price_per_1k:.8f}). Normalizing to Per 1k.")
        price_per_1k *= 1000.0

    aws[provider_service] = {
        "pricePer1kStateTransitions": price_per_1k,
        "pricePerStateTransition": price_per_1k / 1000.0,
    }

    neutral_service, provider_service = "event_bus", "eventBridge"
    eb = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "pricePerMillionEvents": _get_or_warn("AWS", neutral_service, provider_service, "pricePerMillionEvents", eb, 1.00, STATIC_DEFAULTS),
    }

    neutral_service, provider_service = "data_access", "apiGateway"
    ag = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "pricePerMillionCalls": _get_or_warn("AWS", neutral_service, provider_service, "pricePerMillionCalls", ag, 3.50, STATIC_DEFAULTS),
        "dataTransferOutPrice": aws["transfer"]["egressPrice"],
    }

    neutral_service, provider_service = "scheduler", "scheduler"
    sch = fetched.get(neutral_service, {})
    aws[provider_service] = {
        "jobPrice": _get_or_warn("AWS", neutral_service, provider_service, "jobPrice", sch, 0.000001, STATIC_DEFAULTS),
    }

    logger.info("✅ AWS pricing schema built successfully.")
    return aws



# ============================================================
# FETCHING AZURE DATA AND SCHEMA BUILD
# ============================================================
def fetch_azure_data(azure_credentials: dict, service_mapping: dict, region_map: dict, additional_debug=False) -> dict:
    """
    Fetches Azure pricing using the Factory Pattern and builds the canonical structure.
    """
    region = azure_credentials.get("azure_region", "westeurope")
    logger.info(f"🚀 Fetching Azure pricing for region: {region}")
    
    # Factory Pattern: Create Azure fetcher instance
    azure_fetcher = PriceFetcherFactory.create("azure")
    
    fetched = {}

    for neutral_service, service_codes_per_provider in service_mapping.items():
        try:
            service_code = service_codes_per_provider.get("azure", "")

            if not service_code:
                logger.debug(f"ℹ️ Service {neutral_service} has no Azure code, skipping (optional)")
                continue

            logger.info(f"--- Azure Service: {neutral_service} ---")
            # Use Factory-created fetcher with provider-specific kwargs
            fetched[neutral_service] = azure_fetcher.fetch_price(
                service_name=neutral_service,
                region_code=region,
                region_map=region_map,
                debug=additional_debug,
                service_mapping=service_mapping
            )
        except ValueError as e:
            logger.error(e)
            raise
        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"⚠️ Failed to fetch Azure service {neutral_service}: {e}")
            fetched[neutral_service] = {}
        
    
    logger.info(f"🚀 Building Azure structure (region: {region})")
    
    azure = {}

    # Transfer
    neutral_service, provider_service = "transfer", "transfer"
    transfer = fetched.get(neutral_service, {})
    azure[provider_service] = {
        "pricing_tiers": transfer.get("pricing_tiers", {
            "freeTier": {"limit": 100, "price": 0},
            "tier1": {"limit": 10240, "price": 0.087}, 
            "tier2": {"limit": 51200, "price": 0.083},
            "tier3": {"limit": 102400, "price": 0.07},
            "tier4": {"limit": "Infinity", "price": 0.05},
        })
    }

    # IoT Hub
    neutral_service, provider_service = "iot", "iotHub"
    iot = fetched.get(neutral_service, {})
    if "pricing_tiers" not in iot:
        logger.warning(f"   ⚠️ Using fallback for Azure.{provider_service}.pricing_tiers (not returned by API)")
        azure[provider_service] = STATIC_DEFAULTS_AZURE["iot"]
    else:
        azure[provider_service] = iot

    # Azure Functions
    neutral_service, provider_service = "functions", "functions"
    fn = fetched.get(neutral_service, {})
    azure[provider_service] = {
        "requestPrice": _get_or_warn("Azure", neutral_service, provider_service, "requestPrice", fn, 0.0000002, STATIC_DEFAULTS_AZURE),
        "durationPrice": _get_or_warn("Azure", neutral_service, provider_service, "durationPrice", fn, 0.000016, STATIC_DEFAULTS_AZURE),
        "freeRequests": _get_or_warn("Azure", neutral_service, provider_service, "freeRequests", fn, 1_000_000, STATIC_DEFAULTS_AZURE),
        "freeComputeTime": _get_or_warn("Azure", neutral_service, provider_service, "freeComputeTime", fn, 400_000, STATIC_DEFAULTS_AZURE),
    }

    # CosmosDB (storage_hot)
    neutral_service, provider_service = "storage_hot", "cosmosDB"
    sh = fetched.get(neutral_service, {})
    azure[provider_service] = {
        "requestPrice": _get_or_warn("Azure", neutral_service, provider_service, "requestPrice", sh, 0.0584, STATIC_DEFAULTS_AZURE),
        "minimumRequestUnits": _get_or_warn("Azure", neutral_service, provider_service, "minimumRequestUnits", sh, 400, STATIC_DEFAULTS_AZURE),
        "RUsPerRead": _get_or_warn("Azure", neutral_service, provider_service, "RUsPerRead", sh, 1, STATIC_DEFAULTS_AZURE),
        "RUsPerWrite": _get_or_warn("Azure", neutral_service, provider_service, "RUsPerWrite", sh, 10, STATIC_DEFAULTS_AZURE),
        "storagePrice": _get_or_warn("Azure", neutral_service, provider_service, "storagePrice", sh, 0.25, STATIC_DEFAULTS_AZURE),
    }

    # Blob Storage Cool (storage_cool)
    neutral_service, provider_service = "storage_cool", "blobStorageCool"
    sc = fetched.get(neutral_service, {})
    azure[provider_service] = {
        "storagePrice": _get_or_warn("Azure", neutral_service, provider_service, "storagePrice", sc, 0.01, STATIC_DEFAULTS_AZURE),
        "upfrontPrice": _get_or_warn("Azure", neutral_service, provider_service, "upfrontPrice", sc, 0.0001, STATIC_DEFAULTS_AZURE),
        "writePrice": _get_or_warn("Azure", neutral_service, provider_service, "writePrice", sc, 0.02, STATIC_DEFAULTS_AZURE),
        "readPrice": _get_or_warn("Azure", neutral_service, provider_service, "readPrice", sc, 0.01, STATIC_DEFAULTS_AZURE),
        "dataRetrievalPrice": _get_or_warn("Azure", neutral_service, provider_service, "dataRetrievalPrice", sc, 0.01, STATIC_DEFAULTS_AZURE),
        "transferCostFromCosmosDB": 0.087, # Approx
    }

    # Blob Storage Archive (storage_archive)
    neutral_service, provider_service = "storage_archive", "blobStorageArchive"
    sa = fetched.get(neutral_service, {})
    azure[provider_service] = {
        "storagePrice": _get_or_warn("Azure", neutral_service, provider_service, "storagePrice", sa, 0.00099, STATIC_DEFAULTS_AZURE),
        "writePrice": _get_or_warn("Azure", neutral_service, provider_service, "writePrice", sa, 0.02, STATIC_DEFAULTS_AZURE),
        "dataRetrievalPrice": _get_or_warn("Azure", neutral_service, provider_service, "dataRetrievalPrice", sa, 0.02, STATIC_DEFAULTS_AZURE),
    }

    # Azure Digital Twins
    neutral_service, provider_service = "twinmaker", "azureDigitalTwins"
    tm = fetched.get(neutral_service, {})
    azure[provider_service] = {
        "messagePrice": _get_or_warn("Azure", neutral_service, provider_service, "messagePrice", tm, 0.000001, STATIC_DEFAULTS_AZURE),
        "operationPrice": _get_or_warn("Azure", neutral_service, provider_service, "operationPrice", tm, 0.0000025, STATIC_DEFAULTS_AZURE),
        "queryPrice": _get_or_warn("Azure", neutral_service, provider_service, "queryPrice", tm, 0.0000005, STATIC_DEFAULTS_AZURE),
        "queryUnitTiers": tm.get("queryUnitTiers", STATIC_DEFAULTS_AZURE["twinmaker"]["queryUnitTiers"]),
    }

    # Managed Grafana
    neutral_service, provider_service = "grafana", "azureManagedGrafana"
    gf = fetched.get(neutral_service, {})
    azure[provider_service] = {
        "userPrice": _get_or_warn("Azure", neutral_service, provider_service, "userPrice", gf, 6.0, STATIC_DEFAULTS_AZURE),
        "hourlyPrice": _get_or_warn("Azure", neutral_service, provider_service, "hourlyPrice", gf, 0.069, STATIC_DEFAULTS_AZURE),
    }

    # Logic Apps (orchestration)
    neutral_service, provider_service = "orchestration", "logicApps"
    la = fetched.get(neutral_service, {})
    pricePer1kStateTransitions = _get_or_warn("Azure", neutral_service, provider_service, "pricePer1kStateTransitions", la, 0.025, STATIC_DEFAULTS_AZURE)
    azure[provider_service] = {
        "pricePer1kStateTransitions": pricePer1kStateTransitions,
        "pricePerStateTransition": pricePer1kStateTransitions / 1000.0,
    }

    # Event Grid (event_bus)
    neutral_service, provider_service = "event_bus", "eventGrid"
    eg = fetched.get(neutral_service, {})
    azure[provider_service] = {
        "pricePerMillionEvents": _get_or_warn("Azure", neutral_service, provider_service, "pricePerMillionEvents", eg, 0.60, STATIC_DEFAULTS_AZURE),
    }

    # API Management (data_access)
    neutral_service, provider_service = "data_access", "apiManagement"
    am = fetched.get(neutral_service, {})
    azure[provider_service] = {
        "pricePerMillionCalls": _get_or_warn("Azure", neutral_service, provider_service, "pricePerMillionCalls", am, 3.50, STATIC_DEFAULTS_AZURE),
    }

    logger.info("✅ Azure pricing schema built successfully.")
    return azure


# ============================================================
# GOOGLE CLOUD DATA AND SCHEMA BUILD
# ============================================================
def fetch_google_data(google_credentials: dict, service_mapping: dict, region_map: dict, additional_debug=False, billing_client=None) -> dict:
    """
    Fetches Google Cloud pricing using the Factory Pattern and builds the canonical structure.
    
    Args:
        google_credentials: Dict with gcp_region
        service_mapping: Service mapping config
        region_map: Region mapping config
        additional_debug: Enable verbose logging
        billing_client: Optional pre-created billing client (for credential-based fetch)
    """
    region = google_credentials.get("gcp_region", "europe-west1")
    logger.info(f"🚀 Fetching Google Cloud pricing for region: {region}")
    
    # Initialize Client ONCE (unless provided)
    if billing_client is None:
        try:
            credentials = load_gcp_credentials()
            billing_client = billing_v1.CloudCatalogClient(credentials=credentials)
        except Exception as e:
            logger.error(f"⚠️ Failed to initialize GCP Billing Client: {e}")
            # Fallback to empty fetched dict, defaults will be used
            billing_client = None

    # Factory Pattern: Create GCP fetcher instance
    gcp_fetcher = PriceFetcherFactory.create("gcp")
    
    fetched = {}

    for neutral_service, service_codes_per_provider in service_mapping.items():
        try:
            service_code = service_codes_per_provider.get("gcp", "")

            if not service_code:
                logger.debug(f"ℹ️ Service {neutral_service} has no GCP code, skipping (optional)")
                continue

            logger.info(f"--- GCP Service: {neutral_service} ---")
            if billing_client:
                # Use Factory-created fetcher with provider-specific kwargs
                fetched[neutral_service] = gcp_fetcher.fetch_price(
                    service_name=neutral_service,
                    region_code=region,
                    region_map=region_map,
                    debug=additional_debug,
                    billing_client=billing_client
                )
            else:
                fetched[neutral_service] = {}
        except ValueError as e:
            logger.error(e)
            raise
        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"⚠️ Failed to fetch GCP service {neutral_service}: {e}")
            fetched[neutral_service] = {}

    gcp = {}
    
    neutral_service, provider_service = "transfer", "transfer"
    transfer = fetched.get(neutral_service, {})
    gcp[provider_service] = {
        "pricing_tiers": {
            "freeTier": {"limit": 100, "price": 0},
            "tier1": {"limit": 10240, "price": 0.12},
            "tier2": {"limit": "Infinity", "price": 0.08},
        },
        "egressPrice": _get_or_warn("GCP", neutral_service, provider_service, "egressPrice", transfer, 0.12, STATIC_DEFAULTS_GCP)
    }

    neutral_service, provider_service = "iot", "iot"
    iot = fetched.get(neutral_service, {})
    gcp[provider_service] = {
        "pricePerGiB": _get_or_warn("GCP", neutral_service, provider_service, "pricePerGiB", iot, 0.0000004, STATIC_DEFAULTS_GCP),
        "pricePerDeviceAndMonth": _get_or_warn("GCP", neutral_service, provider_service, "pricePerDeviceAndMonth", iot, 0, STATIC_DEFAULTS_GCP),
    }

    neutral_service, provider_service = "functions", "functions"
    fn = fetched.get(neutral_service, {})
    gcp[provider_service] = {
        "requestPrice": _get_or_warn("GCP", neutral_service, provider_service, "requestPrice", fn, 0.0000004, STATIC_DEFAULTS_GCP),
        "durationPrice": _get_or_warn("GCP", neutral_service, provider_service, "durationPrice", fn, 0.0000025, STATIC_DEFAULTS_GCP),
        "freeRequests": _get_or_warn("GCP", neutral_service, provider_service, "freeRequests", fn, 2_000_000, STATIC_DEFAULTS_GCP),
        "freeComputeTime": _get_or_warn("GCP", neutral_service, provider_service, "freeComputeTime", fn, 400_000, STATIC_DEFAULTS_GCP),
    }

    neutral_service, provider_service = "storage_hot", "storage_hot"
    sh = fetched.get(neutral_service, {})
    gcp[provider_service] = {
        "writePrice": _get_or_warn("GCP", neutral_service, provider_service, "writePrice", sh, 0.0000018, STATIC_DEFAULTS_GCP),
        "readPrice": _get_or_warn("GCP", neutral_service, provider_service, "readPrice", sh, 0.0000006, STATIC_DEFAULTS_GCP),
        "storagePrice": _get_or_warn("GCP", neutral_service, provider_service, "storagePrice", sh, 0.18, STATIC_DEFAULTS_GCP),
        "freeStorage": _get_or_warn("GCP", neutral_service, provider_service, "freeStorage", sh, 1, STATIC_DEFAULTS_GCP),
    }

    neutral_service, provider_service = "storage_cool", "storage_cool"
    sc = fetched.get(neutral_service, {})
    gcp[provider_service] = {
        "storagePrice": _get_or_warn("GCP", neutral_service, provider_service, "storagePrice", sc, 0.01, STATIC_DEFAULTS_GCP),
        "upfrontPrice": _get_or_warn("GCP", neutral_service, provider_service, "upfrontPrice", sc, 0.0, STATIC_DEFAULTS_GCP),
        "requestPrice": _get_or_warn("GCP", neutral_service, provider_service, "requestPrice", sc, 0.00001, STATIC_DEFAULTS_GCP),
        "dataRetrievalPrice": _get_or_warn("GCP", neutral_service, provider_service, "dataRetrievalPrice", sc, 0.01, STATIC_DEFAULTS_GCP),
    }

    neutral_service, provider_service = "storage_archive", "storage_archive"
    sa = fetched.get(neutral_service, {})
    gcp[provider_service] = {
        "storagePrice": _get_or_warn("GCP", neutral_service, provider_service, "storagePrice", sa, 0.0012, STATIC_DEFAULTS_GCP),
        "lifecycleAndWritePrice": _get_or_warn("GCP", neutral_service, provider_service, "lifecycleAndWritePrice", sa, 0.00005, STATIC_DEFAULTS_GCP),
        "dataRetrievalPrice": _get_or_warn("GCP", neutral_service, provider_service, "dataRetrievalPrice", sa, 0.05, STATIC_DEFAULTS_GCP),
    }

    neutral_service, provider_service = "twinmaker", "twinmaker"
    tm = fetched.get(neutral_service, {})
    # TwinMaker on GCP maps to Compute Engine (Self-Hosted)
    # e2-medium: 2 vCPU + 4GB RAM
    e2_core_price = tm.get("e2CorePrice", 0.0)
    e2_ram_price = tm.get("e2RamPrice", 0.0)
    e2_medium_price = (2 * e2_core_price) + (4 * e2_ram_price)
    
    # Fallback to static if 0
    if e2_medium_price == 0:
        e2_medium_price = STATIC_DEFAULTS_GCP["computeEngine"]["e2MediumPrice"]
        
    gcp[provider_service] = {
        "e2MediumPrice": e2_medium_price,
        "storagePrice": _get_or_warn("GCP", neutral_service, provider_service, "storagePrice", tm, 0.04, STATIC_DEFAULTS_GCP),
        # These are not used for GCP "TwinMaker" (Compute Engine) but kept for schema consistency if needed, or zeroed out
        "entityPrice": 0, 
        "unifiedDataAccessAPICallsPrice": 0,
        "queryPrice": 0
    }

    neutral_service, provider_service = "grafana", "grafana"
    gr = fetched.get(neutral_service, {})
    # Grafana on GCP maps to Compute Engine (Self-Hosted)
    e2_core_price_gr = gr.get("e2CorePrice", 0.0)
    e2_ram_price_gr = gr.get("e2RamPrice", 0.0)
    e2_medium_price_gr = (2 * e2_core_price_gr) + (4 * e2_ram_price_gr)
    
    if e2_medium_price_gr == 0:
        e2_medium_price_gr = STATIC_DEFAULTS_GCP["computeEngine"]["e2MediumPrice"]

    gcp[provider_service] = {
        "e2MediumPrice": e2_medium_price_gr,
        "storagePrice": _get_or_warn("GCP", neutral_service, provider_service, "storagePrice", gr, 0.04, STATIC_DEFAULTS_GCP),
        "editorPrice": 0,
        "viewerPrice": 0
    }
    
    neutral_service, provider_service = "data_access", "apiGateway"
    da = fetched.get(neutral_service, {})
    # For dataTransferOutPrice, we reuse the transfer service's egress price which is standard internet egress
    egress_price = gcp.get("transfer", {}).get("egressPrice", 0.12)
    
    # Scale pricePerMillionCalls by 1M because the fetcher normalizes to per-call, but the key implies per-million
    normalized_default = STATIC_DEFAULTS_GCP["data_access"]["pricePerMillionCalls"] / 1_000_000
    price_per_call_val = _get_or_warn("GCP", neutral_service, provider_service, "pricePerMillionCalls", da, normalized_default, STATIC_DEFAULTS_GCP)
    
    # Now scale up for the final output
    final_price_per_million = price_per_call_val * 1_000_000

    gcp[provider_service] = {
        "pricePerMillionCalls": final_price_per_million,
        "dataTransferOutPrice": egress_price
    }
    
    neutral_service, provider_service = "orchestration", "cloudWorkflows"
    cw = fetched.get("orchestration", {}) # Mapped to orchestration in fetcher
    gcp[provider_service] = {
        "stepPrice": _get_or_warn("GCP", "orchestration", provider_service, "stepPrice", cw, 0.000001, STATIC_DEFAULTS_GCP)
    }

    neutral_service, provider_service = "scheduler", "cloudScheduler"
    sch = fetched.get(neutral_service, {})
    gcp[provider_service] = {
        "jobPrice": _get_or_warn("GCP", neutral_service, provider_service, "jobPrice", sch, 0.10, STATIC_DEFAULTS_GCP)
    }

    return gcp


if __name__ == "__main__":
    import sys
    target_provider = "gcp" # Default
    if len(sys.argv) > 1 and sys.argv[1] in ["aws", "azure", "gcp"]:
        target_provider = sys.argv[1]
    
    additional_debug = "additional_debug=true" in sys.argv
    calculate_up_to_date_pricing(target_provider, additional_debug=additional_debug)
