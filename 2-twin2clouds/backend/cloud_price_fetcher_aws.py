import boto3
import json
import re
from typing import Dict, Any, Optional, List
from backend.logger import logger
import backend.constants as CONSTANTS
import backend.config_loader as config_loader
from backend.fetch_data import initial_fetch_aws

# --------------------------------------------------------------------
# 1. Dynamic Region Loading
# --------------------------------------------------------------------
def _load_aws_regions() -> Dict[str, str]:
    """
    Load AWS regions using the shared initial fetch logic (with caching).
    """
    return initial_fetch_aws.fetch_region_map()

AWS_REGION_NAMES = _load_aws_regions()

STATIC_DEFAULTS = {
    "iot": {"pricePerDeviceAndMonth": 0.0035},
    "functions": {"freeRequests": 1_000_000, "freeComputeTime": 400_000},
    "storage_hot": {"freeStorage": 25},
    "storage_cool": {"upfrontPrice": 0.0001},
    "grafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
}

# -------------------------------------------------------------------
# Keyword patterns for matching
# -------------------------------------------------------------------
AWS_SERVICE_KEYWORDS = {
    "iot": {
        "include": ["iot", "message", "rule", "device shadow", "registry"],
        "exclude": ["lorawan", "fuota", "everynet"],
        "fields": {
            "pricePerMessage": ["message"],
            "priceRulesTriggered": ["rule", "trigger"],
            "pricePerDeviceAndMonth": ["device", "month"],
        },
        "tier_keywords": ["first", "next", "over"],
    },
    "functions": {
        "include": ["lambda", "request", "invocation", "compute", "gb-second"],
        "exclude": ["edge", "provisioned", "ephemeral", "poller", "streaming", "arm", "snapstart"],
        "fields": {
            "requestPrice": ["total requests"],
            "durationPrice": ["total compute", "gb-second"],
        },
        "tier_keywords": {
            "durationTiers": {"tier1": ["tier-1", "first"], "tier2": ["tier-2", "next"], "tier3": ["tier-3", "over"]}
        },
    },
    "storage_hot": {
        "include": ["read", "write", "storage"],
        "exclude": ["backup", "replica", "restore", "ia", "dax", "streams", "pitr", "global table"],
        "fields": {
            "readPrice": ["per million read request", "read request units"],
            "writePrice": ["per million write request", "write request units"],
            "storagePrice": ["gb-month of storage used", "storage used beyond"],
        },
    },
    "storage_cool": {
        "include": ["standard-infrequent access", "standard-ia", "infrequent access"],
        "exclude": ["one zone", "intelligent tiering", "glacier", "archive", "checksum", "select"],
        "fields": {
            "storagePrice": ["gb-month of storage used", "gb-month prorated"],
            "requestPrice": ["get and all other requests", "per 1,000", "per 10,000"],
            "dataRetrievalPrice": ["retrieval fee", "per gb retrieved", "flat fee"],
        },
    },
    "storage_archive": {
        "include": ["glacier", "deep archive"],
        "exclude": ["instant retrieval", "restore", "replication", "checksum", "select"],
        "fields": {
            "storagePrice": ["gb-month", "storage used", "amazon glacier"],
            "lifecycleAndWritePrice": ["lifecycle", "put request", "upload", "write"],
            "dataRetrievalPrice": ["retrieval fee", "per gb retrieved", "flat fee"],
        },
    },
    "twinmaker": {
        "include": ["iottwinmaker", "iot twinmaker", "twinmaker"],
        "fields": {
            "entityPrice": ["per entity per month", "iottwinmaker-entities"],
            "unifiedDataAccessAPICallsPrice": ["per million api calls", "unifieddataaccess"],
            "queryPrice": ["per 10k queries", "queries executed"],
        },
    },
    "transfer": {
        "include": ["data transfer", "transfer out", "egress", "internet"],
        "fields": {
            "egressPrice": ["data transfer", "transfer out", "data transferred out", "egress", "internet", "out to"]
        },
    },
    "grafana": {
        "include": ["grafana", "workspace", "user"],
        "exclude": ["enterprise", "support"],
        "fields": {
            "editorPrice": ["editor", "admin", "active user"],
            "viewerPrice": ["viewer"],
        },
    },
}

# -------------------------------------------------------------------
# Helper
# -------------------------------------------------------------------
def _warn_static(neutral: str, field: str, debug: bool = False):
    logger.info(f"    ℹ️ Using static value for AWS.{neutral}.{field} (not returned by API)")

