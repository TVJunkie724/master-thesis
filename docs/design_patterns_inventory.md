# Design Patterns Inventory — Complete Codebase Scan

This document catalogs every design pattern, architectural pattern, and software engineering principle identified across all four projects. Patterns are grouped by category. Even patterns that may seem "obvious" or "minor" are included for completeness.

---

## 1. Creational Patterns

### 1.1 Factory Pattern
| Location | Class/Function | Purpose |
|---|---|---|
| [factory.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/backend/fetch_data/factory.py) | `PriceFetcherFactory` | Creates provider-specific `PriceFetcher` instances (AWS/Azure/GCP) by name |
| [factory.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/factory.py) | `create_context()` | Factory function that creates `DeploymentContext` objects from project config |
| [registry.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/registry.py) | `ProviderRegistry.get()` | Creates new provider instances by name lookup (combines Registry + Factory) |

### 1.2 Registry Pattern
| Location | Class/Function | Purpose |
|---|---|---|
| [registry.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/registry.py) | `ProviderRegistry` | Central registry for cloud provider classes. Providers self-register at import time. Enables runtime provider selection. |
| [function_registry.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/function_registry.py) | Module-level `FUNCTION_REGISTRY` | Single source of truth for all serverless function definitions (L0–L4). Replaces hardcoded lists. |

### 1.3 Singleton Pattern (Module-level)
| Location | Instance | Purpose |
|---|---|---|
| [globals.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/iot_device_simulator/google/globals.py) | `config = Config()` | Module-level singleton for simulator configuration |
| [state.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/state.py) | `CURRENT_PROJECT` | Module-level global state for active project tracking |

### 1.4 Builder Pattern (Implicit)
| Location | Function | Purpose |
|---|---|---|
| [tfvars_generator.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/tfvars_generator.py) | `generate_tfvars()` | Builds a `tfvars.json` by assembling config, credentials, providers, IoT devices, events, and inter-cloud settings step by step |
| [deployment_service.py](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/services/deployment_service.py) | `build_project_zip()` | Assembles a ZIP file incrementally: config files → hierarchy → state machine → user functions → scene files |

---

## 2. Structural Patterns

### 2.1 Facade Pattern
| Location | Function/Class | Purpose |
|---|---|---|
| [engine.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/backend/calculation_v2/engine.py) | `calculate_cheapest_costs()` | Hides complexity of multi-provider cost calculation behind a single entry point |
| [deployer.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/providers/deployer.py) | `deploy_all()`, `destroy_all()` | Orchestrates Terraform + SDK operations behind simple deploy/destroy calls |
| [api_service.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/services/api_service.dart) | `ApiService` | Unified API abstraction hiding HTTP details (Dio), auth headers, URL construction, error handling |

### 2.2 Adapter / Wrapper Pattern
| Location | Class | Purpose |
|---|---|---|
| [terraform_runner.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/terraform_runner.py) | `TerraformRunner` | Wraps Terraform CLI (`terraform init`, `plan`, `apply`, `destroy`) as Python methods with structured error handling |
| [api_error_handler.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/utils/api_error_handler.dart) | `ApiErrorHandler` | Adapts various exception types (DioException, generic exceptions) into user-friendly error strings |
| [result.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/core/result.dart) | `AppException.fromDioError()` | Adapts `DioException` into a domain-specific `AppException` |

### 2.3 Decorator Pattern (Implicit)
| Location | Mechanism | Purpose |
|---|---|---|
| [dependencies.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/api/dependencies.py) | FastAPI `Depends()` | Middleware injection for authentication, project validation, etc. |
| [dependencies.py](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/api/dependencies.py) | `get_current_user` DI | Conditionally swaps auth middleware (real JWT vs dev bypass) based on `settings.DEBUG` |

### 2.4 Composite Pattern (Implicit)
| Location | Mechanism | Purpose |
|---|---|---|
| [validator.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/validator.py) | `validate_project_zip()` | Composes multiple validators (config schema, hierarchy, state machine, code syntax) into a single validation pipeline |
| [config_loader.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/config_loader.py) | `load_project_config()` | Composes multiple JSON file loaders into a single `ProjectConfig` object |

---

## 3. Behavioral Patterns

