"""Provider adapters for updating deployed user-function code."""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urljoin, urlparse

import constants as CONSTANTS
from src.api.function_discovery import _get_upload_dir
from src.api.function_errors import FunctionProviderError
from logger import logger
from src.core.config_loader import load_credentials


def _load_provider_credentials(project_name: str, provider: str) -> tuple[Path, Dict[str, Any]]:
    """Load one provider credential section through the canonical config loader."""
    project_path = Path(_get_upload_dir(project_name))
    credentials = load_credentials(project_path).get(provider)
    if not credentials:
        raise ValueError(f"Missing {provider.upper()} credentials for project")
    return project_path, credentials


def _provider_request(method, operation: str, *args, **kwargs):
    """Execute one bounded provider HTTP request without exposing transport details."""
    try:
        return method(*args, **kwargs)
    except requests.RequestException as exc:
        raise FunctionProviderError(f"{operation} request failed") from exc


def _wait_for_kudu_deployment(
    status_url: str,
    *,
    auth: tuple[str, str],
    timeout_seconds: float = 300,
    poll_interval_seconds: float = 2,
) -> None:
    """Wait until Kudu reports a terminal deployment state."""
    if timeout_seconds <= 0 or poll_interval_seconds <= 0:
        raise ValueError("Kudu polling intervals must be positive")
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FunctionProviderError("Kudu ZIP deployment timed out")
        response = _provider_request(
            requests.get,
            "Azure ZIP deployment status",
            status_url,
            auth=auth,
            timeout=min(30, remaining),
        )
        if response.status_code != 200:
            raise FunctionProviderError(
                f"Kudu deployment status failed (HTTP {response.status_code})"
            )
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise FunctionProviderError("Kudu deployment status was not valid JSON") from exc
        status = payload.get("status") if isinstance(payload, dict) else None
        if not isinstance(status, int) or status not in {0, 1, 2, 3, 4}:
            raise FunctionProviderError("Kudu deployment returned an unknown status")
        if status == 4:
            return
        if status == 3:
            raise FunctionProviderError("Kudu ZIP deployment failed")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FunctionProviderError("Kudu ZIP deployment timed out")
        time.sleep(min(poll_interval_seconds, remaining))


def _resolve_kudu_status_url(location: str, kudu_url: str) -> str:
    """Resolve a Kudu status URL without allowing a provider-driven host escape."""
    status_url = urljoin(kudu_url, location)
    expected = urlparse(kudu_url)
    resolved = urlparse(status_url)
    if resolved.scheme != "https" or resolved.netloc != expected.netloc:
        raise FunctionProviderError("Kudu deployment status URL was outside the expected host")
    return status_url

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from google.api_core.exceptions import GoogleAPICallError, RetryError
    from google.cloud import functions_v2
    from google.oauth2 import service_account
    from google.protobuf import field_mask_pb2

    HAS_GCP_FUNCTIONS = True
except ImportError:
    HAS_GCP_FUNCTIONS = False

