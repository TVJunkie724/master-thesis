import boto3
import json
import re
import os
from typing import Dict, Any, Optional, List, Callable

from backend.logger import logger
import backend.constants as CONSTANTS
import backend.config_loader as config_loader
# from backend.fetch_data import initial_fetch_aws # No longer needed for global load

# --------------------------------------------------------------------
# Constants & Configuration
# --------------------------------------------------------------------

# Global loading removed. Passed as arguments now.
# AWS_REGION_NAMES = ...
# SERVICE_MAPPING = ...

STATIC_DEFAULTS = {
    "iot": {"pricePerDeviceAndMonth": 0.0035},
    "functions": {"freeRequests": 1_000_000, "freeComputeTime": 400_000},
    "storage_hot": {"freeStorage": 25},
    "storage_cool": {"upfrontPrice": 0.0001},
    "grafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
}

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
        }
    },
    "grafana": {
        "include": ["grafana", "workspace", "user"],
        "exclude": ["enterprise", "support"],
        "fields": {
            "editorPrice": ["editor", "admin", "active user"],
            "viewerPrice": ["viewer"],
        },
    },
    "orchestration": {
        "include": ["standard", "state transition"],
        "fields": {
            "pricePer1kStateTransitions": ["per 1,000 state transitions", "state transition"]
        }
    },
    "event_bus": {
        "include": ["custom event", "invocations"],
        "fields": {
            "pricePerMillionEvents": ["per million scheduled invocations"]
        }
    },
    "data_access": {
        "include": ["requests", "api gateway"],
        "fields": {
            "pricePerMillionCalls": ["api gateway http api (first 300 million)"],
        }
    },
}

# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------

def _warn_static(neutral: str, field: str, debug: bool = False):
    """Log a warning that a static default value is being used."""
    logger.info(f"    ℹ️ Using static value for AWS.{neutral}.{field} (not returned by API)")

def _get_pricing_client(aws_credentials: Optional[Dict[str, Any]] = None) -> Any:
    """
    Create and return a boto3 pricing client.
    Defaults to loading credentials from config if not provided.
    Always uses 'us-east-1' for the Pricing API.
    """
    try:
        if aws_credentials is None:
            client_args = config_loader.load_aws_credentials()
        else:
            client_args = aws_credentials.copy()
            # Ensure region_name is set for pricing API
            client_args["region_name"] = client_args.get("region_name", "us-east-1")
        
        return boto3.client("pricing", **client_args)
    except Exception as e:
        logger.error(f"Failed to create boto3 client: {e}")
        return None

def _fetch_api_products(pricing_client, service_code: str, region_human: str, usagetype: Optional[str] = None, with_location: bool = True) -> List[str]:
    """
    Fetch product list from AWS Pricing API.
    Handles filters for region and usage type.
    """
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

def _extract_prices_from_api_response(price_list: List[str], field_map: Dict[str, List[str]], include_keywords: List[str] = None, exclude_keywords: List[str] = None, debug: bool = False) -> Dict[str, float]:
    """
    Parse the raw JSON response from AWS Pricing API to extract prices matching the field map.
    """
    prices = {}
    seen_pairs = set()
    include_keywords = include_keywords or []
    exclude_keywords = exclude_keywords or []

    for prod_json in price_list:
        prod = json.loads(prod_json)
        # Iterate over all OnDemand terms
        terms = prod.get("terms", {}).get("OnDemand", {}).values()
        for term in terms:
            # Iterate over all price dimensions in the term
            for dim in term.get("priceDimensions", {}).values():
                desc = dim.get("description", "").lower()
                price = float(dim.get("pricePerUnit", {}).get("USD", 0))
                
                if price == 0:
                    continue

                # Check inclusion keywords
                if include_keywords and not any(k in desc for k in include_keywords):
                    if debug: logger.debug(f"   ❌ No Match: {desc.strip()} {price}")
                    continue
                
                # Check exclusion keywords
                if any(x in desc for x in exclude_keywords):
                    if debug: logger.debug(f"   ❌ Excluded: {desc.strip()} {price}")
                    continue

                # Check against field map
                for key, patterns in field_map.items():
                    if any(p in desc for p in patterns):
                        pair = (key, round(price, 12))
                        if pair not in seen_pairs:
                            prices[key] = price
                            seen_pairs.add(pair)
                            if debug: logger.debug(f"   ✔️ Matched:  {desc.strip()} → {key} = {price}")
                        break # Stop checking other keys for this dimension
    return prices

# -------------------------------------------------------------------
# Specialized Fetchers
# -------------------------------------------------------------------

def _fetch_transfer_prices(region_human: str, pricing_client: Any, debug: bool = False) -> Dict[str, Any]:
    """
    Specialized fetcher for Data Transfer.
    Fetches prices from AmazonEC2 and AWSDataTransfer to build tiered egress pricing.
    """
    field_map = AWS_SERVICE_KEYWORDS["transfer"]["fields"]
    egress_prices = []
    
    # Fetch from both potential sources
    for service_code in ["AmazonEC2", "AWSDataTransfer"]:
        for with_location in (True, False):
            price_list = _fetch_api_products(
                pricing_client, service_code, region_human, usagetype="DataTransfer-Out-Bytes", with_location=with_location
            )
            
            # Parse tiers specifically for transfer
            for prod_json in price_list:
                prod = json.loads(prod_json)
                for term in prod.get("terms", {}).get("OnDemand", {}).values():
                    for dim in term.get("priceDimensions", {}).values():
                        desc = dim.get("description", "").lower()
                        price = float(dim.get("pricePerUnit", {}).get("USD", 0))
                        if price == 0: continue
                        
                        if any(p in desc for p in field_map.get("egressPrice", [])) and "per gb" in desc:
                            egress_prices.append({
                                "desc": desc,
                                "price": price,
                                "begin": float(dim.get("beginRange", "0")),
                                "end": float(dim.get("endRange", "inf")),
                            })
                            if debug: logger.debug(f"   ✔️ Matched transfer tier: {desc} → {price}")

    if not egress_prices:
        logger.warning(f"⚠️ No egress prices found for {region_human}, using static defaults.")
        _warn_static("transfer", "egressPrice", debug)
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

    # Sort and build tier structure
    egress_prices.sort(key=lambda x: x["begin"])
    pricing_tiers = {"freeTier": {"limit": 100, "price": 0}}
    for i, tier in enumerate(egress_prices, start=1):
        limit = tier["end"] if tier["end"] != float("inf") else "Infinity"
        pricing_tiers[f"tier{i}"] = {"limit": limit, "price": tier["price"]}
        
    return {"pricing_tiers": pricing_tiers, "egressPrice": egress_prices[0]["price"]}