### 3.1 Strategy Pattern
| Location | Protocol/Interface | Implementations | Purpose |
|---|---|---|---|
| [protocols.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/protocols.py) | `CloudProvider` | `AWSProvider`, `AzureProvider`, `GCPProvider` | Interchangeable cloud provider implementations |
| [protocols.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/protocols.py) | `DeployerStrategy` | AWS/Azure/GCP deployer strategies | Layer-by-layer deployment varies by provider |
| [factory.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/backend/fetch_data/factory.py) | `PriceFetcher` protocol | `AWSPriceFetcher`, `AzurePriceFetcher`, `GCPPriceFetcher` | Fetching pricing data varies by provider |
| [base.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/backend/calculation_v2/components/base.py) | `ResourceCalculator` protocol | IoT Core, Lambda, DynamoDB, etc. calculators | Calculation formula varies by component |

### 3.2 Observer Pattern
| Location | Mechanism | Purpose |
|---|---|---|
| [sse_service.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/services/sse_service.dart) | Server-Sent Events (SSE) | Backend pushes live deployment/refresh logs to frontend clients |
| [wizard_bloc.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/bloc/wizard/wizard_bloc.dart) | BLoC event→state | UI widgets observe state changes emitted by the BLoC |
| [twins_provider.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/providers/twins_provider.dart) | `ChangeNotifier` | Notifies UI when twin list changes |

### 3.3 State Pattern / State Machine
| Location | Mechanism | Purpose |
|---|---|---|
| [twin.py](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/models/twin.py) | `TwinState` enum | DRAFT → CONFIGURED → DEPLOYING → DEPLOYED → DESTROYING → DESTROYED / ERROR / INACTIVE |
| [wizard_state.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/bloc/wizard/wizard_state.dart) | `WizardStatus` enum + `WizardState` | Multi-step wizard with validation gates between steps |
| [wizard_event.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/bloc/wizard/wizard_event.dart) | Event classes | Discrete events that drive state transitions in the wizard |

### 3.4 Command Pattern (Implicit)
| Location | Mechanism | Purpose |
|---|---|---|
| [wizard_event.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/bloc/wizard/wizard_event.dart) | Event hierarchy (`WizardNextStep`, `WizardSaveDraft`, …) | Events encapsulate user actions as objects, processed by the BLoC |

### 3.5 Template Method Pattern (Implicit)
| Location | Base Class | Template | Purpose |
|---|---|---|---|
| [base.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/backend/calculation_v2/components/base.py) | `CalculatorBase` | `calculate_cost()` abstract method | All component calculators inherit base utilities, implement `calculate_cost()` |
| [base.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/providers/base.py) | `BaseProvider` | `_log_resource_*()` methods | Base logging methods used by all provider implementations |

---

## 4. Architectural Patterns

### 4.1 Layered Architecture (5-Layer IoT Architecture)
| Location | Description |
|---|---|
| [function_registry.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/function_registry.py) | `Layer` enum (L0–L5) defines the 5-layer IoT digital twin architecture |
| Terraform files (`aws_*.tf`, `azure_*.tf`, `gcp_*.tf`) | Each provider's infrastructure is organized by layer (IoT, compute, storage, twins, etc.) |
| [protocols.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/protocols.py) | `DeployerStrategy` methods: `deploy_l1()` through `deploy_l5()` |

### 4.2 Microservices Architecture
| Project | Service | Purpose |
|---|---|---|
| `2-twin2clouds` | **Optimizer** (FastAPI) | Cost calculation & pricing data |
| `3-cloud-deployer` | **Deployer** (FastAPI) | Infrastructure deployment |
| `twin2multicloud_backend` | **Backend/Management** (FastAPI) | Project management, orchestration, persistence |
| `twin2multicloud_flutter` | **Flutter UI** | User interface |

### 4.3 Infrastructure as Code (IaC)
| Location | Description |
|---|---|
| [terraform/](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/terraform) | 30+ Terraform files defining all cloud resources declaratively |
| [variables.tf](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/terraform/variables.tf) | Input variables parameterize the entire infrastructure |
| [outputs.tf](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/terraform/outputs.tf) | Outputs expose created resource identifiers |

### 4.4 BLoC Pattern (Business Logic Component)
| Location | Description |
|---|---|
| [wizard_bloc.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/bloc/wizard/wizard_bloc.dart) | Event → BLoC → State unidirectional data flow for the wizard |
| [twin_overview/](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/bloc/twin_overview) | Separate BLoC for twin overview management |

### 4.5 Repository / Data Access Pattern
| Location | Mechanism | Purpose |
|---|---|---|
| [models/](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/models) | SQLAlchemy ORM models | `DigitalTwin`, `Deployment`, `DeployerConfiguration`, etc. map to database tables |
| [schemas/](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/schemas) | Pydantic schemas | Request/response validation separate from ORM models |

