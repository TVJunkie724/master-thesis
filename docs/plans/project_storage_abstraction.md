# ProjectStorage Abstraction Layer — Implementation Blueprint

## Goal

Introduce a `ProjectStorage` protocol that abstracts all per-project file I/O. Implement `FileSystemStorage` (wrapping current behavior, zero functional change) and a **stub** `DatabaseStorage` (`NotImplementedError`). Migrate consumers to use the abstraction.

> [!IMPORTANT]
> **We are NOT switching to a database.** The stub `DatabaseStorage` shows where a future DB backend would slot in. The actual running storage remains `FileSystemStorage`. All existing behavior is preserved.

---

## Complete File Manifest

Every file that must be created or modified, in implementation order.

### New Files (3)

| # | Path | Purpose |
|---|------|---------|
| 1 | `src/core/storage.py` | `ProjectStorage` protocol definition |
| 2 | `src/core/storage_filesystem.py` | `FileSystemStorage` implementation |
| 3 | `src/core/storage_database.py` | Stub `DatabaseStorage` (`NotImplementedError`) |

### Modified Files — Source (15)

| # | Path | Lines | Change Summary |
|---|------|-------|----------------|
| 4 | `src/api/dependencies.py` | 73 | Add `get_storage()` DI wiring point |
| 5 | `src/core/context.py` | 295 | Add optional `storage` field to `DeploymentContext` |
| 6 | `src/core/config_loader.py` | 427 | Add optional `storage` param to loading functions |
| 7 | `src/core/state.py` | 61 | Use `storage.project_exists()` in `set_active_project()` |
| 8 | `src/core/factory.py` | 55 | Pass storage to `load_project_config()` and `DeploymentContext` |
| 9 | `src/file_manager.py` | 559 | Delegate all filesystem ops to storage internally |
| 10 | `src/tfvars_generator.py` | 676 | Use `storage.get_config()` in `_load_*` functions |
| 11 | `src/terraform_runner.py` | 464 | Use `storage.get_project_path()` for state dir |
| 12 | `src/function_registry.py` | 448 | Use `storage.get_project_path()` for function paths |
| 13 | `src/validator.py` | 1051 | Use storage in `check_duplicate_project()` and config reads |
| 14 | `src/providers/terraform/deployer_strategy.py` | 911 | Pass storage from context to tfvars/package builders |
| 15 | `src/providers/terraform/package_builder.py` | 1171 | Use `storage.get_project_path()` for function code paths |
| 16 | `src/providers/terraform/aws_deployer.py` | — | Use storage for TwinMaker hierarchy reads |
| 17 | `src/providers/terraform/azure_deployer.py` | — | Use storage for DTDL model reads |
| 18 | `src/api/projects.py` | 835 | Pass storage to `file_manager` calls |

### Modified Files — API Layer (light touches, most covered by file_manager migration)

