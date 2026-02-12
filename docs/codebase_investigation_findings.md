# Codebase Investigation Findings

> Exhaustive file-by-file analysis of the Twin2MultiCloud ecosystem.
> Generated: 2026-02-11

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Project 1: The Brain (Optimizer)](#2-project-1-the-brain-optimizer)
3. [Project 2: The Muscle (Deployer)](#3-project-2-the-muscle-deployer)
4. [Project 3: The Orchestrator (Backend)](#4-project-3-the-orchestrator-backend)
5. [Project 4: The Orchestrator (Flutter UI)](#5-project-4-the-orchestrator-flutter-ui)
6. [Infrastructure & Deployment](#6-infrastructure--deployment)
7. [Cross-Cutting Concerns](#7-cross-cutting-concerns)
8. [Findings vs. Thesis Proposal](#8-findings-vs-thesis-proposal)
9. [Deprecated Project: Original Optimizer (JavaScript)](#9-deprecated-project-original-optimizer-javascript)
10. [Deprecated Project: Original Deployer (AWS-Only Python)](#10-deprecated-project-original-deployer-aws-only-python)
11. [Legacy → Current: Comparative Analysis](#11-legacy--current-comparative-analysis)

---

## 1. System Overview

The Twin2MultiCloud ecosystem consists of **4 projects** orchestrated via Docker Compose on a shared bridge network:

| Service | Project | Port | Role |
|---------|---------|------|------|
| `2twin2clouds` | `2-twin2clouds/` | 5003→8000 | Cost Optimizer (The Brain) |
| `3cloud-deployer` | `3-cloud-deployer/` | 5004→8000 | Infrastructure Deployer (The Muscle) |
| `management-api` | `twin2multicloud_backend/` | 5005 | Orchestrator Backend (New) |
| *Flutter app* | `twin2multicloud_flutter/` | 8080 | Frontend UI (New) |
| `thesis-latex` | `twin2multicloud-latex/` | — | LaTeX thesis (profile: `latex`) |

**Dependency chain**: `management-api` depends on both `2twin2clouds` and `3cloud-deployer`.

### Additional Root-Level Files
- `compose.yaml` — Docker Compose orchestration (4 services + LaTeX)
- `compose.debug.yaml` — Debug overrides
- `config.json`, `config_credentials.json` — Shared configuration mounted into containers
- `ONBOARDING.md` (7KB) — Agent onboarding guide
- `FRONTEND_ARCHITECTURE.md` (52KB) — Flutter architecture documentation
- `integration_vision.md` (7KB) — Integration design vision
- `1-AAS-server/` — Legacy Asset Administration Shell (unused)

---

## 2. Project 1: The Brain (Optimizer)

**Path**: `2-twin2clouds/`  
**Tech**: Python, FastAPI  
**Lines**: ~3000+ across backend  
**Purpose**: Calculates and compares multi-cloud Digital Twin deployment costs.

### 2.1 Architecture

```
2-twin2clouds/
├── rest_api.py                    # FastAPI app entry point (121 lines)
├── backend/
│   ├── config_loader.py           # JSON config loader with fallbacks
│   ├── credentials_checker.py     # AWS/Azure/GCP credential validation
│   ├── calculation_v2/            # Refactored calculation engine
│   │   ├── engine.py              # Core engine (501 lines vs. 909-line legacy)
│   │   ├── components/
│   │   │   ├── base.py            # ResourceCalculator Protocol + CalculatorBase
│   │   │   ├── types.py           # Enums: FormulaType, LayerType, Provider
│   │   │   ├── aws/               # 9 AWS service calculators
│   │   │   ├── azure/             # 9 Azure service calculators
│   │   │   └── gcp/               # 7 GCP service calculators
│   │   ├── formulas/
│   │   │   └── core_formulas.py   # 6 provider-independent cost formulas
│   │   └── layers/                # Per-provider layer calculations
│   ├── deprecated_calculation/
│   │   └── engine.py              # Original 909-line monolith (preserved)
│   └── fetch_data/
│       └── factory.py             # PriceFetcherFactory (Factory Pattern)
├── webui/                         # HTML/CSS/JS frontend
├── docs/                          # Static API documentation
└── api/                           # 6 FastAPI routers
    ├── calculation.py
    ├── pricing.py
    ├── regions.py
    ├── file_status.py
    ├── credentials.py
    └── validation.py
```

### 2.2 Key Engineering Facts

**Cost Formulas** (6 provider-independent mathematical models):
| Formula | Symbol | Description |
|---------|--------|-------------|
| Message-Based | CM | IoT Hub / Pub/Sub messaging |
| Execution-Based | CE | Lambda / Functions compute |
| Action-Based | CA | Step Functions / Logic Apps |
| Storage-Based | CS | S3 / Blob / GCS tiers |
| User-Based | CU | Cognito / AD B2C |
| Transfer | CTransfer | Cross-cloud data transfer |

**Design Patterns Used**:
- **Protocol Pattern** (`ResourceCalculator` Protocol for component calculators)
- **Factory Pattern** (`PriceFetcherFactory` for provider-specific price fetching)
- **Template Method** (`CalculatorBase` providing common utilities)
- **Strategy Pattern** (per-provider component implementations)

**Refactoring Evidence**:
- Deprecated engine: 909 lines, single monolithic function
- Refactored engine: 501 lines, component-based, type-safe
- Both versions preserved in codebase for comparison

**Type System**: Strongly-typed enums for `FormulaType` (6 values), `LayerType` (8 values including L3 hot/cool/archive), `Provider` (3), and per-provider component enums (AWS: 9, Azure: 9, GCP: 7).

---

## 3. Project 2: The Muscle (Deployer)

**Path**: `3-cloud-deployer/`  
**Tech**: Python, FastAPI, Terraform  
**Lines**: ~15,000+ (645 files total)  
**Purpose**: Deploys Digital Twin infrastructure across AWS, Azure, and GCP.

### 3.1 Architecture

```
3-cloud-deployer/
├── rest_api.py                        # FastAPI entry (96 lines, 10 routers)
├── src/
│   ├── core/
│   │   ├── protocols.py               # CloudProvider + DeployerStrategy protocols (402 lines)
│   │   ├── registry.py                # ProviderRegistry (165 lines, auto-registration)
│   │   ├── factory.py                 # Context factory (55 lines)
│   │   ├── context.py                 # DeploymentContext w/ dependency injection (295 lines)
│   │   ├── state.py                   # Global state management (61 lines)
│   │   └── exceptions.py
│   ├── providers/
│   │   ├── base.py                    # BaseProvider base class (132 lines)
│   │   ├── deployer.py                # Core deployment orchestration (284 lines)
│   │   ├── aws/
│   │   │   ├── provider.py            # AWSProvider (159 lines)
│   │   │   ├── naming.py              # AWSNaming (12KB)
│   │   │   ├── cleanup.py             # SDK cleanup (18KB)
│   │   │   ├── clients.py             # boto3 client factory
│   │   │   ├── layers/                # Per-layer deployment logic
│   │   │   └── lambda_functions/      # 18 Lambda function directories
│   │   ├── azure/
│   │   │   ├── provider.py            # AzureProvider (10KB)
│   │   │   ├── naming.py              # AzureNaming (11KB)
│   │   │   ├── cleanup.py             # SDK cleanup (21KB)
│   │   │   ├── azure_bundler.py       # ZIP bundler for Kudu deploy (26KB)
│   │   │   ├── layers/                # 6 layer implementation files
│   │   │   └── azure_functions/       # 26 function directories
│   │   └── gcp/
│   │       ├── provider.py            # GCPProvider (8KB)
│   │       ├── naming.py              # GCPNaming (7KB)
│   │       ├── cleanup.py             # SDK cleanup (18KB)
│   │       └── cloud_functions/       # 24 function directories
│   ├── terraform/                     # 31 Terraform files
│   │   ├── main.tf, variables.tf, outputs.tf
│   │   ├── aws_*.tf                   # AWS-specific resources
│   │   ├── azure_*.tf                 # Azure-specific resources
│   │   └── gcp_*.tf                   # GCP-specific resources
│   ├── terraform_runner.py            # Terraform CLI wrapper (466 lines, async streaming)
│   ├── tfvars_generator.py            # Config→Terraform translation (676 lines)
│   ├── function_registry.py           # Single source of truth for functions (448 lines)
│   ├── file_manager.py                # Project lifecycle (559 lines)
│   ├── iot_device_simulator/          # Per-provider IoT simulators
│   │   ├── aws/                       # MQTT via IoT Core
│   │   ├── azure/                     # Azure IoT Hub
│   │   └── google/                    # GCP Pub/Sub
│   ├── deployers/                     # Legacy deployer modules
│   │   ├── core_deployer.py           # Legacy AWS bridge (286 lines)
│   │   ├── iot_deployer.py
│   │   ├── event_action_deployer.py
│   │   └── additional_deployer.py
│   └── api/                           # 10 FastAPI routers
│       ├── projects.py, validation.py, deployment.py
│       ├── status.py, info.py, simulator.py
│       ├── credentials.py, functions.py
│       ├── logs.py, verify.py
│       └── credentials/              # Per-provider credential checkers
├── run_tests/
│   ├── e2e/                           # Azure-focused E2E test scripts
│   └── ...
└── tests/                             # Unit tests
```

### 3.2 Key Engineering Facts

**Hybrid Deployment Approach**:
- **Terraform** handles infrastructure provisioning (31 `.tf` files)
- **Python SDK** handles: code deployment (Lambda ZIP, Azure Kudu ZIP, GCP source upload), post-deployment operations (DTDL model upload, TwinMaker config), SDK cleanup as fallback after Terraform destroy

**Design Patterns Used**:
- **Protocol Pattern** (`CloudProvider`, `DeployerStrategy` — structural subtyping)
- **Registry Pattern** (`ProviderRegistry` — auto-registration at import time)
- **Strategy Pattern** (per-provider deployment strategies for each layer)
- **Factory Pattern** (context creation, client initialization)
- **Dependency Injection** (`DeploymentContext` dataclass explicitly passed)
- **Template Method** (`BaseProvider` providing common logging/state)

**Cloud Functions** (serverless code deployed per provider):
- AWS: 18 Lambda functions including dispatcher, processors, persisters, movers, readers, connectors, event checker/feedback
- Azure: 26 Azure Functions
- GCP: 24 Cloud Functions

**Function Registry** (`function_registry.py`, 448 lines):
- Single source of truth for all static serverless functions (L0-L4)
- `FunctionDefinition` dataclass with layer, providers, naming
- Query APIs: by layer, by provider, by name
- Handles L0 glue function logic for cross-cloud boundaries

**Layer Architecture** (5-layer Digital Twin):
| Layer | Purpose | Services |
|-------|---------|----------|
| L0 | Cross-cloud glue | Connectors, API gateways |
| L1 | Data Acquisition | IoT Core / IoT Hub / Pub/Sub |
| L2 | Processing | Lambda / Functions / Cloud Functions |
| L3 | Storage (hot/cold/archive) | DynamoDB/Cosmos/Firestore, S3/Blob/GCS |
| L4 | Twin Management | TwinMaker / Azure Digital Twins |
| L5 | Visualization | Grafana |

**Per-Provider Naming** (dedicated `naming.py` per provider):
- AWS: 12KB (AWSNaming class)
- Azure: 11KB (AzureNaming class)
- GCP: 7KB (GCPNaming class)
All generate consistent `{twin_name}-{resource_type}[-{suffix}]` formatted names.

---

## 4. Project 3: The Orchestrator (Backend)

**Path**: `twin2multicloud_backend/`  
**Tech**: Python, FastAPI, SQLAlchemy, SQLite  
**Lines**: ~5,000+ across src  
**Purpose**: Central management hub bridging Optimizer and Deployer.

### 4.1 Architecture

```
twin2multicloud_backend/
├── src/
│   ├── main.py                     # FastAPI app (54 lines, 11 route modules)
│   ├── config.py                   # Settings via pydantic-settings (59 lines)
│   ├── api/
│   │   ├── dependencies.py         # Auth dependency injection
│   │   ├── helpers/
│   │   └── routes/
│   │       ├── twins.py            # Twin lifecycle CRUD (1596 lines, 28 endpoints!)
│   │       ├── config.py           # Credential mgmt + dual validation (737 lines)
│   │       ├── deployer.py         # Deployer config + GLB uploads (661 lines)
│   │       ├── optimizer.py        # Optimizer proxy + calculation (486 lines)
│   │       ├── sse.py              # SSE log streaming (432 lines)
│   │       ├── dashboard.py        # Dashboard stats (89 lines)
│   │       ├── auth.py             # OAuth + SAML SSO (339 lines)
│   │       ├── health.py           # Health check
│   │       ├── optimizer_config.py # Optimizer config CRUD
│   │       ├── error_models.py     # Shared error responses
│   │       └── test_endpoints.py   # Mock endpoints for testing (36KB)
│   ├── models/
│   │   ├── database.py             # SQLAlchemy engine + Base
│   │   ├── twin.py                 # DigitalTwin + TwinState enum
│   │   ├── deployment.py           # Deployment history
│   │   ├── deployment_log.py       # SSE log persistence
│   │   ├── twin_config.py          # Encrypted credentials
│   │   ├── deployer_config.py      # Deployer configuration
│   │   ├── optimizer_config.py     # Optimizer params/results
│   │   ├── file_version.py         # File versioning
│   │   └── user.py                 # User model
│   ├── schemas/                    # Pydantic schemas for API I/O
│   ├── auth/
│   │   ├── jwt.py                  # JWT token handling
│   │   └── providers/              # Google OAuth + UIBK SAML
│   ├── services/
│   └── utils/
├── migrations/                     # 5 SQL migration scripts
├── tests/                          # 15 test files
└── data/                           # SQLite database
```

### 4.2 Key Engineering Facts

**Database Schema** (7 SQLAlchemy models):

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `DigitalTwin` | Core entity | state (8-value enum), name, user_id |
| `TwinConfiguration` | Credentials | Fernet-encrypted AWS/Azure/GCP creds |
| `OptimizerConfiguration` | Step 2 data | params_json, result_json, cheapest_path |
| `DeployerConfiguration` | Step 3 data | events, IoT devices, payloads, functions, hierarchy, scenes |
| `Deployment` | History | session_id, status, terraform_outputs |
| `DeploymentLog` | SSE persistence | event_id ordering, 4 DB indices |
| `User` | Auth | OAuth/SAML identity |

**Twin State Machine** (8 states):
```
DRAFT → CONFIGURED → DEPLOYING → DEPLOYED
                                     ↓
                                 DESTROYING → DESTROYED
                   ERROR ← (any deploying/destroying failure)
                   INACTIVE ← (soft delete)
```

**Authentication**:
- Google OAuth 2.0 flow
- UIBK SAML SSO (via ACOnet/eduID.at federation)
- JWT token issuance (HS256, 60-min expiry)

**Security**:
- Fernet symmetric encryption for all cloud credentials
- Per-user+twin encryption keys
- Credentials never exposed to frontend
- Decrypted only when proxying to Deployer/Optimizer APIs

**SSE (Server-Sent Events) Architecture**:
- `LogSession` state machine: PENDING → STREAMING → COMPLETED
- Thread-safe via `asyncio.Lock`
- Background reaper for stuck sessions (>30 min)
- Batch log persistence to database
- Reconnection via `last_event_id`
- 500-event buffer per session

**Microservice Orchestration**:
- Proxies to Optimizer: pricing freshness, credential-forwarded refresh, cost calculation
- Proxies to Deployer: config validation, deployment/destroy, log tracing, verification
- Dual credential validation (calls both APIs in parallel via `asyncio.gather`)

---

## 5. Project 4: The Orchestrator (Flutter UI)

**Path**: `twin2multicloud_flutter/`  
**Tech**: Dart, Flutter, Material 3  
**Files**: 94 in `lib/`, 25 tests  
**Purpose**: Cross-platform UI for the management workflow.

### 5.1 Architecture

```
twin2multicloud_flutter/lib/
├── main.dart                       # Entry point
├── app.dart                        # GoRouter + Material 3 theme (101 lines)
├── bloc/
│   ├── wizard/
│   │   ├── wizard_bloc.dart        # Core wizard logic (48KB!)
│   │   ├── wizard_state.dart       # State definitions (24KB)
│   │   ├── wizard_event.dart       # Event definitions (15KB)
│   │   ├── helpers/                # 4 helper files
│   │   └── services/              # 2 wizard service files
│   └── twin_overview/              # 3 files for overview BLoC
├── screens/
│   ├── dashboard_screen.dart       # Dashboard home (28KB)
│   ├── login_screen.dart           # OAuth login (5KB)
│   ├── settings_screen.dart        # Settings (10KB)
│   ├── wizard/
│   │   ├── wizard_screen.dart      # Wizard orchestrator (31KB)
│   │   ├── step1_configuration.dart    # Credentials + twin name (11KB)
│   │   ├── step2_optimizer.dart        # Cost calculation (23KB)
│   │   ├── step3_deployer.dart         # Deployment config (48KB!)
│   │   └── helpers/
│   └── twin_overview/              # Twin detail view
├── widgets/                        # 46 widget files
│   ├── credential_section.dart         # Credential forms (39KB)
│   ├── deployment_verification_card.dart   # Post-deploy verification (42KB)
│   ├── architecture_graph.dart         # Architecture visualization (25KB)
│   ├── architecture_layer_builder.dart # Layer config builder (25KB)
│   ├── deployment_terminal.dart        # Live log terminal (10KB)
│   ├── terraform_outputs_card.dart     # TF output display (13KB)
│   ├── credentials/                    # 5 provider-specific credential widgets
│   ├── file_inputs/                    # 9 file input components
│   ├── form_inputs/                    # 6 form input components
│   ├── results/                        # 4 result display components
│   └── ...
├── models/                         # 5 data model files
│   ├── calc_params.dart            # 26 calculation parameters
│   ├── calc_result.dart            # Cost result model
│   ├── twin.dart, user.dart
│   └── zip_extraction_result.dart
├── services/
│   ├── api_service.dart            # HTTP client (17KB, 46 API methods)
│   └── sse_service.dart            # SSE client (4KB)
├── providers/                      # Riverpod providers (auth, theme, API)
├── config/                         # API config, step3 constraints/examples
├── theme/                          # Theme definitions
└── utils/                          # 6 utility files
```

### 5.2 Key Engineering Facts

**State Management**: BLoC (Business Logic Component) pattern
- `wizard_bloc.dart`: 48KB — the largest single file in the entire project
- Handles all wizard step transitions, validation, API calls

**Routing**: GoRouter with auth-gated redirects  
**State**: Riverpod for dependency injection (auth, theme, API service)  
**UI Framework**: Material 3 with light/dark theme support  
**Platforms**: Android, Linux, macOS, Windows, Web

**3-Step Wizard Flow**:
1. **Step 1 — Configuration** (11KB): Twin name, cloud credentials (AWS/Azure/GCP), dual validation
2. **Step 2 — Optimizer** (23KB): 26 parameters, cost calculation, architecture visualization, provider selection
3. **Step 3 — Deployer** (48KB): IoT devices, events, payloads, user functions (processors, event feedback, event actions), state machines, L4 hierarchy, 3D scenes, platform user config

**API Service** (`api_service.dart`, 536 lines, 46 methods):
- Full REST client using Dio
- Methods for: twins CRUD, configs, credentials (inline + stored + dual), pricing, calculation, deployer, deployment, SSE, verification, log tracing

---

## 6. Infrastructure & Deployment

### Docker Compose (`compose.yaml`)
- 4 active services on `my_master_thesis_network` bridge
- Shared config files mounted into containers
- Management API uses internal Docker hostnames for inter-service communication
- Named volume `management-data` for persistent SQLite storage
- LaTeX service in optional `latex` profile

### E2E Tests
- Located in `3-cloud-deployer/run_tests/e2e/`
- Azure-focused test scripts (bash + bat for cross-platform)
- Scenarios: full deployment, failure cleanup, all-layer tests

### Per-Project Dockerfiles
Each project has its own Dockerfile for independent containerization.

---

## 7. Cross-Cutting Concerns

### Design Patterns Summary

| Pattern | Optimizer | Deployer | Backend | Flutter |
|---------|-----------|----------|---------|---------|
| Protocol/Interface | ✅ ResourceCalculator | ✅ CloudProvider, DeployerStrategy | — | — |
| Factory | ✅ PriceFetcherFactory | ✅ Context factory | — | — |
| Registry | — | ✅ ProviderRegistry | — | — |
| Strategy | ✅ Per-provider components | ✅ Per-provider deployers | — | — |
| Template Method | ✅ CalculatorBase | ✅ BaseProvider | — | — |
| Dependency Injection | — | ✅ DeploymentContext | ✅ FastAPI Depends | ✅ Riverpod |
| Observer/Reactive | — | — | ✅ SSE streaming | ✅ BLoC pattern |
| State Machine | — | — | ✅ TwinState (8 states) | ✅ WizardState |
| Proxy | — | — | ✅ API proxying | — |
| Repository | — | — | ✅ SQLAlchemy ORM | — |

### File-Based vs. Database State

| System | State Storage | Reason |
|--------|--------------|--------|
| Optimizer | JSON files | Pricing cache, config, credentials from files |
| Deployer | Terraform `.tfstate` + JSON configs | Terraform requires file-based state; project configs are ZIP-uploaded |
| Backend | SQLite database | Persistent twin lifecycle, encrypted credentials, deployment history |
| Flutter | In-memory (BLoC) | Reactive UI state, persisted via API calls |

### Inter-Service Communication

```
Flutter UI ──HTTP──→ Management API (port 5005)
                         │
                    ┌────┴────┐
                    │         │
               HTTP/SSE   HTTP/SSE
                    │         │
                    ↓         ↓
              Optimizer    Deployer
            (port 5003)  (port 5004)
                              │
                         Terraform CLI
                              │
                    ┌────┬────┴────┬────┐
                    ↓    ↓         ↓    ↓
                   AWS  Azure     GCP  (cross-cloud)
```

---

## 8. Findings vs. Thesis Proposal

### Confirmed by Investigation
- ✅ Two isolated legacy prototypes as starting point
- ✅ 909-line monolithic engine refactored to component-based (501 lines)
- ✅ Deployer moved from SDK-only to hybrid Terraform+Python
- ✅ New Orchestrator (Backend + Flutter) as central hub
- ✅ Docker Compose for unified development
- ✅ File-based state in Optimizer/Deployer, DB state in Orchestrator

### Additional Details Discovered
- **Credential security**: Fernet encryption with per-user+twin keys (not mentioned in proposal)
- **Authentication**: Google OAuth + UIBK SAML SSO via ACOnet federation
- **SSE architecture**: Full session state machine with reconnection, batch persistence, and stuck-session recovery
- **Function registry**: Centralized serverless function catalog (448 lines) — a significant engineering artifact
- **Per-provider naming**: Dedicated naming modules per cloud (7-12KB each)
- **SDK cleanup as fallback**: Deployer runs SDK cleanup after Terraform destroy to catch orphaned resources
- **Test endpoints**: 36KB mock implementation for testing without cloud APIs
- **5 database migrations**: Demonstrating iterative schema evolution
- **LaTeX thesis**: Containerized via Docker for reproducible builds

### Potential Proposal Updates
- Section 2.4 (Design Patterns): Now identifiable — Protocol, Factory, Registry, Strategy, Template Method, DI, Observer, State Machine
- Section 4.2 (Data Flow): File-based ↔ DB bridge pattern is clearly defined
- Section 5.3 (Optimizer patterns): Protocol + Factory + Strategy + Template Method
- Section 5.4 (Deployer patterns): Protocol + Registry + Strategy + Factory + DI + Template Method
- Section 5.5 (Orchestrator): Add credential encryption, SSE architecture, dual validation, state machine

---

## 9. Deprecated Project: Original Optimizer (JavaScript)

**Path**: `deprecated/optimizer/`  
**Tech**: Vanilla JavaScript, HTML, CSS (no build tools, no server)  
**Files**: 15 (7 JS, 1 JSON, 1 HTML, 1 CSS, + README, LICENSE, .gitignore)  
**Lines**: ~2,160 total  
**Origin**: Conference paper artifact for EDTConf'25, published as the Twin2Clouds tool.  
**Purpose**: Client-side cost comparison calculator for deploying a Digital Twin across AWS and Azure.

### 9.1 Architecture

```
deprecated/optimizer/
├── index.html                     # UI entry point (188 lines, 12 inputs + 3 presets)
├── styles.css                     # CSS styling (7KB)
├── pricing.json                   # Static pricing data — hardcoded AWS + Azure (115 lines)
├── ui.js                          # UI helpers: slider styling, presets, card flip (101 lines)
├── cost_calculation.js            # Main orchestrator: reads inputs, calls all calculators,
│                                  #   assembles HTML result cards (491 lines)
├── layer_data_acquisition.js      # L1: AWS IoT Core vs Azure IoT Hub (140 lines)
├── layer_data_processing.js       # L3*: AWS Lambda vs Azure Functions (74 lines)
├── layer_data_storage.js          # L2*: DynamoDB/CosmosDB (hot), S3-IA/Blob Cool,
│                                  #       S3 Glacier/Blob Archive (251 lines)
├── layer_twin_management.js       # L4: AWS IoT TwinMaker vs Azure Digital Twins (68 lines)
├── layer_data_visualization.js    # L5: Amazon Managed Grafana vs Azure Managed Grafana (31 lines)
├── data_transfer.js               # Cross-cloud/layer transfer cost functions (148 lines)
├── provider_decision.js           # Graph-based cheapest-path algorithm (126 lines)
├── README.md                      # Usage + repository layout (82 lines)
├── LICENSE                        # License file
└── .gitignore
```

> *Note: The original optimizer uses a different layer numbering than the current system. L2 = Storage, L3 = Processing (reversed vs. current L2 = Processing, L3 = Storage).

### 9.2 Key Engineering Facts

**Execution Model**: Pure client-side — no server, no API, no backend. All calculation runs in the browser. The entire app is a static HTML page served by any HTTP server (`python3 -m http.server`).

**Providers Supported**: **AWS + Azure only**. No GCP whatsoever.

**Input Parameters** (12 vs. 26 in current):
| Parameter | Description |
|-----------|-------------|
| `devices` | Number of IoT devices |
| `interval` | Device sending interval (minutes) |
| `messageSize` | Average message size (KB) |
| `hotStorageDurationInMonths` | Hot storage duration (slider, 1-12) |
| `coolStorageDurationInMonths` | Cool storage duration (slider, 1-24) |
| `archiveStorageDurationInMonths` | Archive storage duration (slider, 6-36) |
| `needs3DModel` | Yes/No radio — determines L4 behavior |
| `entityCount` | Number of 3D entities (conditional) |
| `monthlyEditors` | Dashboard editors |
| `monthlyViewers` | Dashboard viewers |
| `dashboardRefreshesPerHour` | Refresh rate |
| `dashboardActiveHoursPerDay` | Active hours/day (slider, 1-24) |

**3 Presets** (hardcoded in `index.html` via `onclick`):
1. Smart Home (100 devices, 2 min interval)
2. Smart Industrial Facility (4000 devices, 0.5 min interval)
3. Smart Large Building (30,000 devices, 0.1 min interval, 3D model)

**Pricing Data** (`pricing.json`, 115 lines):
- Static JSON file with hardcoded AWS and Azure prices
- No dynamic fetching, no API integration, no caching mechanism
- Tiered pricing defined for: AWS data transfer (4 tiers), AWS IoT Core messages (3 tiers), Azure IoT Hub (3 tiers)
- Individual service pricing for: DynamoDB, S3-IA, S3 Glacier Deep Archive, IoT TwinMaker, Managed Grafana (AWS); CosmosDB, Blob Storage Cool/Archive, Azure Digital Twins, Azure Managed Grafana

**Cost Calculation Architecture** (`cost_calculation.js`, 491 lines):
- Single monolithic `calculateCosts()` function (476 lines!)
- Reads all 12 inputs from the DOM via `document.getElementById()`
- Input validation embedded in the function (not separated)
- Calls each per-provider layer calculator sequentially
- Computes 12 explicit transfer cost values between provider/layer combinations
- Builds a storage graph, runs Dijkstra to find cheapest hot→cool→archive path
- Determines cheapest provider for L1, L4, L5 by simple comparison
- Assembles and injects HTML result cards directly into the DOM
- **No JSON API response** — outputs formatted HTML template literals

**Layer Calculators** (per-provider functions, no abstraction):
| Layer | AWS Function | Azure Function | Lines Each |
|-------|-------------|---------------|------------|
| L1 Data Acquisition | `calculateAWSCostDataAcquisition()` | `calculateAzureCostDataAcquisition()` | ~65, ~50 |
| L2* Storage (Hot) | `calculateDynamoDBCost()` | `calculateCosmosDBCost()` | ~35, ~35 |
| L2* Storage (Cool) | `calculateS3InfrequentAccessCost()` | `calculateAzureBlobStorageCost()` | ~25, ~25 |
| L2* Storage (Archive) | `calculateS3GlacierDeepArchiveCost()` | `calculateAzureBlobStorageArchiveCost()` | ~25, ~25 |
| L3* Processing | `calculateAWSCostDataProcessing()` | `calculateAzureCostDataProcessing()` | ~40, ~10** |
| L4 Twin Mgmt | `calculateAWSIoTTwinMakerCost()` | `calculateAzureDigitalTwinsCost()` | ~25, ~28 |
| L5 Visualization | `calculateAmazonManagedGrafanaCost()` | `calculateAzureManagedGrafanaCost()` | ~15, ~12 |

> **Azure Functions processing cost function literally calls the AWS Lambda function and changes the provider label — "We execute the same function as for AWS since the costs and the free tier per month are identical."

**Graph-Based Storage Path Optimization** (`provider_decision.js`, 126 lines):
- Custom `PriorityQueue` class (sorted array, O(n log n) dequeue)
- `buildGraphForStorage()`: constructs a directed graph of 6 nodes (AWS_Hot, Azure_Hot, AWS_Cool, Azure_Cool, AWS_Archive, Azure_Archive) with 8 edges weighted by transfer costs
- `findCheapestStoragePath()`: Dijkstra's algorithm implementation to find the cheapest Hot→Cool→Archive path across providers
- Returns the cheapest path and total cost

**Cross-Cloud Transfer Model** (`data_transfer.js`, 148 lines):
- 12 explicit transfer cost functions (one for each inter-layer provider combination)
- AWS→AWS and Azure→Azure same-provider transfers are mostly $0
- Cross-provider transfers use tiered egress pricing
- No L0 glue layer concept (data transfer between layers modeled as flat cost additions)

**Design Patterns**: None — purely procedural JavaScript. No classes (except `PriorityQueue`), no modules, no abstraction layers. Global `pricing` variable loaded via `fetch()`. All functions are module-level.

### 9.3 Limitations Identified

1. **No GCP support** — only AWS and Azure
2. **No server component** — cannot be integrated into a larger system
3. **Static pricing** — hardcoded values, no live fetching from provider APIs
4. **No L0 glue layer** — cross-cloud transfer modeled as cost additions, not as a distinct layer
5. **Monolithic calculation** — single 476-line function, not composable or testable
6. **No API/JSON output** — results are HTML-formatted template literals
7. **No Pydantic/TypeScript validation** — manual DOM string parsing with `parseInt()`/`parseFloat()`
8. **Different layer numbering** — L2 = Storage, L3 = Processing (reversed in current system)
9. **No input parameters for**: currency selection, supporter services, GCP self-hosted options, 3D model counts, L4/L5 dashboard configs beyond basic refresh/hours
10. **Conditional L4 logic** — if 3D model needed → AWS TwinMaker only; if not → compares both providers. This was simplified in the current system.

---

## 10. Deprecated Project: Original Deployer (AWS-Only Python)

**Path**: `deprecated/deployer/`  
**Tech**: Python, boto3 (AWS SDK), no Terraform, no web framework  
**Files**: 68 Python files, 11 Lambda function directories  
**Lines**: ~4,332 Python lines total  
**Purpose**: CLI-based deployment tool for AWS-only Digital Twin infrastructure.

### 10.1 Architecture

```
deprecated/deployer/
├── config.json                    # DT name + storage durations (6 lines)
├── config_credentials.json.example # Credential template (placeholder)
├── config_providers.json          # Per-layer provider assignment (10 lines, all "aws")
├── config_iot_devices.json        # IoT device definitions (29 lines, 4 devices)
├── config_events.json             # Event-action definitions (30 lines, 2 events)
├── config_hierarchy.json          # TwinMaker entity hierarchy (40 lines)
├── src/
│   ├── main.py                    # CLI REPL entry point (88 lines)
│   ├── globals.py                 # Global state: 12 boto3 clients + 30 naming functions (257 lines)
│   ├── util.py                    # Lambda packaging, S3 cleanup, console link generators (143 lines)
│   ├── sanity_checker.py          # DT name validation only (21 lines)
│   └── deployers/
│       ├── base.py                # Deployer ABC: deploy(), destroy(), info(), log() (19 lines)
│       └── aws/
│           ├── core/              # 35 files — infrastructure resources
│           │   ├── all.py         # Core aggregator (deploys L1→L5)
│           │   ├── l1.py          # L1: Dispatcher IAM role + Lambda + IoT rule
│           │   ├── l2.py          # L2: Persister, EventFeedback, EventChecker, LambdaChain
│           │   ├── l3_hot.py      # L3 Hot: DynamoDB + Mover + Reader
│           │   ├── l3_cold.py     # L3 Cold: S3 bucket
│           │   ├── l3_archive.py  # L3 Archive: S3 bucket + mover
│           │   ├── l4.py          # L4: TwinMaker S3 + IAM + workspace
│           │   ├── l5.py          # L5: Grafana IAM + workspace
│           │   ├── dispatcher_iam_role.py          # Single IAM role resource
│           │   ├── dispatcher_lambda_function.py   # Single Lambda resource
│           │   ├── dispatcher_iot_rule.py           # Single IoT rule resource
│           │   ├── persister_iam_role.py
│           │   ├── persister_lambda_function.py
│           │   ├── event_checker_iam_role.py
│           │   ├── event_checker_lambda_function.py
│           │   ├── event_feedback_iam_role.py
│           │   ├── event_feedback_lambda_function.py
│           │   ├── lambda_chain_iam_role.py
│           │   ├── lambda_chain_step_function.py
│           │   ├── hot_dynamodb_table.py
│           │   ├── hot_cold_mover_iam_role.py
│           │   ├── hot_cold_mover_lambda_function.py
│           │   ├── hot_cold_mover_event_rule.py
│           │   ├── cold_archive_mover_iam_role.py
│           │   ├── cold_archive_mover_lambda_function.py
│           │   ├── cold_s3_bucket.py
│           │   ├── archive_s3_bucket.py
│           │   ├── hot_reader_iam_role.py
│           │   ├── hot_reader_lambda_function.py
│           │   ├── twinmaker_iam_role.py
│           │   ├── twinmaker_s3_bucket.py
│           │   ├── twinmaker_workspace.py
│           │   ├── grafana_iam_role.py
│           │   └── grafana_workspace.py
│           ├── iot/               # 7 files — per-device resources
│           │   ├── all.py         # IoT aggregator (L1, L2, L4)
│           │   ├── l1.py          # IoT L1: Things
│           │   ├── l2.py          # IoT L2: Processors
│           │   ├── l4.py          # IoT L4: TwinMaker component types
│           │   ├── iot_thing.py
│           │   ├── processor_iam_role.py
│           │   ├── processor_lambda_function.py
│           │   └── twinmaker_component_type.py
│           ├── hierarchy/         # 2 files — TwinMaker entity hierarchy
│           │   ├── all.py
│           │   └── twinmaker_hierarchy.py
│           ├── event_actions/     # 2 files — event-driven Lambda functions
│           │   ├── all.py
│           │   └── lambda_actions.py
│           └── init_values/       # 2 files — initial constant values
│               ├── all.py
│               └── init_values.py
├── lambda_functions/
│   ├── core/                      # 8 core Lambda function directories
│   │   ├── dispatcher/            # Routes incoming IoT messages
│   │   ├── persister/             # Persists data to DynamoDB
│   │   ├── hot-reader/            # Reads from hot storage
│   │   ├── hot-to-cold-mover/     # Lifecycle: DynamoDB → S3-IA
│   │   ├── cold-to-archive-mover/ # Lifecycle: S3-IA → S3 Glacier
│   │   ├── event-checker/         # Checks event conditions
│   │   ├── event-feedback/        # Sends feedback via MQTT
│   │   └── default-processor/     # Default message processor
│   ├── processors/                # 1 custom processor
│   │   └── temperature-sensor-2/  # Custom processor for specific sensor
│   └── event_actions/             # 2 external Lambda actions
│       ├── high-temperature-callback/
│       └── high-temperature-callback-2/
└── iot_device_simulator/          # Single AWS IoT simulator
    ├── config.json                # IoT endpoint + cert paths
    ├── payloads.json              # Sample payloads
    ├── AmazonRootCA1.pem          # AWS IoT root CA
    └── src/                       # Simulator source
```

### 10.2 Key Engineering Facts

**Execution Model**: CLI REPL (Read-Eval-Print Loop)
- Interactive command-line interface: `deploy`, `destroy`, `info`, `help`, `exit`
- No HTTP API, no REST, no FastAPI — purely local terminal interaction
- All operations are synchronous, blocking, sequential

**Cloud Support**: **AWS only**
- `config_providers.json` defines per-layer provider assignment (all `"aws"`)
- The structure supports multi-provider assignment (layer_1_provider through layer_5_provider), but only AWS implementations exist
- No Azure providers, no GCP providers

**Infrastructure-as-Code**: **None (pure SDK)**
- All resources created via imperative `boto3` API calls
- No Terraform, no CloudFormation, no IaC templates
- No state file — resource existence checked via SDK API calls
- Deploy/destroy ordering is manually managed in aggregator files

**Global Mutable State** (`globals.py`, 257 lines):
- 12 `boto3` client objects stored as module-level global variables
- 30+ naming functions using string concatenation: `config["digital_twin_name"] + "-" + suffix`
- All global state initialized at startup via `globals.initialize_*()` calls
- Credentials read directly from `config_credentials.json` at startup
- No dependency injection, no factory pattern — all modules import `globals` directly

**Deployer Architecture**:
- `Deployer` abstract base class with 4 methods: `deploy()`, `destroy()`, `info()`, `log()`
- **One class per resource**: Each AWS resource (IAM role, Lambda function, S3 bucket, etc.) has its own deployer class in its own file
- **Aggregator pattern**: Layer-level deployers compose resource deployers (e.g., `L1Deployer` calls `DispatcherIamRoleDeployer`, `DispatcherLambdaFunctionDeployer`, `DispatcherIotRuleDeployer`)
- **5-phase deployment order**: core → iot → hierarchy → event_actions → init_values
- **Reverse destruction order**: init_values → event_actions → hierarchy → iot → core

**Resource Naming** (`globals.py`):
- All resources use `{digital_twin_name}-{resource_type}` convention
- DT name limited to 10 characters (sanity check)
- IoT rule names replace hyphens with underscores (AWS IoT constraint)
- No uniqueness guarantees beyond DT name prefix

**Lambda Functions** (11 directories):
- 8 core functions: dispatcher, persister, hot-reader, hot-to-cold-mover, cold-to-archive-mover, event-checker, event-feedback, default-processor
- 1 custom processor: `temperature-sensor-2`
- 2 event action callbacks: `high-temperature-callback`, `high-temperature-callback-2`
- Packaged as ZIP files at deploy time via `util.compile_lambda_function()`
- Runtime: Python 3.13, 128MB memory, 3s timeout
- DT info injected via `DIGITAL_TWIN_INFO` environment variable

**Configuration Files** (5 JSON files, ~120 lines total):
| File | Purpose | Key Fields |
|------|---------|------------|
| `config.json` | DT identity + storage | `digital_twin_name`, `hot_storage_size_in_days`, `cold_storage_size_in_days` |
| `config_credentials.json` | AWS credentials | `aws_access_key_id`, `aws_secret_access_key`, `aws_region` |
| `config_providers.json` | Per-layer provider | `layer_1_provider` through `layer_5_provider` (all `"aws"`) |
| `config_iot_devices.json` | Device definitions | Array of `{id, properties: [{name, dataType, initValue?}]}` |
| `config_events.json` | Event-action rules | Array of `{condition, action: {type, functionName, feedback}}` |
| `config_hierarchy.json` | TwinMaker hierarchy | Nested `{type: entity/component, id, children}` tree |

**Utility Functions** (`util.py`, 143 lines):
- `compile_lambda_function()`: Zips directory for Lambda deployment
- `destroy_s3_bucket()`: Empties and deletes S3 bucket (handles versioning)
- `iot_rule_exists()`: Paginated IoT rule lookup
- `get_grafana_workspace_id_by_name()`: Paginated Grafana workspace lookup
- 12 `link_to_*()` functions generating AWS Console URLs for resource inspection

**IoT Device Simulator**:
- Single AWS IoT Core simulator (MQTT protocol)
- Uses `AmazonRootCA1.pem` root certificate
- 4 sample devices: 2 temperature sensors, 1 temperature sensor constants, 1 pressure sensor
- `payloads.json` with sample telemetry data

### 10.3 Limitations Identified

1. **AWS-only** — no Azure or GCP implementation despite config structure supporting multi-provider
2. **No IaC** — imperative boto3 calls, no Terraform/CloudFormation, no state management
3. **No API** — CLI-only, cannot be integrated into a web-based management system
4. **Global mutable state** — all clients and config as module-level globals, no DI
5. **No error recovery** — failed deployments leave orphaned resources with no rollback
6. **No concurrent deployment** — strictly sequential resource creation
7. **No credentials encryption** — plaintext JSON credentials on disk
8. **No multi-tenancy** — single DT per deployer instance
9. **No streaming/SSE** — no progress reporting beyond `print()` statements
10. **Manual deploy ordering** — developer must ensure correct sequencing in aggregator classes
11. **No tests** — no unit tests, integration tests, or E2E tests
12. **Limited validation** — only DT name length and regex check (10 chars, alphanumeric + hyphen + underscore)

---

## 11. Legacy → Current: Comparative Analysis

### 11.1 Optimizer: JavaScript → Python FastAPI

| Dimension | Original (JS) | Current (Python) | Change |
|-----------|---------------|-----------------|--------|
| **Language** | Vanilla JavaScript | Python 3 + FastAPI | Complete rewrite |
| **Execution** | Client-side browser | Server-side REST API | Architectural shift |
| **Cloud Providers** | AWS + Azure (2) | AWS + Azure + GCP (3) | +50% |
| **Input Parameters** | 12 | 26 | +117% |
| **Cost Formulas** | Inline per-function | 6 abstracted formulas (CM, CE, CA, CS, CU, CT) | Generalized |
| **Component Calculators** | ~14 flat functions | 25 typed classes (9 AWS + 9 Azure + 7 GCP) | Protocol pattern |
| **Pricing Data** | Static `pricing.json` (115 lines) | Live API fetching + 7-day cache | Dynamic |
| **Layer Numbering** | L1=Acquisition, L2=Storage, L3=Processing | L1=Ingestion, L2=Processing, L3=Storage | Renumbered |
| **L0 Glue Layer** | None | Cross-cloud connectors + API gateways | New layer |
| **Storage Path** | Dijkstra graph (6 nodes) | Independent per-tier cheapest selection | Simplified |
| **Transfer Costs** | 12 explicit functions | 5 boundary-based calculations | Reduced |
| **Type Safety** | None (`parseInt`, `parseFloat`) | Pydantic + typed enums | Fully typed |
| **Output Format** | HTML template literals | JSON API responses + SSE streaming | API-first |
| **Design Patterns** | Procedural | Protocol, Factory, Strategy, Template Method | 4 patterns |
| **Testability** | None | Separable components | Testable |
| **Lines of Code** | ~2,160 | ~3,000+ | +39% |
| **Engine Size** | 491-line monolith | 501-line orchestrator + 25 component files | Decomposed |
| **Presets** | 3 hardcoded in HTML | None (API-driven) | Removed |
| **Validation** | Manual DOM checks | Pydantic model_validator | Declarative |
| **Currency** | USD only | Multi-currency support | +feature |
| **Credential Checking** | None | Per-provider credential validation | +feature |

### 11.2 Deployer: AWS boto3 CLI → Multi-Cloud Terraform + FastAPI

| Dimension | Original (Python CLI) | Current (Python FastAPI) | Change |
|-----------|----------------------|--------------------------|--------|
| **Interface** | CLI REPL (3 commands) | REST API (10 routers) | API-based |
| **Cloud Providers** | AWS only | AWS + Azure + GCP | +200% |
| **IaC Tool** | None (imperative SDK) | Terraform (31 `.tf` files) + SDK post-deploy | Hybrid |
| **State Management** | None (API existence checks) | Terraform `.tfstate` + JSON project state | Declarative |
| **Client Architecture** | 12 global boto3 clients | Per-provider client factories | DI-based |
| **Naming** | 30 functions in `globals.py` | Dedicated `naming.py` per provider (7-12KB each) | Encapsulated |
| **Base Class** | `Deployer` ABC (4 methods) | `CloudProvider` + `DeployerStrategy` Protocols | Structural typing |
| **Deployer Files** | 49 files (1 class per resource) | Per-provider layer strategies + registry | Consolidated |
| **Lambda Functions** | 11 (8 core + 1 processor + 2 events) | 68 (18 AWS + 26 Azure + 24 GCP) | +518% |
| **Function Packaging** | `util.compile_lambda_function()` | Per-provider bundlers (Lambda ZIP, Kudu ZIP, GCP upload) | Provider-specific |
| **Error Handling** | `ClientError` catch + ignore | Structured exceptions + SDK cleanup as fallback | Resilient |
| **Progress Reporting** | `print()` statements | SSE log streaming + session management | Real-time |
| **Credentials** | Plaintext `config_credentials.json` | Fernet-encrypted, per-user+twin keys | Secure |
| **Multi-Tenancy** | Single DT | Multiple concurrent DTs per user | Multi-tenant |
| **Destruction** | Reverse deploy order | Terraform destroy + SDK cleanup + resource verification | Comprehensive |
| **Validation** | DT name regex only | Per-provider credential + permission checks | Thorough |
| **Testing** | None | Unit tests + E2E test suite | Tested |
| **Lines of Code** | ~4,332 | ~15,000+ | +246% |
| **Config Files** | 5 JSON files | Dynamic API-driven configuration | Programmatic |
| **IoT Simulator** | 1 (AWS MQTT only) | 3 (AWS MQTT, Azure IoT Hub, GCP Pub/Sub) | Per-provider |
| **Concurrent Deploy** | Sequential only | Async with streaming | Concurrent |
| **Recovery** | None (Future Work item) | Terraform state recovery + SDK cleanup | Implemented |

### 11.3 Key Architectural Evolution Patterns

1. **Procedural → Protocol-based**: Both projects moved from flat functions / ABC classes to `typing.Protocol` structural subtyping
2. **CLI → REST API**: Both prototypes were standalone tools; both are now microservices in a Docker Compose network
3. **Single-provider → Multi-cloud**: Optimizer went from 2→3 providers; deployer went from 1→3 providers
4. **Static → Dynamic**: Optimizer moved from hardcoded `pricing.json` to live API fetching; deployer moved from config files to API-driven configuration
5. **Global state → Dependency Injection**: Deployer replaced 12 global boto3 clients with factory-based client creation and `DeploymentContext` injection
6. **Monolith → Component-based**: Optimizer's 491-line `calculateCosts()` was decomposed into 25 `ResourceCalculator` implementations; deployer's 49 per-resource files were consolidated into per-layer strategies
7. **No state → Declarative state**: Deployer moved from existence-check-based state to Terraform `.tfstate` + project-level JSON
8. **Insecure → Encrypted**: Deployer moved from plaintext credential files to Fernet-encrypted, per-user+twin key derivation

