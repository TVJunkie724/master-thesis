from pathlib import Path

PRICING_BASE_PATH = Path("json")

#--------------------------------------------------------------------
# Configuration file paths
#--------------------------------------------------------------------
BASE_CONFIG_DIR = Path(".")

CONFIG_FILE_PATH = BASE_CONFIG_DIR / "config.json"
CREDENTIALS_FILE_PATH = BASE_CONFIG_DIR / "config_credentials.json"
GCP_CREDENTIALS_BASE_FILE_PATH = BASE_CONFIG_DIR 

#--------------------------------------------------------------------
# File paths for storing fetched data
#--------------------------------------------------------------------
BASE_FETCHED_DATA_PATH = PRICING_BASE_PATH / "fetched_data"

CURRENCY_CONVERSION_FILE_PATH = BASE_FETCHED_DATA_PATH / "currency.json"

#--------------------------------------------------------------------
# Fetching URLs
#--------------------------------------------------------------------
AWS_PRICING_API_URL = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json"
AZURE_RETAIL_PRICES_URL = "https://prices.azure.com/api/retail/prices"
