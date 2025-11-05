import boto3, json, traceback, copy
import py.constants as CONSTANTS
from py.config_loader import load_json_file, load_aws_credentials
from py.logger import logger

# -------------------------------------------------------------------
# Region mapping + defaults
# -------------------------------------------------------------------
AWS_REGION_NAMES = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "eu-central-1": "EU (Frankfurt)",
    "eu-west-1": "EU (Ireland)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-northeast-1": "Asia Pacific (Tokyo)"
}

STATIC_DEFAULTS = {
    "transfer": {"egressPrice": 0.09},
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
            # "requestPrice": ["get and all other requests", "per 1,000", "per 10,000"],
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
}


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
    logger.info(f"✅ Final AWS transfer pricing tiers: {pricing_tiers}")
    print("")
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
    """Fetch IoT TwinMaker + Queries pricing using unified parser."""
    field_map = AWS_SERVICE_KEYWORDS["twinmaker"]["fields"]
    include_keywords = AWS_SERVICE_KEYWORDS["twinmaker"]["include"]

    all_prices = {}
    for svc in ["IOTTwinMaker", "IOTTwinMakerQueries"]:
        for with_location in (True, False):
            price_list = _fetch_pricing_response(pricing_client, svc, region_human, with_location=with_location)
            partial = _parse_price_dimensions(price_list, field_map, include_keywords, [], debug)
            all_prices.update(partial)
    defaults = {
        "entityPrice": 0.05,
        "unifiedDataAccessAPICallsPrice": 0.0000015,
        "queryPrice": 0.00005,
    }
    for k, v in defaults.items():
        if k not in all_prices:
            logger.warning(f"⚠️ Using default for twinmaker.{k} (not returned by API)")
            all_prices[k] = v
    logger.info(f"✅ Final IoT TwinMaker pricing: {all_prices}")
    print("")
    return all_prices


# -------------------------------------------------------------------
# Main unified fetcher
# -------------------------------------------------------------------
def fetch_aws_price(credentials: dict, service_mapping: dict, neutral_service_name: str, region_name: str, debug=False):
    """Fetch AWS pricing for any neutral service, dispatching specialized handlers as needed."""
    aws_credentials = copy.deepcopy(credentials)
    aws_credentials["region_name"] = aws_credentials.pop("aws_region", None)
    
    if neutral_service_name == "grafana":
        prices = STATIC_DEFAULTS["grafana"]
        logger.info(f"ℹ️ Using static Grafana pricing")
        logger.info(f"✅ Final AWS prices for {neutral_service_name}: {prices}")
        print("")
        return prices

    pricing_client = boto3.client("pricing", **aws_credentials)
    region_human = AWS_REGION_NAMES.get(region_name, region_name)

    if neutral_service_name == "transfer":
        return fetch_transfer_pricing(region_human, pricing_client, debug)
    if neutral_service_name == "twinmaker":
        return fetch_twinmaker_pricing(region_human, pricing_client, debug)

    # Normal path
    service_code = service_mapping.get(neutral_service_name, {}).get("aws", neutral_service_name)
    if neutral_service_name == "storage_archive":
        service_code = "AmazonS3"

    logger.info(f"--- Fetching AWS prices for {neutral_service_name} ({service_code}) in {region_human} ---")

    try:
        price_list = _fetch_pricing_response(pricing_client, service_code, region_human)
        service_cfg = AWS_SERVICE_KEYWORDS.get(neutral_service_name, {})
        field_map = service_cfg.get("fields", {})
        include = service_cfg.get("include", [])
        exclude = service_cfg.get("exclude", [])
        prices = _parse_price_dimensions(price_list, field_map, include, exclude, debug)
        if neutral_service_name in STATIC_DEFAULTS:
            prices = {**prices, **STATIC_DEFAULTS[neutral_service_name]}
        logger.info(f"✅ Final AWS prices for {neutral_service_name}: {prices}")
        print("")
        return prices

    except Exception as e:
        logger.debug(traceback.format_exc())
        logger.error(f"⚠️ AWS pricing fetch failed for {neutral_service_name}: {e}")
        return STATIC_DEFAULTS.get(neutral_service_name, {})
