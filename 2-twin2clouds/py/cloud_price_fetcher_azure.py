# Refactored Azure price fetcher matching AWS structure and logging style
# (Full file provided here)

import json, copy, traceback
from typing import Dict, Any, Iterable, List, Optional
import requests

from py.logger import logger
import py.constants as CONSTANTS

# -----------------------------------------------------------------------------
# REGION MAP + DEFAULTS
# -----------------------------------------------------------------------------

AZURE_REGION_NAMES = {
    "westeurope": "westeurope",
    "northeurope": "northeurope",
    "uksouth": "uksouth",
    "ukwest": "ukwest",
    "francecentral": "francecentral",
    "germanywestcentral": "germanywestcentral",
    "swedencentral": "swedencentral",
    "eastus": "eastus",
    "eastus2": "eastus2",
    "westus": "westus",
    "westus2": "westus2",
    "centralus": "centralus",
    "italynorth": "italynorth",
    "switzerlandnorth": "switzerlandnorth",
}

REGION_FALLBACK = {
    "westeurope": ["northeurope", "francecentral", "italynorth", "germanywestcentral"],
    "northeurope": ["westeurope", "swedencentral", "uksouth"],
    "uksouth": ["ukwest", "westeurope"],
    "francecentral": ["westeurope", "switzerlandnorth"],
    "germanywestcentral": ["westeurope", "northeurope"],
    "eastus": ["eastus2", "centralus", "westus"],
    "westus": ["westus2", "centralus", "eastus"],
    "centralus": ["eastus", "westus"],
}

RETAIL_API_BASE = "https://prices.azure.com/api/retail/prices"
HTTP_TIMEOUT = 12

STATIC_DEFAULTS_AZURE = {
    "transfer": {"egressPrice": 0.08},

    "iot": {
        "pricing_tiers": {
            "freeTier": {
                "limit": 240_000,      # 240k messages/month, 8k messages/day
                "threshold": 0,
                "price": 0
            },
            "tier1": {
                "limit": 120_000_000,      # 120 million
                "threshold": 12_000_000    # 12 million
            },
            "tier2": {
                "limit": 1_800_000_000,    # 1.8 billion
                "threshold": 180_000_000   # 180 million
            },
            "tier3": {
                "limit": "Infinity",
                "threshold": 9_000_000_000
            }
        }
    },
    "functions": {"freeRequests": 1_000_000, "freeComputeTime": 400_000},
    "storage_hot": {
        "requestPrice": 0.0584,
        "minimumRequestUnits": 400,
        "RUsPerRead": 1,
        "RUsPerWrite": 10,
    },
    "storage_cool": {
        "upfrontPrice": 0.0001,
        "writePrice": 0.02,
        "readPrice": 0.01,
    },
    "twinmaker": {
      "messagePrice": 0.000001,
      "operationPrice": 0.0000025,
      "queryPrice": 0.0000005, 
      "queryUnitTiers": [
        {"lower": 1, "upper": 99, "value": 15}, 
        {"lower": 100, "upper": 9999, "value": 1500},
        {"lower": 10000, "value": 4000}
      ]
    },
    "grafana": {"userPrice": 6.0, "hourlyPrice": 0.069},
}

# -----------------------------------------------------------------------------
# SERVICE KEYWORD MAP (similar to AWS structure)
# -----------------------------------------------------------------------------

