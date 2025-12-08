# Pattern Analysis & Multi-Cloud Restructure Proposal

> **Purpose:** This document serves two roles:
> 1. **For Humans:** A clear, visual guide to understand the proposed architectural changes
> 2. **For AI Agents:** A detailed blueprint with exact file paths, code structures, and migration steps

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Proposed Design Patterns](#3-proposed-design-patterns)
4. [Proposed Directory Structure](#4-proposed-directory-structure)
5. [Protocol Definitions (Contracts)](#5-protocol-definitions-contracts)
6. [Refactoring Examples](#6-refactoring-examples)
7. [Migration Phases](#7-migration-phases)
8. [AI Agent Implementation Guide](#8-ai-agent-implementation-guide)
9. [Verification Checklist](#9-verification-checklist)

---

## 1. Executive Summary

### The Problem
The current codebase uses `match provider:` switch statements in **20+ functions**. Adding Azure and GCP requires modifying every single function:

```python
# This pattern is repeated 20+ times
def deploy_l1(provider: str | None = None):
    match provider:
        case "aws": ...      # ← Existing
        case "azure": ...    # ← Must add here
        case "google": ...   # ← Must add here
        case _: raise ValueError(...)
```

### The Solution
Introduce **design patterns** that allow adding new cloud providers by **creating new files** rather than modifying existing code.

```
Before: 1 new provider = Modify 20+ files
After:  1 new provider = Create 1 new package (src/providers/azure/)
```

---

## 2. Current State Analysis

### 2.1 Architecture Diagram (Current)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              main.py (CLI)                                  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────────────┐
        │                        │                                │
        ▼                        ▼                                ▼
┌───────────────┐       ┌───────────────┐              ┌───────────────────┐
│ core_deployer │       │ iot_deployer  │              │ event_action_     │
│               │       │               │              │ deployer          │
│ match aws:    │       │ match aws:    │              │ match aws:        │
│ match azure:  │       │ match azure:  │              │ match azure:      │
│ match google: │       │ match google: │              │ match google:     │
└───────┬───────┘       └───────┬───────┘              └─────────┬─────────┘
        │                       │                                │
        ▼                       ▼                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                           src/aws/ (AWS-only implementations)             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────────┐  │
│  │ globals_aws  │  │iot_deployer  │  │  deployer_layers/               │  │
│  │ (clients)    │  │    _aws      │  │  ├─ layer_1_iot.py              │  │
│  └──────────────┘  └──────────────┘  │  ├─ layer_2_compute.py          │  │
│                                      │  ├─ layer_3_storage.py          │  │
│                                      │  ├─ layer_4_twinmaker.py        │  │
│                                      │  └─ layer_5_grafana.py          │  │
│                                      └─────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Patterns Currently In Use

| Pattern | Location | How It's Used |
|---------|----------|---------------|
| **Facade** | `core_deployer_aws.py` | Re-exports functions from `deployer_layers/*` |
| **Template Method** | `deploy_l1()`, `deploy_l2()`, etc. | Same structure, different provider implementations |
| **Global State** | `globals.py`, `globals_aws.py` | Shared configuration and AWS clients |
| **Layered Architecture** | `deployer_layers/` | Separation by Digital Twin layer (L1-L5) |

### 2.3 Problems with Current Approach

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Problem: Adding a new provider requires modifying MANY files               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   File: src/deployers/core_deployer.py                                      │
│   ├── deploy_l1()      [MODIFY]  ← Add case "azure"                         │
│   ├── destroy_l1()     [MODIFY]  ← Add case "azure"                         │
│   ├── deploy_l2()      [MODIFY]  ← Add case "azure"                         │
│   ├── destroy_l2()     [MODIFY]  ← Add case "azure"                         │
│   ├── deploy_l3_hot()  [MODIFY]  ← Add case "azure"                         │
│   ├── ... (15+ more functions)                                              │
│                                                                             │
│   File: src/deployers/iot_deployer.py                                       │
│   ├── deploy_l1()      [MODIFY]  ← Add case "azure"                         │
│   ├── destroy_l1()     [MODIFY]  ← Add case "azure"                         │
│   └── ... (5+ more functions)                                               │
│                                                                             │
│   Total files to modify: 5+                                                 │
│   Total functions to modify: 20+                                            │
│                                                                             │
│   Risk: High chance of missing a case or introducing bugs                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Proposed Design Patterns

### 3.1 Strategy Pattern

> **Definition:** The Strategy Pattern defines a family of algorithms, encapsulates each one, and makes them interchangeable. It lets the algorithm vary independently from clients that use it.

#### Why Use It Here?
Each cloud provider (AWS, Azure, GCP) has different ways to deploy the same logical layer. The Strategy pattern allows us to swap implementations without changing the code that uses them.

#### Diagram

```
                          ┌─────────────────────────┐
                          │   DeployerStrategy      │  ← Interface/Protocol
                          │   (Abstract)            │
                          ├─────────────────────────┤
                          │ + deploy_l1(context)    │
                          │ + destroy_l1(context)   │
                          │ + deploy_l2(context)    │
                          │ + destroy_l2(context)   │
                          │ + ...                   │
                          └───────────┬─────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │ implements            │ implements            │ implements
              ▼                       ▼                       ▼
    ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
    │ AWSDeployerStrategy │ │AzureDeployerStrategy│ │ GCPDeployerStrategy │
    ├─────────────────────┤ ├─────────────────────┤ ├─────────────────────┤
    │ Uses boto3, Lambda, │ │ Uses azure-sdk,     │ │ Uses google-cloud,  │
    │ DynamoDB, TwinMaker │ │ Functions, CosmosDB │ │ Pub/Sub, Firestore  │
    └─────────────────────┘ └─────────────────────┘ └─────────────────────┘
```

#### Code Integration

```python
# BEFORE (current code in core_deployer.py)
def deploy_l1(provider: str | None = None):
    match provider:
        case "aws":
            core_aws.create_dispatcher_iam_role()
            core_aws.create_dispatcher_lambda_function()
            core_aws.create_dispatcher_iot_rule()
        case "azure":
            raise NotImplementedError(...)
        # ... more cases

# AFTER (using Strategy Pattern)
def deploy_l1(context: DeploymentContext):
    provider = context.get_provider_for_layer(1)
    strategy = provider.get_deployer_strategy()
    strategy.deploy_l1(context)  # ← Calls the right implementation automatically
```

---

### 3.2 Provider Pattern (Abstract Factory)

> **Definition:** The Abstract Factory Pattern provides an interface for creating families of related objects without specifying their concrete classes.

#### Why Use It Here?
Each cloud provider needs multiple related objects: SDK clients, resource name generators, and deployer strategies. The Provider pattern groups these together.

#### Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CloudProvider (Protocol)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  Properties:                                                                │
│   - name: str                       ← "aws", "azure", or "gcp"              │
│                                                                             │
│  Methods:                                                                   │
│   - initialize_clients(credentials) ← Create SDK clients (boto3, etc.)      │
│   - get_resource_name(type, suffix) ← Generate "{twin}-{type}-{suffix}"     │
│   - get_deployer_strategy()         ← Return the Strategy for this provider │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ implements
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        ▼                             ▼                             ▼
┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
│    AWSProvider    │       │   AzureProvider   │       │    GCPProvider    │
├───────────────────┤       ├───────────────────┤       ├───────────────────┤
│ name = "aws"      │       │ name = "azure"    │       │ name = "gcp"      │
│                   │       │                   │       │                   │
│ Clients:          │       │ Clients:          │       │ Clients:          │
│  - iam_client     │       │  - resource_mgmt  │       │  - pubsub_client  │
│  - lambda_client  │       │  - functions_mgmt │       │  - functions_     │
│  - iot_client     │       │  - cosmos_client  │       │  - firestore_     │
│  - dynamodb_      │       │  - storage_client │       │  - storage_client │
│  - s3_client      │       │  - iot_hub_client │       │                   │
│  - twinmaker_     │       │  - digital_twins_ │       │                   │
│  - grafana_       │       │  - grafana_       │       │                   │
│                   │       │                   │       │                   │
│ Strategy:         │       │ Strategy:         │       │ Strategy:         │
│  AWSDeployer      │       │  AzureDeployer    │       │  GCPDeployer      │
│  Strategy         │       │  Strategy         │       │  Strategy         │
└───────────────────┘       └───────────────────┘       └───────────────────┘
```

#### Code Integration

```python
# File: src/providers/aws/provider.py
class AWSProvider:
    """Concrete implementation of CloudProvider for AWS."""
    
    name = "aws"
    
    def __init__(self):
        self._clients = {}
        self._strategy = None
    
    def initialize_clients(self, credentials: dict):
        """Initialize all AWS SDK clients."""
        import boto3
        session = boto3.Session(
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region_name=credentials["aws_region"]
        )
        self._clients = {
            "iam": session.client("iam"),
            "lambda": session.client("lambda"),
            "iot": session.client("iot"),
            "dynamodb": session.client("dynamodb"),
            # ... more clients
        }
    
    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """Generate AWS resource name: {twin_name}-{type}[-{suffix}]"""
        base = f"{self._twin_name}-{resource_type}"
        return f"{base}-{suffix}" if suffix else base
    
    def get_deployer_strategy(self) -> 'AWSDeployerStrategy':
        if not self._strategy:
            self._strategy = AWSDeployerStrategy(self)
        return self._strategy
```

---

### 3.3 Dependency Injection via Context

> **Definition:** Dependency Injection is a technique where objects receive their dependencies from external sources rather than creating them internally.

#### Why Use It Here?
The current code uses global variables (`globals.config`, `globals_aws.aws_lambda_client`). This makes testing difficult and creates hidden dependencies. A **Context** object makes dependencies explicit.

#### Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DeploymentContext                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Project Info:                                                              │
│   ├── project_name: str              ← "my-factory-twin"                    │
│   └── project_path: Path             ← /app/upload/my-factory-twin/         │
│                                                                             │
│  Configuration:                                                             │
│   └── config: ProjectConfig                                                 │
│        ├── digital_twin_name: str    ← "dt"                                 │
│        ├── hot_storage_size: int     ← 30 (days)                            │
│        ├── cold_storage_size: int    ← 90 (days)                            │
│        ├── iot_devices: list[dict]   ← [{id: "sensor-1", ...}]              │
│        ├── events: list[dict]        ← [{condition: ..., action: ...}]      │
│        ├── providers: dict           ← {layer_1: "aws", layer_2: "azure"}   │
│        └── optimization: dict        ← {useEventChecking: true, ...}        │
│                                                                             │
│  Runtime Objects:                                                           │
│   ├── providers: dict[str, CloudProvider]                                   │
│   │    ├── "aws"   → AWSProvider instance                                   │
│   │    ├── "azure" → AzureProvider instance                                 │
│   │    └── "gcp"   → GCPProvider instance                                   │
│   └── credentials: dict[str, dict]                                          │
│        ├── "aws"   → {access_key, secret_key, region}                       │
│        └── "azure" → {subscription_id, tenant_id, ...}                      │
│                                                                             │
│  Helper Methods:                                                            │
│   └── get_provider_for_layer(layer: int) → CloudProvider                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                              Flow Diagram
                              ────────────
                                   │
                      ┌────────────┴────────────┐
                      │   Create Context        │
                      │   (once per deployment) │
                      └────────────┬────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
            ▼                      ▼                      ▼
    ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
    │  deploy_l1()  │      │  deploy_l2()  │      │  deploy_l3()  │
    │               │      │               │      │               │
    │ Receives ctx  │      │ Receives ctx  │      │ Receives ctx  │
    │ Uses provider │      │ Uses provider │      │ Uses provider │
    │ from ctx      │      │ from ctx      │      │ from ctx      │
    └───────────────┘      └───────────────┘      └───────────────┘
```

#### Code Integration

```python
# BEFORE (using globals)
import globals
import aws.globals_aws as globals_aws

def create_dispatcher_lambda_function():
    function_name = globals_aws.dispatcher_lambda_function_name()  # ← Global
    role_name = globals_aws.dispatcher_iam_role_name()             # ← Global
    
    response = globals_aws.aws_iam_client.get_role(RoleName=role_name)  # ← Global
    role_arn = response['Role']['Arn']
    
    globals_aws.aws_lambda_client.create_function(...)  # ← Global

# AFTER (using Context)
def create_dispatcher_lambda_function(context: DeploymentContext):
    provider = context.get_provider_for_layer(1)  # ← Explicit
    
    function_name = provider.get_resource_name("dispatcher")  # ← From provider
    role_name = provider.get_resource_name("dispatcher-role") # ← From provider
    
    iam_client = provider.clients["iam"]  # ← From provider
    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']
    
    lambda_client = provider.clients["lambda"]  # ← From provider
    lambda_client.create_function(...)
```

---

### 3.4 Registry Pattern

> **Definition:** The Registry Pattern provides a well-known object that other objects can use to find common objects and services.

#### Why Use It Here?
We need a central place to register and look up cloud providers by name. This allows dynamic provider loading and makes the system extensible.

#### Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ProviderRegistry                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Class Attributes:                                                          │
│   └── _providers: dict[str, type[CloudProvider]] = {                        │
│         "aws": AWSProvider,                                                 │
│         "azure": AzureProvider,                                             │
│         "gcp": GCPProvider                                                  │
│       }                                                                     │
│                                                                             │
│  Class Methods:                                                             │
│   ├── register(name, provider_class)  ← Add a new provider                  │
│   ├── get(name) → CloudProvider       ← Get instance by name                │
│   └── list_providers() → list[str]    ← Get all registered names            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                         Registration Flow
                         ─────────────────

    ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
    │  providers/aws/ │      │ providers/azure/│      │  providers/gcp/ │
    │   __init__.py   │      │   __init__.py   │      │   __init__.py   │
    └────────┬────────┘      └────────┬────────┘      └────────┬────────┘
             │                        │                        │
             │ import                 │ import                 │ import
             ▼                        ▼                        ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                                                                    │
    │   ProviderRegistry.register("aws", AWSProvider)                    │
    │   ProviderRegistry.register("azure", AzureProvider)                │
    │   ProviderRegistry.register("gcp", GCPProvider)                    │
    │                                                                    │
    └────────────────────────────────────────────────────────────────────┘

                          Usage Flow
                          ──────────

    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │   # In core_deployer.py or main.py                                  │
    │                                                                     │
    │   provider_name = config.providers["layer_1_provider"]  # "azure"   │
    │   provider = ProviderRegistry.get(provider_name)                    │
    │   provider.initialize_clients(credentials["azure"])                 │
    │   strategy = provider.get_deployer_strategy()                       │
    │   strategy.deploy_l1(context)                                       │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
```

#### Code Integration

```python
# File: src/core/registry.py
class ProviderRegistry:
    """
    Central registry for cloud provider implementations.
    Providers register themselves when their module is imported.
    """
    
    _providers: dict[str, type['CloudProvider']] = {}
    
    @classmethod
    def register(cls, name: str, provider_class: type['CloudProvider']):
        """Register a provider class under a name."""
        cls._providers[name] = provider_class
    
    @classmethod
    def get(cls, name: str) -> 'CloudProvider':
        """Get a new instance of the named provider."""
        if name not in cls._providers:
            raise ValueError(f"Unknown provider: {name}. Available: {list(cls._providers.keys())}")
        return cls._providers[name]()
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())


# File: src/providers/aws/__init__.py
from .provider import AWSProvider
from core.registry import ProviderRegistry

# Self-registration when module is imported
ProviderRegistry.register("aws", AWSProvider)
```

---

## 4. Proposed Directory Structure

```
src/
├── __init__.py
├── main.py                          # CLI entry point (minimal changes)
├── constants.py                     # Global constants (unchanged)
├── logger.py                        # Logging utilities (unchanged)
├── util.py                          # General utilities (unchanged)
│
├── core/                            # ━━━━ [NEW] Core abstractions ━━━━
│   ├── __init__.py
│   ├── protocols.py                 # Protocol/ABC definitions (CloudProvider, etc.)
│   ├── context.py                   # DeploymentContext (replaces globals)
│   ├── registry.py                  # ProviderRegistry (dynamic lookup)
│   ├── config_loader.py             # Config loading (extracted from globals.py)
│   └── exceptions.py                # Custom exceptions (DeploymentError, etc.)
│
├── providers/                       # ━━━━ [NEW] Provider implementations ━━━━
│   ├── __init__.py                  # Imports all providers for auto-registration
│   ├── base.py                      # Shared base classes and utilities
│   │
│   ├── aws/                         # ━━━━ [REFACTORED from src/aws/] ━━━━
│   │   ├── __init__.py              # Auto-registers AWSProvider
│   │   ├── provider.py              # AWSProvider class
│   │   ├── clients.py               # AWS client initialization
│   │   ├── naming.py                # Resource naming functions
│   │   ├── deployer_strategy.py     # AWSDeployerStrategy
│   │   └── layers/                  # Layer-specific deployment logic
│   │       ├── __init__.py
│   │       ├── l1_iot.py            # ← From deployer_layers/layer_1_iot.py
│   │       ├── l2_compute.py        # ← From deployer_layers/layer_2_compute.py
│   │       ├── l3_storage.py        # ← From deployer_layers/layer_3_storage.py
│   │       ├── l4_twinmaker.py      # ← From deployer_layers/layer_4_twinmaker.py
│   │       └── l5_grafana.py        # ← From deployer_layers/layer_5_grafana.py
│   │
│   ├── azure/                       # ━━━━ [NEW] Azure provider ━━━━
│   │   ├── __init__.py              # Auto-registers AzureProvider
│   │   ├── provider.py              # AzureProvider class
│   │   ├── clients.py               # Azure SDK client initialization
│   │   ├── naming.py                # Azure resource naming conventions
│   │   ├── deployer_strategy.py     # AzureDeployerStrategy
│   │   └── layers/
│   │       ├── __init__.py
│   │       ├── l1_iot_hub.py        # IoT Hub deployment
│   │       ├── l2_functions.py      # Azure Functions deployment
│   │       ├── l3_storage.py        # Cosmos DB + Blob Storage
│   │       ├── l4_digital_twins.py  # Azure Digital Twins
│   │       └── l5_grafana.py        # Azure Managed Grafana
│   │
│   └── gcp/                         # ━━━━ [NEW] GCP provider ━━━━
│       ├── __init__.py              # Auto-registers GCPProvider
│       ├── provider.py              # GCPProvider class
│       ├── clients.py               # Google Cloud client initialization
│       ├── naming.py                # GCP resource naming conventions
│       ├── deployer_strategy.py     # GCPDeployerStrategy
│       └── layers/
│           ├── __init__.py
│           ├── l1_pubsub.py         # Cloud Pub/Sub deployment
│           ├── l2_functions.py      # Cloud Functions deployment
│           ├── l3_storage.py        # Firestore + Cloud Storage
│           ├── l4_custom.py         # Custom Digital Twin solution
│           └── l5_grafana.py        # Self-hosted Grafana on GCE/GKE
│
├── deployers/                       # ━━━━ [SIMPLIFIED] Orchestrators ━━━━
│   ├── __init__.py
│   ├── core_deployer.py             # Now uses Strategy pattern (20 lines vs 334)
│   ├── iot_deployer.py              # Now uses Strategy pattern
│   ├── additional_deployer.py       # Entity hierarchy deployment
│   ├── event_action_deployer.py     # Event action Lambda deployment
│   └── init_values_deployer.py      # Initial values deployment
│
├── validation/                      # ━━━━ [REFACTORED] Validators ━━━━
│   ├── __init__.py
│   ├── config_validator.py          # Config file validation
│   ├── code_validator.py            # Lambda code validation
│   └── project_validator.py         # Project structure validation
│
├── file_manager.py                  # File operations (unchanged)
├── info.py                          # Info commands (minimal changes)
├── globals.py                       # ━━━━ [DEPRECATED] → Use context.py ━━━━
└── validator.py                     # ━━━━ [DEPRECATED] → Use validation/ ━━━━
```

---

## 5. Protocol Definitions (Contracts)

### 5.1 CloudProvider Protocol

```python
# File: src/core/protocols.py

from typing import Protocol, runtime_checkable, TypeVar, Dict, Any
from pathlib import Path

@runtime_checkable
class CloudProvider(Protocol):
    """
    Protocol defining the interface for a cloud provider.
    
    Each cloud (AWS, Azure, GCP) must implement this interface.
    The @runtime_checkable decorator allows isinstance() checks.
    """
    
    @property
    def name(self) -> str:
        """
        Return the provider identifier.
        
        Returns:
            One of: "aws", "azure", "gcp"
        """
        ...
    
    @property
    def clients(self) -> Dict[str, Any]:
        """
        Return initialized SDK clients.
        
        Returns:
            Dict mapping service names to client instances.
            Example: {"iam": boto3.client("iam"), "lambda": boto3.client("lambda")}
        """
        ...
    
    def initialize_clients(self, credentials: dict) -> None:
        """
        Initialize SDK clients for this provider.
        
        Args:
            credentials: Dictionary containing provider-specific credentials.
                AWS: {aws_access_key_id, aws_secret_access_key, aws_region}
                Azure: {subscription_id, tenant_id, client_id, client_secret, region}
                GCP: {project_id, credentials_file, region}
        """
        ...
    
    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """
        Generate a namespaced resource name.
        
        Args:
            resource_type: Type of resource (e.g., "dispatcher", "hot-table")
            suffix: Optional suffix (e.g., device ID)
        
        Returns:
            Formatted name like "{twin_name}-{resource_type}[-{suffix}]"
        """
        ...
    
    def get_deployer_strategy(self) -> 'DeployerStrategy':
        """
        Return the deployment strategy for this provider.
        
        Returns:
            An instance of a class implementing DeployerStrategy.
        """
        ...
```

### 5.2 DeployerStrategy Protocol

```python
# File: src/core/protocols.py (continued)

@runtime_checkable
class DeployerStrategy(Protocol):
    """
    Protocol defining the deployment strategy interface.
    
    Each provider implements this to handle layer-by-layer deployment.
    """
    
    def deploy_l1(self, context: 'DeploymentContext') -> None:
        """Deploy Layer 1 (Data Acquisition): IoT Core/Hub/Pub/Sub."""
        ...
    
    def destroy_l1(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 1 resources."""
        ...
    
    def deploy_l2(self, context: 'DeploymentContext') -> None:
        """Deploy Layer 2 (Processing): Lambda/Functions."""
        ...
    
    def destroy_l2(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 2 resources."""
        ...
    
    def deploy_l3(self, context: 'DeploymentContext') -> None:
        """Deploy Layer 3 (Storage): Hot/Cold/Archive."""
        ...
    
    def destroy_l3(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 3 resources."""
        ...
    
    def deploy_l4(self, context: 'DeploymentContext') -> None:
        """Deploy Layer 4 (Twin Management): TwinMaker/Digital Twins."""
        ...
    
    def destroy_l4(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 4 resources."""
        ...
    
    def deploy_l5(self, context: 'DeploymentContext') -> None:
        """Deploy Layer 5 (Visualization): Grafana."""
        ...
    
    def destroy_l5(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 5 resources."""
        ...
    
    def deploy_all(self, context: 'DeploymentContext') -> None:
        """Deploy all layers in order (L1 → L5)."""
        ...
    
    def destroy_all(self, context: 'DeploymentContext') -> None:
        """Destroy all layers in reverse order (L5 → L1)."""
        ...
```

### 5.3 DeploymentContext

```python
# File: src/core/context.py

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path

@dataclass
class ProjectConfig:
    """
    Parsed project configuration from JSON files.
    Replaces the global variables in globals.py.
    """
    digital_twin_name: str
    hot_storage_size_in_days: int
    cold_storage_size_in_days: int
    mode: str
    iot_devices: list[dict]
    events: list[dict]
    hierarchy: list[dict]
    providers: dict[str, str]       # {layer_1_provider: "aws", ...}
    optimization: dict              # {useEventChecking: true, ...}
    inter_cloud: dict               # {connections: {...}}
    

@dataclass
class DeploymentContext:
    """
    Encapsulates all state needed for a deployment operation.
    
    This replaces global variables and is explicitly passed to all
    deployer functions, making dependencies clear and testing easy.
    """
    
    # Project identification
    project_name: str
    project_path: Path
    
    # Parsed configuration
    config: ProjectConfig
    
    # Initialized provider instances (populated by initialize_providers())
    providers: Dict[str, 'CloudProvider'] = field(default_factory=dict)
    
    # Credentials by provider name
    credentials: Dict[str, dict] = field(default_factory=dict)
    
    # Optional: currently active layer (for logging)
    active_layer: Optional[int] = None
    
    def get_provider_for_layer(self, layer: int) -> 'CloudProvider':
        """
        Get the CloudProvider instance assigned to a specific layer.
        
        Args:
            layer: Layer number (1-5) or special keys like "3_hot", "3_cold"
        
        Returns:
            The CloudProvider instance for that layer.
        
        Raises:
            ValueError: If no provider is configured for the layer.
        """
        # Map layer number to config key
        if isinstance(layer, int):
            if layer == 3:
                layer_key = "layer_3_hot_provider"  # Default to hot for L3
            else:
                layer_key = f"layer_{layer}_provider"
        else:
            layer_key = f"layer_{layer}_provider"  # e.g., "3_hot", "3_cold"
        
        provider_name = self.config.providers.get(layer_key)
        if not provider_name:
            raise ValueError(f"No provider configured for {layer_key}")
        
        if provider_name not in self.providers:
            raise ValueError(f"Provider '{provider_name}' not initialized")
        
        return self.providers[provider_name]
    
    def get_upload_path(self, *subpaths) -> Path:
        """Get a path within the project upload directory."""
        return self.project_path / "upload" / self.project_name / Path(*subpaths)
```

---

## 6. Refactoring Examples

### 6.1 core_deployer.py (Before vs After)

#### Before (Current: 334 lines)

```python
# File: src/deployers/core_deployer.py (BEFORE)

from typing import Literal
import globals
import aws.core_deployer_aws as core_aws
from logger import logger

Provider = Literal["aws", "azure", "google"]

def deploy_l1(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    match provider:
        case "aws":
            logger.info("Deploying L1 for AWS...")
            logger.info("Creating dispatcher IAM role...")
            core_aws.create_dispatcher_iam_role()
            logger.info("Creating dispatcher lambda function...")
            core_aws.create_dispatcher_lambda_function()
            logger.info("Creating dispatcher IoT rule...")
            core_aws.create_dispatcher_iot_rule()
        case "azure":
            raise NotImplementedError("Azure deployment not implemented yet.")
        case "google":
            raise NotImplementedError("Google deployment not implemented yet.")
        case _:
            raise ValueError(f"Unsupported provider: '{provider}'")

def destroy_l1(provider: str | None = None) -> None:
    # ... same pattern repeated ...

def deploy_l2(provider: str | None = None) -> None:
    # ... same pattern repeated ...

# ... 15+ more functions with same pattern ...
```

#### After (Proposed: ~50 lines)

```python
# File: src/deployers/core_deployer.py (AFTER)

from core.context import DeploymentContext
from logger import logger

def deploy_l1(context: DeploymentContext) -> None:
    """
    Deploy Layer 1 (Data Acquisition) using the configured provider.
    
    Args:
        context: The deployment context containing config and providers.
    """
    context.active_layer = 1
    provider = context.get_provider_for_layer(1)
    logger.info(f"Deploying L1 for {provider.name}...")
    
    strategy = provider.get_deployer_strategy()
    strategy.deploy_l1(context)


def destroy_l1(context: DeploymentContext) -> None:
    """Destroy Layer 1 resources."""
    context.active_layer = 1
    provider = context.get_provider_for_layer(1)
    logger.info(f"Destroying L1 for {provider.name}...")
    
    strategy = provider.get_deployer_strategy()
    strategy.destroy_l1(context)


def deploy_l2(context: DeploymentContext) -> None:
    """Deploy Layer 2 (Processing) using the configured provider."""
    context.active_layer = 2
    provider = context.get_provider_for_layer(2)
    logger.info(f"Deploying L2 for {provider.name}...")
    
    strategy = provider.get_deployer_strategy()
    strategy.deploy_l2(context)


# ... similar pattern for L3, L4, L5 ...


def deploy_all(context: DeploymentContext) -> None:
    """Deploy all layers in order."""
    deploy_l1(context)
    deploy_l2(context)
    deploy_l3(context)
    deploy_l4(context)
    deploy_l5(context)


def destroy_all(context: DeploymentContext) -> None:
    """Destroy all layers in reverse order."""
    destroy_l5(context)
    destroy_l4(context)
    destroy_l3(context)
    destroy_l2(context)
    destroy_l1(context)
```

---

## 7. Migration Phases

### Phase 1: Foundation (Non-Breaking)
**Goal:** Create new infrastructure without breaking existing code.

| Step | File/Directory | Action |
|------|----------------|--------|
| 1.1 | `src/core/__init__.py` | Create empty package |
| 1.2 | `src/core/protocols.py` | Define CloudProvider, DeployerStrategy protocols |
| 1.3 | `src/core/context.py` | Define ProjectConfig, DeploymentContext |
| 1.4 | `src/core/registry.py` | Define ProviderRegistry |
| 1.5 | `src/core/config_loader.py` | Extract config loading from globals.py |
| 1.6 | `src/core/exceptions.py` | Define custom exceptions |
| 1.7 | `src/providers/__init__.py` | Create empty package |
| 1.8 | `src/providers/base.py` | Create shared base utilities |

**Verification:** All existing tests pass. New modules are importable.

---

### Phase 2: AWS Refactor
**Goal:** Wrap existing AWS code in new pattern without rewriting logic.

| Step | File/Directory | Action |
|------|----------------|--------|
| 2.1 | `src/providers/aws/__init__.py` | Create package, register provider |
| 2.2 | `src/providers/aws/provider.py` | Create AWSProvider class |
| 2.3 | `src/providers/aws/clients.py` | Move code from globals_aws.py (client init) |
| 2.4 | `src/providers/aws/naming.py` | Move code from globals_aws.py (naming funcs) |
| 2.5 | `src/providers/aws/deployer_strategy.py` | Wrap existing layer modules |
| 2.6 | `src/providers/aws/layers/` | Move from `src/aws/deployer_layers/` |
| 2.7 | `src/deployers/core_deployer.py` | Add new context-based functions alongside old |

**Verification:** Existing code still works. New pattern can be used optionally.

---

### Phase 3: Azure/GCP Scaffolding
**Goal:** Create stub implementations for Azure and GCP.

| Step | File/Directory | Action |
|------|----------------|--------|
| 3.1 | `src/providers/azure/` | Create full package structure |
| 3.2 | `src/providers/azure/provider.py` | Implement AzureProvider |
| 3.3 | `src/providers/azure/layers/l1_iot_hub.py` | Implement L1 for Azure |
| 3.4 | `src/providers/gcp/` | Create full package structure |
| 3.5 | `src/providers/gcp/provider.py` | Implement GCPProvider |
| 3.6 | `src/providers/gcp/layers/l1_pubsub.py` | Implement L1 for GCP |

**Verification:** Azure/GCP L1 can be deployed. Integration tests pass.

---

### Phase 4: Full Migration
**Goal:** Remove legacy switch statements and globals.

| Step | File/Directory | Action |
|------|----------------|--------|
| 4.1 | `src/deployers/*.py` | Remove old `match provider:` functions |
| 4.2 | `src/main.py` | Update CLI to create DeploymentContext |
| 4.3 | `api/*.py` | Update API to create DeploymentContext |
| 4.4 | `tests/` | Update all tests for new pattern |
| 4.5 | `src/globals.py` | Mark as deprecated, add migration notes |
| 4.6 | `src/aws/` | Delete (replaced by `src/providers/aws/`) |

**Verification:** All tests pass. Full deployment works on all providers.

---

## 8. AI Agent Implementation Guide

> **Instructions for AI Agents:** Follow these steps when implementing this plan.

### 8.1 Phase 1 Commands (Foundation)

```bash
# Create core package structure
mkdir -p src/core
touch src/core/__init__.py
touch src/core/protocols.py
touch src/core/context.py
touch src/core/registry.py
touch src/core/config_loader.py
touch src/core/exceptions.py

# Create providers package structure
mkdir -p src/providers
touch src/providers/__init__.py
touch src/providers/base.py
```

### 8.2 File Templates

#### `src/core/__init__.py`
```python
"""
Core abstractions for the multi-cloud deployer.

This package contains:
- protocols: Interface definitions (CloudProvider, DeployerStrategy)
- context: DeploymentContext for dependency injection
- registry: ProviderRegistry for dynamic provider lookup
- config_loader: Configuration loading utilities
- exceptions: Custom exception types
"""

from .protocols import CloudProvider, DeployerStrategy
from .context import DeploymentContext, ProjectConfig
from .registry import ProviderRegistry

__all__ = [
    "CloudProvider",
    "DeployerStrategy",
    "DeploymentContext",
    "ProjectConfig",
    "ProviderRegistry",
]
```

#### `src/providers/__init__.py`
```python
"""
Cloud provider implementations.

Importing this package automatically registers all providers.
"""

# Import providers to trigger auto-registration
from . import aws
# from . import azure  # Uncomment when implemented
# from . import gcp    # Uncomment when implemented
```

### 8.3 Testing Strategy

```python
# File: tests/unit/core/test_protocols.py

def test_aws_provider_implements_protocol():
    """Verify AWSProvider implements CloudProvider protocol."""
    from core.protocols import CloudProvider
    from providers.aws.provider import AWSProvider
    
    assert isinstance(AWSProvider(), CloudProvider)


def test_registry_returns_correct_provider():
    """Verify registry returns the correct provider by name."""
    from core.registry import ProviderRegistry
    
    provider = ProviderRegistry.get("aws")
    assert provider.name == "aws"


def test_context_provides_correct_provider_for_layer():
    """Verify context maps layers to providers correctly."""
    from core.context import DeploymentContext, ProjectConfig
    
    config = ProjectConfig(
        digital_twin_name="test",
        providers={"layer_1_provider": "aws", "layer_2_provider": "azure"},
        # ... other fields
    )
    context = DeploymentContext(
        project_name="test",
        project_path=Path("/tmp"),
        config=config,
    )
    # Initialize providers...
    
    assert context.get_provider_for_layer(1).name == "aws"
    assert context.get_provider_for_layer(2).name == "azure"
```

### 8.4 Checklist for Each New Provider

When implementing a new provider (e.g., Azure):

- [ ] Create `src/providers/azure/__init__.py`
- [ ] Create `src/providers/azure/provider.py` with `AzureProvider` class
- [ ] Create `src/providers/azure/clients.py` with Azure SDK initialization
- [ ] Create `src/providers/azure/naming.py` with naming conventions
- [ ] Create `src/providers/azure/deployer_strategy.py` with `AzureDeployerStrategy`
- [ ] Create `src/providers/azure/layers/` directory with L1-L5 modules
- [ ] Add `from . import azure` to `src/providers/__init__.py`
- [ ] Add unit tests for `AzureProvider`
- [ ] Add integration tests for Azure deployment
- [ ] Update documentation

---

## 9. Test Structure Analysis & Recommendations

### 9.1 Current Test Structure

```
tests/
├── conftest.py                      # Global fixtures (mock_globals, mock_env_vars)
├── api/                             # API endpoint tests
│   ├── test_rest_api.py             # Basic REST API tests
│   ├── test_simulator.py            # Simulator endpoint tests
│   └── test_uploads.py              # Upload endpoint tests
├── unit/                            # Unit tests
│   ├── test_globals.py              # globals.py tests
│   ├── test_util.py                 # util.py tests
│   ├── test_util_aws.py             # AWS utility tests
│   ├── test_validation.py           # Validator tests
│   └── lambda_functions/            # Lambda function unit tests
├── integration/                     # Integration tests
│   ├── aws/                         # AWS-specific integration tests
│   │   ├── test_aws_l1_dispatcher.py
│   │   ├── test_aws_l2_compute.py
│   │   ├── test_aws_l3_storage.py
│   │   ├── test_aws_l3_movers.py
│   │   ├── test_aws_l3_readers.py
│   │   ├── test_aws_l4_l5_mocked.py
│   │   ├── test_aws_api_gateway.py
│   │   ├── test_aws_event_actions.py
│   │   ├── test_aws_dynamic_deployment.py
│   │   └── test_aws_simulator_config.py
│   ├── azure/                       # Empty (ready for Azure tests)
│   └── google/                      # Empty (ready for GCP tests)
├── deployers/                       # Deployer logic tests
│   └── test_aws_connector_logic.py  # Connector pattern tests
├── test_cli_simulate.py             # CLI simulation tests
├── test_credentials_checker.py      # Credentials validation tests
├── test_lambda_cli_safety.py        # Lambda safety tests
└── test_multi_project.py            # Multi-project support tests
```

### 9.2 Test Changes Required for Refactor

| Category | Current State | Required Changes |
|----------|---------------|------------------|
| **conftest.py** | Mocks `globals.py` directly | Add fixtures for `DeploymentContext` |
| **Unit tests** | Test individual functions | Add tests for protocols, registry, context |
| **Integration/aws/** | Test AWS deployers directly | Update imports to use new `providers/aws/` path |
| **Integration/azure/** | Empty directory | Keep empty (Azure implementation later) |
| **Deployers** | Tests connector logic | Update to use Strategy pattern tests |

### 9.3 New Tests Needed

#### Core Package Tests (`tests/unit/core/`)

```
tests/unit/core/
├── __init__.py
├── test_protocols.py        # Protocol compliance tests
├── test_context.py          # DeploymentContext tests
├── test_registry.py         # ProviderRegistry tests
└── test_config_loader.py    # Config loading tests
```

**Key Test Cases:**

```python
# tests/unit/core/test_protocols.py

def test_aws_provider_implements_cloud_provider_protocol():
    """Verify AWSProvider satisfies CloudProvider protocol."""
    from core.protocols import CloudProvider
    from providers.aws.provider import AWSProvider
    assert isinstance(AWSProvider(), CloudProvider)

def test_aws_strategy_implements_deployer_strategy_protocol():
    """Verify AWSDeployerStrategy satisfies DeployerStrategy protocol."""
    from core.protocols import DeployerStrategy
    from providers.aws.deployer_strategy import AWSDeployerStrategy
    # ... create with mock provider
    assert isinstance(strategy, DeployerStrategy)
```

```python
# tests/unit/core/test_context.py

def test_get_provider_for_layer_returns_correct_provider():
    """Test layer-to-provider mapping."""
    context = create_test_context(providers={
        "layer_1_provider": "aws",
        "layer_2_provider": "azure"
    })
    assert context.get_provider_for_layer(1).name == "aws"
    assert context.get_provider_for_layer(2).name == "azure"

def test_get_provider_for_missing_layer_raises_error():
    """Test error handling for unconfigured layers."""
    context = create_test_context(providers={})
    with pytest.raises(ValueError):
        context.get_provider_for_layer(1)
```

```python
# tests/unit/core/test_registry.py

def test_registry_registers_and_retrieves_provider():
    """Test provider registration and retrieval."""
    from core.registry import ProviderRegistry
    
    class MockProvider:
        name = "mock"
    
    ProviderRegistry.register("mock", MockProvider)
    provider = ProviderRegistry.get("mock")
    assert provider.name == "mock"

def test_registry_raises_error_for_unknown_provider():
    """Test error handling for unknown providers."""
    from core.registry import ProviderRegistry
    with pytest.raises(ValueError):
        ProviderRegistry.get("nonexistent")
```

### 9.4 Test Fixture Updates

Update `conftest.py` to support both old and new patterns:

```python
# tests/conftest.py (additions)

from core.context import DeploymentContext, ProjectConfig
from core.registry import ProviderRegistry

@pytest.fixture
def test_project_config():
    """Create a test ProjectConfig object."""
    return ProjectConfig(
        digital_twin_name="test-twin",
        hot_storage_size_in_days=30,
        cold_storage_size_in_days=90,
        mode="DEBUG",
        iot_devices=[{"id": "device-1", "iotDeviceId": "device-1", "properties": []}],
        events=[],
        hierarchy=[],
        providers={
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "aws",
            "layer_4_provider": "aws",
            "layer_5_provider": "aws"
        },
        optimization={},
        inter_cloud={}
    )

@pytest.fixture
def test_deployment_context(test_project_config, tmp_path):
    """Create a test DeploymentContext with mocked providers."""
    context = DeploymentContext(
        project_name="test-project",
        project_path=tmp_path,
        config=test_project_config
    )
    # Initialize mock providers
    # ...
    return context
```

### 9.5 Proposed Test Directory Structure (After Refactor)

```
tests/
├── conftest.py                      # Global + new context fixtures
├── unit/
│   ├── core/                        # [NEW] Core package tests
│   │   ├── test_protocols.py
│   │   ├── test_context.py
│   │   ├── test_registry.py
│   │   └── test_config_loader.py
│   ├── providers/                   # [NEW] Provider package tests
│   │   └── aws/
│   │       ├── test_provider.py
│   │       ├── test_clients.py
│   │       ├── test_naming.py
│   │       └── test_strategy.py
│   ├── lambda_functions/            # (unchanged)
│   ├── test_globals.py              # (deprecated after full migration)
│   ├── test_util.py
│   ├── test_util_aws.py
│   └── test_validation.py
├── integration/
│   ├── aws/                         # Update imports only
│   ├── azure/                       # Empty (for later)
│   └── google/                      # Empty (for later)
├── api/                             # (unchanged - tests REST API)
└── deployers/                       # Update to test Strategy pattern
```

---

## 10. Verification Checklist

### Automated Tests
- [ ] All existing unit tests pass (no regressions)
- [ ] New `tests/unit/core/` tests pass
- [ ] New `tests/unit/providers/aws/` tests pass
- [ ] Integration tests pass with updated imports
- [ ] API endpoint tests pass (REST API unchanged)
- [ ] CLI tests pass (CLI behavior unchanged)

### Manual Verification
- [ ] CLI: `python main.py deploy --provider aws` works
- [ ] CLI: `python main.py destroy --provider aws` works
- [ ] API: `POST /deploy?provider=aws` works
- [ ] API: `DELETE /destroy?provider=aws` works
- [ ] Documentation: All new code is documented

### Docker Verification
```bash
# Run tests inside Docker container
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
    python -m pytest tests/ -v

# Test CLI
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
    python src/main.py info
```

---

## 11. Design Decisions (User Approved)

> **Decisions made based on user feedback:**

### 1. Naming: `CloudProvider` ✓
The main interface will be named `CloudProvider`.

### 2. Context Scope: Per-Request/Per-Invocation ✓

**Clarification:** The question was about when `DeploymentContext` should be created:

```
Option A: Per-Request (CHOSEN)
┌─────────────────────────────────────────────────────────────────────────────┐
│  API Request: POST /deploy?provider=aws                                     │
│   └─→ Create new DeploymentContext                                          │
│        └─→ Load config, initialize providers                                │
│        └─→ Execute deploy_l1(), deploy_l2(), ...                            │
│        └─→ Context is garbage collected after response                      │
│                                                                              │
│  Next Request: POST /destroy?provider=aws                                   │
│   └─→ Create NEW DeploymentContext (fresh state)                            │
│        └─→ Load config again, initialize providers again                    │
│        └─→ Execute destroy_l1(), destroy_l2(), ...                          │
└─────────────────────────────────────────────────────────────────────────────┘

Option B: Per-Session (NOT CHOSEN)
┌─────────────────────────────────────────────────────────────────────────────┐
│  Application Startup                                                         │
│   └─→ Create ONE DeploymentContext                                           │
│        └─→ Store in memory (singleton)                                       │
│                                                                              │
│  Request 1: POST /deploy                                                     │
│   └─→ Reuse existing context                                                 │
│                                                                              │
│  Request 2: POST /destroy                                                    │
│   └─→ Reuse SAME context (shared state)                                      │
│                                                                              │
│  Problem: Config changes require restart. Shared state can cause bugs.      │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Decision:** Per-Request is safer and aligns with current behavior where `globals.initialize_all()` can be called to refresh config. Each API request gets a fresh context.

### 3. Migration Priority: AWS First ✓
Fully refactor AWS implementation before adding Azure/GCP. Azure and GCP implementations will be significant undertakings that should wait until the pattern is proven with AWS.

### 4. Azure/GCP Stubs: Minimal Scaffolding ✓
Create minimal stubs (empty provider classes that raise `NotImplementedError`) to validate the pattern structure, but don't invest significant effort until AWS is complete.

### 5. Layer 3 Granularity: Split into Sub-Deployers ✓
Since hot, cold, and archive storage can be on **different providers**, Layer 3 must be split:

```python
class DeployerStrategy(Protocol):
    # L1, L2 (single provider each)
    def deploy_l1(self, context): ...
    def deploy_l2(self, context): ...
    
    # L3 split into 3 sub-deployers
    def deploy_l3_hot(self, context): ...
    def deploy_l3_cold(self, context): ...
    def deploy_l3_archive(self, context): ...
    
    # L4, L5 (single provider each)
    def deploy_l4(self, context): ...
    def deploy_l5(self, context): ...
```

This allows configurations like:
```json
{
  "layer_3_hot_provider": "aws",      // DynamoDB
  "layer_3_cold_provider": "gcp",     // Cloud Storage Nearline
  "layer_3_archive_provider": "azure" // Blob Archive
}
```

### 6. Backward Compatibility: Not Required ✓
As long as the REST API endpoints and CLI commands maintain their current behavior (same inputs, same outputs), no backward compatibility layer is needed. The internal implementation can change freely.
