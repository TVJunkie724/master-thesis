# Refactored Azure price fetcher - Simplified & Readable

import json, copy
from typing import Dict, Any, Iterable, List, Optional
import requests

from backend.logger import logger
import backend.config_loader as config_loader
# from backend.fetch_data import initial_fetch_azure # No longer needed for global load

# -----------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# -----------------------------------------------------------------------------

RETAIL_API_BASE = "https://prices.azure.com/api/retail/prices"
HTTP_TIMEOUT = 12

# Global loading removed. Passed as arguments now.
# AZURE_REGION_NAMES = ...
# SERVICE_MAPPING = ...

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

STATIC_DEFAULTS_AZURE = {
    "transfer": {"egressPrice": 0.08},
    "iot": {
        "pricing_tiers": {
            "freeTier": {"limit": 240_000, "threshold": 0, "price": 0},
            "tier1": {"limit": 120_000_000, "threshold": 12_000_000},
            "tier2": {"limit": 1_800_000_000, "threshold": 180_000_000},
            "tier3": {"limit": "Infinity", "threshold": 9_000_000_000},
        }
    },
    "functions": {"freeRequests": 1_000_000, "freeComputeTime": 400_000},
    "storage_hot": {
        "requestPrice": 0.0584,
        "minimumRequestUnits": 400,
        "RUsPerRead": 1,
        "RUsPerWrite": 10,
    },
    "storage_cool": {"upfrontPrice": 0.0001, "writePrice": 0.00001, "readPrice": 0.000001},
    "storage_archive": {"writePrice": 0.000013},
    "twinmaker": {
        "queryUnitTiers": [
            {"lower": 1, "upper": 99, "value": 15},
            {"lower": 100, "upper": 9999, "value": 1500},
            {"lower": 10000, "value": 4000},
        ],
    },
    "grafana": {"userPrice": 6.0, "hourlyPrice": 0.069},
    "orchestration": {"pricePer1kStateTransitions": 0.000125}, # Raw price per 1 action
    "event_bus": {"pricePerMillionEvents": 0.60}, # Raw price per 1M events
    "data_access": {"pricePerMillionCalls": 0.042}, # Raw price per 10K calls (4.20 per 1M)
}

AZURE_SERVICE_KEYWORDS: Dict[str, Dict[str, Any]] = {
    "functions": {
        "meters": {
            "requestPrice": {"meter_keywords": ["Standard Total Executions"], "unit_keywords": ["1 Million", "1M", "10"]},
            "durationPrice": {"meter_keywords": ["Always Ready Execution Time"], "unit_keywords": ["GB Second", "GiB Second", "GiB Hour"]},
        },
        "include": [], # Removed "Functions" to be more permissive
    },
    "iot": {"tiers": {"S1": "tier1", "S2": "tier2", "S3": "tier3"}},
    "storage_hot": {
        "meters": {"storagePrice": {"meter_keywords": ["Data Stored"], "unit_keywords": ["gb/month", "1 gb/month", "100 gb/month"]}},
        "include": [], # Removed "Cosmos DB" to be more permissive
    },
    "storage_cool": {
        "meters": {
            "storagePrice": {"meter_keywords": ["cool", "data stored"], "unit_keywords": ["gb/month", "1 gb/month", "100 gb/month"]},
            "writePrice": {"meter_keywords": ["cold lrs data write"], "unit_keywords": ["gb"]},
            "readPrice": {"meter_keywords": ["cold lrs read operations"], "unit_keywords": ["10K"]},
            "dataRetrievalPrice": {"meter_keywords": ["cool data retrieval"], "unit_keywords": ["gb", "per gb"]},
        },
        "include": ["blob storage"],
    },
    "storage_archive": {
        "meters": {
            "storagePrice": {"meter_keywords": ["archive", "data stored", "lrs"], "unit_keywords": ["gb/month", "1 gb/month", "100 gb/month"]},
            "writePrice": {"meter_keywords": ["Archive Data Write"], "unit_keywords": ["gb"]},
            "readPrice": {"meter_keywords": ["archive read operations"], "unit_keywords": ["10K"]},
            "dataRetrievalPrice": {"meter_keywords": ["archive data retrieval"], "unit_keywords": ["gb", "per gb"]},
        },
        "include": ["blob storage"],
    },
    "twinmaker": {
        "meters": {
            "messagePrice": {"meter_keywords": ["Standard Message"], "unit_keywords": ["1K"]},
            "operationPrice": {"meter_keywords": ["Standard Operations"], "unit_keywords": ["1K"]},
            "queryPrice": {"meter_keywords": ["Standard Query Units"], "unit_keywords": ["1K"]},
        },
        "include": ["Digital Twins"],
    },
    "grafana": {},
    "orchestration": {
        "meters": {
            "pricePer1kStateTransitions": {"meter_keywords": ["Consumption Standard Connector Actions"], "unit_keywords": ["1"]}
        },
    },
    "event_bus": {
        "meters": {
            "pricePerMillionEvents": {"meter_keywords": ["Standard Event Operations"], "unit_keywords": ["1M", "100K"]}
        },
    },
    "data_access": {
        "meters": {
            "pricePerMillionCalls": {"meter_keywords": ["Consumption Calls"], "unit_keywords": ["10K"]}
        },
    },
}