AZURE_SERVICE_KEYWORDS: Dict[str, Dict[str, Any]] = {
    "functions": {
        "serviceName": "Functions",
        "meters": {
            "requestPrice": {
                "meter_keywords": ["Total Executions"],
                "unit_keywords": ["10", "1 Million", "1M"],
            },
            "durationPrice": {
                "meter_keywords": ["Execution Time"],
                "unit_keywords": ["GB Second", "GiB Second", "GiB Hour"],
            },
        },
        "include": ["Standard", "Functions"],
    },
    "transfer": {
        "serviceName": "Bandwidth",
        "meters": {
            "egressPrice": {
                "meter_keywords": ["Data Transfer Out"],
                "unit_keywords": ["GB"],
            },
        },
        "exclude": ["China"],
    },
    "iot": {
        "serviceName": "IoT Hub",
        "tiers": {"S1": "tier1", "S2": "tier2", "S3": "tier3"},
    },
    "storage_hot": {
        "serviceName": "Azure Cosmos DB",
        "meters": {
            "storagePrice": {
                "meter_keywords": ["Standard Data Stored"],
                "unit_keywords": ["gb/month", "1 gb/month", "100 gb/month"],
            },
        },
        "include": ["Cosmos DB"]
    },
    "storage_cool": {
        "serviceName": ["Blob Storage", "Storage"],
        "meters": {
            "storagePrice": {
                "meter_keywords": ["cool", "data stored"],
                "unit_keywords": ["gb/month", "1 gb/month", "100 gb/month"],
            },
            "writePrice": {
                "meter_keywords": ["cold lrs data write"],
                "unit_keywords": ["gb"],
            },
            "readPrice": {
                "meter_keywords": ["read"],
                "unit_keywords": ["gb"],
            },
            "dataRetrievalPrice": {
                "meter_keywords": ["cool data retrieval"],
                "unit_keywords": ["gb", "per gb"],
            },
        },
        "include": ["blob storage", "cool", "data stored"],
        "exclude": [
            "reserved", "ra-grs", "grs", "zrs",
            "operation", "transaction",
            "disk", "tables", "data lake",
        ],
    },
    "storage_archive": {
        "serviceName": ["Blob Storage", "Storage"],
        "meters": {
            "storagePrice": {
                "meter_keywords": ["archive", "data stored", "lrs", ],
                "unit_keywords": ["gb/month", "1 gb/month", "100 gb/month"],
            },
            "writePrice": {
                "meter_keywords": ["Archive Data Write"],
                "unit_keywords": ["gb"],
            },
            "dataRetrievalPrice": {
                "meter_keywords": ["archive data retrieval"],
                "unit_keywords": ["gb", "per gb"],
            }
        },
        "include": ["blob storage", "archive", "data stored"],
        "exclude": [
            "reserved", "ra-grs", "grs", "zrs",
            "operation", "transaction",
            "disk", "tables", "data lake",
        ],
    }

}

logged_rows = set()
no_match_counter = 0

# -----------------------------------------------------------------------------
# RETAIL API HELPERS
# -----------------------------------------------------------------------------
def _retail_query_items(params: Dict[str, str]) -> Iterable[Dict[str, Any]]:
    next_link = RETAIL_API_BASE
    first = True
    while next_link:
        resp = requests.get(next_link, params=params if first else None, timeout=HTTP_TIMEOUT)
        first = False
        if resp.status_code != 200:
            logger.warning(f"Azure Retail API {resp.status_code}: {resp.text[:300]}")
            return
        data = resp.json()
        for item in data.get("Items", []):
            yield item
        next_link = data.get("NextPageLink")


def _iter_with_region_fallback(region: str, service_names, debug = False) -> List[Dict[str, Any]]:
    """Fetch Retail API rows for any of the given service names, with fallback."""
    region = region.lower()
    tried = []
    rows: List[Dict[str, Any]] = []
    result = []

    # Normalize to list
    if isinstance(service_names, str):
        service_names = [service_names]

    for r in [region] + REGION_FALLBACK.get(region, []):
        tried.append(r)

        service_filters = " or ".join([f"serviceName eq '{s}'" for s in service_names])
        odata_filter = f"armRegionName eq '{r}' and ({service_filters})"
        params = {"$filter": odata_filter}

        fetched = list(_retail_query_items(params))
        if fetched:
            rows.extend(fetched)

        if rows:
            if r != region:
                if debug: logger.debug(f"   ℹ️ Used '{r}' pricing for {service_names} (requested {region}). Tried: {tried}")
            result = rows if rows else []

    # Fallback: try without region
    if not result:
        service_filters = " or ".join([f"serviceName eq '{s}'" for s in service_names])
        odata_filter = f"({service_filters})"
        params = {"$filter": odata_filter}

        fetched = list(_retail_query_items(params))
        if fetched:
            rows.extend(fetched)

        if rows:
            logger.info(f"   ℹ️ Used '{r}' pricing for {service_names} without checking region.")
            result = rows if rows else []
    
    if not result:
        logger.warning(f"No retail prices found for {service_names} in {region}. Tried: {tried}")
        result = []
    return result


