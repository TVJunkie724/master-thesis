from typing import Any, Dict, List
from google.cloud import billing_v1
from backend.logger import logger
from backend.fetch_data.fetch_evidence import (
    FieldMatchEvidence,
    MatchStatus,
    RejectedCandidate,
)
from backend.gcp_pricing_evidence import (
    build_gcp_intent_evidence,
    redact_gcp_error,
)
from backend.transfer_catalog import (
    build_transfer_catalog,
    build_transfer_evidence,
)
# from backend.config_loader import load_service_mapping # Not used
# from backend.fetch_data import initial_fetch_google # No longer needed

# -------------------------------------------------------------------
# Region mapping + defaults
# -------------------------------------------------------------------

# Global loading removed. Passed as arguments now.
# GCP_REGION_NAMES = ...

STATIC_DEFAULTS_GCP = {
    "iot": {"pricePerGiB": 0.0000004, "pricePerDeviceAndMonth": 0},
    "functions": {
        "freeRequests": 2_000_000,
        "freeComputeTime": 400_000
    },
    "storage_hot": {
        "freeStorage": 1
    },
    "storage_cool": {
        "upfrontPrice": 0.0,
    },
    "storage_archive": {
        "upfrontPrice": 0.0,
    },
    "twinmaker": {
        "entityPrice": 0.05,
        "unifiedDataAccessAPICallsPrice": 0.0000015,
        "queryPrice": 0.00005
    },
    "grafana": {
        "editorPrice": 9.0,
        "viewerPrice": 5.0
    },
    "data_access": {
        "pricePerMillionCalls": 3.00,
    },
    "computeEngine": {
        "e2MediumPrice": 0.0335,
        "storagePrice": 0.04
    },
    # Cloud Scheduler is documented globally as USD 0.10 per job-month.
    # The account-wide free allowance is deliberately not allocated per Twin.
    "scheduler": {
        "jobPrice": 0.10,
    },
}


class GCPPricingCatalogAccessError(ValueError):
    """Raised when GCP Cloud Billing Catalog access fails for a live refresh."""

