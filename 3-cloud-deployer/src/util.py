import os
import time
import zipfile
import globals
import json
from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse

import constants as CONSTANTS

def pretty_json(data):
    """Return JSON with indentation and UTF-8 encoding."""
    return JSONResponse(
        content=json.loads(json.dumps(data, indent=2, ensure_ascii=False))
    )

def contains_provider(config_providers, provider_name):
    """Check if any value in the provider config matches provider_name."""
    return any(provider_name in str(v).lower() for v in config_providers.values())

def validate_credentials(provider_name, credentials):
    """Check if credentials exist and all required fields are present."""
    provider_creds = credentials.get(provider_name, {})
    if not provider_creds:
        raise ValueError(f"{provider_name.upper()} credentials are required but not found.")
    
    missing_fields = [field for field in CONSTANTS.REQUIRED_CREDENTIALS_FIELDS[provider_name] if field not in provider_creds]
    if missing_fields:
        raise ValueError(f"{provider_name.upper()} credentials are missing fields: {missing_fields}")
    return provider_creds

def get_path_in_project(subpath=""):
    """
    Returns the absolute path to a file or directory within the currently active project's upload directory.
    """
    project_upload_path = globals.get_project_upload_path()
    if subpath:
        return os.path.join(project_upload_path, subpath)
    return project_upload_path

def resolve_folder_path(folder_path):
  rel_path = os.path.join(globals.project_path(), folder_path)

  if os.path.exists(rel_path):
    return rel_path

  abs_path = os.path.abspath(folder_path)

  if os.path.exists(abs_path):
    return abs_path

  raise FileNotFoundError(
    f"Folder '{folder_path}' does not exist as relative or absolute path."
  )

def zip_directory(folder_path, zip_name='zipped.zip'):
  folder_path = resolve_folder_path(folder_path)
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

def compile_lambda_function(folder_path):
  zip_path = zip_directory(folder_path)

  with open(zip_path, "rb") as f:
    zip_code = f.read()

  return zip_code