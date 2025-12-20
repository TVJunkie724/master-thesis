# Build Function ZIP Endpoint

## Goal

Add new endpoint `POST /functions/build` that:
1. Accepts a Python function file upload
2. Validates the code (syntax, entry point)
3. Builds a provider-specific deployment ZIP
4. Returns the ZIP file for download

---

## Endpoint Design

```
POST /functions/build
```

**Parameters:**
- `provider` (query, required): aws, azure, or google
- `function_type` (query, required): event_action, processor, or standalone
- `file` (body, file): Python file(s) to include

**Response:** ZIP file download

---

## Implementation Steps

### 1. Add endpoint in `functions.py`

```python
@router.post(
    "/build",
    tags=["Functions"],
    summary="Build function deployment ZIP",
    responses={
        200: {"description": "ZIP file", "content": {"application/zip": {}}},
        400: {"description": "Validation failed"}
    }
)
async def build_function_zip(
    provider: str = Query(..., description="Cloud provider: aws, azure, or google"),
    function_type: str = Query("standalone", description="Function type: event_action, processor, or standalone"),
    file: UploadFile = File(..., description="Python function file")
):
```

### 2. Validation (reuse validator.py)

- Check Python syntax (`ast.parse`)
- For `event_action`: require `handler(event, context)` 
- For `processor`: require `process(event)`
- For `standalone`: require `main(request)` or `handler(event, context)`

### 3. Build ZIP (adapt from package_builder.py)

| Provider | ZIP Structure |
|----------|---------------|
| AWS | function files + `_shared/` modules |
| Azure | function files + `host.json` + `function.json` |
| Google | function files + `requirements.txt` |

### 4. Return StreamingResponse

```python
return StreamingResponse(
    io.BytesIO(zip_content),
    media_type="application/zip",
    headers={"Content-Disposition": f"attachment; filename={function_name}.zip"}
)
```

---

## Files to Modify

| File | Change |
|------|--------|
| [functions.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/api/functions.py) | Add `build_function_zip` endpoint |
| [validator.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/validator.py) | Reuse existing `validate_event_action_code`, `validate_processor_code` |
