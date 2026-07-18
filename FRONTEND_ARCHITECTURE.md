# Flutter Frontend Architecture (v4)

## Current Implementation Boundary

This document contains the original design rationale as well as current
architecture constraints. Where historical examples or estimates below differ
from the implemented system, the current code, `docs-site/`, and reviewed
implementation plans are authoritative.

- Flutter calls only the Management API. Optimizer and Deployer ports are
  internal/diagnostic boundaries.
- Riverpod owns runtime mode, authentication, and `ManagementApi` composition.
  Feature BLoCs own complex workflows such as configuration and deployment.
- Web, macOS, Windows, and Linux are all mandatory supported targets. Android,
  iOS, and Fuchsia are unsupported.
- Operation logs use Management API SSE. A transport failure becomes a bounded
  reconnect/error state; it does not authorize a direct downstream call.

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────┐
│  Flutter App (Web + Desktop)                                      │
└───────────────────────┬───────────────────────────────────────────┘
                        │ HTTP + SSE
                        ▼
┌───────────────────────────────────────────────────────────────────┐
│  Management API (FastAPI)  Port 5005                              │
│  • User auth, sessions, JWT                                       │
│  • Digital Twin CRUD + state machine                              │
│  • File versioning (DB storage)                                   │
│  • SSE log streaming                                              │
│  └──────────┬────────────────────────┬────────────────────────────┘
│             │ REST API calls         │ REST API calls             │
│             ▼                        ▼                            │
│  ┌─────────────────┐      ┌─────────────────┐    ┌──────────────┐ │
│  │ Optimizer :5003 │      │ Deployer :5004  │    │ SQLite DB    │ │
│  │ (unchanged)     │      │ (unchanged)     │    │ (source of   │ │
│  │                 │      │ ← file upload   │    │  truth)      │ │
│  └─────────────────┘      └─────────────────┘    └──────────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

**Key principle:** DB stores all config/file versions → Management API uploads to Deployer **via its REST API** → Deployer validates and writes files.

---

## Key Design Decisions

### 1. Real-Time Logs: SSE (Server-Sent Events)

| Option | Pros | Cons | Choice |
|--------|------|------|--------|
| **WebSocket** | Bidirectional, low latency | Complex setup, connection management | ❌ Overkill |
| **Polling** | Simple, no special server code | Wastes bandwidth, 2-5s delay | ❌ Poor UX |
| **SSE** | One-way streaming, native HTTP, bounded reconnect through the owning BLoC | Unidirectional only | ✅ **Selected** |

**Why SSE?** Deployment logs are **one-way** (server → client). The current
`SseService` uses the tracked `http` package on Flutter Web and desktop; the
owning feature BLoC controls reconnect and error behavior.

```python
# FastAPI SSE endpoint (simple!)
@app.get("/stream/deploy/{twin_id}")
async def stream_deploy(twin_id: str):
    async def event_generator():
        for log_line in deploy_with_progress(twin_id):
            yield f"data: {log_line}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

### 2. Why SQLite over NoSQL?

| Aspect | SQLite | NoSQL (MongoDB) |
|--------|--------|-----------------|
| **Relationships** | ✅ Native FK (user→twins→versions) | ❌ Manual references |
| **Deployment** | ✅ Zero config, single file | ❌ Separate container |
| **Docker complexity** | ✅ None | ❌ +1 service, volumes |
| **Transaction safety** | ✅ ACID for file versioning | ⚠️ Eventually consistent |
| **Thesis scope** | ✅ Perfect | ❌ Overkill |
| **Production migration** | ✅ Easy → PostgreSQL | ⚠️ Different paradigm |

**Bottom line:** SQLite is the right choice for structured relational data (users, twins, versions, deployments). NoSQL shines for unstructured or massively scalable data, which isn't this use case.

---

### 3. User Authentication (Extensible OAuth)

#### Plugin-Based Auth Design

```python
# auth/providers/base.py
class OAuthProvider(ABC):
    @abstractmethod
    def get_authorize_url(self) -> str: ...
    
    @abstractmethod
    async def handle_callback(self, code: str) -> UserInfo: ...