# -------------------------------------------------------------------
# Shared: safe AWS Pricing API call
# -------------------------------------------------------------------
def _fetch_pricing_response(pricing_client, service_code, region_human, usagetype=None, with_location=True):
    filters = []
    if usagetype:
        filters.append({"Type": "TERM_MATCH", "Field": "usagetype", "Value": usagetype})
    if with_location:
        filters.append({"Type": "TERM_MATCH", "Field": "location", "Value": region_human})

    try:
        response = pricing_client.get_products(ServiceCode=service_code, Filters=filters, MaxResults=100)
        return response.get("PriceList", [])
    except Exception as e:
        logger.debug(f"⚠️ Query failed for {service_code} ({'with' if with_location else 'without'} location): {e}")
        return []


# -------------------------------------------------------------------
# Generic price-dimension parser (used by all services)
# -------------------------------------------------------------------
def _parse_price_dimensions(price_list, field_map, include_keywords=None, exclude_keywords=None, debug=False):
    prices = {}
    seen_pairs = set()
    include_keywords = include_keywords or []
    exclude_keywords = exclude_keywords or []

    for prod_json in price_list:
        prod = json.loads(prod_json)
        for term in prod.get("terms", {}).get("OnDemand", {}).values():
            for dim in term.get("priceDimensions", {}).values():
                desc = dim.get("description", "").lower()
                price = float(dim.get("pricePerUnit", {}).get("USD", 0))
                if price == 0:
                    continue

                if include_keywords and not any(k in desc for k in include_keywords):
                    if debug: logger.debug(f"   ❌ No Match: {desc.strip()} {price}")
                    continue
                if any(x in desc for x in exclude_keywords):
                    if debug: logger.debug(f"   ❌ Excluded: {desc.strip()} {price}")
                    continue

                for key, patterns in field_map.items():
                    if any(p in desc for p in patterns):
                        pair = (key, round(price, 12))
                        if pair in seen_pairs:
                            break
                        prices[key] = price
                        seen_pairs.add(pair)
                        if debug: logger.debug(f"   ✔️ Matched:  {desc.strip()} → {key} = {price}")
                        break
    return prices


# -------------------------------------------------------------------
# Specialized: Transfer + TwinMaker
# -------------------------------------------------------------------
def fetch_transfer_pricing(region_human, pricing_client, debug=False):
    field_map = AWS_SERVICE_KEYWORDS["transfer"]["fields"]
    egress_prices = []
    for service_code in ["AmazonEC2", "AWSDataTransfer"]:
        for with_location in (True, False):
            price_list = _fetch_pricing_response(
                pricing_client, service_code, region_human, usagetype="DataTransfer-Out-Bytes", with_location=with_location
            )
            egress_prices += _parse_transfer_dimensions(price_list, field_map, debug)

    if not egress_prices:
        logger.warning(f"⚠️ No egress prices found for {region_human}, using static defaults.")
        _warn_static("transfer", "", debug)
        return {
            "pricing_tiers": {
                "freeTier": {"limit": 100, "price": 0},
                "tier1": {"limit": 10240, "price": 0.09},
                "tier2": {"limit": 51200, "price": 0.085},
                "tier3": {"limit": 102400, "price": 0.07},
                "tier4": {"limit": "Infinity", "price": 0.05},
            },
            "egressPrice": 0.09,
        }

    egress_prices.sort(key=lambda x: x["begin"])
    pricing_tiers = {"freeTier": {"limit": 100, "price": 0}}
    for i, tier in enumerate(egress_prices, start=1):
        limit = tier["end"] if tier["end"] != float("inf") else "Infinity"
        pricing_tiers[f"tier{i}"] = {"limit": limit, "price": tier["price"]}
    return {"pricing_tiers": pricing_tiers, "egressPrice": egress_prices[0]["price"]}


def _parse_transfer_dimensions(price_list, field_map, debug=False):
    """Parse transfer-specific dimensions into tier objects."""
    tiers = []
    for prod_json in price_list:
        prod = json.loads(prod_json)
        for term in prod.get("terms", {}).get("OnDemand", {}).values():
            for dim in term.get("priceDimensions", {}).values():
                desc = dim.get("description", "").lower()
                price = float(dim.get("pricePerUnit", {}).get("USD", 0))
                if price == 0:
                    continue
                if any(p in desc for p in field_map.get("egressPrice", [])) and "per gb" in desc:
                    tiers.append(
                        {
                            "desc": desc,
                            "price": price,
                            "begin": float(dim.get("beginRange", "0")),
                            "end": float(dim.get("endRange", "inf")),
                        }
                    )
                    if debug: logger.debug(f"   ✔️ Matched transfer tier: {desc} → {price}")
    return tiers


def fetch_twinmaker_pricing(region_human, pricing_client, debug=False):
    field_map = AWS_SERVICE_KEYWORDS["twinmaker"]["fields"]
    prices = {}
    
    # Try both service codes as AWS sometimes changes them
    for service_code in ["IOTTwinMaker", "IOTTwinMakerQueries"]:
        price_list = _fetch_pricing_response(pricing_client, service_code, region_human)
        fetched = _parse_price_dimensions(price_list, field_map, debug=debug)
        prices.update(fetched)

    return prices


