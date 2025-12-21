# Optimizer Documentation Update Plan

## Goal

Update Twin2Clouds optimizer documentation to reflect current codebase. Focus: design patterns (backend + frontend), UI guide (many new inputs), API reference (missing endpoints).

---

## Proposed Changes

### Component 1: Design Patterns Docs (Backend)

The documented Builder/Strategy patterns are deprecated. Current v2 uses different patterns.

#### [MODIFY] [docs-patterns.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-patterns.html)

Rewrite as overview page linking to subpages.

#### [NEW] 6 Backend Pattern Subpages

| File | Pattern | Location |
|------|---------|----------|
| `docs-pattern-protocol.html` | Protocol | `components/base.py` |
| `docs-pattern-factory.html` | Factory | `fetch_data/factory.py` |
| `docs-pattern-component.html` | Component Calculator | `components/{aws,azure,gcp}/` |
| `docs-pattern-facade.html` | Facade | `layers/{aws,azure,gcp}_layers.py` |
| `docs-pattern-dataclass.html` | Dataclass | `layers/aws_layers.py` |
| `docs-pattern-formulas.html` | Pure Functions | `formulas/core_formulas.py` |

---

### Component 2: Frontend Patterns Documentation (NEW)

#### [NEW] [docs-pattern-frontend.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-pattern-frontend.html)

The frontend has a modular architecture with clear patterns:

**Registry Pattern** - Central config objects:
```javascript
// config/layers.js
const LAYERS = { L1: {...}, L2: {...}, L3_HOT: {...}, ... };

// config/providers.js  
const PROVIDERS = { AWS: {...}, AZURE: {...}, GCP: {...} };
const PROVIDER_STYLES = { aws: {...}, azure: {...}, gcp: {...} };

// config/services.js
// Service definitions per layer per provider
```

**Component Pattern** - Reusable UI generators:
- `layer-card.js` - Flip cards with cost comparison
- `comparison-table.js` - Provider comparison tables
- `warning-box.js` - Warning/info boxes
- `architecture-flowchart.js` - Architecture diagrams

**Orchestrator Pattern** - `ui-components.js`:
```javascript
function updateHtml(awsCosts, azureCosts, gcpCosts, ...) {
    // Coordinates all UI module updates after API response
}
```

**Utility Pattern** - Pure helper functions:
- `formatters.js` - Currency/number formatting
- `path-parser.js` - Cheapest path parsing

---

### Component 3: UI Guide (Complete Rewrite)

#### [MODIFY] [docs-ui-guide.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-ui-guide.html)

**Current docs show ~10 inputs. Actual UI has 20+ inputs:**

| Section | Inputs (Actual) |
|---------|-----------------|
| **L1/L2 Workload** | devices, interval, messageSize, numberOfDeviceTypes |
| **L2 Processing** | triggerNotificationWorkflow, orchestrationActionsPerMessage, useEventChecking, eventsPerMessage, returnFeedbackToDevice, numberOfEventActions |
| **L3 Storage** | hotStorageDurationInMonths (slider), coolStorageDurationInMonths (slider), archiveStorageDurationInMonths (slider) |
| **L4 Twin Mgmt** | needs3DModel (radio), entityCount, average3DModelSizeInMB, allowGcpSelfHostedL4 (disabled) |
| **L5 Visualization** | dashboardRefreshesPerHour, apiCallsPerDashboardRefresh, dashboardActiveHoursPerDay (slider), monthlyEditors, monthlyViewers, allowGcpSelfHostedL5 (disabled) |
| **Global** | currency |

**New features to document:**
- GCP L4/L5 checkboxes disabled with "Not Implemented" badge
- Preset buttons now have 22 parameters each
- Slider inputs with live value display
- Conditional visibility (entity inputs shown only when 3D model = Yes)

---

### Component 4: API Reference

#### [MODIFY] [docs-api-reference.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-api-reference.html)

**Missing endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/regions_age/aws` | AWS regions file age |
| GET | `/api/regions_age/azure` | Azure regions file age |
| GET | `/api/regions_age/gcp` | GCP regions file age |
| POST | `/api/fetch_regions/aws` | Fetch AWS regions |
| POST | `/api/fetch_regions/azure` | Fetch Azure regions |
| POST | `/api/fetch_regions/gcp` | Fetch GCP regions (5-10 min!) |

---

### Component 5: Pricing Schema Docs

#### Status: ✅ OK - No changes needed

Verified pricing JSON structure matches documentation.

---

## Verification Plan

1. **Code verification**: Compare all code examples to actual source files
2. **UI verification**: Test all inputs in live UI at `http://localhost:5003/ui`
3. **API verification**: Test all documented endpoints
4. **Link verification**: Check all internal doc links work
