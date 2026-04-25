# Multi-Cloud Digital Twin Deployer

An automated infrastructure-as-code tool for deploying fully functional Digital Twins across multiple cloud providers (AWS, Azure, GCP). This deployer provisions and manages all necessary cloud resources including IoT devices, data processing pipelines, multi-tier storage, twin management, and visualization.

**Multi-Cloud Capability**: Each layer of the digital twin can be deployed to a different cloud provider, enabling cost-optimized multi-cloud architectures.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
  - [REST API](#rest-api)
  - [CLI Interface](#cli-interface)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Key Concepts](#key-concepts)
- [Deployed Services](#deployed-services)
- [Data Flow](#data-flow)
- [Integration with 2-twin2clouds](#integration-with-2-twin2clouds)
- [Future Roadmap](#future-roadmap)
- [Troubleshooting](#troubleshooting)

---

## Overview

This deployer automates the creation of a complete digital twin infrastructure across AWS, Azure, and GCP. It uses a modular, declarative approach where you define your digital twin through configuration files, and the deployer handles all the cloud resource provisioning, IAM/RBAC policies, serverless functions, IoT rules, and data pipelines.

The deployer is designed to work standalone or as part of a multi-cloud environment, integrating with the [2-twin2clouds](../2-twin2clouds) cost optimizer to determine the optimal cloud provider for each layer.

---

## Features

✅ **Multi-Cloud Support**: Deploy to AWS, Azure, or GCP per layer  
✅ **REST API**: FastAPI-based API for programmatic deployment  
✅ **Docker Support**: Containerized deployment with single command  
✅ **Configuration-Driven**: Define your twin through JSON configuration files  
✅ **Multi-Tier Storage**: Automatic data lifecycle management (Hot → Cold → Archive)  
✅ **Event-Driven Architecture**: Real-time event processing with custom actions  
✅ **Twin Management**: Native cloud services (TwinMaker, Digital Twins)  
✅ **Grafana Integration**: Managed or self-hosted Grafana for monitoring  
✅ **Modular Design**: Each component is independent and self-contained  
✅ **Layer-Based Provider Selection**: Deploy L1-L5 through the canonical Terraform path
✅ **Clean Teardown**: Destroy all resources with proper dependency ordering  
✅ **Resource Inspection**: Query deployed resources with status endpoints

---

## Architecture

### High-Level Overview

```
IoT Devices → IoT Service → Dispatcher → Processors → Persister
              (L1)           (L2)                      ↓
                                           Hot Storage (L3)
                                                      ↓
                                           Cold → Archive
                                                      ↓
                                         Twin Management (L4)
                                                      ↓
                                           Visualization (L5)
```

### Layer Breakdown

The deployer implements a **5-layer architecture** where each layer can be deployed to different cloud providers:

| Layer | Purpose | AWS | Azure | GCP |
|-------|---------|-----|-------|-----|
| **L1** | Data Acquisition | IoT Core | IoT Hub | Pub/Sub |
| **L2** | Data Processing | Lambda | Functions | Cloud Functions |
| **L3-Hot** | Hot Storage | DynamoDB | Cosmos DB | Firestore |
| **L3-Cool** | Cool Storage | S3 IA | Blob Cool | Nearline |
| **L3-Archive** | Archive Storage | S3 Glacier | Blob Archive | Archive |
| **L4** | Twin Management | TwinMaker | Digital Twins | Self-hosted |
| **L5** | Visualization | Managed Grafana | Managed Grafana | Self-hosted Grafana |

---

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd 3-cloud-deployer

# Configure credentials
cp config_credentials.json.example config_credentials.json
# Edit config_credentials.json with your cloud provider credentials

# Build and run with Docker
docker build -t digital-twin-deployer .
docker run -p 8000:8000 -v $(pwd):/app digital-twin-deployer

# Access the API
# - Interactive API docs: http://localhost:8000/docs
# - Alternative docs: http://localhost:8000/redoc
```

### Manual Setup

```bash
# Install dependencies
pip install fastapi uvicorn boto3 requests colorlog

# Configure credentials (see Configuration section)
cp config_credentials.json.example config_credentials.json

# Run the API server
uvicorn rest_api:app --host 0.0.0.0 --port 8000

# Or use the canonical CLI
cd src
python main.py deploy aws
```

---

## Documentation

Comprehensive documentation is available at `/docs`:

- **[Overview](docs/docs-overview.html)** - Project introduction and status
- **[Setup & Usage](docs/docs-setup-usage.html)** - Installation and getting started guide
- **[Architecture](docs/docs-architecture.html)** - 5-layer architecture and deployer patterns
- **[Configuration](docs/docs-configuration.html)** - Complete configuration reference for all config files
- **[REST API Reference](docs/docs-api-reference.html)** - All API endpoints documented
- **[CLI Reference](docs/docs-cli-reference.html)** - Canonical deploy/destroy CLI
- **[AWS Deployment](docs/docs-aws-deployment.html)** - AWS-specific deployment guide
- **[Azure Deployment](docs/docs-azure-deployment.html)** - Azure deployment (in development)
- **[GCP Deployment](docs/docs-gcp-deployment.html)** - GCP deployment (in development)
- **[Twin2Clouds Integration](docs/docs-twin2clouds-integration.html)** - Integration with cost optimizer

To view the documentation, open any HTML file from the `/docs` folder in your web browser.

---

## Configuration

The deployer uses multiple JSON configuration files:

### 1. `config.json` - Main Twin Configuration

```json
{
  "digital_twin_name": "dt",
  "layer_3_hot_to_cold_interval_days": 30,
  "layer_3_cold_to_archive_interval_days": 90
}
```

- **digital_twin_name**: Prefix for all cloud resources (namespace isolation)
- **layer_3_hot_to_cold_interval_days**: Hot storage retention period
- **layer_3_cold_to_archive_interval_days**: Cool storage retention period

### 2. `config_credentials.json` - Cloud Provider Credentials

Create from example:
```bash
cp config_credentials.json.example config_credentials.json
```

Example structure:
```json
{
  "aws": {
    "aws_access_key_id": "YOUR_ACCESS_KEY_ID",
    "aws_secret_access_key": "YOUR_SECRET_ACCESS_KEY",
    "aws_region": "eu-central-1"
  },
  "azure": {
    "azure_subscription_id": "YOUR_SUBSCRIPTION_ID",
    "azure_client_id": "YOUR_CLIENT_ID",
    "azure_client_secret": "YOUR_CLIENT_SECRET",
    "azure_tenant_id": "YOUR_TENANT_ID",
    "azure_region": "westeurope"
  },
  "google": {
    "gcp_project_id": "YOUR_PROJECT_ID",
    "gcp_credentials_file": "path/to/credentials.json",
    "gcp_region": "europe-west1"
  }
}
```

> ⚠️ **Security**: Never commit `config_credentials.json` to version control!

### 3. `config_providers.json` - Multi-Cloud Provider Mapping

Define which cloud provider to use for each layer:

```json
{
  "layer_1_provider": "aws",
  "layer_2_provider": "aws",
  "layer_3_hot_provider": "aws",
  "layer_3_cold_provider": "gcp",
  "layer_3_archive_provider": "gcp",
  "layer_4_provider": "azure",
  "layer_5_provider": "aws"
}
```

Supported values: `"aws"`, `"azure"`, `"google"`

### 4. `config_iot_devices.json` - IoT Device Definitions

Define your IoT devices and their properties:

```json
[
  {
    "id": "temperature-sensor-1",
    "properties": [
      { "name": "temperature", "dataType": "DOUBLE" }
    ]
  },
  {
    "id": "temperature-sensor-1-const",
    "properties": [
      { "name": "serial-number", "dataType": "STRING", "initValue": "temp-sens-143323" },
      { "name": "maxTemperature", "dataType": "DOUBLE", "initValue": 60.0 }
    ]
  }
]
```

### 5. `config_hierarchy.json` - Twin Hierarchy

Define the spatial/logical hierarchy of your digital twin:

```json
[
  {
    "type": "entity",
    "id": "room-1",
    "children": [
      {
        "type": "entity",
        "id": "machine-1",
        "children": [
          {
            "type": "component",
            "name": "temperature-sensor-1",
            "componentTypeId": "dt-temperature-sensor-1"
          }
        ]
      }
    ]
  }
]
```

### 6. `config_events.json` - Event Rules and Actions

Define event conditions and automated responses:

```json
[
  {
    "condition": "room-1.temperature-sensor-2.temperature == DOUBLE(40)",
    "action": {
      "type": "lambda",
      "functionName": "high-temperature-callback",
      "autoDeploy": true,
      "feedback": {
        "type": "mqtt",
        "topic": "dt-temperature-sensor-2",
        "payload": {
          "message": "Temperature too high!"
        }
      }
    }
  }
]
```

---

## Usage

### REST API

The deployer provides a comprehensive REST API for deployment, status checking, and Lambda management.

#### Start the API Server

```bash
# Using Docker
docker run -p 8000:8000 digital-twin-deployer

# Or directly with uvicorn
uvicorn rest_api:app --host 0.0.0.0 --port 8000
```

#### Access API Documentation

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

#### Example API Calls

```bash
# Deploy entire digital twin through the canonical Terraform facade
curl -X POST "http://localhost:8000/infrastructure/deploy?provider=aws&project_name=template"

# Stream deployment logs via SSE
curl -N -X POST "http://localhost:8000/infrastructure/deploy/stream?provider=aws&project_name=template"

# Check infrastructure status
curl "http://localhost:8000/infrastructure/status?project_name=template"

# Verify infrastructure resources
curl -X POST "http://localhost:8000/infrastructure/verify?project_name=template"

# List user-modifiable functions
curl "http://localhost:8000/functions/updatable_functions?project_name=template"

# Destroy entire digital twin through the canonical Terraform facade
curl -X POST "http://localhost:8000/infrastructure/destroy?provider=aws&project_name=template"
```

### CLI Interface

The CLI is a thin adapter over the same canonical Terraform deployer facade used by the REST API:

```bash
cd src
python main.py --project template deploy aws
python main.py --project template destroy aws
```

Supported providers are `aws`, `azure`, `gcp`, and `google` as a compatibility alias for `gcp`.

---

## Deployment Contracts

Deploy and destroy endpoints return stable JSON contracts. Existing compatibility keys remain present.

Deploy response:

```json
{
  "message": "Core and IoT services deployed successfully",
  "status": "success",
  "operation": "deploy",
  "project_name": "template",
  "provider": "aws",
  "terraform_outputs": {}
}
```

Destroy response:

```json
{
  "message": "Core and IoT services destroyed successfully",
  "status": "success",
  "operation": "destroy",
  "project_name": "template",
  "provider": "aws"
}
```

SSE stream events are JSON payloads. Log lines are emitted as `data:` events; terminal events keep named `complete` and `error` events:

```text
data: {"event":"log","operation":"deploy","message":"terraform init"}

event: complete
data: {"event":"complete","operation":"deploy","success":true,"outputs":{}}
```

Provider values are normalized at the API boundary. `google` is accepted as an inbound alias and returned as canonical `gcp`.

---

## API Endpoints

### Deployment Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/infrastructure/deploy` | Deploy entire digital twin through the canonical Terraform facade |
| POST | `/infrastructure/deploy/stream` | Deploy with SSE log streaming |
| POST | `/infrastructure/destroy` | Destroy entire digital twin through the canonical Terraform facade |
| POST | `/infrastructure/destroy/stream` | Destroy with SSE log streaming |
| GET | `/infrastructure/cooldown-check` | Check GCP Firestore redeploy cooldown |

### Status/Info Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/infrastructure/status` | Check complete infrastructure status |
| POST | `/infrastructure/verify` | Run structured infrastructure verification |
| GET | `/` | API health check |

### Function Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/functions/updatable_functions` | List user-modifiable functions |
| POST | `/functions/update_function/{function_name}` | Update function code through provider-specific SDK adapters |
| POST | `/functions/build` | Build a cloud-ready function ZIP |

---

## Project Structure

```
3-cloud-deployer/
├── Dockerfile                       # Docker container definition
├── rest_api.py                      # FastAPI REST API
├── config.json                      # Main configuration
├── config_credentials.json          # Cloud credentials (not in git)
├── config_providers.json            # Multi-cloud provider mapping
├── config_iot_devices.json          # IoT device definitions
├── config_hierarchy.json            # TwinMaker hierarchy
├── config_events.json               # Event rules
├── src/
│   ├── main.py                      # Thin canonical Terraform CLI adapter
│   ├── globals.py                   # Global configuration
│   ├── util.py                      # Utility functions
│   ├── api/                         # FastAPI route adapters
│   ├── core/                        # Context, provider registry, protocols
│   └── providers/                   # AWS/Azure/GCP provider implementations
│       ├── deployer.py              # Canonical deploy/destroy facade
│       └── terraform/               # Terraform strategy and package builders
├── lambda_functions/
│   ├── core/
│   │   ├── dispatcher/              # Routes incoming IoT data
│   │   ├── persister/               # Writes to storage
│   │   ├── default-processor/       # Default data processor
│   │   ├── hot-to-cold-mover/       # Hot → Cold data mover
│   │   └── cold-to-archive-mover/   # Cold → Archive data mover
│   └── event_actions/               # Custom event handlers
├── iot_device_simulator/            # IoT device simulator
├── state_machines/                  # Step Functions definitions
└── README.md                        # This file
```

---

## Key Concepts

### 1. Multi-Cloud Layer Deployment

Each layer (L1-L5) can be deployed to a different cloud provider. This enables:
- **Cost Optimization**: Use cheapest provider per layer
- **Feature Optimization**: Use best service per layer
- **Vendor Diversification**: Reduce vendor lock-in

### 2. Deployer Pattern

Each deployer file manages related resources:

```python
# deployer file

# Deploy Entity
def deploy_resource():
    # Create cloud resource
    ...

def destroy_resource():
    # Delete cloud resource
    ...

def info_resource():
    # Get resource info
    ...

# Deployer orchestration
def deploy(provider):
    deploy_resource()
    ...

def destroy(provider):
    # Reverse order!
    ...
```

### 3. Resource Naming Convention

All resources are prefixed with `digital_twin_name` to:
- Create a dedicated namespace
- Distinguish twin resources from other cloud resources
- Enable easy identification and cleanup

Example: If `digital_twin_name = "dt"`:
- Lambda: `dt-dispatcher`
- DynamoDB: `dt-hot-iot-data`
- S3 Bucket: `dt-cold-iot-data`
- IoT Thing: `dt-temperature-sensor-1`

### 4. Data Processing Pipeline

1. **IoT Device** publishes to IoT service topic
2. **IoT Rule** triggers **Dispatcher Function**
3. **Dispatcher** invokes device-specific **Processor Function**
4. **Processor** transforms data and invokes **Persister Function**
5. **Persister** writes to **Hot Storage**
6. **Hot-to-Cold Mover** (scheduled) archives to **Cool Storage**
7. **Cold-to-Archive Mover** (scheduled) moves to **Archive Storage**

---

## Deployed Services

### AWS Services

| Service | Purpose | Resources |
|---------|---------|-----------|
| **AWS IoT Core** | Device connectivity | Things, Policies, Certificates, Rules |
| **AWS Lambda** | Data processing | dispatcher, persister, processors, movers |
| **IAM** | Access control | Roles and policies for each Lambda |
| **DynamoDB** | Hot storage | `{twin_name}-hot-iot-data` |
| **S3** | Cool & Archive storage | `{twin_name}-cold-iot-data`, archive bucket |
| **EventBridge** | Scheduled movers | hot-to-cold rule, cold-to-archive rule |
| **Step Functions** | Orchestration | Event action workflows |
| **IoT TwinMaker** | 3D twin management | Workspace, entities, components |
| **Managed Grafana** | Visualization | Workspace |
| **CloudWatch Logs** | Logging | Log groups for each function |

### Azure Services (In Development)

- Azure IoT Hub
- Azure Functions
- Azure Cosmos DB
- Azure Blob Storage (Cool, Archive tiers)
- Azure Digital Twins
- Azure Managed Grafana

### GCP Services (In Development)

- Cloud Pub/Sub
- Cloud Functions
- Firestore
- Cloud Storage (Nearline, Archive classes)
- Self-hosted Digital Twin solution
- Self-hosted Grafana on GKE/Compute Engine

---

## Data Flow

### Ingestion Flow

```
IoT Device (MQTT/HTTPS) 
  → IoT Service Topic
    → Trigger Rule
      → Dispatcher Function
        → Processor Function
          → Persister Function
            → Hot Storage
```

### Storage Lifecycle

```
Hot Storage (DynamoDB/Cosmos DB/Firestore)
  ↓ (after layer_3_hot_to_cold_interval_days)
Cool Storage (S3 IA/Blob Cool/Cloud Storage Nearline)
  ↓ (after layer_3_cold_to_archive_interval_days)
Archive Storage (S3 Glacier/Blob Archive/Cloud Storage Archive)
```

---

## Integration with 2-twin2clouds

This deployer is designed to work with the [2-twin2clouds](../2-twin2clouds) cost optimizer, which:
- Analyzes digital twin scenarios (devices, data volume, storage duration, etc.)
- Computes monthly costs for AWS, Azure, and GCP per layer
- Suggests the most cost-efficient multi-cloud deployment path

**Workflow**:
1. User defines scenario in 2-twin2clouds web UI
2. Cost optimizer determines optimal provider per layer
3. User updates `config_providers.json` with recommended path
4. This deployer executes the multi-cloud deployment

**Example**: Cost optimizer suggests:
- L1 (IoT): GCP Pub/Sub (cheapest)
- L2 (Processing): AWS Lambda
- L3-Hot: AWS DynamoDB
- L3-Cool: GCP Cloud Storage Nearline
- L3-Archive: Azure Blob Archive
- L4: AWS TwinMaker
- L5: AWS Managed Grafana

The deployer handles all cross-cloud data transfers and integration automatically.

---

## Future Roadmap

- [x] **REST API**: FastAPI-based deployment API
- [x] **Docker Support**: Containerized deployment
- [x] **Multi-Cloud Foundation**: Layer-based provider selection
- [ ] **Azure Full Implementation**: Complete Azure provider coverage
- [ ] **GCP Full Implementation**: Complete GCP provider coverage
- [ ] **Cross-Cloud Data Transfer**: Automated egress handling
- [ ] **Provider Contract Hardening**: Keep deploy/destroy behavior behind canonical provider interfaces
- [ ] **Recovery Mechanism**: Resume failed deployments from checkpoint
- [ ] **Unit Tests**: Add comprehensive test coverage
- [ ] **Terraform Export**: Generate Terraform/ARM/Deployment Manager templates
- [ ] **Cost Monitoring**: Real-time cost tracking per layer

---

## Troubleshooting

### Common Issues

**1. IAM/RBAC Propagation Delays**

Cloud providers take time to propagate permissions. The deployer includes automatic waits, but if you see permission errors, wait 30-60 seconds and retry.

**2. Resource Already Exists**

If deployment fails midway, run `/infrastructure/destroy` or the CLI `destroy` command to clean up, then redeploy.

**3. Docker Volume Issues**

Ensure configuration files are mounted correctly:
```bash
docker run -p 8000:8000 -v $(pwd):/app digital-twin-deployer
```

**4. API Returns 500 Errors**

Check logs in Docker container:
```bash
docker logs <container-id>
```

For function-specific issues, inspect the provider logs and the Deployer container logs for the corresponding function update or deployment operation.

**5. Cross-Cloud Connectivity**

Multi-cloud deployments require proper network configuration and API access between clouds. Ensure:
- Egress rules allow outbound connections
- API endpoints are publicly accessible or properly peered
- Credentials for all providers are valid

### Debug Mode

Enable detailed logging by checking the console output where `uvicorn` or `main.py` is running.

### Checking Cloud Consoles

Verify deployed resources in respective cloud consoles:
- **AWS**: Lambda, IoT Core, DynamoDB, S3, TwinMaker
- **Azure**: Functions, IoT Hub, Cosmos DB, Blob Storage, Digital Twins
- **GCP**: Cloud Functions, Pub/Sub, Firestore, Cloud Storage

---

## Docker

### Build and Run

```bash
# Build the image
docker build -t digital-twin-deployer .

# Run the container
docker run -d \
  -p 8000:8000 \
  -v $(pwd):/app \
  --name dt-deployer \
  digital-twin-deployer

# View logs
docker logs -f dt-deployer

# Stop container
docker stop dt-deployer

# Remove container
docker rm dt-deployer
```

### Environment Variables

You can override configuration via environment variables:

```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd):/app \
  -e PYTHONPATH=/app \
  digital-twin-deployer
```

---

## Contributing

Contributions are welcome! Please follow the existing code conventions:
- Each deployer in its own file
- Keep components separated and self-contained
- Use the resource naming convention (prefix with `digital_twin_name`)
- Add deploy/destroy/info functions for each resource
- Document all API endpoints with clear docstrings

---

## License

See [LICENSE](LICENSE) file.

---

## Citation

This project is part of a master's thesis on multi-cloud digital twin deployment. If you use this code, please cite:

```
[Citation information to be added]
```

---

## Contact

For questions or issues, please open a GitHub issue.
