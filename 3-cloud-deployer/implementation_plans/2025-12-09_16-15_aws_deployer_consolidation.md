# AWS Legacy Code Cleanup Plan

## Goal
Fully consolidate all AWS functionality into `src/providers/aws/` by merging missing logic, moving Lambda functions, and deleting legacy files.

## User Review Required
> [!IMPORTANT]
> This plan involves moving `src/aws/lambda_functions` to `src/providers/aws/lambda_functions`. This requires updating `src/constants.py` and all consumers.

## Proposed Changes

### 1. Unified Info/Status Strategy (Merge & Extinguish)
- **Extend** `src/core/protocols.py` (DeployerStrategy) to include `info_l1`, `info_l2`, etc.
- **Extend** `src/providers/deployer.py` to include `info_l1(context, provider)`, etc.
- **Implement** `info_lX` methods in `AWSDeployerStrategy` (`src/providers/aws/deployer_strategy.py`).

### 2. Move Core Lambdas
- **Move** `src/aws/lambda_functions/` -> `src/providers/aws/lambda_functions/`.
- **Update** `src/constants.py`: Change `AWS_CORE_LAMBDA_DIR_NAME` to `src/providers/aws/lambda_functions`.

### 3. Layer 1: IoT & Init Values
- **Merge** `src/aws/init_values_deployer_aws.py` -> `src/providers/aws/layers/layer_1_iot.py`
- **Merge** `src/aws/info_aws.py` (L1 checks) -> `src/providers/aws/layers/layer_1_iot.py`
- **Update** `l1_adapter.py`.

### 4. Layer 2: Compute & Event Actions
- **Merge** `src/aws/event_action_deployer_aws.py` -> `src/providers/aws/layers/layer_2_compute.py`
- **Merge** `src/aws/info_aws.py` (L2 checks) -> `src/providers/aws/layers/layer_2_compute.py`
- **Update** `l2_adapter.py`.

### 5. Layer 3: Storage
- **Merge** `src/aws/info_aws.py` (L3 checks) -> `src/providers/aws/layers/layer_3_storage.py`
- **Update** `l3_adapter.py`.

### 6. Layer 4: TwinMaker & Hierarchy
- **Merge** `src/aws/additional_deployer_aws.py` -> `src/providers/aws/layers/layer_4_twinmaker.py`
- **Merge** `src/aws/info_aws.py` (L4 checks) -> `src/providers/aws/layers/layer_4_twinmaker.py`
- **Update** `l4_adapter.py`.

### 7. Layer 5: Grafana
- **Merge** `src/aws/info_aws.py` (L5 checks) -> `src/providers/aws/layers/layer_5_grafana.py`
- **Update** `l5_adapter.py`.

### 8. Utilities & Schemas
- **Move** `src/aws/api_lambda_schemas.py` -> `src/providers/aws/schemas.py`
- **Move** `src/aws/lambda_manager.py` -> `src/providers/aws/lambda_manager.py`
- **Move** `src/aws/util_aws.py` -> `src/providers/aws/util.py`

### 9. Documentation
- **Update** `docs/docs-aws-deployment.html` (and others) to reflect new source paths if mentioned.
- **Update** `README.md` if it references `src/aws`.

### 10. Delete Legacy Files
- `src/aws/*.py`
- `src/aws/__init__.py`
- `src/aws/lambda_functions/` (after move)

## Implementation Phases
| Phase | Components | Action |
|-------|------------|--------|
| 1 | Protocols & Core | Add `info` to `DeployerStrategy` and `providers/deployer.py` |
| 2 | Move Lambdas | Move directory + Update `src/constants.py` |
| 3 | Layer 1 (IoT) | Merge Init + Info -> `layer_1_iot.py` |
| 4 | Layer 2 (Compute) | Merge Actions + Info -> `layer_2_compute.py` |
| 5 | Layers 3-5 | Merge Info/Hierarchy logic |
| 6 | Utils/Schemas | Move to `src/providers/aws/` and update imports |
| 7 | Consumers | Refactor `src/info.py` and `src/api/*.py` |
| 8 | Tests & Docs | Update tests for path changes; Update documentation |
| 9 | Cleanup | Delete `src/aws/` |

## Verification
- Run `pytest /app/tests` (including `test_aws_event_actions.py`).
- Manual check of `docs/docs-aws-deployment.html`.
- Verification of imports via grep.