# -----------------------------------------------------------------------------
# SMALL HELPERS
# -----------------------------------------------------------------------------

def _filter_row(row: Dict[str, Any]):
    return {
        "unitPrice": row.get("unitPrice"),
        "meterName": row.get("meterName"),
        "unitOfMeasure": row.get("unitOfMeasure"),
        "skuName": row.get("skuName"),
        "productName": row.get("productName"),
    }

def _get_unit_price(row: Optional[Dict[str, Any]]) -> Optional[float]:
    if not row:
        return None
    try:
        return float(row.get("unitPrice", 0))
    except:
        return None
    
def _warn_static(neutral: str, field: str):
    logger.warning(f" ℹ️ Using default value for Azure.{neutral}.{field} (not returned by API)")

# -----------------------------------------------------------------------------
# MATCHING
# -----------------------------------------------------------------------------
def _find_matching_row(
    rows: List[Dict[str, Any]],
    meter_kw: str,
    unit_kw: str,
    *,
    neutral: str,
    key: str,
    debug: bool
):
    spec = AZURE_SERVICE_KEYWORDS.get(neutral, {})
    include_kw = [x.lower() for x in spec.get("include", [])]
    exclude_kw = [x.lower() for x in spec.get("exclude", [])]

    best = None
    global no_match_counter
    global logged_rows

    for r in rows:
        filtered = _filter_row(r)

        product = (r.get("productName") or "").lower()
        meter   = (r.get("meterName") or "").lower()
        unit    = (r.get("unitOfMeasure") or "").lower()
        sku     = (r.get("skuName") or "").lower()
        currency = r.get("currencyCode")

        row_sig = (neutral, key, product, meter, unit, sku)
        if row_sig in logged_rows:
            continue
        logged_rows.add(row_sig)
        

        # ---------- EXCLUDE ----------
        exclude_kw_exists = any(x in product or x in meter or x in sku for x in exclude_kw)
        exclude_replication_tiers = any(x in product or x in sku for x in ["grs", "ra-grs", "zrs", "gzs"])
        exist_reserved_product = "reserved" in product
        exist_read_or_write_for_storageprice = key == "storagePrice" and ("write" in meter or "read" in meter)

        if exclude_kw_exists or exclude_replication_tiers or exist_reserved_product or exist_read_or_write_for_storageprice:
            # if debug: logger.debug(f"   🪚 Excluded: {filtered}")
            continue

        # ---------- INCLUDE ----------
        exist_include_kw_in_product_or_meter = any(x in product for x in include_kw)
        meter_kw_matches = meter_kw.lower() in meter
        unit_kw_matches = unit_kw.lower() in unit
        if not exist_include_kw_in_product_or_meter or not meter_kw_matches or not unit_kw_matches:
                no_match_counter += 1
                if debug: logger.debug(f"   ❌ No Match ({no_match_counter}): {filtered}")
                continue

        # ---------- Valid price ----------
        price = _get_unit_price(r)
        if price is None:
            continue
        if price == 0:
            logger.warning(f" ℹ️ Zero price found for Azure.{neutral}.{key}")
            if key in STATIC_DEFAULTS_AZURE.get(neutral, {}):
                price = STATIC_DEFAULTS_AZURE[neutral][key]
                logger.warning(f" ℹ️ Value was zero for Azure.{neutral}.{key}, using default: {price}")

        # Best = lowest price
        if best is None or price < _get_unit_price(best):
            best = r

        logger.debug(f"   ✔️ Matched ({neutral} - {key}): {price} {currency} <== {filtered}")
    return best