# -------------------------------------------------------------------
# Keywords for Matching
# -------------------------------------------------------------------
GCP_SERVICE_KEYWORDS = {
    "functions": {
        "service_display_name": "Cloud Run Functions",
        "meters": {
            "requestPrice": {"desc_keywords": ["Invocations"], "unit_keywords": ["1000000", "1/1000000", "count"]},
            "durationPrice": {"desc_keywords": ["Memory"], "unit_keywords": ["gibibyte second", "gib second"]},
        }
    },
    "storage_hot": {
        "service_display_name": "Cloud Firestore",
        "meters": {
            "storagePrice": {"desc_keywords": ["Storage"], "unit_keywords": ["gibibyte"]},
            "writePrice": {"desc_keywords": ["Entity Writes"], "unit_keywords": ["count"]},
            "readPrice": {"desc_keywords": ["Read"], "unit_keywords": ["count"]},
        }
    },
    "storage_cool": {
        "service_display_name": "Cloud Storage",
        "meters": {
            "storagePrice": {"desc_keywords": ["Nearline Storage"], "unit_keywords": ["gibibyte"]},
            "dataRetrievalPrice": {"desc_keywords": ["Nearline Data Retrieval"], "unit_keywords": ["gibibyte"]},
            "requestPrice": {"desc_keywords": ["Nearline", "Class A"], "unit_keywords": ["count", "operations"]},
        }
    },
    "storage_archive": {
        "service_display_name": "Cloud Storage",
        "meters": {
            "storagePrice": {"desc_keywords": ["Archive Storage"], "unit_keywords": ["gibibyte"]},
            "dataRetrievalPrice": {"desc_keywords": ["Archive Data Retrieval"], "unit_keywords": ["gibibyte"]},
            "lifecycleAndWritePrice": {"desc_keywords": ["Archive", "Class A"], "unit_keywords": ["count", "operations"]},
        }
    },
    "transfer": {
        "service_display_name": "Compute Engine",
        "meters": {}
    },
    "orchestration": { # Maps to Cloud Workflows
        "service_display_name": "Workflows",
        "meters": {
            "stepPrice": {"desc_keywords": ["Steps"], "unit_keywords": ["count"]}
        }
    },
    "cloudWorkflows": { # Alias for clarity if needed, or separate
        "service_display_name": "Workflows",
        "meters": {
            "stepPrice": {"desc_keywords": ["Steps"], "unit_keywords": ["count"]}
        }
    },
    "apiGateway": {
        "service_display_name": "Google Service Control",
        "meters": {
            "pricePerMillionCalls": {
                "desc_keywords": ["Operations"],
                "unit_keywords": ["count"]
            }
        }
    },
    "iot": {
        "service_display_name": "Cloud Pub/Sub",
        "meters": {
            "pricePerGiB": {"desc_keywords": ["Message Delivery"], "unit_keywords": ["gibibyte", "tebibyte"]}
        }
    },
    "event_bus": {
        "service_display_name": "Cloud Pub/Sub",
        "meters": {
            "pricePerGiB": {"desc_keywords": ["Message Delivery"], "unit_keywords": ["gibibyte", "tebibyte"]}
        }
    },
    "twinmaker": {
        "service_display_name": "Compute Engine",
        "meters": {
            "e2CorePrice": {
                "desc_keywords": ["E2 Instance Core"], 
                "unit_keywords": ["hour"],
                "negative_keywords": ["Spot", "Preemptible"]
            },
            "e2RamPrice": {
                "desc_keywords": ["E2 Instance Ram"], 
                "unit_keywords": ["gibibyte hour"],
                "negative_keywords": ["Spot", "Preemptible"]
            },
            "storagePrice": {"desc_keywords": ["Balanced PD Capacity"], "unit_keywords": ["gibibyte month"]}
        }
    },
    "grafana": {
        "service_display_name": "Compute Engine",
        "meters": {
            "e2CorePrice": {
                "desc_keywords": ["E2 Instance Core"], 
                "unit_keywords": ["hour"],
                "negative_keywords": ["Spot", "Preemptible"]
            },
            "e2RamPrice": {
                "desc_keywords": ["E2 Instance Ram"], 
                "unit_keywords": ["gibibyte hour"],
                "negative_keywords": ["Spot", "Preemptible"]
            },
            "storagePrice": {"desc_keywords": ["Balanced PD Capacity"], "unit_keywords": ["gibibyte month"]}
        }
    },
    "computeEngine": {
        "service_display_name": "Compute Engine",
        "meters": {
            "e2CorePrice": {
                "desc_keywords": ["E2 Instance Core"], 
                "unit_keywords": ["hour"],
                "negative_keywords": ["Spot", "Preemptible"]
            },
            "e2RamPrice": {
                "desc_keywords": ["E2 Instance Ram"], 
                "unit_keywords": ["gibibyte hour"],
                "negative_keywords": ["Spot", "Preemptible"]
            },
            "storagePrice": {"desc_keywords": ["Balanced PD Capacity"], "unit_keywords": ["gibibyte month"]}
        }
    },
    "data_access": {
        "service_display_name": "Google Service Control",
        "meters": {
            "pricePerMillionCalls": {
                "desc_keywords": ["Operations"],
                "unit_keywords": ["count"]
            }
        }
    }
}


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------
def _sanitize_sku(sku: Any) -> Dict[str, Any]:
    """Filter out noisy fields for cleaner logging."""
    return {
        "name": sku.name,
        "description": sku.description,
        "category": sku.category.resource_family,
        "service_regions": sku.service_regions[:3], # Limit regions
        "pricing_info": str(sku.pricing_info)[:100] + "..." if sku.pricing_info else "None"
    }

def _normalize_price(price: float, unit_text: str) -> float:
    """Normalize price to per 1 unit if it's per 1M or 10k."""
    unit_text = unit_text.lower()
    if "1000000" in unit_text:
        return price / 1_000_000
    if "100000" in unit_text:
        return price / 100_000
    if "10000" in unit_text:
        return price / 10_000
    if "1000" in unit_text:
        return price / 1_000
    if "tebibyte" in unit_text:
        return price / 1024
    return price

