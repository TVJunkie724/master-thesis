"""
Connector Lambda Function.

Bridges L1 (IoT Core) to L2 (Processing) when they are on different clouds.
Receives events from the Dispatcher and POSTs them to the remote Ingestion endpoint.

Source: src/providers/aws/lambda_functions/connector/lambda_function.py
Editable: Yes - This is the runtime Lambda code
"""
import os
import sys

# Handle import path for both Lambda (deployed with _shared) and test (local development) contexts
try:
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    # When running tests locally, add the lambda_functions directory to path
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env


# ==========================================
# Environment Variable Validation (Fail-Fast)
# ==========================================

# Required environment variables - fail fast if missing
REMOTE_INGESTION_URL = require_env("REMOTE_INGESTION_URL")
INTER_CLOUD_TOKEN = require_env("INTER_CLOUD_TOKEN")


# ==========================================
# Handler
# ==========================================

def lambda_handler(event, context):
    """
    Forward IoT event to remote L2 Ingestion endpoint.
    
    This Lambda is deployed when L1 and L2 are on different clouds.
    It wraps the event in a standardized envelope and POSTs it
    to the remote Ingestion Function URL.
    
    Args:
        event: IoT event from Dispatcher
        context: Lambda context
    
    Returns:
        dict: Response from remote Ingestion endpoint
    """
    return post_to_remote(
        url=REMOTE_INGESTION_URL,
        token=INTER_CLOUD_TOKEN,
        payload=event,
        target_layer="L2"
    )