# -----------------------------------------------------------------------------
# SERVICE FETCHERS
# -----------------------------------------------------------------------------
def _fetch_iot(rows: List[Dict[str, Any]], neutral: str, debug: bool) -> Dict[str, Any]:
    defaults = STATIC_DEFAULTS_AZURE["iot"]
    tier_defaults = defaults["pricing_tiers"]

    result = {
        "pricing_tiers": {
            "freeTier": tier_defaults["freeTier"].copy()
        }
    }

    SKU_MAP = AZURE_SERVICE_KEYWORDS[neutral]["tiers"]

    filtered = [_filter_row(r) for r in rows]

    for sku_label, tier_key in SKU_MAP.items():
        matched_price = None

        for r in filtered:
            sku = r.get("skuName") or ""
            meter = r.get("meterName") or ""

            if sku_label in sku and "unit" in meter.lower():
                price = _get_unit_price(r)
                if price:
                    matched_price = price
                    logger.debug(f"   ✔️ Match {neutral}.{tier_key} → sku='{sku}', meter='{meter}', unit='{r.get('unitOfMeasure')}', price={price}")
                    break

        if matched_price is None:
            if debug: 
                logger.debug(
                    f"     ❌ No match for {neutral}.{tier_key} "
                    f"(sku_kw='{sku_label}', meter_kw='unit') in {len(filtered)} rows."
                )
            _warn_static(neutral, tier_key)
            continue

        result["pricing_tiers"][tier_key] = {
            "limit": tier_defaults[tier_key]["limit"],
            "threshold": tier_defaults[tier_key]["threshold"],
            "price": matched_price,
        }

    return result

def _fetch_generic_meter_service(rows, neutral: str, debug: bool):
    spec = AZURE_SERVICE_KEYWORDS.get(neutral)
    result = {}

    for key, m in spec["meters"].items():
        meter_match = None
        for mk in m["meter_keywords"]:
            for uk in m["unit_keywords"]:
                candidate = _find_matching_row(rows, mk, uk, neutral=neutral, key=key, debug=debug)
                if candidate:
                    meter_match = candidate
                    break
            if meter_match:
                break

        if not meter_match:
            logger.debug(f"---❌ Unable to find: {neutral}.{key} (all keyword combinations failed)")
            continue

        price = _get_unit_price(meter_match)
        if price is None:
            continue

        unit_text = (meter_match.get("unitOfMeasure") or "").lower()

        normalized = price
        if "10" in unit_text:
            normalized = price * (1_000_000 / 10)
        elif "100" in unit_text:
            normalized = price * (1_000_000 / 100)

        result[key] = normalized

        f = _filter_row(meter_match)

        if key == "requestPricePerMillion":
            result["requestPrice"] = normalized / 1_000_000
        elif key == "durationPricePerGBSecond":
            result["durationPrice"] = normalized

    return result

# -----------------------------------------------------------------------------
# MAIN ENTRY
# -----------------------------------------------------------------------------
def fetch_azure_price(service_mapping: Dict[str, Any], neutral_service_name: str, region_name: str, additional_debug: bool=False) -> Dict[str, Any]:
    region = AZURE_REGION_NAMES.get(region_name.lower(), region_name.lower())
    neutral = neutral_service_name.lower()

    spec = AZURE_SERVICE_KEYWORDS.get(neutral)
    default_statics = STATIC_DEFAULTS_AZURE.get(neutral, {})
    
    if not spec:
        for field in STATIC_DEFAULTS_AZURE.get(neutral, {}):
            _warn_static(neutral, field)
        result = copy.deepcopy(STATIC_DEFAULTS_AZURE.get(neutral, {}))

    else:
        service_names = spec.get("serviceName")
        rows = _iter_with_region_fallback(region, service_names, additional_debug)
        if additional_debug: logger.debug(f"   ℹ️ Azure rows for {neutral} in {region}: {len(rows)} found.")
        if not rows:
            result = copy.deepcopy(STATIC_DEFAULTS_AZURE.get(neutral, {}))

        # if neutral == "iot":
        #     result = _fetch_iot(rows, neutral, additional_debug)
        # elif neutral == "functions":
        #     result = _fetch_generic_meter_service(rows, neutral, additional_debug)
        #     for k, v in default_statics.items():
        #         if k not in result:
        #             _warn_static(neutral, k)
        #         result[k] = v
        elif neutral == "transfer":
            result = _fetch_generic_meter_service(rows, neutral, additional_debug)
             
        else:
            result = {}
            # result = _fetch_generic_meter_service(rows, neutral, additional_debug)

    if neutral != "iot":
        result = {**result, **default_statics}
    logger.info(f"✅ Final Azure prices for {neutral}: {result}")
    print("")
    return result