# Complete Legacy Code Removal

## 1. Executive Summary

### The Problem
The codebase has a dual-architecture: legacy `globals.py`/`globals_aws.py` pattern running alongside the new `DeploymentContext`/`AWSProvider` pattern. This creates confusion, maintenance burden, and prevents clean dependency injection.

### The Solution
Fully migrate to the new context-based architecture by:
1. Refactoring `main.py` CLI to use `DeploymentContext`
2. Removing all global state dependencies from utility and AWS files
3. Updating REST API endpoints to use the new pattern
4. Deleting deprecated modules

### Impact
- Clean, testable architecture with explicit dependencies
- No more global mutable state
- Single source of truth for configuration and providers
- Removal of ~800 lines of deprecated code

---

## 2. Current State

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CURRENT ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  main.py (CLI)                                                        │
│      │                                                                │
│      ├──▶ globals.py (DEPRECATED)                                     │
│      │        ├── config, config_iot_devices, config_events          │
│      │        ├── CURRENT_PROJECT                                     │
│      │        └── initialize_all(), is_optimization_enabled()        │
│      │                                                                │
│      ├──▶ globals_aws.py (DEPRECATED)                                │
│      │        ├── aws_*_client (boto3 clients)                        │
│      │        └── naming functions (dispatcher_iam_role_name()...)   │
│      │                                                                │
│      └──▶ deployers/ (DEPRECATED wrappers)                           │
│               ├── core_deployer.py → providers/deployer.py           │
│               ├── iot_deployer.py → providers/iot_deployer.py        │
│               └── additional/event_action/init_values_deployer.py    │
│                                                                       │
│  ════════════════════════════════════════════════════════════════    │
│                                                                       │
│  NEW ARCHITECTURE (Running in Parallel):                              │
│                                                                       │
│      DeploymentContext                                                │
│           ├── ProjectConfig (from config_loader)                      │
│           └── providers: {aws: AWSProvider}                           │
│                               ├── clients (boto3)                     │
│                               └── naming (ResourceNaming)             │
│                                                                       │
│      providers/deployer.py                                            │
│           └── deploy_l1(context, provider) → strategy.deploy_l1()    │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Proposed Changes

### Component: CLI

#### [MODIFY] main.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\main.py`
- **Description:** Complete refactor to use DeploymentContext. Replace all globals/deployers imports with new pattern. Create context on-demand per command.

---

### Component: Core

#### [NEW] config_loader.py (if incomplete)
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\core\config_loader.py`
- **Description:** Standalone function to load ProjectConfig from disk

---

### Component: Utilities

#### [MODIFY] util.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\util.py`
- **Description:** Remove lazy globals imports, require `project_path` parameter

#### [MODIFY] sanity_checker.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\sanity_checker.py`
- **Description:** Remove lazy globals imports, require `config` parameter

#### [MODIFY] validator.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\validator.py`
- **Description:** Add `project_path` parameter to functions that need it

#### [MODIFY] file_manager.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\file_manager.py`
- **Description:** Add `project_path` parameter, remove module-level globals import

#### [MODIFY] info.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\info.py`
- **Description:** Accept context/config parameter instead of globals.config_iot_devices

---

### Component: AWS Modules

#### [MODIFY] aws/iot_deployer_aws.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\aws\iot_deployer_aws.py`
- **Description:** Add provider parameter to all functions, remove module-level globals

#### [MODIFY] aws/info_aws.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\aws\info_aws.py`
- **Description:** Add provider parameter to all check_* functions

#### [MODIFY] aws/util_aws.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\aws\util_aws.py`
- **Description:** Remove globals, pass clients explicitly

#### [MODIFY] aws/init_values_deployer_aws.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\aws\init_values_deployer_aws.py`
- **Description:** Remove legacy fallback code

#### [MODIFY] aws/lambda_manager.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\aws\lambda_manager.py`
- **Description:** Remove legacy fallback code

#### [MODIFY] aws/event_action_deployer_aws.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\aws\event_action_deployer_aws.py`
- **Description:** Remove legacy fallback code

#### [MODIFY] aws/additional_deployer_aws.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\aws\additional_deployer_aws.py`
- **Description:** Remove legacy fallback code

---

### Component: REST API

#### [MODIFY] api/dependencies.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\api\dependencies.py`
- **Description:** Remove globals import, use new context pattern

#### [MODIFY] api/projects.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\api\projects.py`
- **Description:** Remove globals/globals_aws imports

#### [MODIFY] api/info.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\api\info.py`
- **Description:** Remove globals import

#### [MODIFY] api/validation.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\api\validation.py`
- **Description:** Remove globals import

#### [MODIFY] api/simulator.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\api\simulator.py`
- **Description:** Remove globals import

#### [MODIFY] api/credentials_checker.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\api\credentials_checker.py`
- **Description:** Remove lazy globals import