# auth/providers/google.py
class GoogleOAuth(OAuthProvider):
    def get_authorize_url(self):
        return f"https://accounts.google.com/o/oauth2/auth?client_id={...}"

# auth/providers/microsoft.py (future)
class MicrosoftOAuth(OAuthProvider):
    def get_authorize_url(self):
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?..."
```

#### Extensible Endpoints

```python
# Single entry point, provider is dynamic
@app.get("/auth/{provider}/login")
async def oauth_login(provider: str):
    oauth = get_provider(provider)  # "google", "microsoft", etc.
    return RedirectResponse(oauth.get_authorize_url())

@app.get("/auth/{provider}/callback")
async def oauth_callback(provider: str, code: str):
    oauth = get_provider(provider)
    user_info = await oauth.handle_callback(code)
    # Create/find user, issue JWT
    ...
```

---

### 4. Flutter Tech Stack Explained

All of these are **Flutter/Dart packages** (libraries):

| Package | What It Does |
|---------|--------------|
| **Riverpod** | Runtime mode, authentication, and API adapter composition. |
| **flutter_bloc** | Complex feature workflows and state transitions. |
| **dio** | Management API request/response client. |
| **http** | Streaming transport used by `SseService`. |
| **go_router** | URL-based navigation. Essential for web (browser back/forward). |
| **Material 3** | Google's design system (buttons, cards, etc.). Built into Flutter. |

---

### 5. File Versioning: DB as Truth, Files via Deployer API

```
┌─────────────────┐     Save Config      ┌─────────────────────┐
│  Flutter UI     │ ──────────────────►  │  Management API     │
│  (edit config)  │                      │                     │
└─────────────────┘                      │  1. Store in SQLite │
                                         │     (versioned)     │
                                         │                     │
                                         │  2. Call Deployer   │
                                         │     upload API      │
                                         └─────────┬───────────┘
                                                   │ REST call
                                         ┌─────────▼───────────┐
                                         │  Deployer API       │
                                         │  (validates + saves)│
                                         └─────────────────────┘
```

#### API Flow Example: Save Config

```python
@app.put("/twins/{twin_id}/config")
async def update_config(twin_id: str, config: dict, description: str = None):
    # 1. Get next version number
    latest = db.query(FileVersion).filter_by(
        twin_id=twin_id, file_path='config.json'
    ).order_by(FileVersion.version.desc()).first()
    next_version = (latest.version + 1) if latest else 1
    
    # 2. Store in database
    new_version = FileVersion(
        twin_id=twin_id,
        file_path='config.json',
        content=json.dumps(config),
        version=next_version,
        description=description
    )
    db.add(new_version)
    db.commit()
    
    # 3. Upload to Deployer via its REST API
    await deployer_client.upload_file(twin_id, 'config.json', config)
    
    return {"version": next_version}
```

---

## Digital Twin States

| State | Meaning | Transitions To |
|-------|---------|----------------|
| `draft` | In-progress setup, missing required files | `configured`, `inactive` |
| `configured` | All required files uploaded, ready to deploy | `deployed`, `draft`, `inactive` |
| `deployed` | Infrastructure live on cloud(s) | `destroyed`, `error`, `inactive` |
| `destroyed` | Infrastructure torn down cleanly | `configured`, `error`, `inactive` |
| `error` | Deployment or destroy operation failed | `configured`, `destroyed`, `inactive` |
| `inactive` | User soft-deleted, kept in DB for history | (terminal) |

> [!NOTE]
> **Why `inactive` instead of hard delete?** Cloud services (e.g., Azure resource groups, AWS S3 buckets) often have a **5-10 minute cooldown** before a resource with the same name can be recreated. Keeping the twin in `inactive` state allows the backend to check for naming conflicts if the user immediately creates a new twin with the same name.

> [!IMPORTANT]
> **Wizard Workflow & State Transitions:**
> 1. **Step 1 (Configuration) Filled** → State remains `draft`.
> 2. **Step 2 (Optimizer) Filled** → State remains `draft`.
> 3. **Step 3 (Deployer) Filled** → State transitions to `configured`.
> 
> The **Wizard** is responsible for getting the twin to the `configured` state (all files/configs ready).
> The **Dashboard/Overview** is responsible for the actual deployment action (`configured` → `deployed`).

```mermaid
graph TD
    Start((Start)) --> S1[Wizard Step 1:<br>Configuration]
    S1 -->|Save| Draft1[State: Draft<br>(Has Credentials)]
    Draft1 --> S2[Wizard Step 2:<br>Optimizer]
    S2 -->|Save| Draft2[State: Draft<br>(Has Cost Model)]
    Draft2 --> S3[Wizard Step 3:<br>Deployer Config]
    S3 -->|Finish| Configured[State: Configured]
    
    Configured -->|User clicks Deploy<br>on Dashboard| Deployed[State: Deployed]
    Deployed -->|User clicks Destroy| Destroyed[State: Destroyed]
    Destroyed -->|Reset| Configured
    
    Deployed -->|Error| Error[State: Error]
    Error -->|Retry| Configured
    
    subgraph Wizard
    S1
    S2
    S3
    end
