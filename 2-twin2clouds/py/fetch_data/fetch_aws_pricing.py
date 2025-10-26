import boto3
import json
from py.logger import logger
import py.pricing_utils as pricing_utils
from py.config_loader import get_aws_credentials
import py.constants as CONSTANTS
from py.config_loader import load_json_file

def load_aws_regions_file() -> dict:
    """
    Load AWS regions from the local file.
    """
    logger.info("Loading AWS regions from local file")
    try:
        regions = load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)
        regions_sorted = dict(sorted(regions.items()))
        return regions_sorted
    except Exception as e:
        logger.error(f"Failed to load AWS regions from file: {e}")
        raise e
    
def load_aws_service_codes_file() -> dict:
    """
    Load AWS service codes from the local file.
    """
    logger.info("Loading AWS service codes from local file")
    try:
        services = load_json_file(CONSTANTS.AWS_SERVICE_CODES_FILE_PATH)
        services_sorted = dict(sorted(services.items()))
        return services_sorted
    except Exception as e:
        logger.error(f"Failed to load AWS service codes from file: {e}")
        raise e

def get_pricing_client_aws():
    """
    Create a boto3 Pricing API client using loaded credentials.
    """
    client_args = get_aws_credentials()
    return boto3.client("pricing", region_name="us-east-1", **client_args)


def fetch_aws_pricing(service: str, region: str = "eu-central-1") -> dict:
    """
    Fetch AWS pricing for a given service and region.
    """
    client = get_pricing_client_aws()

    # Only apply a region filter for region-specific services
    filters = []
    if service not in ["iot_core", "route53", "cloudfront", "iam"]:
        filters.append({"Type": "TERM_MATCH", "Field": "location", "Value": region})

    response = client.get_products(ServiceCode=service, Filters=filters, MaxResults=1)
    price_list = response.get("PriceList", [])
    if not price_list:
        raise ValueError(f"No pricing data found for service '{service}' in region '{region}'.")

    product = json.loads(price_list[0])
    try:
        terms = next(iter(product["terms"]["OnDemand"].values()))
        price_dim = next(iter(terms["priceDimensions"].values()))
        usd_price = float(price_dim["pricePerUnit"].get("USD", 0))
        eur_price = pricing_utils.usd_to_eur(usd_price)
    except Exception as e:
        logger.error(f"Failed to parse AWS pricing data: {str(e)}")
        usd_price, eur_price = -1.0, -1.0

    return {
        "region": region,
        "service": service,
        "price_usd": usd_price,
        "price_eur": eur_price,
        "raw": product,
    }
