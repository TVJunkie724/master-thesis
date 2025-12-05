# Refine Web UI Styling & Tooltips

## Goal
Enhance the Web UI (`index.html`) with visual tooltips (info icons), styled checkboxes, improved layout separation in Layer 2, and a better currency selector.

## User Review Required
> [!NOTE]
> I will replace standard `title` attributes with custom info icons that show tooltips on hover.

## Proposed Changes

### Web UI (`index.html`)
#### [MODIFY] [index.html](file:///d:/Git/master-thesis/2-twin2clouds/index.html)
- **Tooltips**: Remove `title` attributes from labels/inputs. Add `<span class="info-icon" data-tooltip="...">&#9432;</span>` next to each label.
- **Layer 2**: Insert `<hr class="sub-separator" />` between the Archive Storage slider and the Event Checking checkbox.
- **Currency**: Wrap the currency label and select in a `<div class="currency-container">` for better styling control.

### Styling (`css/styles.css`)
#### [MODIFY] [styles.css](file:///d:/Git/master-thesis/2-twin2clouds/css/styles.css)
- **Info Icons**:
    - Style `.info-icon` as a small, circular badge or simple text icon.
    - Implement tooltip visibility on hover using `::after` or `::before` pseudo-elements based on `data-tooltip`.
- **Checkboxes**:
    - Target `input[type="checkbox"]`.
    - Increase size (`transform: scale(1.3)`).
    - Set `accent-color` to match the theme (e.g., `#007bff`).
    - Ensure labels are bold (`.checkbox-group label`).
- **Separators**:
    - Style `.sub-separator` to be lighter/thinner than the main `<hr>`.
- **Currency**:
    - Style `.currency-container` to be more prominent.
    - Style `select#currency` with padding, border radius, and font size.

## Verification Plan
### Manual Verification
- Open `index.html`.
- Hover over info icons to see tooltips.
- Check checkbox appearance (size, color, bold labels).
- Verify visual separation in Layer 2.
- Verify currency dropdown styling.
