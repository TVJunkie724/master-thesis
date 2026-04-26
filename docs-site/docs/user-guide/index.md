# User Guide

The user-facing workflow is centered around a Digital Twin, not around individual backend services.

## Main Workflow

1. Create or select a Digital Twin.
2. Enter the scenario parameters that influence cost and deployment shape.
3. Run the optimizer and review the recommended provider placement.
4. Select or create the required Cloud Connections.
5. Confirm the deployment configuration.
6. Start deployment and follow status, logs, verification, and outputs in the app.
7. Operate, inspect, or destroy the deployed twin.

The app should hide internal service shortcuts. Users should not need to know which optimizer endpoint or deployer endpoint was called to complete a workflow.

## Current Thesis Scope

The guide should document the workflows needed for thesis demonstration and development: local mock/demo usage, real cloud deployment with explicit credentials, deployment result inspection, and safe destroy behavior.

Provider-specific cloud setup belongs in [Cloud Setup](../cloud-setup/index.md). API-level details belong in [API](../api/index.md).
