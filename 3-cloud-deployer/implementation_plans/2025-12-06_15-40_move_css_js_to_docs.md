# Move CSS and JS to docs/ folder

**Date:** 2025-12-06  
**Project:** 3-cloud-deployer

## Goal Description
To verify and execute the consolidation of static assets (`css`, `js`) into the `docs/` directory, updating all HTML references to reflect the new relative paths.

## User Review Required
> [!NOTE]
> This changes the relative paths in the documentation. If any external tools link to these assets directly (unlikely), they will need updating.

## Proposed Changes

### [MOVE] Directory Structure
*   Move `d:\Git\master-thesis\3-cloud-deployer\css` -> `d:\Git\master-thesis\3-cloud-deployer\docs\css`
*   Move `d:\Git\master-thesis\3-cloud-deployer\js` -> `d:\Git\master-thesis\3-cloud-deployer\docs\js`
*   Move `d:\Git\master-thesis\3-cloud-deployer\references` -> `d:\Git\master-thesis\3-cloud-deployer\docs\references`

### [MODIFY] rest_api.py
*   Remove explicit mounts for `/css`, `/js`, `/references` (they are now served via `/documentation`).
*   Update `favicon.ico` path to `docs/references/favicon.ico`.

### [MODIFY] Documentation Files
Update all `.html` files in `docs/` to replace:
*   `../css/` -> `css/`
*   `../js/` -> `js/`
*   `../references/` -> `references/`

**Affected Files:**
*   `docs-api-reference.html`
*   `docs-architecture.html`
*   `docs-aws-deployment.html`
*   `docs-azure-deployment.html`
*   `docs-cli-reference.html`
*   `docs-configuration.html`
*   `docs-gcp-deployment.html`
*   `docs-nav.html`
*   `docs-overview.html`
*   `docs-setup-usage.html`
*   `docs-testing.html`
*   `docs-twin2clouds-integration.html`

## Verification Plan
*   **Manual Check:** Open `docs/docs-overview.html` and verify the links are correct.
*   **Visual Check:** Ensure no 404s for styles/scripts.
