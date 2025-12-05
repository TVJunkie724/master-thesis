# Enhance Result Card Information

## Goal
Update the result cards in the Web UI to display comprehensive service information, including "glue code" (connector services) when cross-cloud architectures are selected, and optional services (e.g., EventBridge, Step Functions) based on user configuration.

## User Review Required
> [!NOTE]
> I will infer the usage of "Glue Code" (Connectors, API Gateways) by comparing the selected providers in the optimal path (e.g., if L1 is AWS and L2 is Azure, glue code is implied).

## Proposed Changes

### API Client (`js/api-client.js`)
#### [MODIFY] [api-client.js](file:///d:/Git/master-thesis/2-twin2clouds/js/api-client.js)
- **`calculateCheapestCostsFromUI`**: Pass `params` to `updateHtml`.
- **`updateHtml`**: Accept `params`. Parse `cheapestPath` to identify the selected provider for each layer (L1, L2 Hot, L3, L4, L5).
- **`generateResultHTML`**: Pass `params` and `selectedProviders` to `generateLayerCard`.
- **`generateLayerCard`**:
    - Update signature to accept `params` and `selectedProviders`.
    - Implement logic to generate a list of **Specific Services** for each provider based on the layer and `params`:
        - **L1**: IoT Core/Hub + (Connector Function if L1 != L2 Hot).
        - **L2**: DynamoDB/Cosmos + (Ingestion Function if L1 != L2 Hot).
        - **L3**: Lambda/Functions + (Event Bus if `useEventChecking`) + (Orchestrator if `triggerNotificationWorkflow`) + (API Gateway/Reader if L3 != L4/L5).
    - Update the "Back" of the card to list these services explicitly.
    - Add a visual indicator (e.g., badge) on the front if Glue Code is active for that layer.

## Verification Plan
### Manual Verification
- **Glue Code**:
    - Force a cross-cloud scenario (e.g., via presets or manual inputs that favor different providers).
    - Verify "Connector Function" / "Ingestion Function" appears in L1/L2 cards.
    - Verify "API Gateway" appears in L3 if L3 != L5.
- **Optional Services**:
    - Toggle "Enable Event Checking" -> Verify EventBridge/Event Grid appears in L3.
    - Toggle "Trigger Notification Workflow" -> Verify Step Functions/Logic Apps appears in L3.