def _fetch_twinmaker_prices(region_human: str, pricing_client: Any, debug: bool = False) -> Dict[str, float]:
    """
    Specialized fetcher for TwinMaker.
    Checks multiple service codes (IOTTwinMaker, IOTTwinMakerQueries).
    """
    field_map = AWS_SERVICE_KEYWORDS["twinmaker"]["fields"]
    prices = {}
    
    for service_code in ["IOTTwinMaker", "IOTTwinMakerQueries"]:
        price_list = _fetch_api_products(pricing_client, service_code, region_human)
        fetched = _extract_prices_from_api_response(price_list, field_map, debug=debug)
        prices.update(fetched)

    return prices

def _fetch_grafana_prices(region_human: str, pricing_client: Any, debug: bool = False) -> Dict[str, float]:
    """
    Specialized fetcher for Grafana.
    Currently returns static defaults as dynamic fetching is TODO.
    """
    prices = STATIC_DEFAULTS["grafana"]
    _warn_static("grafana", "grafana", debug)
    return prices

# Dispatch dictionary for specialized services
SPECIALIZED_FETCHERS: Dict[str, Callable] = {
    "transfer": _fetch_transfer_prices,
    "twinmaker": _fetch_twinmaker_prices,
    "grafana": _fetch_grafana_prices,
}

# -------------------------------------------------------------------
# Main Fetcher
# -------------------------------------------------------------------

def fetch_aws_price(service_name: str, service_code: str, region_code: str, region_map: Dict[str, str], aws_credentials: Optional[Dict] = None, debug: bool = False) -> Dict[str, Any]:
    """
    Fetch pricing for a specific AWS service in a given region.
    
    Args:
        service_name: Neutral service name (e.g., 'storage_hot').
        service_code: AWS Service Code (e.g., 'AmazonDynamoDB').
        region_code: AWS Region Code (e.g., 'eu-central-1').
        region_map: Mapping of region codes to human-readable names.
        aws_credentials: Optional dictionary of AWS credentials.
        debug: Boolean to enable debug logging.
        
    Returns:
        Dictionary of fetched prices.
    """
    region_human = region_map.get(region_code)
    if not region_human:
        logger.warning(f"⚠️ Unknown AWS region code: {region_code}")
        return {}

    neutral_service_name = service_name.lower().replace(" ", "_")
    
    # 1. Initialize Client
    pricing_client = _get_pricing_client(aws_credentials)
    if not pricing_client:
        _warn_static(neutral_service_name, "client_error", debug)
        return STATIC_DEFAULTS.get(neutral_service_name, {})

    logger.info(f"🔍 Fetching AWS {service_name} pricing for {region_human}...")

    # 2. Check for Specialized Fetcher
    if neutral_service_name in SPECIALIZED_FETCHERS:
        prices = SPECIALIZED_FETCHERS[neutral_service_name](region_human, pricing_client, debug)
        logger.info(f"✅ Final AWS {neutral_service_name} pricing: {prices}")
        print("")
        return prices

    # 3. Standard Fetching Logic
    service_config = AWS_SERVICE_KEYWORDS.get(neutral_service_name)
    if not service_config:
        logger.warning(f"⚠️ No keyword config for service: {service_name}")
        _warn_static(neutral_service_name, "no_config", debug)
        return STATIC_DEFAULTS.get(neutral_service_name, {})

    # Fetch raw products
    price_list = _fetch_api_products(pricing_client, service_code, region_human)
    
    # Extract prices
    prices = _extract_prices_from_api_response(
        price_list, 
        service_config["fields"], 
        include_keywords=service_config.get("include"),
        exclude_keywords=service_config.get("exclude"),
        debug=debug
    )

    # Handle tiers if defined
    if "tier_keywords" in service_config and isinstance(service_config["tier_keywords"], dict):
        for tier_group, tiers in service_config["tier_keywords"].items():
            tier_data = {}
            for tier_name, keywords in tiers.items():
                tier_prices = _extract_prices_from_api_response(
                    price_list, 
                    {tier_name: keywords}, 
                    include_keywords=service_config.get("include"),
                    exclude_keywords=service_config.get("exclude"),
                    debug=debug
                )
                if tier_prices:
                    tier_data[tier_name] = list(tier_prices.values())[0]
            if tier_data:
                prices[tier_group] = tier_data

    # 4. Merge with Defaults
    defaults = STATIC_DEFAULTS.get(neutral_service_name, {})
    for k, v in defaults.items():
        if k not in prices:
            prices[k] = v
            _warn_static(neutral_service_name, k, debug)

    logger.info(f"✅ Final AWS {neutral_service_name} pricing: {prices}")
    print("")
    return prices