# -----------------------------------------------------------------------------
# API & MATCHING HELPERS
# -----------------------------------------------------------------------------

def _retail_query_items(params: Dict[str, str]) -> Iterable[Dict[str, Any]]:
    """Yields all items from the Azure Retail API for the given params."""
    next_link = RETAIL_API_BASE
    first = True
    while next_link:
        try:
            resp = requests.get(next_link, params=params if first else None, timeout=HTTP_TIMEOUT)
            if resp.status_code != 200:
                logger.warning(f"Azure Retail API {resp.status_code}: {resp.text[:200]}")
                return
            data = resp.json()
            for item in data.get("Items", []):
                yield item
            next_link = data.get("NextPageLink")
            first = False
        except Exception as e:
            logger.error(f"Error querying Azure Retail API: {e}")
            return

def _fetch_rows_with_fallback(region: str, service_names: List[str], debug: bool = False) -> List[Dict[str, Any]]:
    """Fetch pricing rows, trying the primary region then fallbacks."""
    region = region.lower()
    tried_regions = []
    
    # 1. Try primary + fallback regions
    for r in [region] + REGION_FALLBACK.get(region, []):
        tried_regions.append(r)
        # Construct OData filter: armRegionName eq 'r' and (serviceName eq 's1' or ...)
        service_filter = " or ".join([f"serviceName eq '{s}'" for s in service_names])
        odata_filter = f"armRegionName eq '{r}' and ({service_filter})"
        
        rows = list(_retail_query_items({"$filter": odata_filter}))
        if rows:
            if r != region and debug:
                logger.debug(f"   ℹ️ Used fallback region '{r}' for {service_names}")
            return rows

    # 2. Last resort: Try without region filter (global services)
    service_filter = " or ".join([f"serviceName eq '{s}'" for s in service_names])
    rows = list(_retail_query_items({"$filter": service_filter}))
    if rows:
        return rows
        
    logger.warning(f" ℹ️ No retail prices found for {service_names} in {region}. Tried: {tried_regions}")
    return []