def _sku_price(sku: Any) -> float:
    if not sku.pricing_info:
        return 0.0
    pricing_expression = sku.pricing_info[0].pricing_expression
    if not pricing_expression.tiered_rates:
        return 0.0
    for rate in pricing_expression.tiered_rates:
        price_currency = rate.unit_price.units + (rate.unit_price.nanos / 1_000_000_000)
        if price_currency > 0:
            return price_currency
    return 0.0


def _money_payload(value: Any) -> dict[str, Any]:
    currency_code = getattr(value, "currency_code", None)
    if not isinstance(currency_code, str) or not currency_code.strip():
        raise ValueError("GCP unit price currencyCode is missing")
    units = int(getattr(value, "units", 0))
    nanos = int(getattr(value, "nanos", 0))
    if abs(nanos) >= 1_000_000_000:
        raise ValueError("GCP unit price nanos is outside the supported range")
    return {
        "currencyCode": currency_code,
        "units": units,
        "nanos": nanos,
    }


def _gcp_enum_name(
    value: Any,
    *,
    names: dict[int, str],
    field_name: str,
) -> str:
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name
    if isinstance(value, str) and value:
        return value
    try:
        numeric_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"GCP {field_name} is invalid") from exc
    try:
        return names[numeric_value]
    except KeyError as exc:
        raise ValueError(f"GCP {field_name} is unsupported") from exc


def _aggregation_payload(expression: Any) -> dict[str, Any]:
    aggregation = getattr(expression, "aggregation_info", None)
    if aggregation is None:
        raise ValueError("GCP pricing aggregationInfo is missing")
    return {
        "level": _gcp_enum_name(
            getattr(aggregation, "aggregation_level", None),
            names={0: "AGGREGATION_LEVEL_UNSPECIFIED", 1: "ACCOUNT", 2: "PROJECT"},
            field_name="aggregation level",
        ),
        "interval": _gcp_enum_name(
            getattr(aggregation, "aggregation_interval", None),
            names={
                0: "AGGREGATION_INTERVAL_UNSPECIFIED",
                1: "DAILY",
                2: "MONTHLY",
            },
            field_name="aggregation interval",
        ),
        "count": int(getattr(aggregation, "aggregation_count", 0)),
    }


def _gcp_sku_catalog_row(
    sku: Any,
    *,
    service_id: str,
    service_display_name: str,
) -> dict[str, Any]:
    category = sku.category
    pricing_info = []
    for info in sku.pricing_info:
        expression = info.pricing_expression
        pricing_info.append(
            {
                "pricingExpression": {
                    "usageUnit": expression.usage_unit,
                    "usageUnitDescription": expression.usage_unit_description,
                    "baseUnit": expression.base_unit,
                    "baseUnitDescription": expression.base_unit_description,
                    "baseUnitConversionFactor": (
                        expression.base_unit_conversion_factor
                    ),
                    "displayQuantity": expression.display_quantity,
                    "aggregationInfo": _aggregation_payload(expression),
                    "tieredRates": [
                        {
                            "startUsageAmount": rate.start_usage_amount,
                            "unitPrice": _money_payload(rate.unit_price),
                        }
                        for rate in expression.tiered_rates
                    ],
                }
            }
        )
    return {
        "serviceId": service_id,
        "serviceDisplayName": service_display_name,
        "skuId": sku.sku_id,
        "description": sku.description,
        "category": {
            "resourceFamily": category.resource_family,
            "resourceGroup": category.resource_group,
            "usageType": category.usage_type,
        },
        "serviceRegions": list(sku.service_regions),
        "pricingInfo": pricing_info,
    }