# -------------------------------------------------------------------
# Main Fetcher
# -------------------------------------------------------------------
def fetch_aws_price(service_name, region_code, aws_credentials=None, debug=False):
    """
    Fetch pricing for a specific AWS service in a given region.
    Uses boto3 Pricing API with keyword matching.
    """
    region_human = AWS_REGION_NAMES.get(region_code)
    if not region_human:
        logger.warning(f"⚠️ Unknown AWS region code: {region_code}")
        return None

    # Normalize service name
    neutral_service_name = service_name.lower().replace(" ", "_")
    
    # Handle Grafana specifically (Static for now, dynamic TODO)
    if neutral_service_name == "grafana":
        prices = STATIC_DEFAULTS["grafana"]
        _warn_static(neutral_service_name, "grafana", debug)
        logger.info(f"✅ Final AWS {neutral_service_name} pricing: {prices}")
        print("")
        return prices

    # Check if we have keywords for this service
    service_config = AWS_SERVICE_KEYWORDS.get(neutral_service_name)
    if not service_config:
        logger.warning(f"⚠️ No keyword config for service: {service_name}")
        _warn_static(neutral_service_name, "", debug)
        return STATIC_DEFAULTS.get(neutral_service_name)

    logger.info(f"🔍 Fetching AWS {service_name} pricing for {region_human}...")
    
    try:
        # Use provided credentials or load them
        if aws_credentials is None:
            client_args = config_loader.load_aws_credentials()
        else:
            client_args = aws_credentials.copy()
            # Ensure region_name is set for pricing API
            client_args["region_name"] = client_args.get("region_name", "us-east-1")
        
        # Pricing API endpoint is only in us-east-1 or ap-south-1 usually
        pricing_client = boto3.client("pricing", **client_args)
    except Exception as e:
        logger.error(f"Failed to create boto3 client: {e}")
        _warn_static(neutral_service_name, "", debug)
        return STATIC_DEFAULTS.get(neutral_service_name)

    # Special handling for Transfer (complex tiered pricing)
    if neutral_service_name == "transfer":
        result = fetch_transfer_pricing(region_human, pricing_client, debug)
        logger.info(f"✅ Final AWS {neutral_service_name} pricing: {result}")
        print("")
        return result

    # Special handling for TwinMaker (multiple service codes)
    if neutral_service_name == "twinmaker":
        prices = fetch_twinmaker_pricing(region_human, pricing_client, debug)
        if not prices:
             logger.warning(f"⚠️ Failed to fetch TwinMaker prices, using defaults.")
             # Fallback logic could go here if needed
        logger.info(f"✅ Final AWS {neutral_service_name} pricing: {prices}")
        print("")
        return prices

    # Standard handling for other services
    # We need to guess the AWS ServiceCode. This is tricky without a map.
    # Common ones: AmazonEC2, AmazonS3, AmazonDynamoDB, AWSLambda, AmazonIoTCore
    service_code_map = {
        "iot": "AWSIoT",
        "functions": "AWSLambda",
        "storage_hot": "AmazonDynamoDB",
        "storage_cool": "AmazonS3",
        "storage_archive": "AmazonS3",
    }
    
    aws_service_code = service_code_map.get(neutral_service_name)
    if not aws_service_code:
        logger.warning(f"⚠️ No AWS ServiceCode mapped for {service_name}")
        _warn_static(neutral_service_name, "", debug)
        return STATIC_DEFAULTS.get(neutral_service_name)

    price_list = _fetch_pricing_response(pricing_client, aws_service_code, region_human)
    
    # Parse dimensions
    prices = _parse_price_dimensions(
        price_list, 
        service_config["fields"], 
        include_keywords=service_config.get("include"),
        exclude_keywords=service_config.get("exclude"),
        debug=debug
    )

    # Handle tiers if defined (e.g. Lambda duration)
    if "tier_keywords" in service_config and isinstance(service_config["tier_keywords"], dict):
        for tier_group, tiers in service_config["tier_keywords"].items():
            tier_data = {}
            for tier_name, keywords in tiers.items():
                # Re-scan price list for these specific tier keywords
                tier_prices = _parse_price_dimensions(
                    price_list, 
                    {tier_name: keywords}, # temporary field map
                    include_keywords=service_config.get("include"),
                    exclude_keywords=service_config.get("exclude"),
                    debug=debug
                )
                if tier_prices:
                    tier_data[tier_name] = list(tier_prices.values())[0]
            if tier_data:
                prices[tier_group] = tier_data

    # Merge with defaults if missing keys
    defaults = STATIC_DEFAULTS.get(neutral_service_name, {})
    for k, v in defaults.items():
        if k not in prices:
            prices[k] = v
            _warn_static(neutral_service_name, k, debug)

    logger.info(f"✅ Final AWS {neutral_service_name} pricing: {prices}")
    print("")
    return prices
