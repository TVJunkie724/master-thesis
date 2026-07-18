"""
Processor Wrapper Azure Function.

Calls user-defined processor function via HTTP and invokes the Persister.
Dynamically constructs processor URL from device ID.

Architecture:
    Ingestion → Processor Wrapper → HTTP → User Processor → Wrapper → Persister

Source: src/providers/azure/azure_functions/processor_wrapper/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging
import urllib.request
import urllib.error

import azure.functions as func

# Handle import path for shared module
try:
    from _shared.env_utils import MissingEnvironmentVariableError, require_env
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, parse_json_request
    from _shared.inter_cloud import safe_urlopen
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.env_utils import MissingEnvironmentVariableError, require_env
    from _shared.http_errors import InvalidRequestBody, error_response, failure_response, parse_json_request
    from _shared.inter_cloud import safe_urlopen


# Lazy loading for environment variables to allow Azure function discovery
_persister_function_url = None
_digital_twin_info = None
_user_function_key = None
# NOTE: _l2_function_key removed - persister is now AuthLevel.ANONYMOUS (Terraform cycle workaround)

def _get_persister_function_url():
    global _persister_function_url
    if _persister_function_url is None:
        _persister_function_url = require_env("PERSISTER_FUNCTION_URL")
    return _persister_function_url

def _get_digital_twin_info():
    """Lazy-load DIGITAL_TWIN_INFO to avoid import-time failures."""
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info

def _get_user_function_key():
    """Lazy-load USER_FUNCTION_KEY for Azure→user-functions HTTP authentication."""
    global _user_function_key
    if _user_function_key is None:
        _user_function_key = require_env("USER_FUNCTION_KEY")
    return _user_function_key

def _get_processor_url(device_id: str) -> str:
    """Construct processor URL dynamically from device ID with function key."""
    processor_name = f"{device_id}-processor"
    base_url = os.environ.get("FUNCTION_APP_BASE_URL", "").strip()
    if not base_url:
        raise MissingEnvironmentVariableError(
            "FUNCTION_APP_BASE_URL is missing or empty"
        )
    user_key = _get_user_function_key()
    return f"{base_url}/api/{processor_name}?code={user_key}"


# Create Blueprint for registration by main function_app.py
bp = func.Blueprint()


def _invoke_persister(payload: dict) -> None:
    """
    Invoke Persister function via HTTP POST.
    
    NOTE: Persister uses AuthLevel.ANONYMOUS (no function key required).
    This is a workaround for Terraform cycle limitations - see persister/function_app.py
    for full security documentation.
    
    Args:
        payload: Processed event data to persist
    """
    persister_url = _get_persister_function_url()
    # No function key needed - persister uses AuthLevel.ANONYMOUS
    
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(persister_url, data=data, headers=headers, method="POST")
    
    try:
        with safe_urlopen(req, timeout=30) as response:
            logging.info(f"Persister invoked successfully: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logging.error("Failed to invoke Persister: HTTP %s", e.code)
        raise
    except urllib.error.URLError as e:
        logging.error(
            "Network error invoking Persister: %s",
            type(e.reason).__name__,
        )
        raise


@bp.function_name(name="processor")
@bp.route(route="processor", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def processor(req: func.HttpRequest) -> func.HttpResponse:
    """
    Call user processor via HTTP and invoke Persister.
    
    Dynamically constructs the processor URL from the device ID in the event,
    calls the user's processor function, then sends the result to Persister.
    """
    logging.info("Azure Processor Wrapper: Executing user logic...")
    
    try:
        # Parse input event
        event = parse_json_request(req)
        if not isinstance(event, dict):
            return error_response(
                code="INVALID_REQUEST",
                message="Request body must be a JSON object",
                status_code=400,
            )
        
        # 1. Call User Processor via HTTP
        device_id = event.get("device_id") or event.get("iotDeviceId", "default")
        try:
            url = _get_processor_url(device_id)
            if not url or not url.startswith("http"):
                raise Exception(f"Cannot construct processor URL for device {device_id}")
            else:
                logging.info("Calling configured user processor")
                data = json.dumps(event).encode("utf-8")
                headers = {"Content-Type": "application/json"}
                req_proc = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with safe_urlopen(req_proc, timeout=30) as response:
                    processed_event = json.loads(response.read().decode("utf-8"))
                logging.info("User logic completed")
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            return failure_response(
                component="azure.processor.user-logic",
                error=exc,
                code="USER_LOGIC_ERROR",
                message="The configured user processor failed.",
                status_code=502,
            )
        except MissingEnvironmentVariableError:
            raise
        except Exception as exc:
            return failure_response(
                component="azure.processor.user-logic",
                error=exc,
                code="USER_LOGIC_ERROR",
                message="The configured user processor failed.",
                status_code=502,
            )
        
        # 2. Invoke Persister
        _invoke_persister(processed_event)
        
        return func.HttpResponse(
            json.dumps({"status": "processed", "result": processed_event}),
            status_code=200,
            mimetype="application/json"
        )
        
    except InvalidRequestBody:
        return error_response(
            code="INVALID_REQUEST",
            message="Invalid JSON body",
            status_code=400,
        )

    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        return failure_response(
            component="azure.processor.persister",
            error=exc,
            code="UPSTREAM_ERROR",
            message="The persistence service is unavailable.",
            status_code=502,
        )

    except MissingEnvironmentVariableError as exc:
        return failure_response(
            component="azure.processor.configuration",
            error=exc,
            code="CONFIGURATION_ERROR",
            message="Processor configuration is unavailable.",
            status_code=500,
        )

    except Exception as exc:
        return failure_response(
            component="azure.processor",
            error=exc,
        )
