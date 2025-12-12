"""
Cold-to-Archive Mover Lambda Function.

Moves data from S3 Cold Storage to S3 Archive (DEEP_ARCHIVE).
Supports multi-cloud: If L3 Archive is on different cloud, POSTs to remote Archive Writer.

Source: src/providers/aws/lambda_functions/cold-to-archive-mover/lambda_function.py
Editable: Yes - This is the runtime Lambda code
"""
import boto3
import os
import sys
import json
import datetime

# Handle import path for both Lambda (deployed with _shared) and test (local development) contexts
try:
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _lambda_funcs_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _lambda_funcs_dir not in sys.path:
        sys.path.insert(0, _lambda_funcs_dir)
    from _shared.inter_cloud import post_raw
    from _shared.env_utils import require_env


# ==========================================
# Environment Variable Validation (Fail-Fast)
# ==========================================

# Validate env vars at startup (fail-fast)
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))

COLD_S3_BUCKET_NAME = require_env("COLD_S3_BUCKET_NAME")
ARCHIVE_S3_BUCKET_NAME = require_env("ARCHIVE_S3_BUCKET_NAME")

# Multi-cloud config (optional)
REMOTE_ARCHIVE_WRITER_URL = os.environ.get("REMOTE_ARCHIVE_WRITER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

s3_client = boto3.client("s3")

# Constants
MAX_OBJECT_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB memory guard


# ==========================================
# Multi-Cloud Detection
# ==========================================

class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is invalid."""
    pass


def _is_multi_cloud_archive() -> bool:
    """
    Check if L3 Archive storage is on a different cloud.
    
    Returns True only if:
    1. REMOTE_ARCHIVE_WRITER_URL is set AND non-empty
    2. layer_3_cold_provider != layer_3_archive_provider in DIGITAL_TWIN_INFO
    """
    if not REMOTE_ARCHIVE_WRITER_URL:
        return False
    
    providers = DIGITAL_TWIN_INFO.get("config_providers")
    if providers is None:
        raise ConfigurationError(
            "CRITICAL: 'config_providers' missing from DIGITAL_TWIN_INFO. "
            "Ensure deployer injects config.providers into DIGITAL_TWIN_INFO."
        )
    
    l3_cold = providers.get("layer_3_cold_provider")
    l3_archive = providers.get("layer_3_archive_provider")
    
    if l3_cold is None or l3_archive is None:
        raise ConfigurationError(
            f"CRITICAL: Missing provider mapping. "
            f"layer_3_cold_provider={l3_cold}, layer_3_archive_provider={l3_archive}"
        )
    
    if l3_cold == l3_archive:
        print(f"Warning: REMOTE_ARCHIVE_WRITER_URL set but providers match ({l3_cold}). Using local S3.")
        return False
    
    return True


# ==========================================
# Remote POST with Retry (using shared module)
# ==========================================

def _post_to_remote_archive_writer(object_key: str, data: str) -> None:
    """
    POST object content to remote Archive Writer using shared inter_cloud module.
    """
    if not INTER_CLOUD_TOKEN:
        raise ValueError("INTER_CLOUD_TOKEN is required for multi-cloud transfers")
    
    payload = {
        "object_key": object_key,
        "data": data,
        "source_cloud": "aws"
    }
    
    result = post_raw(
        url=REMOTE_ARCHIVE_WRITER_URL,
        token=INTER_CLOUD_TOKEN,
        payload=payload,
        timeout=60  # Longer timeout for potentially large archive data
    )
    
    print(f"Successfully posted {object_key} to remote Archive Writer")


# ==========================================
# Main Handler
# ==========================================

def lambda_handler(event, context):
    print("Cold-to-Archive Mover: Starting")
    print(f"Event: {json.dumps(event)}")
    
    # Detect multi-cloud mode
    multi_cloud = _is_multi_cloud_archive()
    if multi_cloud:
        print(f"Multi-cloud mode: Posting to {REMOTE_ARCHIVE_WRITER_URL}")
    else:
        print(f"Single-cloud mode: Copying to s3://{ARCHIVE_S3_BUCKET_NAME}")

    try:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=DIGITAL_TWIN_INFO["config"]["cold_storage_size_in_days"]
        )
        print(f"Archiving items older than: {cutoff.isoformat()}")

        paginator = s3_client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=COLD_S3_BUCKET_NAME):
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                last_modified = obj["LastModified"]
                size = obj.get("Size", 0)

                if last_modified < cutoff:
                    # Memory guard for large objects
                    if size > MAX_OBJECT_SIZE_BYTES:
                        print(f"Warning: Skipping {key} ({size} bytes) - exceeds memory limit")
                        continue
                    
                    if multi_cloud:
                        # Read object and POST to remote
                        response = s3_client.get_object(Bucket=COLD_S3_BUCKET_NAME, Key=key)
                        data = response['Body'].read().decode('utf-8')
                        _post_to_remote_archive_writer(key, data)
                    else:
                        # Local S3 copy
                        s3_client.copy_object(
                            CopySource={"Bucket": COLD_S3_BUCKET_NAME, "Key": key},
                            Bucket=ARCHIVE_S3_BUCKET_NAME,
                            Key=key,
                            StorageClass="DEEP_ARCHIVE",
                            MetadataDirective="COPY"
                        )
                        print(f"Copied {key} to s3://{ARCHIVE_S3_BUCKET_NAME}/{key}")

                    # Delete from cold storage
                    s3_client.delete_object(Bucket=COLD_S3_BUCKET_NAME, Key=key)
                    print(f"Deleted {key} from {COLD_S3_BUCKET_NAME}")

    except Exception as e:
        print(f"Cold-to-Archive Mover Error: {e}")
        raise e
    
    print("Cold-to-Archive Mover: Complete")
