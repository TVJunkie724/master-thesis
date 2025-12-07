# Refactoring rest_api.py

## Goal Description
The `rest_api.py` file has become too large and unmaintainable. The goal is to split it into smaller, logically grouped modules within a new `api/` directory using FastAPI's `APIRouter`.

## User Review Required
- **New Directory Structure**: Moving API logic to `api/`.
- **Endpoint Grouping**:
    - `projects.py`: Project management and upload.
    - `validation.py`: Validation endpoints.
    - `deployment.py`: Core, IoT, and additional deployment endpoints.
    - `destroy.py`: Destruction endpoints (or combined with deployment?). *Decision: Combine with deployment for cohesion, or separate if desired. I will combine in `deployment.py` using different tags, or `lifecycle.py`? User said "endpoint category". Tags are Deployment and Destroy. I'll stick to `deployment.py` and maybe `ops.py` or separate.*
    - `status.py`: Check/Status endpoints.
    - `info.py`: Configuration info endpoints.
    - `aws_endpoints.py`: AWS specific lambda management.

> [!NOTE]
> I will group "Deployment" and "Destroy" tags into `deployment.py` or `lifecycle.py` unless requested otherwise. However, `rest_api.py` separated them by tag. I'll put them in `deployment.py` to keep related logic (deploy l1 / destroy l1) in one file, or split by functional area.
> Tags:
> - Projects (api/projects.py)
> - Info (api/info.py)
> - Deployment (api/deployment.py)
> - Destroy (api/destroy.py) -- *Wait, having deploy and destroy in one file `deployment.py` is usually better for maintenance. I will propose `api/deployment.py` covering both.*
> - Status (api/status.py)
> - AWS (api/aws.py)
> - Validation (api/validation.py)

## Proposed Changes

### `3-cloud-deployer`

#### [NEW] `api/__init__.py`
Empty file to make it a package.

#### [NEW] `api/projects.py`
Endpoints with tag "Projects".
- `list_projects`
- `create_project`
- `activate_project`
- `update_config`
- `update_project_zip`
- `update_function_file`
- `upload_state_machine`

#### [NEW] `api/validation.py`
Endpoints with tag "Validation".
- `validate_zip`
- `validate_config`
- `validate_function`

#### [NEW] `api/deployment.py`
Endpoints with tag "Deployment" and "Destroy".
- `deploy_all`, `destroy_all`
- `recreate_updated_events`
- `deploy_l1`...`l5`, `destroy_l1`...`l5`

#### [NEW] `api/status.py`
Endpoints with tag "Status".
- `check_endpoint`
- `check_l1`...`l5`

#### [NEW] `api/info.py`
Endpoints with tag "Info".
- `read_root` (maybe keep in main?)
- `get_main_config`
- `get_iot_config`
- `get_providers_config`
- `get_config_hierarchy`
- `get_config_events`

#### [NEW] `api/aws_gateway.py` (renamed from AWS to avoid conflict with local aws folder?)
Endpoints with tag "AWS".
- `lambda_update`
- `get_lambda_logs`
- `lambda_invoke`

#### [MODIFY] `rest_api.py`
- Remove all endpoint implementations.
- Import `APIRouter` from `fastapi`.
- Import routers from `api/*`.
- `app.include_router(...)`.
- Keep `startup_event` and global init.
- Keep `favicon`.

## Verification Plan

### Automated Tests
- Run existing tests to ensure no regressions.
- Verify API starts up: `docker restart master-thesis-3cloud-deployer-1` then check logs.
- Use `curl` or browser to hit a few endpoints (e.g. `/`, `/projects`).

### Manual Verification
- Check `/documentation` to ensure Swagger UI still loads and grouped correctly.