---

### Component: Cleanup

#### [DELETE] globals.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\globals.py`

#### [DELETE] aws/globals_aws.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\aws\globals_aws.py`

#### [DELETE] deployers/core_deployer.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\deployers\core_deployer.py`

#### [DELETE] deployers/iot_deployer.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\deployers\iot_deployer.py`

#### [DELETE] deployers/additional_deployer.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\deployers\additional_deployer.py`

#### [DELETE] deployers/event_action_deployer.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\deployers\event_action_deployer.py`

#### [DELETE] deployers/init_values_deployer.py
- **Path:** `d:\Git\master-thesis\3-cloud-deployer\src\deployers\init_values_deployer.py`

---

## 4. Implementation Phases

### Phase 1: Config Loader Completion
| Step | File | Action |
|------|------|--------|
| 1.1 | `src/core/config_loader.py` | Verify/complete `load_project_config()` function |
| 1.2 | Tests | Verify config_loader tests pass |

### Phase 2: CLI Refactor (main.py)
| Step | File | Action |
|------|------|--------|
| 2.1 | `src/main.py` | Create `create_context()` factory function |
| 2.2 | `src/main.py` | Replace globals.initialize_all() with config loading |
| 2.3 | `src/main.py` | Replace globals_aws with AWSProvider |
| 2.4 | `src/main.py` | Replace deployer imports with providers.deployer |
| 2.5 | `src/main.py` | Update all command handlers to pass context |
| 2.6 | Tests | Run full test suite |

### Phase 3: Utility Files
| Step | File | Action |
|------|------|--------|
| 3.1 | `src/util.py` | Remove lazy import fallbacks |
| 3.2 | `src/sanity_checker.py` | Remove lazy import fallbacks |
| 3.3 | `src/validator.py` | Add project_path params, remove module import |
| 3.4 | `src/file_manager.py` | Add project_path params, remove module import |
| 3.5 | `src/info.py` | Refactor to accept context/config |
| 3.6 | Tests | Run full test suite |

### Phase 4: AWS Modules
| Step | File | Action |
|------|------|--------|
| 4.1 | `src/aws/util_aws.py` | Remove globals, pass clients |
| 4.2 | `src/aws/info_aws.py` | Add provider to all functions |
| 4.3 | `src/aws/iot_deployer_aws.py` | Full refactor to require provider |
| 4.4 | `src/aws/*_deployer_aws.py` | Remove legacy fallbacks (4 files) |
| 4.5 | Tests | Run full test suite |

### Phase 5: REST API
| Step | File | Action |
|------|------|--------|
| 5.1 | `api/dependencies.py` | Refactor globals usage |
| 5.2 | `api/projects.py` | Remove globals/globals_aws |
| 5.3 | `api/info.py` | Remove globals |
| 5.4 | `api/validation.py` | Remove globals |
| 5.5 | `api/simulator.py` | Remove globals |
| 5.6 | `api/credentials_checker.py` | Remove lazy globals |
| 5.7 | Tests | Run full test suite including API tests |

### Phase 6: Delete Legacy Files
| Step | File | Action |
|------|------|--------|
| 6.1 | Verify | Grep for any remaining imports |
| 6.2 | `src/globals.py` | DELETE |
| 6.3 | `src/aws/globals_aws.py` | DELETE |
| 6.4 | `src/deployers/*.py` | DELETE (5 files) |
| 6.5 | `src/aws/deployer_layers/` | DELETE directory |
| 6.6 | Tests | Final test suite run |

---

## 5. Verification Checklist

- [ ] All 241+ tests pass inside Docker
- [ ] No remaining `import globals` in src/ (verified with grep)
- [ ] No remaining `import aws.globals_aws` in src/ (verified with grep)
- [ ] No remaining `from deployers` imports (verified with grep)
- [ ] CLI `help` command works
- [ ] CLI `deploy aws` smoke test works (if AWS configured)
- [ ] REST API `/projects` endpoint works
- [ ] IoT Simulator still functional (has separate globals)

**Test Command:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v
```

**Import Verification:**
```bash
docker exec master-thesis-3cloud-deployer-1 grep -r "import globals" /app/src --include="*.py"
```

---

## 6. Design Decisions

### D1: Context Factory Function
**Decision:** Create a `create_context(project_name, provider)` function in main.py rather than modifying DeploymentContext class.

**Reasoning:** Keeps DeploymentContext pure and testable. Factory encapsulates the loading/initialization logic.

### D2: IoT Simulator Globals
**Decision:** Keep `iot_device_simulator/aws/globals.py` as a separate, standalone context.

**Reasoning:** The simulator runs as a separate subprocess with different configuration needs. It doesn't share state with the main application.

### D3: Incremental Testing
**Decision:** Run full test suite after each phase.

**Reasoning:** Catch regressions early. Each phase should leave the codebase in a working state.