```

```
          ┌─────────────────────────────────────────┐
          │                                         │
          ▼                                         │
       ┌──────┐    Wizard Step 3         ┌───────────┐      │
       │draft │ ──────────────►          │configured │      │
       └──┬───┘   (Deployer Config)      └─────┬─────┘      │
          │                                    │            │
          │                           User     │            │
          │                           Deploy   │            │
          │                           Action   ▼            │
          │                           ┌──────────┐          │
          │                           │ deployed │───────┤ destroy
          │                           └────┬─────┘       │
          │                                │             │
          │                    fail deploy │             │
          │                                ▼             │
          │                           ┌─────────┐        │
          │                ┌──────────│  error  │◄───────┤ fail destroy
          │                │          └─────────┘        │
          │                │ retry         │             │
          │                ▼               │             │
          │          ┌───────────┐         │             │
          │          │ configured│◄────────┘             │
          │          └───────────┘                       │
          │               ┌──────────────────────────────┘
          │               │ soft delete (any state)
          ▼               ▼
       ┌───────────────────────────────────────────┐
       │              inactive                     │
       │  (kept for naming conflict detection)     │
       └───────────────────────────────────────────┘
```

---

## Screens

### 1. Login Screen

- Google OAuth button (mocked initially, real implementation planned)
- Simple centered card layout
- Auto-redirect if already authenticated

---

### 2. Dashboard

```
┌─────────────────────────────────────────────────────────────────────┐
│  Twin2MultiCloud                                    [User Avatar ▼] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ Deployed    │  │ Est. Cost   │  │ Active      │  │ Errors     │ │
│  │     3       │  │ $142/month  │  │ Devices     │  │     0      │ │
│  │  twins      │  │             │  │    347      │  │            │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
│                                                                     │
│  My Digital Twins                              [+ New Twin]         │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Name           │ State      │ Provider(s)  │ Last Deploy │ Act ││
│  ├─────────────────────────────────────────────────────────────────┤│
│  │ Smart Home     │ 🟢deployed │ AWS+Azure    │ 2 days ago  │ 👁️✏️ ││
│  │ Factory Floor  │ 🟡configured│ GCP         │ -           │ 👁️✏️ ││
│  │ Office HVAC    │ 🔴error    │ AWS          │ 5h ago      │ 👁️✏️ ││
│  │ Test Project   │ ⚪draft    │ -            │ -           │ 👁️✏️ ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

**Stat blocks recommendations:**
- Deployed twins (count)
- Estimated monthly cost (sum from last optimizations)
- Active devices (sum across all deployed twins)
- Errors/warnings (twins in error state)
- Optional: Last deployment time, Total deployments

---

