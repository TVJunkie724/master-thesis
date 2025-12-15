"""
Component Types
===============

Enums and type definitions for the component-level cost calculator.

This module defines:
- FormulaType: The 6 formula types from docs-formulas.html
- LayerType: Digital twin architecture layers (L0-L5)
- Provider: Cloud provider identifiers
- AWSComponent, AzureComponent, GCPComponent: Provider-specific component enums
- GlueRole: Cross-cloud function roles (for documentation only)
"""

from enum import Enum, auto


class FormulaType(Enum):
    """
    Formula types from docs-formulas.html.
    
    These correspond to the mathematical formulas in core_formulas.py.
    """
    CM = auto()         # Message-Based: c_m × N_m
    CE = auto()         # Execution-Based: c_e × max(0, N_e - free) + c_t × max(0, T_e - free)
    CA = auto()         # Action-Based: c_a × N_a
    CS = auto()         # Storage-Based: c_s × V × D
    CU = auto()         # User-Based: (c_editor × N_editor + c_viewer × N_viewer) + c_hour × H
    CTRANSFER = auto()  # Data Transfer: c_transfer × GB_transferred


class LayerType(Enum):
    """
    Digital twin architecture layers.
    
    Based on the Twin2Clouds 5-layer architecture with L0 as glue.
    """
    L0_GLUE = auto()                # Cross-cloud communication functions
    L1_INGESTION = auto()           # Data Acquisition (IoT)
    L2_PROCESSING = auto()          # Data Processing (Serverless compute)
    L3_HOT_STORAGE = auto()         # Hot Storage (NoSQL)
    L3_COOL_STORAGE = auto()        # Cool Storage (Object storage IA tier)
    L3_ARCHIVE_STORAGE = auto()     # Archive Storage (Glacier/Archive tier)
    L4_TWIN_MANAGEMENT = auto()     # Twin Management (Digital Twins)
    L5_VISUALIZATION = auto()       # Visualization (Grafana)


class Provider(Enum):
    """Cloud provider identifiers."""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


# =============================================================================
# PROVIDER-SPECIFIC COMPONENT ENUMS
# =============================================================================
#
# Components are separated per provider because they map to different
# pricing JSON keys, even when using the same formula.
#
# Example: Lambda and Azure Functions both use CE formula, but:
#   - Lambda: pricing["aws"]["lambda"]
#   - Functions: pricing["azure"]["functions"]
# =============================================================================


class AWSComponent(Enum):
    """
    AWS-specific service components.
    
    Each component maps to a specific pricing key in the JSON.
    Components using the same pricing key should NOT be duplicated.
    """
    # L1: Data Acquisition
    IOT_CORE = auto()               # pricing["aws"]["iotCore"]
    
    # L2: Data Processing
    LAMBDA = auto()                 # pricing["aws"]["lambda"] - Also used for glue functions
    STEP_FUNCTIONS = auto()         # pricing["aws"]["stepFunctions"]
    EVENTBRIDGE = auto()            # pricing["aws"]["eventBridge"]
    
    # L3: Storage
    DYNAMODB = auto()               # pricing["aws"]["dynamoDB"]
    S3_INFREQUENT_ACCESS = auto()   # pricing["aws"]["s3InfrequentAccess"]
    S3_GLACIER_DEEP_ARCHIVE = auto() # pricing["aws"]["s3GlacierDeepArchive"]
    
    # L4: Twin Management
    TWINMAKER = auto()              # pricing["aws"]["iotTwinMaker"]
    
    # L5: Visualization
    MANAGED_GRAFANA = auto()        # pricing["aws"]["awsManagedGrafana"]


class AzureComponent(Enum):
    """
    Azure-specific service components.
    
    Each component maps to a specific pricing key in the JSON.
    """
    # L1: Data Acquisition
    IOT_HUB = auto()                # pricing["azure"]["iotHub"]
    
    # L2: Data Processing
    FUNCTIONS = auto()              # pricing["azure"]["functions"] - Also used for glue functions
    LOGIC_APPS = auto()             # pricing["azure"]["logicApps"]
    EVENT_GRID = auto()             # pricing["azure"]["eventGrid"]
    
    # L3: Storage
    COSMOS_DB = auto()              # pricing["azure"]["cosmosDB"]
    BLOB_COOL = auto()              # pricing["azure"]["blobStorageCool"]
    BLOB_ARCHIVE = auto()           # pricing["azure"]["blobStorageArchive"]
    
    # L4: Twin Management
    DIGITAL_TWINS = auto()          # pricing["azure"]["azureDigitalTwins"]
    
    # L5: Visualization
    MANAGED_GRAFANA = auto()        # pricing["azure"]["azureManagedGrafana"]


class GCPComponent(Enum):
    """
    GCP-specific service components.
    
    Each component maps to a specific pricing key in the JSON.
    Note: L4 and L5 on GCP are self-hosted (Compute Engine).
    """
    # L1: Data Acquisition
    PUBSUB = auto()                 # pricing["gcp"]["iot"] (Pub/Sub for IoT)
    
    # L2: Data Processing
    CLOUD_FUNCTIONS = auto()        # pricing["gcp"]["functions"] - Also used for glue functions
    CLOUD_WORKFLOWS = auto()        # pricing["gcp"]["cloudWorkflows"]
    
    # L3: Storage
    FIRESTORE = auto()              # pricing["gcp"]["storage_hot"] (Firestore)
    GCS_NEARLINE = auto()           # pricing["gcp"]["storage_cool"]
    GCS_COLDLINE = auto()           # pricing["gcp"]["storage_archive"]
    
    # L4: Twin Management (Self-hosted)
    SELF_HOSTED_TWIN = auto()       # pricing["gcp"]["twinmaker"] (Compute Engine)
    
    # L5: Visualization (Self-hosted)
    SELF_HOSTED_GRAFANA = auto()    # pricing["gcp"]["grafana"] (Compute Engine)


class GlueRole(Enum):
    """
    Role of a function in cross-cloud communication.
    
    NOTE: Glue functions use the SAME Lambda/Functions pricing!
    This enum is for context/documentation only, not a separate component.
    
    Current implementation (aws.py lines 470-480) confirms:
    - calculate_aws_connector_function_cost → _calculate_lambda_cost
    - calculate_aws_ingestion_function_cost → _calculate_lambda_cost
    - calculate_aws_writer_function_cost → _calculate_lambda_cost
    - calculate_aws_reader_function_cost → _calculate_lambda_cost
    """
    CONNECTOR = auto()   # L1→L2: Forwards data from source cloud to target cloud
    INGESTION = auto()   # L1→L2: Receives data at target cloud
    WRITER = auto()      # L3: Hot→Cool, Cool→Archive cross-cloud transfers
    READER = auto()      # L3→L4: Data retrieval for twin management
