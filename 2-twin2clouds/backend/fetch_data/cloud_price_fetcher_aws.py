import boto3
import json
from typing import Dict, Any, Optional, List, Callable

from backend.logger import logger
import backend.config_loader as config_loader
from backend.aws_pricing_evidence import build_aws_intent_evidence
from backend.fetch_data.fetch_evidence import (
    FieldMatchEvidence,
    MatchStatus,
    RejectedCandidate,
    distinct_prices,
)
from backend.transfer_catalog import (
    build_transfer_catalog,
    build_transfer_evidence,
)
# from backend.fetch_data import initial_fetch_aws # No longer needed for global load

# --------------------------------------------------------------------
# Constants & Configuration
# --------------------------------------------------------------------

# Global loading removed. Passed as arguments now.
# AWS_REGION_NAMES = ...
# SERVICE_MAPPING = ...

STATIC_DEFAULTS = {
    "iot": {"pricePerDeviceAndMonth": 0.0035, "priceRulesTriggered": 0.00000015},
    "functions": {"freeRequests": 1_000_000, "freeComputeTime": 400_000},
    "storage_hot": {"freeStorage": 25},
    "storage_cool": {"upfrontPrice": 0.0001},
    "grafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
    "scheduler": {"jobPrice": 0.000001}, # Fallback if fetch fails
}

TWINMAKER_STANDARD_SUFFIXES = {
    "IoTTwinMaker-Entities": "entityPricePerMonth",
    "IoTTwinMaker-Queries": "queryPrice",
    "IoTTwinMaker-UnifiedDataAccess": "unifiedDataAccessApiCallPrice",
}
TWINMAKER_BUNDLE_ENTITY_RANGES = {
    "TIER_1": (1, 1_000),
    "TIER_2": (1_001, 5_000),
    "TIER_3": (5_001, 10_000),
    "TIER_4": (10_001, 20_000),
}
TWINMAKER_EVIDENCE_SCHEMA_VERSION = "aws-twinmaker-price-list-evidence.v1"


class TwinMakerPricingCatalogError(RuntimeError):
    """Stable base error for TwinMaker Price List failures."""

    code = "AWS_TWINMAKER_CATALOG_FAILED"
    public_message = "AWS TwinMaker catalog pricing could not be refreshed."


class TwinMakerPricingContractError(TwinMakerPricingCatalogError):
    """The AWS Price List response cannot satisfy the TwinMaker contract."""

    code = "AWS_TWINMAKER_CATALOG_CONTRACT_INVALID"
    public_message = "AWS returned an incomplete TwinMaker pricing contract."


class TwinMakerPricingFetchError(TwinMakerPricingCatalogError):
    """The AWS Price List API request failed before contract validation."""

    code = "AWS_TWINMAKER_CATALOG_FETCH_FAILED"
    public_message = "AWS TwinMaker catalog pricing is temporarily unavailable."


