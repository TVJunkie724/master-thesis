import json
import re
from typing import Dict, Any, Optional, List
from google.cloud import billing_v1
from backend.logger import logger
import backend.constants as CONSTANTS
# from backend.config_loader import load_service_mapping # Not used
# from backend.fetch_data import initial_fetch_google # No longer needed

# -------------------------------------------------------------------
# Region mapping + defaults
# -------------------------------------------------------------------

# Global loading removed. Passed as arguments now.
# GCP_REGION_NAMES = ...

STATIC_DEFAULTS_GCP = {
    "transfer": {"egressPrice": 0.12},
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
        "dataTransferOutPrice": 0.12
    },
    "computeEngine": {
        "e2MediumPrice": 0.0335,
        "storagePrice": 0.04
    }
}

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
        "meters": {
            "egressPrice": {"desc_keywords": ["Internet Egress", "Premium"], "unit_keywords": ["gibibyte"]},
        }
    },
    "scheduler": {
        "service_display_name": "Cloud Scheduler",
        "meters": {
            "jobPrice": {"desc_keywords": ["Job"], "unit_keywords": ["job month", "count"]}
        }
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
    "apiGateway_egress": {
        "service_display_name": "API Gateway",
        "meters": {
            "dataTransferOutPrice": {
                "desc_keywords": ["Internet Egress", "Intercontinental"],
                "unit_keywords": ["gibibyte"]
            }
        }
    },
    "computeEngine": {
        "service_display_name": "Compute Engine",
        "meters": {
            "e2Core": {
                "desc_keywords": ["E2 Instance Core"],
                "unit_keywords": ["hour"]
            },
            "e2Ram": {
                "desc_keywords": ["E2 Instance Ram"],
                "unit_keywords": ["gibibyte hour"]
            },
            "storagePrice": {
                "desc_keywords": ["Balanced PD Capacity"],
                "unit_keywords": ["gibibyte month"]
            }
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

# -------------------------------------------------------------------
# Main Fetcher
# -------------------------------------------------------------------
def fetch_gcp_price(client: billing_v1.CloudCatalogClient, service_name: str, region_code: str, region_map: Dict[str, str], debug: bool = False) -> Dict[str, Any]:
    """
    Fetch pricing for a specific GCP service in a given region.
    """
    region_human = region_map.get(region_code, region_code)
    
    logger.info(f"🔍 Fetching GCP {service_name} pricing for {region_human}...")

    # 1. Client is passed in
    
    # 2. Get Config
    config = GCP_SERVICE_KEYWORDS.get(service_name)
    if not config:
        logger.warning(f"⚠️ No keyword config for GCP service: {service_name}")
        return {}

    # 3. Find Service ID
    service_id = None
    try:
        # List all services (cached ideally, but for now we fetch)
        # Note: This list is large, in production we might want to cache this map.
        request = billing_v1.ListServicesRequest()
        for service in client.list_services(request=request):
            if service.display_name == config["service_display_name"]:
                service_id = service.service_id
                break
    except Exception as e:
        logger.error(f"Error listing GCP services: {e}")
        return {}

    if not service_id:
        logger.warning(f"⚠️ GCP Service '{config['service_display_name']}' not found in catalog.")
        return {}

    # 4. List SKUs for Service
    fetched = {}
    try:
        request = billing_v1.ListSkusRequest(parent=f"services/{service_id}")
        skus = client.list_skus(request=request)
        
        # Convert to list for multiple passes
        sku_list = list(skus)
        
        if debug:
            logger.debug(f"-- Available SKUs for {service_name} ({len(sku_list)}) --")
            # Show first 5 for context
            for s in sku_list[:5]:
                logger.debug("    " + str(_sanitize_sku(s)))
            logger.debug("------------------------------------------------")

        # 5. Match Meters
        for key, meter_conf in config["meters"].items():
            match = None
            best_price = None
            
            for sku in sku_list:
                # Region Check
                if region_code not in sku.service_regions and "global" not in sku.service_regions:
                    # if debug: logger.debug(f"Skipping {sku.description} due to region mismatch (Expected {region_code} or global, got {sku.service_regions})")
                    continue

                # Keyword Check
                desc = sku.description.lower()
                if not all(k.lower() in desc for k in meter_conf["desc_keywords"]):
                    continue
                
                # Negative Keyword Check
                if "negative_keywords" in meter_conf:
                    if any(nk.lower() in desc for nk in meter_conf["negative_keywords"]):
                        continue

                # Pricing Info Check
                if not sku.pricing_info:
                    continue
                
                # We take the first pricing info (usually standard)
                pricing_expression = sku.pricing_info[0].pricing_expression
                unit = pricing_expression.usage_unit_description.lower()
                
                # Unit Check
                if not any(u in unit for u in meter_conf["unit_keywords"]):
                    # if debug: logger.debug(f"Skipping {sku.description} due to unit mismatch (Expected {meter_conf['unit_keywords']}, got {unit})")
                    continue
                
                # Extract Price (Iterate tiers to find non-zero)
                if not pricing_expression.tiered_rates:
                    continue
                    
                best_tier_price = 0.0
                for rate in pricing_expression.tiered_rates:
                    price_currency = rate.unit_price.units + (rate.unit_price.nanos / 1_000_000_000)
                    if price_currency > 0:
                        best_tier_price = price_currency
                        # We usually want the first non-zero tier (or the highest? usually they decrease, but for free tier the first is 0)
                        # If we find a non-zero, we take it.
                        break
                
                if best_tier_price > 0:
                     match = sku
                     best_price = best_tier_price
                     break # Found a match
            
            if match:
                # Normalize
                final_price = _normalize_price(best_price, match.pricing_info[0].pricing_expression.usage_unit_description)
                fetched[key] = final_price
                if debug:
                    logger.debug(f"   ✔️ Matched {service_name}.{key}: {match.description}")
                    logger.debug(f"      Price: {best_price} -> Normalized: {final_price}")
            else:
                if debug:
                    logger.debug(f"   ❌ {service_name}.{key} not found.")

    except Exception as e:
        logger.error(f"Error listing SKUs for {service_name}: {e}")
        return {}

    # 6. Defaults are handled by the caller (_get_or_warn), so we just return what we found.
    
    logger.info(f"✅ Final GCP {service_name} pricing: {fetched}")
    print("")
    return fetched
