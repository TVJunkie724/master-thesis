# Implementation Plan: Synchronize API and CLI

**Date:** 2025-12-05
**Task:** Synchronize capabilities of `src/main.py` (CLI) and `rest_api.py` (API).

## Goal
Ensure that the CLI and API expose a consistent set of commands for deploying, destroying, and managing the Digital Twin environment.

## Analysis
- **Missing in CLI:** Granular destroy commands (`destroy_l1` to `destroy_l5`).
- **Missing in API:** `recreate_updated_events` and `lambda_invoke`.

## User Review Required
> [!NOTE]
> `info_config_credentials` is intentionally commented out in the API for security. This will remain unchanged.

## Proposed Changes

### [MODIFY] `src/main.py`
Add the following keys to the `deployment_commands` dictionary:
- `destroy_l1`: calls `core_deployer.destroy_l1`
- `destroy_l2`: calls `core_deployer.destroy_l2`
- `destroy_l3`: calls `core_deployer.destroy_l3_hot`, `cold`, `archive` (wrapper needed?) -> actually `core_deployer` has `destroy_l3_hot` etc. I should check if there is a `destroy_l3` wrapper.
    - *Correction*: `rest_api.py` calls `destroy_l3_hot`, `cold`, `archive` sequentially for `destroy_l3`. I should replicate this in `main.py` lambda.
- `destroy_l4`: calls `core_deployer.destroy_l4`
- `destroy_l5`: calls `core_deployer.destroy_l5`

### [MODIFY] `rest_api.py`
Add the following endpoints:
- `POST /recreate_updated_events`: calls `event_action_deployer.redeploy` and `core_deployer.redeploy_l2_event_checker`.
- `POST /lambda_invoke`:
    - Defines a `LambdaInvokeRequest` model (local_function_name, payload, sync).
    - Calls `lambda_manager.invoke_function`.

## Verification Plan

### Automated Tests
- None available for this specific CLI/API sync.

### Manual Verification
- **CLI**: Run `docker exec ... python src/main.py help` to see if it lists new commands (if we update help, or just try running them).
    - Try: `docker exec ... python src/main.py destroy_l1 aws` (expect success or specific error from deployer, not "unknown command").
- **API**: Check `http://localhost:8000/docs` (if accessible) or inspect code to ensure endpoints are registered.
