# Azure Layer Implementation Handoff

## Current Status

**Completed Layers:**
- ✅ Setup Layer (Resource Group, Managed Identity, Storage Account)
- ✅ L0 Glue Layer (Multi-cloud receiver functions)
- ✅ L1 IoT Layer (IoT Hub, Event Grid, Dispatcher, Connector, IoT Devices)

**Remaining Layers:**
- ❌ L2 Compute (Azure Functions for data processing)
- ❌ L3 Storage (Cosmos DB, Blob Storage)
- ❌ L4 Digital Twins (Azure Digital Twins)
- ❌ L5 Visualization (Azure Managed Grafana)

## Implementation Status

| File | Status |
|------|--------|
| `src/providers/azure/layers/layer_setup_azure.py` | ✅ Complete with error handling |
| `src/providers/azure/layers/layer_0_glue.py` | ✅ Complete with error handling, zip deploy |
| `src/providers/azure/layers/layer_1_iot.py` | ✅ Complete with error handling, zip deploy |
| `src/providers/azure/deployer_strategy.py` | Has NotImplementedError stubs for L2-L5 |

## Key Files to Reference

1. **AI Guide**: `docs/ai-layer-implementation-guide.md` - MUST READ FIRST
2. **Development Guide**: `development_guide.md`
3. **AWS Reference Implementations**:
   - `src/providers/aws/layers/layer_2_compute.py`
   - `src/providers/aws/layers/layer_3_storage.py`
   - `src/providers/aws/layers/layer_4_twinmaker.py`
   - `src/providers/aws/layers/layer_5_grafana.py`
4. **Azure L1 Reference** (use as template):
   - `src/providers/azure/layers/layer_1_iot.py` - Best example of patterns
   - `src/providers/azure/layers/l1_adapter.py` - Adapter pattern

## Azure Functions Available

All Azure Functions are in `src/providers/azure/azure_functions/`:
- `default-processor/` - L2
- `persister/` - L2
- `processor_wrapper/` - L2
- `event-checker/` - L2
- `hot-to-cold-mover/` - L3
- `cold-to-archive-mover/` - L3
- `digital-twin-data-connector/` - L4
- `digital-twin-data-connector-last-entry/` - L4

## Lessons Learned (From This Session)

1. **Always deploy function code**: Creating a Function App is NOT enough - you MUST deploy the actual function code via Kudu zip deploy
2. **Error handling order**: Catch `ClientAuthenticationError` BEFORE `HttpResponseError` BEFORE `AzureError`
3. **Test mocks**: When adding `requests.post` calls, tests need `@patch('requests.post')` and `@patch('util.compile_azure_function')`
4. **Bundle L0 functions**: All L0 functions go into ONE Function App as a bundled zip
5. **Fail-fast validation**: Every function validates inputs at the top before SDK calls

## Test Patterns to Follow

- `tests/unit/azure_provider/test_azure_l1_iot.py` - Unit tests pattern
- `tests/integration/azure_provider/test_l0_glue_edge_cases.py` - Edge cases pattern

## Tests: 759 Passing

All existing tests pass. New layers MUST maintain test suite green.

---

## Startoff Prompt for New Agent

Copy this prompt to start the next session:

```
I need you to implement Azure L2-L5 deployer layers for my multi-cloud Digital Twin deployment system.

**CRITICAL**: Before doing ANYTHING, read these files IN ORDER:
1. `.agent/workflows/azure-layer-handoff.md` - Handoff from previous session with status
2. `docs/ai-layer-implementation-guide.md` - This is your implementation bible
3. `development_guide.md` - Project standards

**Context**:
- Azure Setup, L0, and L1 are COMPLETE (759 tests passing)
- L2-L5 have `NotImplementedError` stubs in `src/providers/azure/deployer_strategy.py`
- Use AWS implementations as reference (same layer structure)
- Azure Functions code already exists in `src/providers/azure/azure_functions/`

**Requirements**:
1. NO placeholders or TODOs - every function must be complete
2. Follow the create/destroy/check triplet pattern
3. Use comprehensive error handling (ClientAuthenticationError, HttpResponseError, AzureError)
4. Deploy function code via Kudu zip deploy (see L1 implementation)
5. Add extensive edge case tests mirroring AWS test patterns
6. All 759+ tests must pass after each layer

**Start with**: Azure L2 (Compute) layer implementation
- Study `src/providers/aws/layers/layer_2_compute.py` first
- Create `src/providers/azure/layers/layer_2_compute.py`
- Create `src/providers/azure/layers/l2_adapter.py`
- Update `deployer_strategy.py` to call the adapter

Ask me questions if you're unsure about any implementation detail rather than leaving gaps.
```