### 3. Digital Twin View (read-only)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Twin2MultiCloud                                    [User Avatar ▼] │  ← Header (same on all screens)
├─────────────────────────────────────────────────────────────────────┤
│  ← Back to Dashboard          Smart Home Digital Twin               │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  ACTIONS (not collapsible)                                      ││
│  │  [Edit Twin] [Deploy] [Destroy] [Check Status]                  ││
│  │                                                                 ││
│  │  Log Window (appears when action clicked):                      ││
│  │  ┌────────────────────────────────────────────────────────────┐ ││
│  │  │ > terraform init...                                        │ ││
│  │  │ > terraform plan...                                        │ ││
│  │  │ > terraform apply...                                       │ ││
│  │  └────────────────────────────────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ▼ Access & Links                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Grafana:  https://xxx.grafana.aws.com   Login: admin@email.com ││
│  │ IoT Hub:  https://xxx.azure.com                                ││
│  │ Console:  [AWS ↗] [Azure ↗] [GCP ↗]                            ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ▼ Deployment Status                                                │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  State: 🟢 Deployed (2 days ago)                                ││
│  │                                                                 ││
│  │  L1 Data Acquisition  ───► AWS IoT Core                        ││
│  │  L2 Processing        ───► AWS Lambda                          ││
│  │  L3 Storage           ───► Azure Cosmos (hot) + AWS S3 (cold)  ││
│  │  L4 Management        ───► Azure Digital Twins                 ││
│  │  L5 Visualization     ───► AWS Grafana                         ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ▼ Configuration Files                                              │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  ▸ config.json           v3  [View] [Download] [History ▼]     ││
│  │  ▸ config_grafana.json   v1  [View] [Download] [History ▼]     ││
│  │  ▸ payloads.json         v2  [View] [Download] [History ▼]     ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ▼ User Functions                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  ▸ processors/temp-sensor/     [View] [Download] [History ▼]   ││
│  │  ▸ processors/humidity-sensor/ [View] [Download] [History ▼]   ││
│  │  ▸ event-feedback/             [View] [Download] [History ▼]   ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ▼ Deployment History (TBD - keeping for now)                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Dec 23, 2024 14:30  SUCCESS  "Added humidity sensor"          ││
│  │  Dec 20, 2024 09:15  SUCCESS  "Initial deployment"             ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

**Sections:**
- **Header**: Twin2MultiCloud branding + user avatar (same on ALL screens)
- **Actions** (NOT collapsible): Edit, Deploy, Destroy, Check Status → opens log window
- **Access & Links** (▼): Grafana URL + login, cloud console links
- **Deployment Status** (▼): State badge + layer→provider mapping
- **Configuration Files** (▼): List with [View] [Download] [History ▼] actions
- **User Functions** (▼): Grouped by type (processors, event-feedback, etc.)
- **Deployment History** (▼): Timeline with status and description (TBD)

**[History ▼] dropdown**: Shows previous versions with description, allows rollback (UI details TBD)

---

### 4. Create/Edit Twin Wizard

> [!NOTE]
> This wizard is used for both **creating new twins** and **editing existing twins**. All steps support caching/draft saving.

#### Wizard Step Indicator

```
┌─────────────────────────────────────────────────────────────────────┐
│  Twin2MultiCloud                                    [User Avatar ▼] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Create New Digital Twin                                            │
│                                                                     │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐         │
│  │ ● Step 1      │───│ ○ Step 2      │───│ ○ Step 3      │         │
│  │ Configuration │   │ Optimizer     │   │ Deployer      │         │
│  └───────────────┘   └───────────────┘   └───────────────┘         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

#### Step 1: Overall Configuration

```
┌─────────────────────────────────────────────────────────────────────┐
│  Twin2MultiCloud                                    [User Avatar ▼] │
├─────────────────────────────────────────────────────────────────────┤
│  Step 1 of 3: Configuration               [● ─ ○ ─ ○]              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Digital Twin Name: [_________________________]                     │
│                                                                     │
│  Mode:  ○ Production   ● Debug (verbose logging)                    │
│                                                                     │
│  ─────────────────────────────────────────────────────────────────  │
│  ▼ AWS Credentials                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Access Key ID:     [_______________]    │ [Upload JSON] [Check]││
│  │  Secret Access Key: [_______________]    │                      ││
│  │  Region:            [us-east-1     ▼]    │                      ││
│  │                                                                 ││
│  │  Status: ✅ Credentials valid, all permissions OK               ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ▼ Azure Credentials                                                │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Subscription ID:   [_______________]    │ [Upload JSON] [Check]││
│  │  Client ID:         [_______________]    │                      ││
│  │  Client Secret:     [_______________]    │                      ││
│  │  Tenant ID:         [_______________]    │                      ││
│  │                                                                 ││
│  │  Status: ⚠️ Missing permission: Microsoft.DocumentDB/...        ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ▼ GCP Credentials                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Project ID:        [_______________]    │ [Upload JSON] [Check]││
│  │  Service Account:   (from JSON upload)   │                      ││
│  │                                                                 ││
│  │  Status: ❌ Not configured                                      ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ─────────────────────────────────────────────────────────────────  │
│                                          [Save Draft]  [Next Step →]│
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- Twin name + debug mode toggle
- Per-provider credential sections (collapsible)
- Dual input: manual fields (left) OR JSON upload (right)
- [Check] button calls Deployer's credential validation API
- Status shows validation result (disappears on credential change)
- [Save Draft] saves to DB, stays on page
- [Next Step] proceeds to Optimizer

