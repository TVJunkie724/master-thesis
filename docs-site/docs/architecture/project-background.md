# Project Background

Twin2MultiCloud combines and extends earlier Digital Twin research and bachelor-project artifacts into one integrated platform.

## Origins

The project is based on two important inputs:

- **Twin2Clouds / EDTconf 2025 paper artifact**: the original cost-modeling tool and formulas from [Twin2Clouds: Cost-Aware Digital Twin Engineering and Deployment Across Federated Clouds](../references/EDT_25__CloudDT_engineering.pdf).
- **Cloud Deployer bachelor project**: the deployment-oriented codebase for provisioning Digital Twin infrastructure across cloud providers.

The current thesis project adds the missing orchestration layer between these worlds: a Management API and Flutter UI that turn cost optimization and infrastructure deployment into one workflow.

## Original Optimizer

The original optimizer was a client-side web application for comparing Digital Twin costs across cloud providers.

Important differences to the current platform:

- the original optimizer was browser-only,
- it had no Management API, user model, deployment state, or deployment integration,
- it used static/local pricing data in early versions,
- it focused on cost calculation rather than lifecycle management,
- its layer numbering differed from the current unified platform in places.

The current `2-twin2clouds` service keeps the optimizer role but moves it behind an API and connects it to the Management API.

## Original Deployer

The Deployer started as a cloud-infrastructure project focused on provisioning provider resources and user functions.

Important differences to the current platform:

- the current Deployer is treated as the execution engine, not the owner of user lifecycle state,
- Terraform-first deployment is the canonical path,
- provider-specific implementation is behind `src/providers/*`,
- the Management API owns user/twin state and calls the Deployer through service contracts,
- deployment templates and runtime upload folders are being separated.

## Current Thesis Integration

The integrated target workflow is:

```text
Flutter UI
  -> Management API
    -> Twin2Clouds Optimizer
    -> Cloud Deployer
```

This integration is the core thesis contribution from an engineering perspective: the system connects theoretical cost modeling, user-facing configuration, persistent twin lifecycle state, and executable multi-cloud infrastructure deployment.

## Documentation Goal

This documentation should support two audiences:

- thesis work: architecture, rationale, deviations from the source projects, and evaluation context,
- developers: setup, service boundaries, cloud setup, API contracts, and implementation notes for maintaining the system.