def _upload_aws_lambda(function_name: str, zip_content: bytes, project_name: str) -> Dict[str, Any]:
    """
    Upload function code to AWS Lambda via boto3.
    
    Args:
        function_name: Name of the Lambda function
        zip_content: ZIP file content
        project_name: Name of the project (for getting credentials)
        
    Returns:
        Dict with upload result
        
    Raises:
        ValueError: If boto3 not available or credentials missing
    """
    if not HAS_BOTO3:
        raise ValueError("boto3 not installed - cannot upload to AWS Lambda")
    
    _project_path, creds = _load_provider_credentials(project_name, "aws")
    
    # Validate required AWS credentials
    required = ["aws_access_key_id", "aws_secret_access_key", "aws_region"]
    for key in required:
        if key not in creds:
            raise ValueError(f"Missing required AWS credential: {key}")
    
    lambda_client = boto3.client(
        'lambda',
        aws_access_key_id=creds["aws_access_key_id"],
        aws_secret_access_key=creds["aws_secret_access_key"],
        region_name=creds["aws_region"]
    )
    
    try:
        response = lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_content,
            Publish=True
        )
        logger.info(f"✓ AWS Lambda code updated: {function_name}")
        return {
            "success": True,
            "function_arn": response.get("FunctionArn"),
            "version": response.get("Version")
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            raise ValueError(f"Lambda function not found: {function_name}. Deploy infrastructure first.")
        raise FunctionProviderError(f"AWS Lambda update failed ({error_code})") from e


def _upload_azure_function(function_app_name: str, zip_content: bytes, project_name: str) -> Dict[str, Any]:
    """
    Upload function code to Azure Function App via Kudu zipdeploy.
    
    Args:
        function_app_name: Name of the Azure Function App
        zip_content: ZIP file content
        project_name: Name of the project (for getting credentials)
        
    Returns:
        Dict with upload result
        
    Raises:
        ValueError: If requests not available or credentials missing
    """
    if not HAS_REQUESTS:
        raise ValueError("requests library not installed - cannot upload to Azure")
    
    project_path, creds = _load_provider_credentials(project_name, "azure")
    upload_dir = os.fspath(project_path)
    
    # Validate required Azure credentials
    required = ["azure_subscription_id", "azure_tenant_id", "azure_client_id", "azure_client_secret"]
    for key in required:
        if key not in creds:
            raise ValueError(f"Missing required Azure credential: {key}")
    
    # Get Azure publish credentials via Management API
    # First, get access token
    token_url = f"https://login.microsoftonline.com/{creds['azure_tenant_id']}/oauth2/v2.0/token"
    token_data = {
        "client_id": creds["azure_client_id"],
        "client_secret": creds["azure_client_secret"],
        "scope": "https://management.azure.com/.default",
        "grant_type": "client_credentials"
    }
    
    token_response = _provider_request(
        requests.post,
        "Azure token",
        token_url,
        data=token_data,
        timeout=30,
    )
    if token_response.status_code != 200:
        raise FunctionProviderError(
            f"Failed to get Azure access token (HTTP {token_response.status_code})"
        )
    
    try:
        access_token = token_response.json()["access_token"]
    except (KeyError, TypeError, ValueError) as exc:
        raise FunctionProviderError("Azure token response was missing access_token") from exc
    
    # Get publish credentials for the Function App
    # We need to find the resource group - check inter_cloud config or use naming convention
    inter_cloud_path = os.path.join(upload_dir, CONSTANTS.CONFIG_INTER_CLOUD_FILE)
    resource_group = None
    
    if os.path.exists(inter_cloud_path):
        with open(inter_cloud_path, 'r') as f:
            inter_cloud = json.load(f)
            resource_group = inter_cloud.get("azure_resource_group")
    
    if not resource_group:
        # Try to derive from config.json
        config_path = os.path.join(upload_dir, CONSTANTS.CONFIG_FILE)
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                if "digital_twin_name" not in config:
                    raise ValueError(f"Missing digital_twin_name in {CONSTANTS.CONFIG_FILE}")
                resource_group = f"{config['digital_twin_name']}-rg"
        else:
            raise ValueError("Cannot determine Azure resource group - missing config.json")
    
    # Get publish credentials
    creds_url = (
        f"https://management.azure.com/subscriptions/{creds['azure_subscription_id']}"
        f"/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{function_app_name}"
        f"/config/publishingcredentials/list?api-version=2022-03-01"
    )
    
    creds_response = _provider_request(
        requests.post,
        "Azure publishing credentials",
        creds_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30
    )
    
    if creds_response.status_code != 200:
        raise FunctionProviderError(
            f"Failed to get Azure publish credentials (HTTP {creds_response.status_code})"
        )
    
    try:
        properties = creds_response.json()["properties"]
        pub_user = properties["publishingUserName"]
        pub_pass = properties["publishingPassword"]
    except (KeyError, TypeError, ValueError) as exc:
        raise FunctionProviderError(
            "Azure publishing credential response was incomplete"
        ) from exc
    
    # Deploy via Kudu zipdeploy
    kudu_url = f"https://{function_app_name}.scm.azurewebsites.net/api/zipdeploy"
    
    deploy_response = _provider_request(
        requests.post,
        "Azure ZIP deployment",
        kudu_url,
        data=zip_content,
        auth=(pub_user, pub_pass),
        headers={"Content-Type": "application/zip"},
        timeout=300
    )
    
    if deploy_response.status_code not in (200, 202):
        raise FunctionProviderError(f"Kudu zipdeploy failed (HTTP {deploy_response.status_code})")
    if deploy_response.status_code == 202:
        location = deploy_response.headers.get("Location")
        if not location:
            raise FunctionProviderError(
                "Kudu accepted asynchronous deployment without a status URL"
            )
        _wait_for_kudu_deployment(
            _resolve_kudu_status_url(location, kudu_url),
            auth=(pub_user, pub_pass),
        )
    
    logger.info(f"✓ Azure Function code updated: {function_app_name}")
    return {
        "success": True,
        "function_app": function_app_name
    }


def _upload_gcp_function(function_name: str, zip_content: bytes, project_name: str) -> Dict[str, Any]:
    """Upload source and update an existing second-generation GCP Cloud Function."""
    if not HAS_GCP_FUNCTIONS or not HAS_REQUESTS:
        raise ValueError("GCP Cloud Functions dependencies are not installed")

    project_path, creds = _load_provider_credentials(project_name, "gcp")
    required = ["gcp_project_id", "gcp_region", "gcp_credentials_file"]
    for key in required:
        if not creds.get(key):
            raise ValueError(f"Missing required GCP credential: {key}")

    credentials_path = Path(creds["gcp_credentials_file"])
    if not credentials_path.is_absolute():
        credentials_path = project_path / credentials_path
    if not credentials_path.is_file():
        raise ValueError("Configured GCP service-account file does not exist")

    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    client = functions_v2.FunctionServiceClient(credentials=credentials)
    parent = f"projects/{creds['gcp_project_id']}/locations/{creds['gcp_region']}"
    resource_name = f"{parent}/functions/{function_name}"

    try:
        upload = client.generate_upload_url(request={"parent": parent}, timeout=30)
        upload_response = _provider_request(
            requests.put,
            "GCP source upload",
            upload.upload_url,
            data=zip_content,
            headers={
                "Content-Type": "application/zip",
                "x-goog-content-length-range": "0,104857600",
            },
            timeout=300,
        )
        if upload_response.status_code not in {200, 201}:
            raise FunctionProviderError(
                f"GCP function source upload failed (HTTP {upload_response.status_code})"
            )

        function = client.get_function(request={"name": resource_name}, timeout=30)
        function.build_config.source = functions_v2.Source(storage_source=upload.storage_source)
        operation = client.update_function(
            request={
                "function": function,
                "update_mask": field_mask_pb2.FieldMask(paths=["build_config.source"]),
            },
            timeout=30,
        )
        updated = operation.result(timeout=900)
    except (GoogleAPICallError, RetryError) as exc:
        raise FunctionProviderError("GCP Cloud Function update failed") from exc

    logger.info(f"GCP Cloud Function code updated: {function_name}")
    return {
        "success": True,
        "function_name": function_name,
        "resource_name": getattr(updated, "name", resource_name),
    }