AWS_SERVICE_KEYWORDS = {
    "iot": {
        "include": ["iot", "message", "rule", "device shadow", "registry"],
        "exclude": ["lorawan", "fuota", "everynet", "direct message"],
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
            "requestPrice": ["total requests", "request", "requests", "per request", "lambda-managed-instances-request"],
            "durationPrice": ["total compute", "gb-second"],
        },
        "tier_keywords": {
            "durationTiers": {"tier1": ["tier-1", "first"], "tier2": ["tier-2", "next"], "tier3": ["tier-3", "over"]}
        },
    },
    "scheduler": {
        "include": ["scheduler", "scheduled", "invocation"],
        "fields": {
            "jobPrice": ["scheduled invocation", "invocation"]
        }
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
        "include": ["standard-infrequent access", "standard-ia", "infrequent access", "standard - infrequent access", "standard retrieval"],
        "exclude": ["one zone", "intelligent tiering", "glacier", "archive", "checksum", "select"],
        "fields": {
            "storagePrice": ["gb-month of storage used", "gb-month prorated"],
            "requestPrice": ["get and all other requests", "per 1,000", "per 10,000"],
            "dataRetrievalPrice": ["retrieval fee", "per gb retrieved", "flat fee", "data retrieval"],
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

def _fetch_api_products(
    pricing_client,
    service_code: str,
    region_human: str,
    usagetype: Optional[str] = None,
    with_location: bool = True,
    extra_filters: Optional[List[Dict[str, str]]] = None,
    *,
    fail_closed: bool = False,
) -> List[str]:
    """
    Fetch product list from AWS Pricing API.
    Handles filters for region, usage type, and arbitrary extra filters.
    """
    filters = []
    if usagetype:
        filters.append({"Type": "TERM_MATCH", "Field": "usagetype", "Value": usagetype})
    if with_location:
        filters.append({"Type": "TERM_MATCH", "Field": "location", "Value": region_human})
    
    if extra_filters:
        filters.extend(extra_filters)

    try:
        paginator = pricing_client.get_paginator('get_products')
        page_iterator = paginator.paginate(
            ServiceCode=service_code, 
            Filters=filters, 
            PaginationConfig={'MaxItems': 2000}  # Limit to avoid excessive fetching, but enough for Lambda/S3
        )
        
        all_products = []
        for page in page_iterator:
            all_products.extend(page.get("PriceList", []))
            
        return all_products
    except Exception as e:
        if fail_closed:
            logger.warning(
                "AWS Price List request failed for required service %s.",
                service_code,
            )
            raise TwinMakerPricingFetchError(
                "AWS Price List API request failed for TwinMaker."
            ) from e
        logger.debug(f"⚠️ Query failed for {service_code} ({'with' if with_location else 'without'} location): {e}")
        return []

def _extract_prices_with_evidence(
    price_list: List[str],
    field_map: Dict[str, List[str]],
    include_keywords: List[str] = None,
    exclude_keywords: List[str] = None,
    debug: bool = False,
    *,
    service_name: str = "unknown",
) -> Dict[str, FieldMatchEvidence]:
    """
    Parse AWS Pricing API responses and return field-level match evidence.
    """
    include_keywords = include_keywords or []
    exclude_keywords = exclude_keywords or []
    selected_rows: Dict[str, List[Dict[str, Any]]] = {key: [] for key in field_map}
    rejected: Dict[str, List[RejectedCandidate]] = {key: [] for key in field_map}

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
                    for key in field_map:
                        rejected[key].append(RejectedCandidate("zero price", {"description": desc, "price": price}))
                    continue

                # Check inclusion keywords
                if include_keywords and not any(k in desc for k in include_keywords):
                    if debug:
                        logger.debug(f"   ❌ No Match: {desc.strip()} {price}")
                    for key in field_map:
                        rejected[key].append(RejectedCandidate("include keyword mismatch", {"description": desc, "price": price}))
                    continue
                
                # Check exclusion keywords
                if any(x in desc for x in exclude_keywords):
                    if debug:
                        logger.debug(f"   ❌ Excluded: {desc.strip()} {price}")
                    for key in field_map:
                        rejected[key].append(RejectedCandidate("exclude keyword match", {"description": desc, "price": price}))
                    continue

                # Check against field map
                for key, patterns in field_map.items():
                    if any(p in desc for p in patterns):
                        selected_rows[key].append({"description": desc.strip(), "price": price})
                        if debug:
                            logger.debug(f"   ✔️ Matched:  {desc.strip()} → {key} = {price}")
                        break  # Stop checking other keys for this dimension

    evidence = {}
    for key, rows in selected_rows.items():
        unique_prices = distinct_prices(rows, price_key="price")
        if len(unique_prices) > 1:
            evidence[key] = FieldMatchEvidence(
                provider="aws",
                service_name=service_name,
                field_key=key,
                status=MatchStatus.AMBIGUOUS,
                rejected_candidates=tuple(rejected[key][:25]),
                reason=f"Multiple paid candidates matched with distinct prices: {unique_prices}",
            )
            continue
        if not rows:
            evidence[key] = FieldMatchEvidence(
                provider="aws",
                service_name=service_name,
                field_key=key,
                status=MatchStatus.NO_MATCH,
                rejected_candidates=tuple(rejected[key][:25]),
                reason="No price dimension matched include, exclude, and field patterns.",
            )
            continue
        selected = rows[0]
        evidence[key] = FieldMatchEvidence(
            provider="aws",
            service_name=service_name,
            field_key=key,
            status=MatchStatus.SELECTED,
            selected_row=selected,
            selected_price=float(selected["price"]),
            normalized_price=float(selected["price"]),
            rejected_candidates=tuple(rejected[key][:25]),
        )
    return evidence


def _extract_prices_from_api_response(price_list: List[str], field_map: Dict[str, List[str]], include_keywords: List[str] = None, exclude_keywords: List[str] = None, debug: bool = False) -> Dict[str, float]:
    """
    Parse the raw JSON response from AWS Pricing API to extract deterministic prices.
    Ambiguous fields are omitted so callers can fall into review/fallback paths.
    """
    evidence = _extract_prices_with_evidence(
        price_list,
        field_map,
        include_keywords=include_keywords,
        exclude_keywords=exclude_keywords,
        debug=debug,
    )
    return {
        key: item.normalized_price
        for key, item in evidence.items()
        if item.status == MatchStatus.SELECTED and item.normalized_price is not None
    }

# -------------------------------------------------------------------
# Specialized Fetchers
# -------------------------------------------------------------------

def _fetch_transfer_prices(
    region_code: str,
    region_human: str,
    pricing_client: Any,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Specialized fetcher for Data Transfer.
    Fetches prices from AWSDataTransfer using fromLocation (Region) -> toLocation (External).
    """
    # We specifically want:
    # Service: AWSDataTransfer
    # fromLocation: <Current Region>
    # toLocation: External
    # transferType: AWS Outbound
    
    extra_filters = [
        {"Type": "TERM_MATCH", "Field": "fromLocation", "Value": region_human},
        {"Type": "TERM_MATCH", "Field": "toLocation", "Value": "External"},
        {"Type": "TERM_MATCH", "Field": "transferType", "Value": "AWS Outbound"},
    ]

    # Note: with_location=False because we are using 'fromLocation' instead of 'location'
    price_list = _fetch_api_products(
        pricing_client, 
        "AWSDataTransfer", 
        region_human, 
        with_location=False, 
        extra_filters=extra_filters
    )
    
    evidence = build_aws_intent_evidence(
        price_list,
        intent_id="transfer.egress_gb",
        region=region_code,
    )
    if evidence["review_required"] or not evidence["selected_rows"]:
        raise ValueError(
            "AWS transfer pricing evidence is incomplete or requires review"
        )
    if evidence.get("currency") != "USD":
        raise ValueError("AWS transfer pricing must use USD")
    normalized_tiers = evidence["normalized_tiers"]
    _validate_aws_transfer_ranges(normalized_tiers)
    selected_rows = evidence["selected_rows"]
    transfer_evidence = build_transfer_evidence(
        provider="aws",
        pricing_region=region_code,
        source_type="provider_api",
        source_api="aws-price-list",
        source_url="https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer",
        mapping_version=evidence["mapping_version"],
        selected_rows=selected_rows,
        fetched_at=evidence["fetched_at"],
    )
    catalog = build_transfer_catalog(
        provider="aws",
        pricing_region=region_code,
        tier_thresholds=[
            {
                "tier_id": f"aws-paid-{index + 1}",
                "start_quantity": tier["lower_bound"],
                "unit_price": tier["price"],
            }
            for index, tier in enumerate(normalized_tiers)
        ],
        free_allowance_quantity=100,
        evidence_id=transfer_evidence["evidence_id"],
        currency=evidence["currency"],
    )
    if debug:
        logger.debug(
            "Matched %s exact AWS transfer tiers for %s",
            len(normalized_tiers),
            region_human,
        )
    return {
        **catalog,
        "__evidence__": transfer_evidence,
        "__intent_evidence__": evidence,
    }


def _validate_aws_transfer_ranges(tiers: List[Dict[str, Any]]) -> None:
    if not tiers:
        raise ValueError("AWS transfer pricing returned no paid tiers")
    for index, tier in enumerate(tiers):
        if tier.get("unit") != "GB":
            raise ValueError("AWS transfer pricing must use GB")
        if tier.get("price", 0) <= 0:
            raise ValueError("AWS transfer paid tiers must have positive prices")
        expected_end = (
            tiers[index + 1]["lower_bound"]
            if index + 1 < len(tiers)
            else "Infinity"
        )
        if tier.get("limit") != expected_end:
            raise ValueError("AWS transfer tiers are gapped or overlapping")

def _fetch_twinmaker_prices(
    region_human: str,
    pricing_client: Any,
    debug: bool = False,
) -> Dict[str, Any]:
    """Fetch and validate the complete regional TwinMaker pricing contract."""

    price_list = _fetch_api_products(
        pricing_client,
        "IOTTwinMaker",
        region_human,
        fail_closed=True,
    )
    return _extract_twinmaker_pricing(price_list, region_human, debug=debug)


def _extract_twinmaker_pricing(
    price_list: List[str],
    region_human: str,
    *,
    debug: bool = False,
) -> Dict[str, Any]:
    """Select TwinMaker rows by exact usage-type suffix and location."""

    expected_suffixes = set(TWINMAKER_STANDARD_SUFFIXES)
    for tier_number in range(1, 5):
        expected_suffixes.update(
            {
                f"IoTTwinMaker-BaseTier{tier_number}-Entities",
                f"IoTTwinMaker-BaseTier{tier_number}-Queries",
                f"IoTTwinMaker-BaseTier{tier_number}-UnifiedDataAccess",
            }
        )

    selected: Dict[str, Dict[str, Any]] = {}
    for raw_product in price_list:
        try:
            product = json.loads(raw_product)
        except (TypeError, json.JSONDecodeError) as exc:
            raise TwinMakerPricingContractError(
                "AWS TwinMaker Price List contains malformed JSON."
            ) from exc

        attributes = product.get("product", {}).get("attributes", {})
        usage_type = attributes.get("usagetype")
        if not isinstance(usage_type, str):
            continue
        suffix = next(
            (
                candidate
                for candidate in expected_suffixes
                if usage_type.endswith(candidate)
            ),
            None,
        )
        if suffix is None:
            continue

        location = attributes.get("location")
        if location != region_human:
            raise TwinMakerPricingContractError(
                "AWS TwinMaker Price List contains a matching usage type "
                "for a different location."
            )

        dimensions = []
        for term in product.get("terms", {}).get("OnDemand", {}).values():
            dimensions.extend(term.get("priceDimensions", {}).values())
        positive_dimensions = [
            dimension
            for dimension in dimensions
            if _positive_usd_price(dimension) is not None
        ]
        if len(positive_dimensions) != 1:
            raise TwinMakerPricingContractError(
                f"AWS TwinMaker pricing dimension {suffix} must have exactly "
                "one positive USD price."
            )
        if suffix in selected:
            raise TwinMakerPricingContractError(
                f"AWS TwinMaker pricing dimension {suffix} is duplicated."
            )

        dimension = positive_dimensions[0]
        row = {
            "usageType": usage_type,
            "location": location,
            "sku": product.get("product", {}).get("sku"),
            "description": str(dimension.get("description") or "")[:500],
            "unit": dimension.get("unit"),
            "beginRange": dimension.get("beginRange"),
            "endRange": dimension.get("endRange"),
            "priceUsd": _positive_usd_price(dimension),
        }
        selected[suffix] = row
        if debug:
            logger.debug(
                "   Matched exact TwinMaker dimension %s at %s",
                suffix,
                region_human,
            )

    missing = sorted(expected_suffixes.difference(selected))
    if missing:
        raise TwinMakerPricingContractError(
            "AWS TwinMaker Price List contract is incomplete. Missing: "
            + ", ".join(missing)
        )

    usage_rates = {
        field: selected[suffix]["priceUsd"]
        for suffix, field in TWINMAKER_STANDARD_SUFFIXES.items()
    }
    tiers = []
    query_overage_prices = set()
    api_overage_prices = set()
    included_queries: list[int] = []
    included_api_calls: list[int] = []
    for tier_number, tier_id in enumerate(TWINMAKER_BUNDLE_ENTITY_RANGES, start=1):
        entity_row = selected[
            f"IoTTwinMaker-BaseTier{tier_number}-Entities"
        ]
        query_row = selected[
            f"IoTTwinMaker-BaseTier{tier_number}-Queries"
        ]
        api_row = selected[
            f"IoTTwinMaker-BaseTier{tier_number}-UnifiedDataAccess"
        ]
        query_limit = _nonnegative_integer_range(
            query_row["beginRange"],
            f"{tier_id} included queries",
        )
        api_limit = _nonnegative_integer_range(
            api_row["beginRange"],
            f"{tier_id} included API calls",
        )
        included_queries.append(query_limit)
        included_api_calls.append(api_limit)
        query_overage_prices.add(query_row["priceUsd"])
        api_overage_prices.add(api_row["priceUsd"])
        minimum_entities, maximum_entities = TWINMAKER_BUNDLE_ENTITY_RANGES[tier_id]
        tiers.append(
            {
                "tierId": tier_id,
                "minimumEntities": minimum_entities,
                "maximumEntities": maximum_entities,
                "monthlyBasePrice": entity_row["priceUsd"],
                "includedQueries": query_limit,
                "includedApiCalls": api_limit,
                "queryOveragePrice": query_row["priceUsd"],
                "apiCallOveragePrice": api_row["priceUsd"],
            }
        )

    if len(query_overage_prices) != 1 or len(api_overage_prices) != 1:
        raise TwinMakerPricingContractError(
            "AWS TwinMaker bundle overage rates are inconsistent within the region."
        )
    if included_queries != sorted(set(included_queries)):
        raise TwinMakerPricingContractError(
            "AWS TwinMaker included query limits must be unique and increasing."
        )
    if included_api_calls != sorted(set(included_api_calls)):
        raise TwinMakerPricingContractError(
            "AWS TwinMaker included API-call limits must be unique and increasing."
        )

    return {
        "usageRates": usage_rates,
        "tieredBundle": {"tiers": tiers},
        "__evidence__": {
            "schema_version": TWINMAKER_EVIDENCE_SCHEMA_VERSION,
            "location": region_human,
            "selected_dimensions": [
                selected[suffix] for suffix in sorted(selected)
            ],
        },
    }


def _positive_usd_price(dimension: Dict[str, Any]) -> float | None:
    try:
        price = float(dimension.get("pricePerUnit", {}).get("USD"))
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _nonnegative_integer_range(value: Any, label: str) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TwinMakerPricingContractError(
            f"AWS TwinMaker {label} is not numeric."
        ) from exc
    if not number.is_integer() or number < 0:
        raise TwinMakerPricingContractError(
            f"AWS TwinMaker {label} must be a non-negative integer."
        )
    return int(number)


def _extract_iot_message_tiers(price_list: List[str], debug: bool = False) -> Dict[str, float]:
    """Extract standard AWS IoT Core MQTT message tiers from Price List rows."""
    tiers: list[dict[str, Any]] = []
    for prod_json in price_list:
        prod = json.loads(prod_json)
        attrs = prod.get("product", {}).get("attributes", {})
        usage_type = (attrs.get("usagetype") or "").lower()
        if not usage_type.endswith("-messages"):
            continue
        if any(blocked in usage_type for blocked in ("lorawan", "direct")):
            continue

        for term in prod.get("terms", {}).get("OnDemand", {}).values():
            for dim in term.get("priceDimensions", {}).values():
                price = float(dim.get("pricePerUnit", {}).get("USD", 0))
                if price <= 0:
                    continue
                try:
                    begin = float(dim.get("beginRange", "0"))
                except ValueError:
                    begin = 0.0
                tiers.append({"begin": begin, "price": price})
                if debug:
                    logger.debug(
                        "   ✔️ Matched IoT message tier: %s -> %s",
                        dim.get("description", "").strip(),
                        price,
                    )

    if not tiers:
        return {}

    tiers.sort(key=lambda item: item["begin"])
    result = {}
    for tier in tiers:
        begin = tier["begin"]
        if begin == 0:
            result["tier_first"] = tier["price"]
        elif begin < 5_000_000_000:
            result["tier_next"] = tier["price"]
        else:
            result["tier_over"] = tier["price"]
    return result


def _extract_iot_connection_price_per_device_month(
    price_list: List[str],
    debug: bool = False,
) -> float | None:
    """Extract AWS IoT Core connection-minute price as an always-on device month."""
    for prod_json in price_list:
        prod = json.loads(prod_json)
        attrs = prod.get("product", {}).get("attributes", {})
        usage_type = (attrs.get("usagetype") or "").lower()
        if not usage_type.endswith("-connectionminutes"):
            continue

        for term in prod.get("terms", {}).get("OnDemand", {}).values():
            for dim in term.get("priceDimensions", {}).values():
                price = float(dim.get("pricePerUnit", {}).get("USD", 0))
                if price <= 0:
                    continue
                monthly_price = price * 60 * 24 * 30
                if debug:
                    logger.debug(
                        "   ✔️ Matched IoT connection minutes: %s -> %s per device-month",
                        dim.get("description", "").strip(),
                        monthly_price,
                    )
                return monthly_price
    return None


def _fetch_iot_prices(
    service_code: str,
    region_human: str,
    pricing_client: Any,
    debug: bool = False,
) -> Dict[str, Any]:
    """Fetch AWS IoT Core prices plus tiered standard message pricing."""
    service_config = AWS_SERVICE_KEYWORDS["iot"]
    price_list = _fetch_api_products(pricing_client, service_code, region_human)
    prices = _extract_prices_from_api_response(
        price_list,
        service_config["fields"],
        include_keywords=service_config.get("include"),
        exclude_keywords=service_config.get("exclude"),
        debug=debug,
    )
    message_tiers = _extract_iot_message_tiers(price_list, debug=debug)
    if message_tiers:
        prices["messageTiers"] = message_tiers
    connection_price = _extract_iot_connection_price_per_device_month(
        price_list,
        debug=debug,
    )
    if connection_price is not None:
        prices["pricePerDeviceAndMonth"] = connection_price
    return prices


def _fetch_grafana_prices(region_human: str, pricing_client: Any, debug: bool = False) -> Dict[str, float]:
    """
    Specialized fetcher for Grafana.
    Fetches Managed Grafana editor/viewer user prices. Amazon Managed Grafana
    uses the AWS Pricing API service code `AmazonGrafana`.
    """
    price_list = _fetch_api_products(
        pricing_client,
        "AmazonGrafana",
        region_human,
    )
    if not price_list:
        price_list = _fetch_api_products(
            pricing_client,
            "AmazonGrafana",
            region_human,
            with_location=False,
        )

    prices: Dict[str, float] = {}
    for prod_json in price_list:
        prod = json.loads(prod_json)
        attrs = prod.get("product", {}).get("attributes", {})
        usage_type = (attrs.get("usagetype") or "").lower()
        for term in prod.get("terms", {}).get("OnDemand", {}).values():
            for dim in term.get("priceDimensions", {}).values():
                desc = (dim.get("description") or "").lower()
                price = float(dim.get("pricePerUnit", {}).get("USD", 0))
                if price <= 0 or "enterprise" in usage_type or "free" in usage_type:
                    continue
                if "editoruser" in usage_type or "per editor" in desc:
                    prices.setdefault("editorPrice", price)
                elif "vieweruser" in usage_type or "per viewer" in desc:
                    prices.setdefault("viewerPrice", price)

    return prices

# Dispatch dictionary for specialized services
SPECIALIZED_FETCHERS: Dict[str, Callable] = {
    "iot": _fetch_iot_prices,
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
        return {}

    logger.info(f"🔍 Fetching AWS {service_name} pricing for {region_human}...")

    # 2. Check for Specialized Fetcher
    if neutral_service_name in SPECIALIZED_FETCHERS:
        if neutral_service_name == "iot":
            prices = SPECIALIZED_FETCHERS[neutral_service_name](
                service_code,
                region_human,
                pricing_client,
                debug,
            )
        elif neutral_service_name == "transfer":
            prices = SPECIALIZED_FETCHERS[neutral_service_name](
                region_code,
                region_human,
                pricing_client,
                debug,
            )
        else:
            prices = SPECIALIZED_FETCHERS[neutral_service_name](region_human, pricing_client, debug)
        logger.info(f"✅ Final AWS {neutral_service_name} pricing: {prices}")
        print("")
        return prices

    # 3. Standard Fetching Logic
    service_config = AWS_SERVICE_KEYWORDS.get(neutral_service_name)
    if not service_config:
        logger.warning(f"⚠️ No keyword config for service: {service_name}")
        _warn_static(neutral_service_name, "no_config", debug)
        return {}

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

    logger.info(f"✅ Final AWS {neutral_service_name} pricing: {prices}")
    print("")
    return prices
