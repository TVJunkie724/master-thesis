"""Validated, provider-specific function ZIP build API."""

import ast
import json
import zipfile
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from src.api.error_handling import internal_server_error, safe_error_detail
from src.api.error_models import ERROR_RESPONSES
from src.api.upload_limits import read_upload_bounded

router = APIRouter()

MAX_FUNCTION_SOURCE_BYTES = 2 * 1024 * 1024
MAX_REQUIREMENTS_BYTES = 1024 * 1024


async def _read_bounded_upload(upload: UploadFile, limit: int, description: str) -> bytes:
    try:
        return await read_upload_bounded(upload, max_bytes=limit)
    except HTTPException as exc:
        if exc.status_code == 413:
            exc.detail = f"{description} exceeds the {limit}-byte limit"
        raise

def _validate_python_syntax(content: bytes, filename: str) -> None:
    """
    Validate Python syntax using AST parsing.
    
    Args:
        content: Python file content as bytes
        filename: Name of the file (for error messages)
        
    Raises:
        ValueError: If syntax is invalid
    """
    try:
        ast.parse(content.decode('utf-8'))
    except SyntaxError as e:
        raise ValueError(f"Python syntax error in {filename}: {e.msg} (line {e.lineno})")
    except UnicodeDecodeError as e:
        raise ValueError(f"Invalid encoding in {filename}: {e}")


def _validate_entry_point(content: bytes, provider: str) -> None:
    """
    Validate that the function has a valid entry point.
    
    Args:
        content: Python file content as bytes
        provider: Cloud provider (aws, azure, google)
        
    Raises:
        ValueError: If entry point is missing
    """
    source = content.decode('utf-8')
    tree = ast.parse(source)
    
    # Extract function names
    function_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    
    # Check for expected entry points by provider
    if provider == "aws":
        valid_entries = ["handler", "lambda_handler"]
        if not any(name in function_names for name in valid_entries):
            raise ValueError(
                f"AWS Lambda requires 'handler(event, context)' or 'lambda_handler(event, context)'. "
                f"Found functions: {function_names}"
            )
    elif provider == "azure":
        # Azure Functions use decorators, check for any function
        if not function_names:
            raise ValueError("No functions found in the file. Azure Functions require at least one function.")
    elif provider == "google":
        # GCP Cloud Functions use a specific entry point
        valid_entries = ["main", "handler", "hello_http"]
        if not any(name in function_names for name in valid_entries):
            raise ValueError(
                f"GCP Cloud Functions require 'main(request)' or 'handler(request)'. "
                f"Found functions: {function_names}"
            )


def _build_aws_zip(function_content: bytes, requirements_content: bytes = None) -> bytes:
    """Build AWS Lambda deployment ZIP."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", function_content)
        if requirements_content:
            zf.writestr("requirements.txt", requirements_content)
    buffer.seek(0)
    return buffer.getvalue()


def _build_azure_zip(function_content: bytes, requirements_content: bytes = None) -> bytes:
    """Build Azure Function deployment ZIP."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add function code
        zf.writestr("function_app.py", function_content)
        
        # Add host.json
        host_json = {
            "version": "2.0",
            "extensionBundle": {
                "id": "Microsoft.Azure.Functions.ExtensionBundle",
                "version": "[4.*, 5.0.0)"
            }
        }
        zf.writestr("host.json", json.dumps(host_json, indent=2))
        
        # Add requirements.txt
        if requirements_content:
            zf.writestr("requirements.txt", requirements_content)
        else:
            zf.writestr("requirements.txt", "azure-functions\n")
    
    buffer.seek(0)
    return buffer.getvalue()


def _build_gcp_zip(function_content: bytes, requirements_content: bytes = None) -> bytes:
    """Build GCP Cloud Function deployment ZIP."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add function code
        zf.writestr("main.py", function_content)
        
        # Add requirements.txt
        if requirements_content:
            zf.writestr("requirements.txt", requirements_content)
        else:
            zf.writestr("requirements.txt", "functions-framework\n")
    
    buffer.seek(0)
    return buffer.getvalue()


@router.post(
    "/build",
    operation_id="buildFunctionZip",
    tags=["Functions"],
    summary="Build function deployment ZIP",
    description=(
        "**Purpose:** Create cloud-ready ZIP from Python function file.\n\n"
        "**When to call:** To prepare a function for manual deployment.\n\n"
        "**Validation:** Syntax check, entry point validation per provider."
    ),
    responses={
        200: {"description": "ZIP file download", "content": {"application/zip": {}}},
        400: ERROR_RESPONSES[400],
        413: ERROR_RESPONSES[413],
        422: ERROR_RESPONSES[422],
    }
)
async def build_function_zip(
    provider: str = Query(..., description="Cloud provider: aws, azure, or google"),
    function_file: UploadFile = File(..., description="Python function file (.py)"),
    requirements_file: UploadFile = File(None, description="Optional requirements.txt")
):
    """
    Build a cloud-ready deployment ZIP from a Python function file.
    
    **Validation performed:**
    - Python syntax check (AST parsing)
    - Entry point validation by provider:
      - AWS: `handler(event, context)` or `lambda_handler(event, context)`
      - Azure: Any function (uses decorators)
      - Google: `main(request)` or `handler(request)`
    
    **ZIP contents by provider:**
    - **AWS**: `lambda_function.py` + optional `requirements.txt`
    - **Azure**: `function_app.py` + `host.json` + `requirements.txt`
    - **Google**: `main.py` + `requirements.txt`
    
    **Returns:** ZIP file download ready for cloud deployment.
    """
    # Validate provider
    provider = provider.lower()
    if provider == "gcp":
        provider = "google"
    if provider not in ("aws", "azure", "google"):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid provider: {provider}. Must be aws, azure, or google."
        )
    
    # Validate file extension
    function_filename = function_file.filename or ""
    if not function_filename.endswith('.py'):
        raise HTTPException(
            status_code=400,
            detail=f"Function file must be a Python file (.py). Got: {function_filename or '<missing>'}"
        )
    if requirements_file and not (requirements_file.filename or "").endswith(".txt"):
        raise HTTPException(status_code=400, detail="Requirements file must use the .txt extension")
    
    try:
        # Read function file
        function_content = await _read_bounded_upload(
            function_file,
            MAX_FUNCTION_SOURCE_BYTES,
            "Function source",
        )
        
        if not function_content:
            raise HTTPException(status_code=400, detail="Function file is empty")
        
        # Validate Python syntax
        _validate_python_syntax(function_content, function_filename)
        
        # Validate entry point
        _validate_entry_point(function_content, provider)
        
        # Read optional requirements file
        requirements_content = None
        if requirements_file:
            requirements_content = await _read_bounded_upload(
                requirements_file,
                MAX_REQUIREMENTS_BYTES,
                "Requirements file",
            )
        
        # Build ZIP based on provider
        if provider == "aws":
            zip_content = _build_aws_zip(function_content, requirements_content)
            filename = "lambda_function.zip"
        elif provider == "azure":
            zip_content = _build_azure_zip(function_content, requirements_content)
            filename = "azure_function.zip"
        else:  # google
            zip_content = _build_gcp_zip(function_content, requirements_content)
            filename = "cloud_function.zip"
        
        # Return as downloadable ZIP
        return StreamingResponse(
            BytesIO(zip_content),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=safe_error_detail(exc)) from exc
    except Exception as exc:
        raise internal_server_error(
            "Build function ZIP",
            exc,
            detail="Function operation failed. Check logs.",
        ) from exc