> [!IMPORTANT]
> **Validation gating:** [Next Step] only enabled when:
> - Twin name is set
> - All credentials are valid (at least one provider configured and passing [Check])

---

#### Step 2: Optimizer

```
┌─────────────────────────────────────────────────────────────────────┐
│  Twin2MultiCloud                                    [User Avatar ▼] │
├─────────────────────────────────────────────────────────────────────┤
│  Step 2 of 3: Optimizer                   [● ─ ● ─ ○]              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ▼ Data Freshness (Section 1)                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Pricing Data:                                                  ││
│  │    AWS:   Last fetched 2 hours ago    ✅                        ││
│  │    Azure: Last fetched 3 days ago     ⚠️ [Refresh]             ││
│  │    GCP:   Last fetched 12 hours ago   ✅                        ││
│  │                                                                 ││
│  │  Region Data:                                                   ││
│  │    AWS:   Last fetched 15 days ago    ✅                        ││
│  │    Azure: Last fetched 45 days ago    ⚠️ [Refresh]             ││
│  │    GCP:   Last fetched 20 days ago    ✅                        ││
│  │                                                                 ││
│  │  (⚠️ = stale: pricing >1 day, regions >1 month)                 ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ▼ Cost Calculation (Section 2 - Optimizer UI)                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  ┌─────────────────────────────────────────────────────────────┐││
│  │  │  (Recreate Optimizer index.html UI here in Flutter)         │││
│  │  │  - Device count, message frequency, retention sliders       │││
│  │  │  - L2/L4/L5 advanced parameters                             │││
│  │  │  - Region/currency selection                                │││
│  │  │  - [Calculate] button                                       │││
│  │  │  - NO architecture overview (that's on View screen)         │││
│  │  └─────────────────────────────────────────────────────────────┘││
│  │                                                                 ││
│  │  RESULTS (after Calculate):                                     ││
│  │  ┌─────────────────────────────────────────────────────────────┐││
│  │  │  Cheapest Path: L1→AWS  L2→GCP  L3→Azure  L4→AWS  L5→AWS    │││
│  │  │  Estimated Cost: $142.50/month                              │││
│  │  │                                                             │││
│  │  │  [Recalculate with different inputs]                        │││
│  │  └─────────────────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ─────────────────────────────────────────────────────────────────  │
│                          [← Back]  [Save Draft]  [Next Step →]      │
└─────────────────────────────────────────────────────────────────────┘
```

**Features:**
- **Section 1**: Data freshness indicators
  - Pricing: stale if >1 day old → show [Refresh] button
  - Regions: stale if >1 month old → show [Refresh] button
  - Currency handled automatically by backend
- **Section 2**: Optimizer UI recreated (without architecture overview)
  - All input parameters from `index.html`
  - Calculate button calls Optimizer API
  - Results include: cheapest path, estimated cost, **provider cards** (like original), **detailed pricing tables per layer**
- **Navigation**: [Back] returns to Step 1 (inputs cached), [Save Draft], [Next Step]
- **No validation gating** on this step - but user must press [Calculate] at least once before [Next Step]

> [!WARNING]
> **Implementation complexity:** The original Optimizer `index.html` has significant JS logic for visibility toggling, conditional field display, and dynamic updates. Recreating this in Flutter requires careful analysis of `ui.js` / `api-client.js` to port all conditional behaviors.

> [!TIP]
> **On draft saving:** Use debounced auto-save (save after 2s of no input changes). This is better UX than save-on-every-keystroke (overkill) or save-only-on-button (user might lose work).

