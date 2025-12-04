# Add Hover Effect to Service Links

## Goal Description
The user wants the service links on the back of the cards to be underlined when hovered, to make it clear they are clickable.

## Proposed Changes

### Styles (`css/styles.css`)
#### [MODIFY] [styles.css](file:///d:/Git/master-thesis/2-twin2clouds/css/styles.css)
- Add the following CSS rule:
```css
/* Hover effect for service links */
.hover-underline:hover {
  text-decoration: underline !important;
}
```

## Verification Plan

### Manual Verification
1.  **Visual Check**: Hover over any service link on the back of a card and verify it becomes underlined.
