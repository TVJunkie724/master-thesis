from pathlib import Path

PRICING_BASE_PATH = Path("json")

#--------------------------------------------------------------------
# Configuration file paths
#--------------------------------------------------------------------
BASE_CONFIG_DIR = Path("/config")

CONFIG_FILE_PATH = BASE_CONFIG_DIR / "config.json"
CREDENTIALS_FILE_PATH = BASE_CONFIG_DIR / "config_credentials.json"
GCP_CREDENTIALS_BASE_FILE_PATH = BASE_CONFIG_DIR 

#--------------------------------------------------------------------
# File paths for storing fetched data
#--------------------------------------------------------------------
BASE_FETCHED_DATA_PATH = PRICING_BASE_PATH / "fetched_data"

CURRENCY_CONVERSION_FILE_PATH = BASE_FETCHED_DATA_PATH / "currency.json"

FORMULAS_FILE_PATH = PRICING_BASE_PATH / "formulas.json"
SERVICE_CALC_PARAMS_FILE_PATH = PRICING_BASE_PATH / "service_calc_params.json"
SERVICE_MAPPING_FILE_PATH = PRICING_BASE_PATH / "service_mapping.json"


AWS_REGIONS_FILE_PATH = BASE_FETCHED_DATA_PATH / "aws_regions.json"
AZURE_REGIONS_FILE_PATH = BASE_FETCHED_DATA_PATH / "azure_regions.json"
GCP_REGIONS_FILE_PATH = BASE_FETCHED_DATA_PATH / "gcp_regions.json"

AWS_PRICING_FILE_PATH = PRICING_BASE_PATH / "fetched_data" / "pricing_dynamic_aws.json"
AZURE_PRICING_FILE_PATH = PRICING_BASE_PATH / "fetched_data" / "pricing_dynamic_azure.json"
GCP_PRICING_FILE_PATH = PRICING_BASE_PATH / "fetched_data" / "pricing_dynamic_gcp.json"

# Legacy path for backward compatibility if needed, or to be removed
DYNAMIC_PRICING_FILE_PATH = PRICING_BASE_PATH / "pricing_dynamic.json"

#--------------------------------------------------------------------
# Fetching URLs
#--------------------------------------------------------------------
AWS_PRICING_API_URL = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json"
AZURE_RETAIL_PRICES_URL = "https://prices.azure.com/api/retail/prices"