| # | Path | Lines | Change Summary |
|---|------|-------|----------------|
| 19 | `src/api/functions.py` | 1120 | Use storage for function code R/W, config reads, hash metadata |
| 20 | `src/api/deployment.py` | 363 | Storage flows through DeploymentContext |
| 21 | `src/api/validation.py` | 1392 | Pass storage for config reads |
| 22 | `src/api/simulator.py` | 359 | Use storage for project-upload-dir reads only (NOT `src/` script paths) |
| 23 | `src/api/status.py` | 475 | Use storage for hash metadata and state paths |
| 24 | `src/api/credentials_checker.py` | — | Use storage for credential file reads |
| 25 | `src/api/azure_credentials_checker.py` | — | Use storage for credential file reads (same pattern as #24) |
| 26 | `src/api/gcp_credentials_checker.py` | — | Use storage for credential file reads (same pattern as #24) |

### Modified Files — Tests (4 modified + 1 new)

| # | Path | Change Summary |
|---|------|----------------|
| 27 | `tests/conftest.py` | Add `mock_storage` fixture |
| 28 | `tests/unit/core_tests/test_storage_filesystem.py` | **[NEW]** Unit tests for `FileSystemStorage` |
| 29 | `tests/unit/test_file_manager_crud.py` | Update for storage-backed `file_manager` |
| 30 | `tests/unit/test_file_manager_versioning.py` | Update for storage-backed `file_manager` |
| 31 | `tests/unit/core_tests/test_config_loader.py` | Add test variants with `storage` param |

### Files NOT Touched (explicitly excluded)

| File/Module | Reason |
|-------------|--------|
| `src/globals.py` | Legacy CLI path, 18 importers (mostly for `logger_proxy`), high-risk churn |
| `src/main.py` | CLI entry point, calls `globals.initialize_all()` |
| `src/info.py`, `src/util.py` | Legacy helpers reading from `globals.*` |
| `src/aws/**` | Legacy deployers, access data via `globals.*` |
| `src/deployers/**` | Legacy deployers, access data via `globals.*` |
| `src/iot_device_simulator/**` | Standalone plug-and-play module, has own separate globals per provider |

---

## Phase 1: Core Abstraction Layer (files 1–4)

### [NEW] `src/core/storage.py` — Protocol Definition

> [!WARNING]
> **Must be standalone — no imports from other `core/` modules.** This prevents circular imports since `context.py` will import from this file.

Define `ProjectStorage` as a Python `Protocol` class with all methods listed below.

**Config type mapping** (used by `get_config`/`save_config`):

| `config_type` string | File on disk |
|----------------------|-------------|
| `"config"` | `config.json` |
| `"providers"` | `config_providers.json` |
| `"iot_devices"` | `config_iot_devices.json` |
| `"events"` | `config_events.json` |
| `"credentials"` | `config_credentials.json` |
| `"optimization"` | `config_optimization.json` |
| `"inter_cloud"` | `config_inter_cloud.json` |
| `"user"` | `config_user.json` |

Methods:

```python
class ProjectStorage(Protocol):
    def get_config(self, project: str, config_type: str) -> dict: ...
    def save_config(self, project: str, config_type: str, data: dict) -> None: ...
    def get_file(self, project: str, path: str) -> bytes: ...
    def save_file(self, project: str, path: str, content: bytes) -> None: ...
    def list_files(self, project: str, prefix: str = "") -> list[str]: ...
    def file_exists(self, project: str, path: str) -> bool: ...
    def delete_file(self, project: str, path: str) -> None: ...
    def project_exists(self, project: str) -> bool: ...
    def list_projects(self) -> list[str]: ...
    def create_project_from_zip(self, project: str, zip_data: BytesIO, description: str = None) -> dict: ...
    def delete_project(self, project: str) -> None: ...
    def get_project_path(self, project: str) -> Path: ...
    def get_project_metadata(self, project: str) -> dict: ...
    def save_project_metadata(self, project: str, data: dict) -> None: ...
```

---

### [NEW] `src/core/storage_filesystem.py` — FileSystemStorage

- Constructor: `__init__(self, upload_dir: str = "/app/upload")`
- Each method wraps the exact filesystem patterns currently used inline across the codebase
- `get_project_path()` → returns `Path(self.upload_dir) / project`
- `get_config()` → `json.load(open(upload_dir/project/CONFIG_TYPE_MAP[config_type]))` with error handling
- `save_config()` → `json.dump()` to same path
- `create_project_from_zip()` → extracts logic from `file_manager.create_project_from_zip()`: validate ZIP, check duplicates, extract, write `project_info.json`, archive version
- `list_projects()` → `os.listdir(upload_dir)` filtered to directories
- `list_files()` → `os.walk()` with prefix filtering, returns relative paths
- Credentials: `get_config("credentials")` loads `config_credentials.json`. Per-provider files (`config_credentials_aws.json`) use `get_file()`.

---

### [NEW] `src/core/storage_database.py` — Stub

Every method: `raise NotImplementedError("Database storage not yet implemented")`

---

### [MODIFY] `src/api/dependencies.py`

Add:
```python
from core.storage import ProjectStorage
from core.storage_filesystem import FileSystemStorage

_storage: ProjectStorage = FileSystemStorage("/app/upload")

def get_storage() -> ProjectStorage:
    return _storage
```

---

## Phase 2: Migrate Core Layer (files 5–8)

### [MODIFY] `src/core/context.py`

- Add `storage: Optional['ProjectStorage'] = None` field to `DeploymentContext`
- Use `TYPE_CHECKING` guard: `from .storage import ProjectStorage` (same pattern as existing `CloudProvider`)
- `get_upload_path()` → if `self.storage`, delegate to `self.storage.get_project_path(self.project_name)`, else use `self.project_path`

### [MODIFY] `src/core/config_loader.py`

- `load_project_config(project_path, storage=None, project_name=None)` → when `storage` provided, use `storage.get_config(project_name, ...)` instead of `_load_json_file()`. When `project_name` is `None`, extract it from `project_path.name`.
- `_load_hierarchy_for_provider(project_path, provider, storage=None, project_name=None)` → when `storage` provided, use `storage.get_file()` for hierarchy JSON
- `save_inter_cloud_connection(project_path, conn_id, url, token, storage=None, project_name=None)` → when `storage` provided, use `storage.get_config()` + `storage.save_config()`
- `load_credentials(project_path, storage=None, project_name=None)` → handles both combined + per-provider file patterns via storage
- `load_optimization_flags(project_path, storage=None, project_name=None)` → use storage when available
- `_load_json_file()` stays as internal fallback for when `storage=None`

> [!NOTE]
> **Project name extraction:** `storage.get_config()` requires a project name, but `load_project_config()` currently receives a `Path`. When `project_name` is not provided, extract it via `project_path.name` (the directory name is the project name). This keeps backward compatibility while enabling storage.

### [MODIFY] `src/core/state.py`

- `set_active_project()` → lazy import `get_storage` inside function body, use `storage.project_exists()` instead of `os.path.exists()`
- Lazy import avoids circular imports at module level

### [MODIFY] `src/core/factory.py`

- `create_context()` → import `get_storage`, pass storage to `load_project_config()`, set `context.storage = storage`

---

## Phase 3: Migrate Business Logic Layer (files 9–13)

### [MODIFY] `src/file_manager.py`

**Keep current function signatures and API surface.** Add optional `storage` param with default from `get_storage()`:

- `create_project_from_zip(project_name, zip_source, project_path=None, description=None, storage=None)` → delegate ZIP extraction/validation to `storage.create_project_from_zip()`
- `list_projects(project_path=None, storage=None)` → `storage.list_projects()`
- `update_config_file(...)` → `storage.save_config()`
- `delete_project(...)` → `storage.delete_project()`
- `export_project_to_zip(...)` → `storage.list_files()` + `storage.get_file()`, or use `storage.get_project_path()` + `os.walk()` for the complex tree exclusion logic
- `get_project_file_content(...)` → `storage.get_file()`
- `get_project_file_tree(...)` → use `storage.get_project_path()` with existing `os.walk()` tree builder
- `update_project_info(...)` → `storage.get_project_metadata()` + `storage.save_project_metadata()`
- Remove `_get_project_base_path()` — replaced by storage's `upload_dir`

### [MODIFY] `src/tfvars_generator.py`

- Accept `storage` parameter in `generate_tfvars()`
- 7 internal `_load_*` functions → use `storage.get_config()` instead of `open()`
- Function path lookups → `storage.get_project_path()` (Terraform needs real files)

### [MODIFY] `src/terraform_runner.py`

- Per-project state path → `storage.get_project_path()` to resolve state directory
- Minimal change — Terraform requires actual files

### [MODIFY] `src/function_registry.py`

- `get_function_path()` / `get_wrapper_path()` → use `storage.get_project_path()` instead of hardcoded `Path`

### [MODIFY] `src/validator.py`

- `check_duplicate_project()` → use `storage.list_projects()` + `storage.get_config()`
- Other validation mostly operates on in-memory data — minimal changes
- `validate_project_zip()` works on BytesIO — no change

---

## Phase 4: Migrate Provider & Deployer Layer (files 14–17)

### [MODIFY] `src/providers/terraform/deployer_strategy.py`

- Access storage from `context.storage` (set by factory in Phase 2)
- Pass storage to `tfvars_generator.generate_tfvars()`
- Pass storage to `package_builder` functions

### [MODIFY] `src/providers/terraform/package_builder.py`

- Use `storage.get_project_path()` (or `context.storage.get_project_path()`) for function code directory resolution
- Package building needs files on disk — `get_project_path()` provides that

### [MODIFY] `src/providers/terraform/aws_deployer.py`

- TwinMaker hierarchy reads → use `context.storage.get_file()` or `context.storage.get_config()`

### [MODIFY] `src/providers/terraform/azure_deployer.py`

- DTDL model reads → use `context.storage`

---

## Phase 5: Migrate API Layer (files 18–26)

> [!NOTE]
> Since `file_manager.py` is the main intermediary between API endpoints and the filesystem, most API endpoints get coverage automatically once `file_manager.py` is migrated. The changes below cover remaining direct file access.

### [MODIFY] `src/api/projects.py`

- Pass storage to `file_manager.*` calls
- Direct `open()` / `os.path` calls → use storage

### [MODIFY] `src/api/functions.py`

- Function code read/write → use storage
- Hash metadata management → use storage

### [MODIFY] `src/api/deployment.py`

- Storage flows through `DeploymentContext` → no direct storage calls needed, but ensure context creation passes storage

### [MODIFY] `src/api/validation.py`

- Config reads for validation → use storage

### [MODIFY] `src/api/simulator.py`

- Project-upload-dir reads (config_generated, payloads.json, auth certs) → use storage
- Application-level script paths (`src/iot_device_simulator/`) → keep as-is, these reference application code not per-project data
- `state.get_project_upload_path()` calls → use `storage.get_project_path()`

### [MODIFY] `src/api/status.py`

- Hash metadata reads → use storage
- Terraform state path → `storage.get_project_path()`

### [MODIFY] `src/api/credentials_checker.py`

- Credential file reads (`open(config_path)` → `json.load`) → use `storage.get_config(project, "credentials")`

### [MODIFY] `src/api/azure_credentials_checker.py`

- Same credential reading pattern as `credentials_checker.py` → use storage

### [MODIFY] `src/api/gcp_credentials_checker.py`

- Same credential reading pattern as `credentials_checker.py` → use storage
- GCP credentials file path resolution (line 547 `os.path.join(project_dir, creds_path)`) → use `storage.get_project_path()` to resolve

---

## Phase 6: Tests (files 27–31)

### [NEW] `tests/unit/core_tests/test_storage_filesystem.py`

Unit tests for `FileSystemStorage` using `tmp_path`:
- `test_get_config` / `test_save_config` — round-trip JSON
- `test_get_file` / `test_save_file` — round-trip binary
- `test_list_files` / `test_file_exists` / `test_delete_file`
- `test_project_exists` / `test_list_projects`
- `test_create_project_from_zip` / `test_delete_project`
- `test_get_project_path` — returns correct `Path`

### [MODIFY] `tests/conftest.py`

Add shared `mock_storage` fixture:
```python
@pytest.fixture
def mock_storage(tmp_path):
    from core.storage_filesystem import FileSystemStorage
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    return FileSystemStorage(str(upload_dir))
```

### [MODIFY] `tests/unit/test_file_manager_crud.py`

- Update fixtures to create `FileSystemStorage(tmp_path)` and pass to `file_manager` functions

### [MODIFY] `tests/unit/test_file_manager_versioning.py`

- Same approach as CRUD tests

### [MODIFY] `tests/unit/core_tests/test_config_loader.py`

- Add test variants that pass `storage` to `load_project_config()`
- Existing tests with `project_path` only must continue to work (backward compat)

---

## Verification Plan

### Test Commands

```bash
# Full unit + integration suite (excludes E2E)
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v

# New storage tests only
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/core_tests/test_storage_filesystem.py -v

# Directly affected tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/test_file_manager_crud.py tests/unit/test_file_manager_versioning.py tests/unit/core_tests/test_config_loader.py -v
```

### Success Criteria

1. **All existing unit/integration tests pass** — zero regression
2. **New `test_storage_filesystem.py` tests pass**
3. **Grep check** — no direct `open()` for per-project data in migrated files:
   ```bash
   grep -rn "open(" src/file_manager.py src/core/config_loader.py src/core/state.py src/core/factory.py src/tfvars_generator.py
   ```

> [!NOTE]
> E2E tests should NOT be run. Legacy files (`globals.py`, `iot_device_simulator/`, `aws/`, `deployers/`) are excluded from the grep check — they are not migrated.

---

## Phase 7: Definition of Done — Final Checklist

After all phases are complete, go through this checklist to confirm every change is implemented.

### New Files Created

- [ ] `src/core/storage.py` exists and contains `ProjectStorage` protocol with all 14 methods
- [ ] `src/core/storage.py` has NO imports from other `core/` modules (circular import guard)
- [ ] `src/core/storage_filesystem.py` exists and implements all 14 `ProjectStorage` methods
- [ ] `src/core/storage_filesystem.py` constructor accepts `upload_dir` parameter
- [ ] `src/core/storage_database.py` exists, every method raises `NotImplementedError`
- [ ] `tests/unit/core_tests/test_storage_filesystem.py` exists with tests for all storage methods

### DI Wiring

- [ ] `src/api/dependencies.py` has `get_storage()` function returning `FileSystemStorage("/app/upload")`
- [ ] Swapping storage backend requires changing only the `_storage = ...` line in `dependencies.py`

### Core Layer Migration

- [ ] `src/core/context.py` — `DeploymentContext` has optional `storage` field
- [ ] `src/core/config_loader.py` — `load_project_config()` accepts optional `storage` param
- [ ] `src/core/config_loader.py` — `save_inter_cloud_connection()` accepts optional `storage` param
- [ ] `src/core/config_loader.py` — `load_credentials()` accepts optional `storage` param
- [ ] `src/core/config_loader.py` — `load_optimization_flags()` accepts optional `storage` param
- [ ] `src/core/config_loader.py` — all functions still work with `storage=None` (backward compat)
- [ ] `src/core/state.py` — `set_active_project()` uses `storage.project_exists()`
- [ ] `src/core/factory.py` — `create_context()` passes storage to config loader and context

### Business Logic Migration

- [ ] `src/file_manager.py` — all functions delegate to storage internally
- [ ] `src/file_manager.py` — all existing function signatures preserved (backward compat)
- [ ] `src/file_manager.py` — `_get_project_base_path()` removed or replaced by storage
- [ ] `src/tfvars_generator.py` — `_load_*` functions use `storage.get_config()`
- [ ] `src/terraform_runner.py` — uses `storage.get_project_path()` for state dir
- [ ] `src/function_registry.py` — uses `storage.get_project_path()` for function paths
- [ ] `src/validator.py` — `check_duplicate_project()` uses storage

### Provider & Deployer Migration

- [ ] `src/providers/terraform/deployer_strategy.py` — accesses storage from `context.storage`
- [ ] `src/providers/terraform/package_builder.py` — uses `storage.get_project_path()`
- [ ] `src/providers/terraform/aws_deployer.py` — hierarchy reads use storage
- [ ] `src/providers/terraform/azure_deployer.py` — DTDL model reads use storage

### API Layer Migration

- [ ] `src/api/projects.py` — passes storage to `file_manager` calls
- [ ] `src/api/functions.py` — function code R/W uses storage
- [ ] `src/api/deployment.py` — storage flows through `DeploymentContext`
- [ ] `src/api/validation.py` — config reads use storage
- [ ] `src/api/simulator.py` — project-upload-dir reads use storage (app-level script paths unchanged)
- [ ] `src/api/status.py` — metadata reads use storage
- [ ] `src/api/credentials_checker.py` — credential reads use storage
- [ ] `src/api/azure_credentials_checker.py` — credential reads use storage
- [ ] `src/api/gcp_credentials_checker.py` — credential reads use storage

### Tests

- [ ] `tests/conftest.py` — `mock_storage` fixture added
- [ ] `tests/unit/core_tests/test_storage_filesystem.py` — all tests pass
- [ ] `tests/unit/test_file_manager_crud.py` — updated and passing
- [ ] `tests/unit/test_file_manager_versioning.py` — updated and passing
- [ ] `tests/unit/core_tests/test_config_loader.py` — updated and passing
- [ ] Full test suite passes: `python -m pytest tests/ --ignore=tests/e2e -v`

### Architectural Checks

- [ ] No circular imports — application starts without `ImportError`
- [ ] `grep -rn "open(" src/file_manager.py src/core/config_loader.py src/core/state.py src/core/factory.py src/tfvars_generator.py` returns zero hits for per-project data access
- [ ] Legacy files untouched: `globals.py`, `iot_device_simulator/`, `aws/`, `deployers/`, `main.py`, `info.py`, `util.py`
