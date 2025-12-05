# Update Documentation

## Goal Description
Update the project documentation to match the current state of the codebase, including recent refactoring, API changes, calculation logic enhancements, and the findings from the high L3 cost investigation.

## Proposed Changes

### 1. API Reference & Endpoint Config
#### [MODIFY] [rest_api.py](file:///d:/Git/master-thesis/2-twin2clouds/rest_api.py)
- **Change Mount Point:** Remount the static docs directory from `/docs` to `/documentation` to avoid conflict with Swagger UI (which uses `/docs` by default).
- Remove redundant individual endpoints (`/documentation/overview`, etc.) in favor of serving the static directory directly.

#### [MODIFY] [docs-api-reference.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-api-reference.html)
- Update the `/api/calculate` endpoint description.
- Ensure all internal links are **relative** or point to the new `/documentation/` prefix.

### 2. Architecture & Logic
#### [MODIFY] [docs-architecture.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-architecture.html)
- **Clarify Dependency:** Explicitly explain that "Global L2+L3 Optimization" determines the *Data Gravity Anchor*, which is then used as the fixed starting point for the "Full Path Storage Optimization".
- Add section on **"Global L2+L3 Optimization (Hot Path)"**.
- Add section on **"Full Path Storage Optimization"**.
- Source material: `docs/optimization_logic_v2.md`.

### 3. Pricing Pages (AWS, Azure, GCP)
#### [MODIFY] [docs-aws-pricing.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-aws-pricing.html)
#### [MODIFY] [docs-azure-pricing.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-azure-pricing.html)
#### [MODIFY] [docs-google-pricing.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-google-pricing.html)
- Add a **"High Volume L3 Cost"** note/alert section derived from `docs/high_l3_cost_investigation.md`.
- Explain why costs might seem "incorrectly high" or "incorrectly low" (before fix) for Preset 3, and the architectural reality of using Standard tier serverless for billions of events.

### 4. UI Guide
#### [MODIFY] [docs-ui-guide.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-ui-guide.html)
- **Primary Focus:** This page will contain the *main* documentation for the "Optimization Notes" feature.
- Explain **how to read** the Optimization Note tables (what "Trans" means, why paths are shown).
- Add descriptions of the new UI features:
    - **Row Highlighting:** Green highlighting for selected providers.
    - **Detailed Cost Breakdown:** The new "Base vs Glue vs Transfer" breakdown tables.
- Source material: `docs/calculation_logic_and_changes.md`.

### 5. Calculation Logic
#### [MODIFY] [docs-calculation-logic.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-calculation-logic.html)
- Focus on the **theoretical reasoning** (Transfer Cost vs Tier Change).
- **Add L4 Glue Code Section:** Explain that if Layer 4 (Twin Management) provider differs from Layer 3 (Data Processing), "Glue Code" (Function + API Gateway) costs are added to bridge the gap.
- Reference the UI Guide for the visual representation ("Optimization Notes").
- Source material: `docs/calculation_logic_and_changes.md`.

## Verification Plan

### Manual Verification
1.  **Serve Documentation:** Open the HTML files in a browser (or use a simple server).
2.  **Review Content:** Check that the new sections appear correctly and formatted well.
3.  **Check Links:** Ensure internal links between docs are working (e.g., clicking "Formula Documentation" from Overview goes to the right relative path).
