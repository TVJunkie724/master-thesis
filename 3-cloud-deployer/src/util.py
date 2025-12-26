import os
import time
import zipfile
import globals
import json
from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse

REQUIRED_CREDENTIALS_FIELDS = {
    "aws": ["aws_access_key_id", "aws_secret_access_key", "aws_region"],
    "azure": ["azure_subscription_id", "azure_client_id", "azure_client_secret", "azure_tenant_id", "azure_region"],
    "google": ["gcp_project_id", "gcp_credentials_file", "gcp_region"]
}

def pretty_json(data):
    """Return JSON with indentation and UTF-8 encoding."""
    return JSONResponse(
        content=json.loads(json.dumps(data, indent=2, ensure_ascii=False))
    )

def zip_directory(relative_folder_path, zip_name='zipped.zip'):
  folder_path = os.path.join(globals.project_path(), relative_folder_path)
  output_path = os.path.join(folder_path, zip_name)

  with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(folder_path):
      for file in files:
        full_path = os.path.join(root, file)
        if full_path == output_path:
          continue
        arcname = os.path.relpath(full_path, start=folder_path)
        zf.write(full_path, arcname)

  return output_path


def contains_provider(config_providers, provider_name):
    """Check if any value in the provider config matches provider_name."""
    return any(provider_name in str(v).lower() for v in config_providers.values())

def validate_credentials(provider_name, credentials):
    """Check if credentials exist and all required fields are present."""
    provider_creds = credentials.get(provider_name, {})
    if not provider_creds:
        raise ValueError(f"{provider_name.upper()} credentials are required but not found.")
    
    missing_fields = [field for field in REQUIRED_CREDENTIALS_FIELDS[provider_name] if field not in provider_creds]
    if missing_fields:
        raise ValueError(f"{provider_name.upper()} credentials are missing fields: {missing_fields}")
    return provider_creds