def _fetch_gcp_transfer_catalog(
    sku_list: List[Any],
    *,
    service_id: str,
    service_display_name: str,
    region_code: str,
) -> Dict[str, Any]:
    raw_skus = [
        _gcp_sku_catalog_row(
            sku,
            service_id=service_id,
            service_display_name=service_display_name,
        )
        for sku in sku_list
    ]
    evidence = build_gcp_intent_evidence(
        raw_skus,
        intent_id="transfer.egress_gb",
        region=region_code,
    )
    if evidence["review_required"] or not evidence["selected_rows"]:
        raise ValueError(
            "GCP transfer pricing evidence is incomplete or requires review"
        )
    if evidence["currency"] != "USD":
        raise ValueError("GCP transfer pricing must use USD")
    tiers = evidence["normalized_tiers"]
    if not tiers or any(tier.get("unit") != "gibibyte" for tier in tiers):
        raise ValueError("GCP transfer pricing must use gibibyte tiers")

    transfer_evidence = build_transfer_evidence(
        provider="gcp",
        pricing_region=region_code,
        source_type="provider_api",
        source_api="gcp-cloud-billing-catalog",
        source_url=(
            "https://cloud.google.com/skus/sku-groups/"
            "network-premium-gce-internet-egress"
        ),
        mapping_version=evidence["mapping_version"],
        selected_rows=evidence["selected_rows"],
        fetched_at=evidence["fetched_at"],
    )
    catalog = build_transfer_catalog(
        provider="gcp",
        pricing_region=region_code,
        tier_thresholds=[
            {
                "tier_id": f"gcp-paid-{index + 1}",
                "start_quantity": tier["lower_bound"],
                "unit_price": tier["price"],
            }
            for index, tier in enumerate(tiers)
        ],
        free_allowance_quantity=1,
        evidence_id=transfer_evidence["evidence_id"],
        currency=evidence["currency"],
    )
    return {
        **catalog,
        "__evidence__": transfer_evidence,
        "__intent_evidence__": evidence,
    }

def _select_gcp_sku_with_evidence(
    sku_list: List[Any],
    meter_conf: Dict[str, Any],
    region_code: str,
    *,
    service_name: str,
    field_key: str,
) -> FieldMatchEvidence:
    candidates = []
    rejected = []

    for sku in sku_list:
        row = _sanitize_sku(sku)

        if region_code not in sku.service_regions and "global" not in sku.service_regions:
            rejected.append(RejectedCandidate("region mismatch", row))
            continue

        desc = sku.description.lower()
        if not all(k.lower() in desc for k in meter_conf["desc_keywords"]):
            rejected.append(RejectedCandidate("description keyword mismatch", row))
            continue

        if "negative_keywords" in meter_conf:
            if any(nk.lower() in desc for nk in meter_conf["negative_keywords"]):
                rejected.append(RejectedCandidate("negative keyword match", row))
                continue

        if not sku.pricing_info:
            rejected.append(RejectedCandidate("missing pricing info", row))
            continue

        pricing_expression = sku.pricing_info[0].pricing_expression
        unit = pricing_expression.usage_unit_description.lower()
        if not any(u in unit for u in meter_conf["unit_keywords"]):
            rejected.append(RejectedCandidate("unit keyword mismatch", row))
            continue

        price = _sku_price(sku)
        if price <= 0:
            rejected.append(RejectedCandidate("zero price", row))
            continue

        candidates.append((sku, price, unit))

    distinct = sorted({round(price, 12) for _, price, _ in candidates})
    if len(distinct) > 1:
        return FieldMatchEvidence(
            provider="gcp",
            service_name=service_name,
            field_key=field_key,
            status=MatchStatus.AMBIGUOUS,
            rejected_candidates=tuple(rejected[:25]),
            reason=f"Multiple paid candidates matched with distinct prices: {tuple(distinct)}",
        )
    if not candidates:
        return FieldMatchEvidence(
            provider="gcp",
            service_name=service_name,
            field_key=field_key,
            status=MatchStatus.NO_MATCH,
            rejected_candidates=tuple(rejected[:25]),
            reason="No SKU matched region, description, unit, and pricing filters.",
        )

    selected_sku, raw_price, unit = candidates[0]
    normalized = _normalize_price(raw_price, unit)
    return FieldMatchEvidence(
        provider="gcp",
        service_name=service_name,
        field_key=field_key,
        status=MatchStatus.SELECTED,
        selected_row=_sanitize_sku(selected_sku),
        selected_price=raw_price,
        normalized_price=normalized,
        source_unit=unit,
        rejected_candidates=tuple(rejected[:25]),
    )