---

#### Step 3: Deployer Configuration

```
┌─────────────────────────────────────────────────────────────────────┐
│  Twin2MultiCloud                                    [User Avatar ▼] │
├─────────────────────────────────────────────────────────────────────┤
│  Step 3 of 3: Deployer Configuration      [● ─ ● ─ ●]              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Cheapest Path: L1→AWS  L2→GCP  L3→Azure/AWS/AWS  L4→AWS  L5→AWS   │
│                                                                     │
│  ┌─────────────────────────────┬───────────────────────────────────┐│
│  │ ARCHITECTURE VIEW (Left)   │ FILE EDITORS (Right)              ││
│  │                            │                                   ││
│  │ ┌────────────────────────┐ │ ▼ config.json *(use form)*        ││
│  │ │ L1: AWS IoT Core       │ │ ┌───────────────────────────────┐ ││
│  │ │ ├─ iot-dispatcher    ○ │ │ │ Twin Name: [Smart Home     ] │ ││
│  │ │ └─ (system managed)    │ │ │ Region:    [us-east-1     ▼] │ ││
│  │ └────────────────────────┘ │ │ Layer 1:   [AWS          ▼] │ ││
│  │                            │ │ ...                           │ ││
│  │ ┌────────────────────────┐ │ │ [Validate] Status: ✅ Valid   │ ││
│  │ │ L2: GCP Cloud Func     │ │ └───────────────────────────────┘ ││
│  │ │ ├─ 🟢 temp-sensor    ✓ │ │                                   ││
│  │ │ ├─ 🟡 humidity-sens  ? │ │ ▼ config_grafana.json             ││
│  │ │ └─ event-checker     ○ │ │ ┌───────────────────────────────┐ ││
│  │ └────────────────────────┘ │ │ Name: [file] [Upload] [Validate]│││
│  │                            │ │ ┌─────────────────────────────┐│││
│  │ ┌────────────────────────┐ │ │ │{                            ││││
│  │ │ L3: Storage            │ │ │ │  "admin_email": "..."       ││││
│  │ │ ├─ Hot: Azure Cosmos ○ │ │ │ │}                            ││││
│  │ │ ├─ Cold: AWS S3      ○ │ │ │ └─────────────────────────────┘│││
│  │ │ └─ Archive: AWS Glac ○ │ │ │ Status: ⚠️ Missing admin_email │││
│  │ └────────────────────────┘ │ │ [View History ▼]               │ ││
│  │                            │ └───────────────────────────────┘ ││
│  │ ┌────────────────────────┐ │                                   ││
│  │ │ L4: AWS TwinMaker      │ │ ▼ processors/temp-sensor/         ││
│  │ │ └─ (system managed)  ○ │ │ ┌───────────────────────────────┐ ││
│  │ └────────────────────────┘ │ │ [Upload] [Validate]            │ ││
│  │                            │ │ ┌─────────────────────────────┐ ││
│  │ ┌────────────────────────┐ │ │ │def process(event):         │ ││
│  │ │ L5: AWS Grafana        │ │ │ │    return event            │ ││
│  │ │ └─ (system managed)  ○ │ │ │ └─────────────────────────────┘ ││
│  │ └────────────────────────┘ │ │ Status: ✅ Valid                │ ││
│  │                            │ └───────────────────────────────┘ ││
│  │ LEGEND:                    │                                   ││
│  │ 🟢 = valid, filled         │ ▼ processors/humidity-sensor/     ││
│  │ 🟡 = needs attention       │ ...                               ││
│  │ ○  = system managed/grey   │                                   ││
│  └────────────────────────────┴───────────────────────────────────┘│
│                                                                     │
│  ─────────────────────────────────────────────────────────────────  │
│               [← Back]  [Save Draft]  [Finish Configuration →]      │
│                                                                     │
│  ⚠️ "Finish" only enabled when all user-editable files are valid    │
└─────────────────────────────────────────────────────────────────────┘
```

