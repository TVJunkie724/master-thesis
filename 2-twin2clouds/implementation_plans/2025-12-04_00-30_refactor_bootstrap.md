# Refactor UI to Bootstrap

## Goal
Migrate the existing custom-styled Web UI (`index.html`) to use **Bootstrap 5**. This will reduce custom CSS, improve responsiveness, and provide a standardized look and feel.

## User Review Required
> [!NOTE]
> I will be replacing the custom collapsible section with a **Bootstrap Accordion** and custom tooltips with **Bootstrap Tooltips**.

## Proposed Changes

### Web UI (`index.html`)
#### [MODIFY] [index.html](file:///d:/Git/master-thesis/2-twin2clouds/index.html)
- **Include Bootstrap**: Add CDN links for Bootstrap 5 CSS, Bootstrap Icons, and Bootstrap JS Bundle.
- **Layout**: Use `.container`, `.row`, and `.col-*` for grid layout.
- **Components**:
    - **Header**: Use `.text-center`, `.py-5`.
    - **Architecture Overview**: Replace `<details>` with **Bootstrap Accordion**.
    - **Preset Buttons**: Use `.card` deck or grid with `.btn-outline-primary`.
    - **Forms**: Use `.form-label`, `.form-control`, `.form-select`, `.form-range`, `.form-check`.
    - **Tooltips**: Use Bootstrap Tooltips (initialized via JS) attached to Bootstrap Icons (`<i class="bi bi-info-circle"></i>`).
    - **Currency**: Use a `.input-group` or styled `.form-select`.
    - **Buttons**: Use `.btn`, `.btn-primary`, `.btn-lg`.

### Styling (`css/styles.css`)
#### [MODIFY] [styles.css](file:///d:/Git/master-thesis/2-twin2clouds/css/styles.css)
- **Cleanup**: Remove significant portions of custom CSS (container, forms, buttons, slider styling, custom tooltip logic).
- **Retain**: Keep custom tweaks that Bootstrap doesn't cover (e.g., specific diagram sizing if needed, or custom colors if not using default theme).

### JavaScript (`js/calculation/ui.js`)
#### [MODIFY] [ui.js](file:///d:/Git/master-thesis/2-twin2clouds/js/calculation/ui.js)
- **Tooltip Initialization**: Add code to initialize Bootstrap tooltips.
- **Slider Logic**: Ensure `updateSliderStyle` still works or is adapted to Bootstrap's range input (Bootstrap range inputs are styled by default, so custom gradient logic might be removable or need adjustment).

## Verification Plan
### Manual Verification
- Open `index.html`.
- Verify responsive layout.
- Check Accordion functionality.
- Check Tooltip functionality (hover).
- Verify Form controls look correct.
- Verify "Calculate Cost" button works.