# -------------------------------------------------------------------
# Main Fetcher
# -------------------------------------------------------------------
def fetch_gcp_price(client: billing_v1.CloudCatalogClient, service_name: str, region_code: str, region_map: Dict[str, str], debug: bool = False) -> Dict[str, Any]:
    """
    Fetch pricing for a specific GCP service in a given region.
    """
    region_human = region_map.get(region_code, region_code)
    
    logger.info(f"🔍 Fetching GCP {service_name} pricing for {region_human}...")

    if client is None:
        raise GCPPricingCatalogAccessError(
            "GCP Cloud Billing Catalog client is not initialized. "
            "Provide valid service account credentials with Cloud Billing Catalog access."
        )

    # 1. Client is passed in
    
    # 2. Get Config
    config = GCP_SERVICE_KEYWORDS.get(service_name)
    if not config:
        logger.warning(f"⚠️ No keyword config for GCP service: {service_name}")
        return {}

    # 3. Find Service ID
    service_id = None
    service_display_name = None
    try:
        # List all services (cached ideally, but for now we fetch)
        # Note: This list is large, in production we might want to cache this map.
        request = billing_v1.ListServicesRequest()
        for service in client.list_services(request=request):
            if service.display_name == config["service_display_name"]:
                service_id = service.service_id
                service_display_name = service.display_name
                break
    except Exception as e:
        message = redact_gcp_error(e)
        logger.error(f"Error listing GCP services: {message}")
        raise GCPPricingCatalogAccessError(
            "GCP Cloud Billing Catalog service listing failed. "
            "Verify service account credentials, token validity, and "
            "cloudbilling.services.list permission."
        ) from e

    if not service_id:
        logger.warning(f"⚠️ GCP Service '{config['service_display_name']}' not found in catalog.")
        return {}

    # 4. List SKUs for Service
    try:
        request = billing_v1.ListSkusRequest(parent=f"services/{service_id}")
        sku_list = list(client.list_skus(request=request))
    except Exception as e:
        message = redact_gcp_error(e)
        logger.error(f"Error listing SKUs for {service_name}: {message}")
        raise GCPPricingCatalogAccessError(
            f"GCP Cloud Billing Catalog SKU listing failed for {service_name}. "
            "Verify service account credentials, token validity, and "
            "cloudbilling.skus.list permission."
        ) from e

    if service_name == "transfer":
        return _fetch_gcp_transfer_catalog(
            sku_list,
            service_id=service_id,
            service_display_name=service_display_name,
            region_code=region_code,
        )

    fetched = {}
    try:
        if debug:
            logger.debug(f"-- Available SKUs for {service_name} ({len(sku_list)}) --")
            # Show first 5 for context
            for s in sku_list[:5]:
                logger.debug("    " + str(_sanitize_sku(s)))
            logger.debug("------------------------------------------------")

        # 5. Match Meters
        for key, meter_conf in config["meters"].items():
            evidence = _select_gcp_sku_with_evidence(
                sku_list,
                meter_conf,
                region_code,
                service_name=service_name,
                field_key=key,
            )
            if evidence.status == MatchStatus.SELECTED:
                fetched[key] = evidence.normalized_price
                if debug:
                    logger.debug(f"   ✔️ Matched {service_name}.{key}: {evidence.selected_row}")
                    logger.debug(f"      Price: {evidence.selected_price} -> Normalized: {evidence.normalized_price}")
            else:
                if debug:
                    logger.debug(f"   ❌ {service_name}.{key}: {evidence.reason}")

    except (AttributeError, TypeError, ValueError) as e:
        logger.error("Invalid GCP pricing catalog contract for %s", service_name)
        raise ValueError(
            f"GCP pricing catalog contract is invalid for {service_name}"
        ) from e

    logger.info(f"✅ Final GCP {service_name} pricing: {fetched}")
    print("")
    return fetched
