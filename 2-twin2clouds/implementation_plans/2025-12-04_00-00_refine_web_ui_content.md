# Refine Web UI & Content

## Goal
Enhance the Web UI (`index.html`) with detailed descriptions, tooltips, and improved usability based on the `3-cloud-deployer` documentation and user feedback.

## User Review Required
> [!NOTE]
> I will be using the `3-cloud-deployer` documentation and code to infer the detailed descriptions and tooltip content.

## Proposed Changes

### Web UI (`index.html`)
#### [MODIFY] [index.html](file:///d:/Git/master-thesis/2-twin2clouds/index.html)
- **Collapsible Overview**: Wrap the "Architecture Overview" section in a `<details>`/`<summary>` block or implement a custom collapsible section using JS/CSS.
- **Detailed Descriptions**:
    - Expand the "Architecture Overview" text.
    - Expand the layer descriptions (L1-L5) with specific details from the deployer docs (e.g., mentioning specific services and their roles).
    - Add descriptions for the **Preset Buttons** explaining what scenario each represents.
- **Tooltips**:
    - Add `title` attributes or custom tooltip elements to all input fields (`devices`, `interval`, `useEventChecking`, etc.) explaining their impact on cost and architecture.
- **Verify `fillScenario`**: Double-check and ensure all `onclick` handlers are up-to-date (though preliminary check suggests they are).

### Styling (`css/styles.css`)
#### [MODIFY] [styles.css](file:///d:/Git/master-thesis/2-twin2clouds/css/styles.css)
- Add styles for the collapsible section (animation, icon rotation).
- Add styles for custom tooltips (if `title` attribute is insufficient).
- Add styles for preset descriptions.

### JavaScript (`js/calculation/ui.js`)
#### [MODIFY] [ui.js](file:///d:/Git/master-thesis/2-twin2clouds/js/calculation/ui.js)
- Add logic for the collapsible section if needed (though HTML5 `<details>` might suffice).

## Verification Plan
### Manual Verification
- Open `index.html` in the browser.
- Verify the "Architecture Overview" expands/collapses.
- Hover over inputs to verify tooltips appear and are informative.
- Read the new descriptions for clarity and accuracy.
- Click preset buttons and verify all fields are populated correctly.
