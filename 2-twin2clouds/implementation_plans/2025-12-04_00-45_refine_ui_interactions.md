# Refine UI Interactions & Result Styling

## Goal
Enhance the Web UI by implementing persistent highlighting for selected presets (cleared on manual input), moving the currency selector, and restoring the "flip card" result visualization with provider-specific color coding.

## User Review Required
> [!NOTE]
> I will move the Currency selector to be below the "Calculate Cost" button as requested.

## Proposed Changes

### Web UI (`index.html`)
#### [MODIFY] [index.html](file:///d:/Git/master-thesis/2-twin2clouds/index.html)
- **Currency Selector**: Move from top to below the "Calculate Cost" button.
- **Result Section**: Add a distinct separator or container style to visually separate results from the calculation button.

### JavaScript (`js/calculation/ui.js`)
#### [MODIFY] [ui.js](file:///d:/Git/master-thesis/2-twin2clouds/js/calculation/ui.js)
- **Preset Highlighting**:
    - Update `fillScenario` to add a `.active` or `.btn-primary` class to the clicked button and remove it from others.
    - Add event listeners to all input fields to detect manual changes and remove the highlight from all preset buttons.

### API Client (`js/api-client.js`)
#### [MODIFY] [api-client.js](file:///d:/Git/master-thesis/2-twin2clouds/js/api-client.js)
- **Result Generation**:
    - **Path**: Render path segments as badges (`.badge`) with provider-specific colors.
    - **Cards**: Apply provider-specific border/header colors to the result cards based on the cheapest provider for that layer.
    - **Flip Cards**: Ensure the flip interaction is preserved and works with the new coloring.

### Styling (`css/styles.css`)
#### [MODIFY] [styles.css](file:///d:/Git/master-thesis/2-twin2clouds/css/styles.css)
- **Provider Colors**: Define classes for AWS (Warning/Orange), Azure (Primary/Blue), and GCP (Success/Green) to match the overview.
- **Badges**: Style path badges to look like distinct chips.
- **Separation**: Add styles for the result section separator.

## Verification Plan
### Manual Verification
- **Preset Highlighting**: Click a preset -> button highlights. Change an input -> highlight disappears.
- **Currency Placement**: Verify it's below the button.
- **Result Styling**: Run calculation. Verify path badges are colored. Verify cards are colored by provider. Verify flip animation works.