### 4.6 Service Layer Pattern
| Location | Class/Module | Purpose |
|---|---|---|
| [deployment_service.py](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/services/deployment_service.py) | `build_deploy_config()`, `run_real_deploy_stream()` | Business logic extracted from API route handlers into a reusable service |

---

## 5. Cross-Cutting Patterns

### 5.1 Protocol / Interface Pattern (Structural Subtyping)
| Location | Protocol | Purpose |
|---|---|---|
| [protocols.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/protocols.py) | `CloudProvider`, `DeployerStrategy` | Defines contracts using Python's `Protocol` (duck typing with static checks) |
| [factory.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/backend/fetch_data/factory.py) | `PriceFetcher` | Runtime-checkable protocol for price fetchers |
| [base.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/backend/calculation_v2/components/base.py) | `ResourceCalculator` | Runtime-checkable protocol for cost calculators |

### 5.2 Dependency Injection
| Location | Mechanism | Purpose |
|---|---|---|
| [context.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/context.py) | `DeploymentContext` dataclass | Explicit DI container passed to all deployer functions instead of global state |
| [dependencies.py](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/api/dependencies.py) | FastAPI `Depends()` | Injects auth user, DB sessions into route handlers |
| [dependencies.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/api/dependencies.py) | FastAPI `Depends()` | Injects project path, validation into route handlers |

### 5.3 Error Handling Hierarchy
| Location | Base Exception | Children | Purpose |
|---|---|---|---|
| [exceptions.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/exceptions.py) | `DeploymentError` | `ProviderNotFoundError`, `ConfigurationError`, `ResourceCreationError`, `ResourceDeletionError` | Typed exception hierarchy with provider/layer context |
| [terraform_runner.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/terraform_runner.py) | `TerraformError` | N/A | Wraps CLI failures with command, return code, stderr |
| [error_models.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/api/error_models.py) | `ErrorResponse` | `FieldError` | Pydantic models for structured API error responses |
| [result.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/core/result.dart) | `AppException` | N/A | Domain-specific exception with error codes |

### 5.4 Result Type Pattern (Monadic Error Handling)
| Location | Class | Purpose |
|---|---|---|
| [result.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/core/result.dart) | `sealed class Result<T>` = `Success<T>` \| `Failure<T>` | Kotlin/Rust-style Result type for compile-time safe error handling in Flutter |

### 5.5 Immutable State with `copyWith` Pattern
| Location | Class | Purpose |
|---|---|---|
| [wizard_state.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/bloc/wizard/wizard_state.dart) | `WizardState.copyWith()` | Immutable state transitions — each event produces a new state object |
| Models using `Equatable` | `ProviderCredentials.copyWith()` | Value objects with structural equality |

### 5.6 Data Transfer Object (DTO) / Schema Pattern
| Location | Mechanism | Purpose |
|---|---|---|
| [schemas/](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/schemas) | Pydantic schemas | Separate read/write schemas from ORM models (e.g., `TwinCreate`, `TwinRead`) |
| [error_models.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/api/error_models.py) | `FieldError`, `ErrorResponse` | Structured API response DTOs with OpenAPI documentation |
| [models/](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/models) | Dart model classes | `CalcParams`, `CalcResult`, `Twin`, `User` — JSON serialization/deserialization |

### 5.7 Enum-Based Type Safety
| Location | Enums | Purpose |
|---|---|---|
| [types.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/backend/calculation_v2/components/types.py) | `FormulaType`, `LayerType`, `Provider`, `AWSComponent`, `AzureComponent`, `GCPComponent`, `GlueRole` | Type-safe identifiers for components, layers, providers |
| [function_registry.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/function_registry.py) | `Layer` enum | Type-safe layer numbering (L0–L5) |
| [twin.py](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/models/twin.py) | `TwinState` | Type-safe deployment lifecycle states |

### 5.8 Dataclass / Data Carrier Pattern
| Location | Class | Purpose |
|---|---|---|
| [context.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/context.py) | `ProjectConfig`, `DeploymentContext` | `@dataclass` for structured configuration and deployment state |
| [function_registry.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/function_registry.py) | `FunctionDefinition` | `@dataclass` for serverless function metadata |

### 5.9 Auto-Registration Pattern
| Location | Mechanism | Purpose |
|---|---|---|
| [providers/__init__.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/providers/__init__.py) | Import-time side effects | Importing the package triggers `ProviderRegistry.register()` for each provider module |