def _sanitize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out noisy fields for cleaner logging."""
    # Strict allowlist as requested
    keep = {"productName", "meterName", "skuName", "unitOfMeasure", "unitPrice", "currencyCode", "serviceName"}
    return {k: v for k, v in row.items() if k in keep}

def _find_best_match(rows: List[Dict[str, Any]], meter_kw: str, unit_kw: str, include_kw: List[str], debug: bool) -> Optional[Dict[str, Any]]:
    """Find the best matching row based on keywords, prioritizing non-zero prices."""
    best_row = None
    best_price = None
    candidates = []

    for r in rows:
        product = (r.get("productName") or "").lower()
        meter = (r.get("meterName") or "").lower()
        unit = (r.get("unitOfMeasure") or "").lower()
        sku = (r.get("skuName") or "").lower()
        price = float(r.get("unitPrice", 0))

        # 1. Basic Filtering
        if "reserved" in product: continue
        if include_kw and not all(k.lower() in product for k in include_kw): continue 
        if meter_kw.lower() not in meter: continue
        if unit_kw.lower() not in unit: continue
        
        candidates.append(r)

        # 2. Prioritization Logic
        # We want the cheapest *paid* option if possible, or free if that's all there is.
        # But we prefer a non-zero price over a zero price to avoid "free tier" traps when we want unit costs.
        
        if best_row is None:
            best_row = r
            best_price = price
        elif best_price == 0 and price > 0:
            best_row = r
            best_price = price
        elif price > 0 and price < best_price:
            best_row = r
            best_price = price
            
    if not best_row and debug:
         # Log why we didn't find a match if we expected one
         if candidates:
             logger.debug(f"   ⚠️ Found {len(candidates)} candidates but none selected (logic error?):")
             for c in candidates[:3]:
                 logger.debug(f"      - {_sanitize_row(c)}")
         else:
             # If no candidates, we might want to know what we missed
             pass
            
    return best_row

# -----------------------------------------------------------------------------
# PRICE NORMALIZATION
# -----------------------------------------------------------------------------

def _normalize_price(price: float, unit_text: str, neutral_service: str) -> float:
    """Normalize price to a standard unit (usually per 1 or per 1M)."""
    unit_text = unit_text.lower()
    
    # Special Case: Logic Apps (Actions are per 1, we want per 1k)
    if neutral_service == "orchestration" and "1" in unit_text:
        return price * 1000

    # Special Case: Blob Storage (Operations are per 10k, we want per 1)
    if neutral_service in ["storage_cool", "storage_archive"] and "10k" in unit_text:
        return price / 10_000

    # Standard Normalization (to per 1M or per GB)
    if "10k" in unit_text:
        return price * 100 # 10k * 100 = 1M
    elif "10" in unit_text:
        return price * 100_000 # 10 * 100k = 1M
    elif "100" in unit_text:
        return price * 10_000 # 100 * 10k = 1M
        
    return price

# -----------------------------------------------------------------------------
# FETCHERS
# -----------------------------------------------------------------------------

def _fetch_iot_hub(rows: List[Dict[str, Any]], neutral: str, debug: bool) -> Dict[str, Any]:
    """Fetch IoT Hub tiered pricing."""
    if debug:
        logger.debug(f"-- Available rows for {neutral} ({len(rows)}) --")
        for r in rows:
            logger.debug("    " + str(_sanitize_row(r)))
        logger.debug("------------------------------------------------")

    defaults = STATIC_DEFAULTS_AZURE["iot"]
    result = {"pricing_tiers": {"freeTier": defaults["pricing_tiers"]["freeTier"].copy()}}
    
    sku_map = AZURE_SERVICE_KEYWORDS[neutral]["tiers"]
    
    for sku_label, tier_key in sku_map.items():
        # Find row matching SKU and "unit" meter
        match = next((r for r in rows if sku_label in (r.get("skuName") or "") and "unit" in (r.get("meterName") or "").lower()), None)
        
        if match:
            price = float(match.get("unitPrice", 0))
            result["pricing_tiers"][tier_key] = {
                "limit": defaults["pricing_tiers"][tier_key]["limit"],
                "threshold": defaults["pricing_tiers"][tier_key]["threshold"],
                "price": price
            }
            if debug: logger.debug(f"   ✔️ Matched IoT {tier_key}: {_sanitize_row(match)}")
        else:
            if debug: logger.debug(f"   ❌ IoT {tier_key} not found (SKU: {sku_label})")
            pass
            
    return result

def _fetch_standard(rows: List[Dict[str, Any]], neutral: str, debug: bool) -> Dict[str, Any]:
    """Standard fetcher for most services, handling unit normalization."""
    if debug:
        logger.debug(f"-- Available rows for {neutral} ({len(rows)}) --")
        more_than_10_rows = len(rows) > 10
        for r in (rows if not more_than_10_rows else rows[:10]):
            logger.debug("    " + str(_sanitize_row(r)))
        if more_than_10_rows:
            logger.debug("    ...")
            logger.debug("    (and {} more)")
        logger.debug("------------------------------------------------")

    spec = AZURE_SERVICE_KEYWORDS.get(neutral)
    result = {}
    
    meter_items = None
    try:
        # Meters not specified -> skip
        # Assume all required values are in STATIC_DEFAULTS_AZURE
        meter_items = spec["meters"]
    except KeyError:
        return result

    for key, m in meter_items.items():
        match = None
        # Try all combinations of meter/unit keywords
        for mk in m["meter_keywords"]:
            for uk in m["unit_keywords"]:
                match = _find_best_match(rows, mk, uk, spec.get("include", []), debug)
                if match: break
            if match: break
            
        if match:
            raw_price = float(match.get("unitPrice", 0))
            unit_text = match.get("unitOfMeasure", "")
            
            # Use default if API returns 0 (and we have a default)
            if raw_price == 0 and key in STATIC_DEFAULTS_AZURE.get(neutral, {}):
                logger.warning(f" ℹ️ Zero price for {neutral}.{key}, using default.")
                result[key] = STATIC_DEFAULTS_AZURE[neutral][key]
                continue

            # Normalize
            final_price = _normalize_price(raw_price, unit_text, neutral)
            
            # Special Post-Processing
            if neutral == "storage_hot" and key == "requestPrice":
                # Cosmos DB: 100 RU/s/hr -> 1 RU/s/mo
                final_price = (raw_price * 730) / 100
                
            result[key] = final_price
            
            # Derived fields
            if key == "requestPricePerMillion":
                result["requestPrice"] = final_price / 1_000_000
            elif key == "durationPricePerGBSecond":
                result["durationPrice"] = final_price

            if debug:
                logger.debug(f"   ✔️ Matched {neutral}.{key}: {_sanitize_row(match)}")
                logger.debug(f"      Price: {raw_price} ({unit_text}) -> Normalized: {final_price}")
        else:
            if debug: 
                logger.debug(f"   ❌ {neutral}.{key} not found.")
                logger.debug(f"      Searched for meter_kw='{m['meter_keywords']}' unit_kw='{m['unit_keywords']}'")

    return result

# -----------------------------------------------------------------------------
# MAIN ENTRY POINT
# -----------------------------------------------------------------------------

def fetch_azure_price(service_name: str, region_code: str, region_map: Dict[str, str], service_mapping: Dict[str, Any], debug: bool=False) -> Dict[str, Any]:
    """
    Fetch Azure pricing for a given service.
    """
    neutral = service_name.lower()
    
    # 1. Get Service Name from Mapping (passed as argument)
    mapping = service_mapping.get(neutral, {})
    azure_service_name = mapping.get("azure")

    # 2. Prepare Defaults
    defaults = copy.deepcopy(STATIC_DEFAULTS_AZURE.get(neutral, {}))
    
    if not azure_service_name:
        logger.warning(f"⚠️ No Azure service mapping for {neutral}")
        return {} 

    # 3. Fetch Rows
    # Use region_map passed as argument
    region = region_map.get(region_code.lower(), region_code.lower())
    
    # Handle case where service name might be a list (e.g. storage) or single string
    service_names = [azure_service_name] if isinstance(azure_service_name, str) else azure_service_name
    
    # Special handling for storage types that map to multiple Azure services in our config
    if neutral in ["storage_cool", "storage_archive"] and not isinstance(service_names, list):
         service_names = ["Blob Storage", "Storage"] 

    rows = _fetch_rows_with_fallback(region, service_names, debug)
    
    if not rows:
        fetched = {}
    else:
        # 4. Dispatch to Fetcher
        if neutral == "iot":
            fetched = _fetch_iot_hub(rows, neutral, debug)
        else:
            fetched = _fetch_standard(rows, neutral, debug)

    # 5. Apply Defaults if values could not be fetched and log the use of defaults
    for key, value in defaults.items():
        if key not in fetched:
            # fetched[key] = value
            logger.info(f"    ℹ️ Using static value for Azure.{neutral}.{key}")
            fetched[key] = value

    logger.info(f"✅ Final Azure prices for {neutral}: {fetched}")
    print("")
    return fetched