**Left Column - Architecture View (Dynamic Flowchart):**
- **Dynamic based on Optimizer output:** Shows all architecture components for selected providers
- **Flowchart visualizes data flow:** L1 → L2 → L3 → L4 → L5 with arrows
- **Glue/L0 functions shown as connectors** between layers (not a separate layer) in multi-cloud scenarios
- Reference: see `/docs/` provider deployment guides (AWS, Azure are up to date)
- **All components shown**, but un-editable ones are greyed out
- User-editable components: large blocks with status indicator
- System-managed components: small, greyed out
- Color coding: 🟢 valid, 🟡 needs attention, ○ system-managed/greyed

**Right Column - File Editors (Dynamic based on providers):**
- **Only shows files relevant to selected providers**
  - If L2=Azure: show Azure processor files, NOT AWS or GCP
  - If L3=AWS+Azure: show both storage config sections
- **config.json**: Form-based (not raw JSON editor) - has more fields than workspace version
- **config_grafana.json, payloads.json, etc.**: Upload + editor + validate
- **processors/**: Per-processor sections with upload/editor/validate (filtered by L2 provider)
- Each section: filename header, [Upload], [Validate], editor, status, [History ▼]

**Backend Integration:**
- Optimizer output → converted to deployer input format between Step 2 and Step 3
- Validation calls Deployer REST API
- [Finish] only enabled when ALL user-editable files pass validation

**After Finish:** Navigate to **Digital Twin View** (the overview screen)

---

### 5. Settings Screen

*To be discussed later*

---

## DB Schema (Updated)

```sql
-- Users table (for OAuth)
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    picture_url TEXT,
    google_id TEXT UNIQUE,
    created_at TIMESTAMP
);

-- Digital twins (projects)
CREATE TABLE digital_twins (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft',  -- draft/configured/deployed/destroyed/error/inactive
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE file_versions (
    id TEXT PRIMARY KEY,
    twin_id TEXT REFERENCES digital_twins(id),
    file_path TEXT NOT NULL,        -- e.g., "config.json", "processors/temp-sensor/process.py"
    content BLOB NOT NULL,
    version INTEGER NOT NULL,
    description TEXT,
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP,
    UNIQUE(twin_id, file_path, version)
);

CREATE TABLE deployments (
    id TEXT PRIMARY KEY,
    twin_id TEXT REFERENCES digital_twins(id),
    status TEXT,                    -- pending/running/success/failed
    description TEXT,               -- user note for this deployment
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    terraform_outputs JSON,
    logs TEXT
);
```

---

## Implementation Estimate

| Component | Days |
|-----------|------|
| Management API (FastAPI + SQLite + Deployer API integration) | 4 |
| Google OAuth + JWT | 2 |
| Flutter: Login + Dashboard | 2 |
| Flutter: Wizard Step 1 (Configuration + credentials) | 2 |
| Flutter: Wizard Step 2 (Optimizer UI recreation) | 3 |
| Flutter: Wizard Step 3 (Deployer config + architecture view) | 4 |
| Flutter: Twin View (actions, collapsible sections, log window) | 2 |
| SSE streaming for deploy/destroy logs | 1.5 |
| Polish & Desktop build | 1.5 |
| **Total** | **~22 days** |

> [!NOTE]
> Estimate increased due to wizard complexity. Can be reduced by simplifying Step 3 architecture view.

---

## Summary of Agreed Decisions

| Topic | Decision | Notes |
|-------|----------|-------|
| **Frontend** | Flutter (Web + Desktop) | Web, macOS, Windows, and Linux are mandatory |
| **Backend** | Python FastAPI Management API | Ports: 5003 Optimizer, 5004 Deployer, 5005 Management |
| **Database** | SQLite | Relational fits this use case; easy migration to PostgreSQL |
| **Real-time logs** | SSE (Server-Sent Events) | One-way, simpler than WebSocket |
| **Authentication** | Google OAuth + JWT | Extensible plugin pattern for future providers |
| **File management** | DB stores versions → uploads via Deployer REST API | Deployer validates; DB is source of truth |
| **Project terminology** | "Digital Twin" | Not "project" in UI |
| **Project states** | draft/configured/deployed/destroyed/error/inactive | Soft-delete via inactive (for naming conflict cooldown) |
| **File versioning** | All uploadable files, with optional description | Configs, processors, payloads, etc. |
| **UI Framework** | Material 3 | Confirmed |
| **Header** | Same on all screens | Twin2MultiCloud branding + user avatar |
| **Draft saving** | Debounced auto-save (2s delay) | Better UX than manual-only or per-keystroke |
| **Wizard reuse** | Same wizard for Create and Edit | All steps support caching |

---

## Open Items

- [x] ~~Edit screen design~~ → Wizard reused for edit
- [x] ~~Optimizer screen details~~ → Wizard Step 2 designed
- [ ] **Settings screen** - to be discussed
- [ ] **Deployment History section** - TBD if keeping
- [ ] **[History ▼] UI details** - dropdown vs modal vs page

---

## Critical Architectural Review

> [!NOTE]
> As a senior software architect, here is my critical assessment of this plan.

### ✅ Strengths

| Aspect | Assessment |
|--------|------------|
| **Separation of Concerns** | Clean: Flutter (UI) → Management API (orchestration) → Existing APIs (business logic). No tight coupling. |
| **Technology Choices** | SQLite, SSE, FastAPI are appropriate for thesis scope. Avoid over-engineering. |
| **Extensibility** | OAuth plugin pattern, provider-dynamic file editors, state machine - all support future growth. |
| **Existing API Reuse** | Optimizer and Deployer remain unchanged. Minimizes risk of breaking working systems. |
| **File Versioning** | DB-as-truth with Deployer-as-validator is elegant. Rollback is straightforward. |

### ⚠️ Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Step 2 JS Port Complexity** | HIGH | The Optimizer UI has ~500+ lines of conditional JS. **Mitigation:** Create a mapping doc of all UI behaviors before coding. Consider phased approach: basic inputs first, advanced toggles later. |
| **Step 3 Flowchart Rendering** | MEDIUM | Custom flowchart is complex. **Mitigation:** Use existing Flutter packages (`graphview`, `flutter_flow_chart`) rather than custom canvas drawing. Start with simple box-arrow layout. |
| **SSE in Flutter Web** | LOW | SSE is less battle-tested in Flutter Web than native. **Mitigation:** Use bounded reconnect and explicit error states through the Management API. Test early. |
| **Credential Storage Security** | MEDIUM | Storing cloud credentials in SQLite. **Mitigation:** Encrypt at rest using `sqlcipher` or store only in memory with secure keychain integration. Document threat model. |
| **22-day Estimate** | HIGH | Ambitious for thesis timeline. **Mitigation:** Identify MVP-cut scope (see below). |

### 🎯 Recommended MVP Cuts (if time-constrained)

If the 22-day estimate is too long, here's a prioritized cut list:

| Cut | Savings | Impact |
|-----|---------|--------|
| Simplify Step 3 flowchart → static image per scenario | 2 days | Acceptable for demo |
| Skip [History ▼] rollback UI → keep backend versioning | 1 day | Can add post-thesis |
| Mock OAuth → hardcoded test user | 1 day | Fine for local demo |
| ~~Desktop build → Web only~~ | 0 days | Rejected: all four supported targets are mandatory |
| Simplify Step 2 → fewer advanced toggles | 1 day | Core calculation still works |

**Minimum viable: ~17 days** with cuts above.

### 🔒 Security Considerations

1. **Credentials:** Never log or expose cloud credentials in UI. Mask in all views.
2. **JWT:** Use short expiry (1 hour) with refresh tokens.
3. **CORS:** Lock Management API to Flutter app origin only.
4. **Input Validation:** All file uploads must be validated by Deployer before storage.

### 📐 Missing Details (to address during implementation)

1. **Error handling UX:** What happens when Deployer validation fails? Toast? Inline error?
2. **Concurrent editing:** What if user opens same twin in two browser tabs?
3. **Terraform state:** Where is `.tfstate` stored? How does UI show current infra status?
4. **Offline support:** Not planned, but Flutter could cache. Decide: support or not?
5. **Testing strategy:** Unit tests for Management API, widget tests for Flutter, E2E how?

---

## Conclusion

This architecture is **sound and appropriate for thesis scope**. The main risks are:
1. Step 2 JS complexity (requires careful porting)
2. Timeline pressure (have MVP cuts ready)

The plan is ready for implementation.
