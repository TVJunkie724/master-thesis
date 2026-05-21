"""
Pricing API endpoints for fetching cloud provider pricing data.

This module provides endpoints for refreshing and retrieving cloud pricing data
from AWS, Azure, and GCP. Pricing data is cached locally for 7 days and can be
force-refreshed when needed. The data is used by the calculation engine to
determine optimal cloud provider distribution.
"""
import asyncio
import logging
import os
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from starlette.requests import Request
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

from backend.logger import logger
from backend.utils import is_file_fresh
from backend.config_loader import load_json_file
from backend.fetch_data.calculate_up_to_date_pricing import calculate_up_to_date_pricing
from backend.sse_utils import ThreadSafeSseHandler, emit_sse
import backend.constants as CONSTANTS
from api.error_models import ERROR_RESPONSES

router = APIRouter(tags=["Pricing"])

LOCAL_CREDENTIAL_FILE_CHECKS_ENV = "ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS"


def _require_local_credential_file_checks_enabled() -> None:
    if os.getenv(LOCAL_CREDENTIAL_FILE_CHECKS_ENV, "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "LOCAL_CREDENTIAL_FILE_CHECKS_DISABLED",
                "message": "File-based pricing refresh is disabled for this runtime.",
                "fix_suggestion": (
                    "Use /fetch_pricing_with_credentials/{provider} with request-body "
                    "credentials or start the explicit local-cloud Compose override."
                ),
                "http_status": 403,
            },
        )


# --------------------------------------------------
# Pricing Fetching Endpoints
# --------------------------------------------------

@router.post(
    "/fetch_pricing/aws",
    operation_id="refreshAwsPricing",
    summary="Refresh AWS pricing data from Price List API",
    description=(
        "**Purpose:** Fetches current AWS pricing data and caches it locally for use in cost calculations.\n\n"
        "**When to use:**\n"
        "- Before running calculations if pricing data is stale (>7 days old)\n"
        "- Debug/local-cloud mode when you need guaranteed fresh pricing data from mounted credential files\n"
        "- After AWS announces pricing changes\n\n"
        "**Behavior:**\n"
        "- Uses cached data if less than 7 days old (unless force_fetch=true)\n"
        "- Fresh file-based refresh requires `ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS=true`\n"
        "- App flows should use `/fetch_pricing_with_credentials/aws`\n"
        "- May take 30-60 seconds for a full refresh"
    ),
    responses={
        200: {"description": "Pricing data (cached or freshly fetched)"},
        403: ERROR_RESPONSES[403],
        401: ERROR_RESPONSES[401],
        500: ERROR_RESPONSES[500],
    }
)
def fetch_pricing_aws(additional_debug: bool = False, force_fetch: bool = False):
    """
    Fetches the latest AWS pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the AWS Price List API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for AWS services.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AWS_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached AWS pricing data")
            return load_json_file(CONSTANTS.AWS_PRICING_FILE_PATH)

        _require_local_credential_file_checks_enabled()
        logger.info("🔄 Fetching fresh AWS pricing...")
        return calculate_up_to_date_pricing("aws", additional_debug)
    except FileNotFoundError as e:
        logger.error(f"Pricing file not found: {e}")
        raise HTTPException(status_code=404, detail="AWS pricing data not available. Run refresh first.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching AWS pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch AWS pricing. Check server logs.")


@router.post(
    "/fetch_pricing/azure",
    operation_id="refreshAzurePricing",
    summary="Refresh Azure pricing data from Retail Prices API",
    description=(
        "**Purpose:** Fetches current Azure pricing data and caches it locally.\n\n"
        "**When to use:**\n"
        "- Before running calculations if pricing data is stale\n"
        "- The Azure Retail Prices API is public - no credentials required\n\n"
        "**Behavior:**\n"
        "- Uses cached data if less than 7 days old (unless force_fetch=true)\n"
        "- No authentication required (public API)"
    ),
    responses={
        200: {"description": "Pricing data (cached or freshly fetched)"},
        500: ERROR_RESPONSES[500],
    }
)
def fetch_pricing_azure(additional_debug: bool = False, force_fetch: bool = False):
    """
    Fetches the latest Azure pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the Azure Retail Prices API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for Azure services.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AZURE_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached Azure pricing data")
            return load_json_file(CONSTANTS.AZURE_PRICING_FILE_PATH)
        
        logger.info("🔄 Fetching fresh Azure pricing...")
        return calculate_up_to_date_pricing("azure", additional_debug)
    except FileNotFoundError as e:
        logger.error(f"Pricing file not found: {e}")
        raise HTTPException(status_code=404, detail="Azure pricing data not available. Run refresh first.")
    except Exception as e:
        logger.error(f"Error fetching Azure pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch Azure pricing. Check server logs.")