### 5.10 Conditional Feature Toggle
| Location | Mechanism | Purpose |
|---|---|---|
| [dependencies.py](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/api/dependencies.py) | `get_current_user = ... if settings.DEBUG else ...` | Swaps auth implementation based on environment flag |
| Terraform `.tf` files | `count = ... ? 1 : 0` | Conditional resource creation based on provider configuration |

---

## 6. Communication / Integration Patterns

### 6.1 Server-Sent Events (SSE) Streaming
| Location | Purpose |
|---|---|
| [sse_service.dart](file:///Users/caroline/git/master-thesis/twin2multicloud_flutter/lib/services/sse_service.dart) | Flutter subscribes to SSE streams for real-time deployment logs |
| [deployment_service.py](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/services/deployment_service.py) | Backend acts as SSE proxy: subscribes to Deployer SSE, forwards to UI |
| Deployer API (deployment endpoints) | Terraform output streamed as SSE events |

### 6.2 API Gateway / BFF (Backend for Frontend)
| Location | Purpose |
|---|---|
| `twin2multicloud_backend` | Acts as a Backend-For-Frontend: aggregates Optimizer + Deployer APIs behind a single REST interface for the Flutter UI |

### 6.3 Proxy Pattern
| Location | Purpose |
|---|---|
| [deployment_service.py](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/services/deployment_service.py) | Backend proxies deployment requests to the Deployer API and streams responses back |

---

## 7. Data / Persistence Patterns

### 7.1 ORM / Active Record Pattern
| Location | Mechanism | Purpose |
|---|---|---|
| [models/](file:///Users/caroline/git/master-thesis/twin2multicloud_backend/src/models) | SQLAlchemy declarative models | `DigitalTwin`, `Deployment`, `User`, etc. map directly to database tables with relationships |

### 7.2 Configuration Loader Pattern (with Fallbacks)
| Location | Purpose |
|---|---|
| [config_loader.py](file:///Users/caroline/git/master-thesis/2-twin2clouds/backend/config_loader.py) | Loads pricing, credentials, regions from JSON files with optional fallbacks |
| [config_loader.py](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/core/config_loader.py) | Loads project config from multiple JSON files into a unified `ProjectConfig` |

---

## 8. Testing Patterns

### 8.1 Test Doubles (Mocking)
- Extensive use of `unittest.mock.patch` and `MagicMock` across all Python test suites
- Provider protocol mocking for isolated layer testing

### 8.2 Fixture-Based Testing
- `conftest.py` files provide shared fixtures (`DeploymentContext`, mock providers)

### 8.3 E2E Clean-Up Pattern
- Dedicated `cleanup_scenario.py` scripts for tearing down cloud resources after E2E tests

---

## Summary Table by Project

| Project | Key Patterns |
|---|---|
| **Optimizer** (`2-twin2clouds`) | Factory, Protocol/Interface, Strategy, Facade, Component Architecture, Enum Type Safety, Config Loader, Pydantic DTOs |
| **Deployer** (`3-cloud-deployer`) | Registry, Strategy, Protocol/Interface, Dependency Injection (Context), Facade, Adapter (TerraformRunner), IaC, Auto-Registration, Exception Hierarchy, Builder (tfvars), Layered Architecture, Function Registry (Dataclass), Feature Toggles |
| **Backend** (`twin2multicloud_backend`) | Service Layer, ORM/Active Record, Pydantic Schemas, SSE Proxy, BFF, Dependency Injection (FastAPI), State Machine (TwinState), Builder (ZIP) |
| **Flutter UI** (`twin2multicloud_flutter`) | BLoC, Observer, State Machine, Result Type, Immutable State (copyWith), SSE Streaming, API Facade, Error Adapter, Command (Events), Enum Type Safety |

---

## Thesis Structure Relevance

These patterns naturally cluster around the following thesis chapters:

1. **System Architecture** → Microservices, Layered Architecture, BFF, IaC, SSE
2. **Implementation / Design Decisions** → Strategy, Registry, Factory, Protocol, DI (Context), Auto-Registration, Result Type, BLoC
3. **Data Flow & Integration** → SSE Streaming, Proxy, Observer, State Machine
4. **Quality & Maintainability** → Exception Hierarchy, DTOs, Immutable State, Testing Patterns, Enum Type Safety
5. **Legacy → Modern Refactoring Story** → How Factory replaced hardcoded spaghetti, how Context replaced global state, how Registry replaced scattered imports
