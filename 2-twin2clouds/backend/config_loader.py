import boto3
import json
import os
import time
from backend.logger import logger
from google.oauth2 import service_account
import backend.constants as CONSTANTS

def load_json_file(file_path: str):
    try:
        
        with open(file_path) as f:
            data = json.load(f)
        
        modification_time = os.path.getmtime(file_path)
        readable_time = time.ctime(modification_time)
        logger.debug(f"Loaded JSON file: {file_path} (last modified: {readable_time})")
        return data
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}")
        raise e

def load_json_file_optional(file_path: str):
    """
    Loads a JSON file if it exists, otherwise returns an empty dict.
    Logs a warning if the file is missing.
    """
    if not os.path.exists(file_path):
        logger.warning(f"⚠️ Optional JSON file not found: {file_path}. Returning empty dict.")
        return {}
    return load_json_file(file_path)

def load_combined_pricing():
    """
    Loads pricing data from separate provider files and merges them into a single dictionary.
    Expected structure:
    {
        "aws": { ... },
        "azure": { ... },
        "gcp": { ... }
    }
    """
    logger.info("🧩 Loading combined pricing data from separate files...")
    
    aws_pricing = load_json_file_optional(CONSTANTS.AWS_PRICING_FILE_PATH)
    azure_pricing = load_json_file_optional(CONSTANTS.AZURE_PRICING_FILE_PATH)
    gcp_pricing = load_json_file_optional(CONSTANTS.GCP_PRICING_FILE_PATH)
    
    combined = {
        "aws": aws_pricing,
        "azure": azure_pricing,
        "gcp": gcp_pricing
    }
    
    return combined

# --------------------------------------------------------------------
# Configuration Loader
# --------------------------------------------------------------------
def load_config_file():
    """
    Load credentials from a JSON file.

    JSON Example
    -------------
    {
        "mode": "DEBUG"
    }
    """
    return load_json_file(CONSTANTS.CONFIG_FILE_PATH)


# --------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------
def load_credentials_file():
    """
    Load credentials from a JSON file.

    JSON Example
    -------------
    {
        "aws": {...},
        "gcp": {...},
        "azure": {...}
    }
    """
    return load_json_file(CONSTANTS.CREDENTIALS_FILE_PATH)


def load_aws_credentials() -> dict:
    """
    Load AWS credentials from the local configuration file.
    """
    logger.info("    Loading AWS credentials from configuration file.")
    creds = load_credentials_file()
    if not creds:
        raise ValueError("Failed to load credentials configuration.")

    aws_credentials = creds.get("aws", {})
    if not aws_credentials:
        raise ValueError("AWS credentials not found in configuration.")

    aws_credentials_dict = {
        "aws_access_key_id": aws_credentials["aws_access_key_id"],
        "aws_secret_access_key": aws_credentials["aws_secret_access_key"],
        "region_name": aws_credentials.get("region_name", "eu-central-1"),
    }

    session_token = aws_credentials.get("aws_session_token")
    if session_token:
        aws_credentials_dict["aws_session_token"] = session_token

    return aws_credentials_dict

def load_azure_credentials():
    """
    Load Azure credentials from the local configuration file.
    """
    logger.info("    Loading Azure credentials from configuration file.")
    creds = load_credentials_file()
    if not creds:
        raise ValueError("Failed to load credentials configuration.")

    azure_credentials = creds.get("azure", {})
    if not azure_credentials:
        raise ValueError("Azure credentials not found in configuration.")

    return azure_credentials

def load_gcp_credentials():
    """
    Load GCP service account credentials from the specified file.
    """
    logger.info("    Loading GCP credentials from configuration file.")
    creds = load_credentials_file()
    if not creds:
        raise ValueError("Failed to load credentials configuration.")
    google_credentials = creds.get("gcp", {})
    cred_file_path = google_credentials.get("gcp_credentials_file")
    if not cred_file_path:
        raise ValueError("Google credentials file path not specified in configuration.")
    credentials = service_account.Credentials.from_service_account_file(CONSTANTS.GCP_CREDENTIALS_BASE_FILE_PATH / cred_file_path)
    return credentials

# --------------------------------------------------------------------
# Service Codes Loaders
# --------------------------------------------------------------------
def load_service_mapping():
    """
    Load service mapping from a JSON file.  (for fallback purposes)
    """
    logger.info("✅ Loading service mapping from local file.")
    return load_json_file(CONSTANTS.SERVICE_MAPPING_FILE_PATH)

# --------------------------------------------------------------------
# Regions Loaders
# --------------------------------------------------------------------
def load_aws_regions_file():
    """
    Load AWS regions from a JSON file.  (for fallback purposes)
    
    Regions taken from cli command: 
    ```
    aws ec2 describe-regions
    ```
    
    Products taken from cli command: 
    ```
    aws pricing get-products 
        --service-code AmazonEC2 
        --filters Type=TERM_MATCH,Field=preInstalledSw,Value=NA 
        --max-results 100
    ```
    """
    logger.info("Loading AWS products for regions map from local file.")
    products = load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)
    return products

def load_azure_regions_file():
    """
    Load AZURE regions from a JSON file.  (for fallback purposes)
    """
    logger.info("Loading AZURE regions map from local file.")
    regions = load_json_file(CONSTANTS.AZURE_REGIONS_FILE_PATH)
    return regions

def load_google_regions_file():
    """
    Load GCP regions from a JSON file. (for fallback purposes)
    """
    logger.info("Loading GCP regions from local file.")
    return load_json_file(CONSTANTS.GCP_REGIONS_FILE_PATH)

# --------------------------------------------------------------------
# Currency Conversion Loaders
# --------------------------------------------------------------------
def load_currency_convertion_file():
    """
    Load currency conversion rates from a JSON file. (for fallback purposes)

    JSON Example
    -------------
    {
        "usd_to_eur_rate": 0.91,
        "eur_to_usd_rate": 1.10
    }
    """
    logger.info("Loading currency conversion rates from local file.")
    return load_json_file(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)