@router.post(
    "/fetch_pricing/gcp",
    operation_id="refreshGcpPricing",
    summary="Refresh GCP pricing data from Cloud Billing API",
    description=(
        "**Purpose:** Fetches current Google Cloud pricing data and caches it locally.\n\n"
        "**When to use:**\n"
        "- Before running calculations if pricing data is stale (>7 days old)\n"
        "- Debug/local-cloud mode when mounted GCP service account credentials are available\n\n"
        "**Behavior:**\n"
        "- Uses cached data if less than 7 days old (unless force_fetch=true)\n"
        "- Fresh file-based refresh requires `ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS=true`\n"
        "- App flows should use `/fetch_pricing_with_credentials/gcp`"
    ),
    responses={
        200: {"description": "Pricing data (cached or freshly fetched)"},
        403: ERROR_RESPONSES[403],
        401: ERROR_RESPONSES[401],
        500: ERROR_RESPONSES[500],
    }
)
def fetch_pricing_gcp(additional_debug: bool = False, force_fetch: bool = False):
    """
    Fetches the latest Google Cloud Platform (GCP) pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the Google Cloud Billing API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for GCP services.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.GCP_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached GCP pricing data")
            return load_json_file(CONSTANTS.GCP_PRICING_FILE_PATH)

        _require_local_credential_file_checks_enabled()
        logger.info("🔄 Fetching fresh GCP pricing...")
        return calculate_up_to_date_pricing("gcp", additional_debug)
    except FileNotFoundError as e:
        logger.error(f"Pricing file not found: {e}")
        raise HTTPException(status_code=404, detail="GCP pricing data not available. Run refresh first.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching GCP pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch GCP pricing. Check server logs.")


# --------------------------------------------------
# Currency Endpoint
# --------------------------------------------------

@router.post(
    "/fetch_currency",
    operation_id="refreshCurrencyRates",
    summary="Refresh currency exchange rates (USD/EUR)",
    description=(
        "**Purpose:** Fetches current currency exchange rates for cost display.\n\n"
        "**When to use:**\n"
        "- The calculation engine uses these rates to convert costs between currencies\n"
        "- Rates are cached for 1 day"
    ),
    responses={
        200: {
            "description": "Current exchange rates",
            "content": {"application/json": {"example": {"USD": 1.0, "EUR": 0.92}}}
        },
        500: ERROR_RESPONSES[500],
    }
)
def fetch_currency_rates():
    """
    Fetches up-to-date currency exchange rates (USD/EUR).
    
    - **Cache Duration**: 1 day.
    
    **Returns**: A dictionary of currency rates (e.g., `{"USD": 1.0, "EUR": 0.92}`).
    """
    try:
        from backend import pricing_utils
        logger.info("🔄 Fetching fresh currency rates...")
        rates = pricing_utils.get_currency_rates()
        return rates
    except Exception as e:
        logger.error(f"Error fetching currency rates: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch currency rates. Check server logs.")


# --------------------------------------------------
# Pricing Export (for snapshotting)
# --------------------------------------------------

from datetime import datetime, timezone

@router.get(
    "/pricing/export/{provider}",
    operation_id="exportPricingSnapshot",
    summary="Export cached pricing data for audit/snapshot purposes",
    description=(
        "**Purpose:** Returns the complete cached pricing data for a provider with metadata.\n\n"
        "**When to use:**\n"
        "- To capture exact pricing data used in a calculation for audit trail\n"
        "- To understand what pricing data is currently cached\n\n"
        "**Parameters:**\n"
        "- provider: 'aws', 'azure', or 'gcp'"
    ),
    responses={
        200: {
            "description": "Full pricing data with metadata",
            "content": {"application/json": {"example": {
                "provider": "aws",
                "updated_at": "2026-01-29T10:00:00Z",
                "pricing": {"...full pricing object..."}
            }}}
        },
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
    }
)
def export_pricing(provider: str):
    """
    Export full pricing JSON for a provider (for snapshotting).
    
    Used by Management API to capture the exact pricing data used
    during a calculation for audit trail purposes.
    
    **Returns**: Provider name, last update timestamp, and full pricing data.
    """
    if provider not in ["aws", "azure", "gcp"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")
    
    file_map = {
        "aws": CONSTANTS.AWS_PRICING_FILE_PATH,
        "azure": CONSTANTS.AZURE_PRICING_FILE_PATH,
        "gcp": CONSTANTS.GCP_PRICING_FILE_PATH,
    }
    
    cache_file = file_map[provider]
    if not os.path.exists(cache_file):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No cached pricing for {provider}")
    
    data = load_json_file(cache_file)
    mtime = os.path.getmtime(cache_file)
    updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    
    return {
        "provider": provider,
        "updated_at": updated_at,
        "pricing": data
    }


# --------------------------------------------------
# Credential-based Pricing Endpoint (for Management API)
# --------------------------------------------------

from fastapi import Body
from pydantic import BaseModel
from typing import Optional


class CredentialRequest(BaseModel):
    """Credentials for pricing fetch."""
    # AWS
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = "eu-central-1"
    # GCP
    gcp_service_account_json: Optional[str] = None
    gcp_region: Optional[str] = "europe-west1"


@router.post(
    "/fetch_pricing_with_credentials/{provider}",
    operation_id="fetchPricingWithCredentials",
    summary="Fetch pricing using twin credentials",
    description=(
        "**Purpose:** Refresh pricing data using credentials from request body.\n\n"
        "**When to call:** Management API integration to refresh pricing with saved twin credentials.\n\n"
        "**Credentials:** AWS needs access keys; Azure uses public API; GCP needs service account JSON."
    ),
    responses={
        200: {"description": "Pricing data fetched"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
def fetch_pricing_with_credentials(
    provider: str,
    credentials: CredentialRequest = Body(...),
    force_fetch: bool = True
):
    """
    Fetch pricing using credentials from request body (for Management API integration).
    
    This endpoint is used by the Management API to refresh pricing data using
    credentials stored in the twin configuration (from Step 1).
    
    - **provider**: aws, azure, or gcp
    - **credentials**: Provider-specific credentials
    - **force_fetch**: Always fetch fresh data (default: True)
    
    **Credential Requirements:**
    - AWS: aws_access_key_id, aws_secret_access_key, aws_region
    - Azure: None (public API)
    - GCP: gcp_service_account_json, gcp_region
    """
    if provider not in ["aws", "azure", "gcp"]:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": f"Invalid provider: {provider}"})
    
    try:
        # Azure uses public API - no credentials needed
        if provider == "azure":
            if not force_fetch and is_file_fresh(CONSTANTS.AZURE_PRICING_FILE_PATH, max_age_days=7):
                logger.info("✅ Using cached Azure pricing data")
                return load_json_file(CONSTANTS.AZURE_PRICING_FILE_PATH)
            logger.info("🔄 Fetching fresh Azure pricing...")
            return calculate_up_to_date_pricing("azure", additional_debug=False)
        
        # AWS/GCP need credentials
        from backend.fetch_data.calculate_up_to_date_pricing import (
            calculate_up_to_date_pricing_with_credentials
        )
        
        creds_dict = credentials.model_dump()
        return calculate_up_to_date_pricing_with_credentials(provider, creds_dict)
        
    except Exception as e:
        logger.error(f"Error fetching {provider} pricing with credentials: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch {provider} pricing. Check server logs.")


# --------------------------------------------------
# SSE Streaming Endpoint
# --------------------------------------------------

@router.post(
    "/stream/fetch_pricing/{provider}",
    operation_id="streamFetchPricing",
    summary="SSE stream for pricing fetch with real-time logs",
    description=(
        "**Purpose:** Stream real-time logs during pricing data fetch via Server-Sent Events.\n\n"
        "**Event types:**\n"
        "- `log`: Progress message from pricing fetch operations\n"
        "- `heartbeat`: Keep-alive signal (every 10s during long operations)\n"
        "- `complete`: Pricing fetch completed successfully\n"
        "- `error`: An error occurred during fetch\n\n"
        "**Dual Output:** Logs appear in both SSE stream AND container logs."
    ),
    responses={
        200: {"description": "SSE stream of log events"},
        400: ERROR_RESPONSES[400],
    }
)
async def stream_fetch_pricing(
    provider: str,
    request: Request,
    credentials: CredentialRequest = Body(default=CredentialRequest())
):
    """
    SSE endpoint that streams logger output during pricing fetch.
    
    Uses log handler capture pattern to stream all logger.info() calls
    from the pricing fetch functions to the SSE stream, while also
    writing them to container logs (dual output).
    """
    if provider not in ["aws", "azure", "gcp"]:
        return StreamingResponse(
            iter([emit_sse(f"Invalid provider: {provider}. Must be aws, azure, or gcp.", "error")]),
            media_type="text/event-stream"
        )
    
    async def event_generator():
        loop = asyncio.get_event_loop()
        queue = asyncio.Queue(maxsize=100)
        handler = ThreadSafeSseHandler(queue, loop)
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        try:
            yield emit_sse(f"Starting {provider.upper()} pricing fetch...")
            
            # Import pricing functions
            from backend.fetch_data.calculate_up_to_date_pricing import (
                calculate_up_to_date_pricing_with_credentials
            )
            
            # Run sync pricing function in thread pool
            if provider == "azure":
                # Azure uses public API - no credentials needed
                task = loop.run_in_executor(
                    None, calculate_up_to_date_pricing, provider, False
                )
            else:
                creds_dict = credentials.model_dump()
                task = loop.run_in_executor(
                    None, calculate_up_to_date_pricing_with_credentials,
                    provider, creds_dict, False
                )
            
            # Yield logs as they arrive, check for disconnect
            while not task.done():
                if await request.is_disconnected():
                    task.cancel()
                    return
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=10.0)
                    yield emit_sse(msg)
                except asyncio.TimeoutError:
                    yield emit_sse("⏳", "heartbeat")
            
            # Drain remaining logs from queue
            while not queue.empty():
                try:
                    msg = queue.get_nowait()
                    yield emit_sse(msg)
                except asyncio.QueueEmpty:
                    break
            
            # Check if task raised an exception
            try:
                await task
                yield emit_sse(f"✅ {provider.upper()} pricing fetch complete!", "complete")
            except Exception as e:
                yield emit_sse(f"❌ Pricing fetch failed: {str(e)}", "error")
            
        except Exception as e:
            yield emit_sse(f"❌ Error: {str(e)}", "error")
        finally:
            logger.removeHandler(handler)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
