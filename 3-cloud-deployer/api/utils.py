import base64
from fastapi import Request, HTTPException, UploadFile
from api.dependencies import Base64FileRequest
import json

async def extract_file_content(request: Request, file_field: str = "file", base64_field: str = "file_base64") -> bytes:
    """
    Extracts file content from a request, supporting both Multipart/Form-Data and Application/JSON (Base64).
    
    Args:
        request (Request): The FastAPI request object.
        file_field (str): The field name for multipart upload.
        base64_field (str): The field name for base64 string in JSON body.
        
    Returns:
        bytes: The binary content of the file.
        
    Raises:
        HTTPException: If extraction fails or content type is unsupported.
    """
    content_type = request.headers.get("content-type", "")
    
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get(file_field)
        
        # Robust check: Ensure it's not None and not a simple string field
        if not file or isinstance(file, str):
             raise HTTPException(status_code=400, detail=f"Missing or invalid file field '{file_field}' in multipart request.")
             
        # Duck typing or assumption it's UploadFile
        return await file.read()
        
    elif "application/json" in content_type:
        try:
            body = await request.json()
            # Check if body parses to our model structure or direct dict
            if isinstance(body, dict):
                 b64_str = body.get(base64_field)
            else:
                 raise HTTPException(status_code=400, detail="Invalid JSON body.")

            if not b64_str:
                raise HTTPException(status_code=400, detail=f"Missing '{base64_field}' field in JSON body.")
                
            return base64.b64decode(b64_str)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON.")
        except  ValueError: # base64 error
             raise HTTPException(status_code=400, detail="Invalid Base64 string.")
             
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported Content-Type: {content_type}. Use 'multipart/form-data' or 'application/json'.")
