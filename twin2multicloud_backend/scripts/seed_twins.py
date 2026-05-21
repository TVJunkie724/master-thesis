"""
Seed Test Digital Twins on Management Backend Startup.

Creates 5 test digital twins with user-scoped CloudConnections, optimizer
config, and deployer config. Validates credentials against Deployer +
Optimizer APIs.

Twins with invalid credentials remain in DRAFT state with log warnings.
Twins with valid credentials advance to CONFIGURED state.

Idempotent: skips entirely if seed user already exists.
"""
import asyncio
import json
import uuid

import httpx

from src.config import settings
from src.models.cloud_connection import CloudConnection
from src.models.database import SessionLocal
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.deployer_config import DeployerConfiguration
from src.models.user import User
from src.services.cloud_connection_service import CloudConnectionService
from src.utils.crypto import encrypt, encrypt_scoped



SEED_USER_EMAIL = "seed@twin2multicloud.dev"

# ============================================================================
# Template Data (embedded — not read from deployer filesystem)
# ============================================================================

CONFIG_EVENTS_JSON = json.dumps([
    {
        "condition": "testEntityId.temperature-sensor-1.temperature == DOUBLE(30)",
        "action": {
            "type": "lambda",
            "functionName": "high-temperature-callback",
            "autoDeploy": True,
            "feedback": {
                "type": "mqtt",
                "iotDeviceId": "temperature-sensor-1",
                "payload": "High Temp Warning"
            }
        }
    },
    {
        "condition": "testEntityId.temperature-sensor-2.temperature == DOUBLE(40)",
        "action": {
            "type": "lambda",
            "functionName": "high-temperature-callback-2",
            "pathToCode": "lambda_functions/event_actions/high-temperature-callback-2",
            "autoDeploy": True,
            "feedback": {
                "type": "mqtt",
                "iotDeviceId": "temperature-sensor-2",
                "payload": "action-result"
            }
        }
    }
])

CONFIG_IOT_DEVICES_JSON = json.dumps([
    {
        "id": "temperature-sensor-1",
        "properties": [
            {"name": "temperature", "dataType": "DOUBLE", "initValue": 25.0}
        ],
        "constProperties": [
            {"name": "serial-number", "dataType": "STRING", "value": "1232323"}
        ]
    },
    {
        "id": "temperature-sensor-2",
        "properties": [
            {"name": "temperature", "dataType": "DOUBLE", "initValue": 22.0},
            {"name": "maxTemperature", "dataType": "DOUBLE", "initValue": 60.0}
        ],
        "constProperties": [
            {"name": "serial-number", "dataType": "STRING", "value": "temp-sens-143323"}
        ]
    },
    {
        "id": "pressure-sensor-1",
        "properties": [
            {"name": "pressure", "dataType": "DOUBLE", "initValue": 1000.0},
            {"name": "density", "dataType": "DOUBLE"},
            {"name": "hardness", "dataType": "DOUBLE"}
        ]
    }
])

DEVICE_IDS = ["temperature-sensor-1", "temperature-sensor-2", "pressure-sensor-1"]
EVENT_ACTION_NAMES = ["high-temperature-callback", "high-temperature-callback-2"]

# Minimal payloads for each device
PAYLOADS_JSON = json.dumps({
    device_id: {"temperature": 25.0} if "temperature" in device_id else {"pressure": 1000.0}
    for device_id in DEVICE_IDS
})

# Processor validation (JSON string, per-device bool map)
PROCESSOR_VALIDATED = json.dumps({device_id: True for device_id in DEVICE_IDS})

# Provider-specific function stubs
_PROCESSOR_CODE = {
    "AWS":   "def lambda_handler(event, context):\n    return event",
    "AZURE": "def main(req):\n    return req",
    "GCP":   "def process(event):\n    return event",
}
_FEEDBACK_CODE = {
    "AWS":   "def lambda_handler(event, context):\n    return event",
    "AZURE": "def main(req):\n    return req",
    "GCP":   "def process(event):\n    return event",
}
_ACTION_CODE = {
    "AWS":   "def lambda_handler(event, context):\n    pass",
    "AZURE": "def main(req):\n    pass",
    "GCP":   "def handle(event):\n    pass",
}

def _processor_contents(l2: str) -> str:
    code = _PROCESSOR_CODE.get(l2, _PROCESSOR_CODE["AWS"])
    return json.dumps({device_id: code for device_id in DEVICE_IDS})

def _feedback_content(l2: str) -> str:
    return _FEEDBACK_CODE.get(l2, _FEEDBACK_CODE["AWS"])

def _action_contents(l2: str) -> str:
    code = _ACTION_CODE.get(l2, _ACTION_CODE["AWS"])
    return json.dumps({name: code for name in EVENT_ACTION_NAMES})

# Event action validation (JSON string, per-function bool map)
EVENT_ACTION_VALIDATED = json.dumps({name: True for name in EVENT_ACTION_NAMES})

# State machine templates per L2 provider
STATE_MACHINES = {
    "AWS": json.dumps({
        "Comment": "Executing two lambda functions consecutively",
        "StartAt": "LambdaA",
        "States": {
            "LambdaA": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName.$": "$.LambdaAArn",
                    "Payload.$": "$.InputData"
                },
                "ResultPath": "$.LambdaAResult",
                "Next": "LambdaB"
            },
            "LambdaB": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName.$": "$.LambdaBArn",
                    "Payload": {
                        "fromA.$": "$.LambdaAResult.Payload",
                        "event.$": "$.InputData"
                    }
                },
                "OutputPath": "$.Payload",
                "End": True
            }
        }
    }),
    "AZURE": json.dumps({
        "definition": {
            "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
            "actions": {},
            "triggers": {"manual": {"type": "Request", "kind": "Http"}},
            "contentVersion": "1.0.0.0"
        }
    }),
    "GCP": "main:\n  steps:\n    - init:\n        assign:\n          - result: \"Hello from workflow\"\n    - returnResult:\n        return: ${result}\n"
}

# Hierarchy templates per L4 provider
HIERARCHY_AWS = json.dumps([
    {
        "type": "entity", "id": "room-1",
        "children": [
            {
                "type": "entity", "id": "machine-1",
                "children": [
                    {
                        "type": "component", "name": "temperature-sensor-1",
                        "componentTypeId": "temperature-sensor",
                        "properties": [
                            {"name": "temperature", "dataType": "DOUBLE"},
                            {"name": "humidity", "dataType": "DOUBLE"}
                        ],
                        "constProperties": [
                            {"name": "sensorId", "dataType": "STRING", "value": "temp-001"},
                            {"name": "location", "dataType": "STRING", "value": "machine-1"}
                        ]
                    }
                ]
            },
            {
                "type": "component", "name": "temperature-sensor-2",
                "componentTypeId": "temperature-sensor",
                "iotDeviceId": "temperature-sensor-2",
                "properties": [{"name": "temperature", "dataType": "DOUBLE"}],
                "constProperties": [
                    {"name": "sensorId", "dataType": "STRING", "value": "temp-002"}
                ]
            }
        ]
    },
    {
        "type": "entity", "id": "room-2",
        "children": [
            {
                "type": "component", "name": "pressure-sensor-1",
                "componentTypeId": "pressure-sensor",
                "iotDeviceId": "pressure-sensor-1",
                "properties": [{"name": "pressure", "dataType": "DOUBLE"}],
                "constProperties": [
                    {"name": "sensorId", "dataType": "STRING", "value": "pressure-001"}
                ]
            }
        ]
    }
])

# Azure hierarchy uses same structure as AWS for seed purposes
HIERARCHY_AZURE = HIERARCHY_AWS

# User config (platform user for L4/L5)
USER_CONFIG_JSON = json.dumps({
    "email": "platform-user@challerlive560.onmicrosoft.com",
    "name": "Platform User"
})

# ============================================================================
# Twin Definitions
# ============================================================================

TWIN_DEFINITIONS = [
    {
        "name": "aws-single-cloud",
        "layers": {"l1": "AWS", "l2": "AWS", "l3_hot": "AWS", "l3_cool": "AWS", "l3_archive": "AWS", "l4": "AWS", "l5": "AWS"},
        "required_providers": {"aws"},
    },
    {
        "name": "azure-single-cloud",
        "layers": {"l1": "AZURE", "l2": "AZURE", "l3_hot": "AZURE", "l3_cool": "AZURE", "l3_archive": "AZURE", "l4": "AZURE", "l5": "AZURE"},
        "required_providers": {"azure"},
    },
    {
        "name": "gcp-single-cloud",
        "layers": {"l1": "GCP", "l2": "GCP", "l3_hot": "GCP", "l3_cool": "GCP", "l3_archive": "GCP", "l4": "AWS", "l5": "AWS"},
        "required_providers": {"gcp", "aws"},
    },
    {
        "name": "mixed-all-providers",
        "layers": {"l1": "GCP", "l2": "AZURE", "l3_hot": "AWS", "l3_cool": "GCP", "l3_archive": "AZURE", "l4": "AZURE", "l5": "AWS"},
        "required_providers": {"aws", "azure", "gcp"},
    },
    {
        "name": "mixed-cost-optimized",
        "layers": {"l1": "AWS", "l2": "GCP", "l3_hot": "AZURE", "l3_cool": "AWS", "l3_archive": "GCP", "l4": "AWS", "l5": "AZURE"},
        "required_providers": {"aws", "azure", "gcp"},
    },
]


def _or_none(value: str) -> str | None:
    """Treat empty strings as None."""
    return value if value else None


def _build_cheapest_path(layers: dict) -> list[str]:
    """Build cheapestPath list in the format Flutter expects, e.g. ['L1_AWS', 'L2_AZURE', ...]."""
    mapping = {
        "l1": "L1", "l2": "L2", "l3_hot": "L3_hot",
        "l3_cool": "L3_cool", "l3_archive": "L3_archive",
        "l4": "L4", "l5": "L5",
    }
    return [f"{mapping[k]}_{v}" for k, v in layers.items()]


def _build_result_json(layers: dict) -> str:
    """Build minimal CalcResult JSON that satisfies Flutter's CalcResult.fromJson()."""
    def _layer_cost(cost: float = 1.0):
        return {"cost": cost, "components": {"compute": cost}}

    # Build per-provider cost structure
    provider_costs = {}
    for provider in ["AWS", "AZURE", "GCP"]:
        costs = {}
        for layer_key, layer_label in [("l1", "L1"), ("l2", "L2"), ("l3_hot", "L3_hot"),
                                        ("l3_cool", "L3_cool"), ("l3_archive", "L3_archive"),
                                        ("l4", "L4"), ("l5", "L5")]:
            if layers.get(layer_key) == provider:
                costs[layer_label] = _layer_cost(1.0)
        provider_costs[f"{provider.lower()}Costs"] = costs

    total_cost = sum(
        c.get("cost", 0) for pc in provider_costs.values() for c in pc.values()
    )

    result = {
        "totalCost": total_cost,
        **provider_costs,
        "cheapestPath": _build_cheapest_path(layers),
        "inputParamsUsed": {
            "useEventChecking": True,
            "triggerNotificationWorkflow": True,
            "returnFeedbackToDevice": True,
            "integrateErrorHandling": False,
            "needs3DModel": False,
        }
    }
    return json.dumps(result)


def _build_params_json() -> str:
    """Build minimal optimizer params JSON."""
    return json.dumps({
        "numDevices": 3,
        "messagesPerSecond": 1,
        "messagesSizeKB": 1,
        "dataSizeGB": 10,
        "useEventChecking": True,
        "triggerNotificationWorkflow": True,
        "returnFeedbackToDevice": True,
        "integrateErrorHandling": False,
        "needs3DModel": False,
    })


# ============================================================================
# Cloud Connection Seed Helpers
# ============================================================================

def _build_aws_payload(aws_creds: dict) -> dict | None:
    if not aws_creds.get("aws_access_key_id"):
        return None
    payload = {
        "aws_access_key_id": aws_creds["aws_access_key_id"],
        "aws_secret_access_key": aws_creds.get("aws_secret_access_key", ""),
        "aws_region": aws_creds.get("aws_region", "eu-central-1"),
    }
    session_token = _or_none(aws_creds.get("aws_session_token", ""))
    if session_token:
        payload["aws_session_token"] = session_token
    sso_region = _or_none(aws_creds.get("aws_sso_region", ""))
    if sso_region:
        payload["aws_sso_region"] = sso_region
    return payload


def _build_azure_payload(azure_creds: dict) -> dict | None:
    if not azure_creds.get("azure_subscription_id"):
        return None
    azure_region = azure_creds.get("azure_region", "westeurope")
    return {
        "azure_subscription_id": azure_creds["azure_subscription_id"],
        "azure_client_id": azure_creds.get("azure_client_id", ""),
        "azure_client_secret": azure_creds.get("azure_client_secret", ""),
        "azure_tenant_id": azure_creds.get("azure_tenant_id", ""),
        "azure_region": azure_region,
        "azure_region_iothub": azure_creds.get("azure_region_iothub") or azure_region,
        "azure_region_digital_twin": azure_creds.get("azure_region_digital_twin") or azure_region,
    }


def _build_gcp_payload(gcp_creds: dict, gcp_sa_json: str | None) -> dict | None:
    if not (gcp_creds.get("gcp_project_id") or gcp_sa_json):
        return None
    payload = {
        "gcp_project_id": gcp_creds.get("gcp_project_id", ""),
        "gcp_region": gcp_creds.get("gcp_region", "europe-west1"),
        "gcp_credentials_file": gcp_sa_json,
    }
    billing = _or_none(gcp_creds.get("gcp_billing_account", ""))
    if billing:
        payload["gcp_billing_account"] = billing
    return {key: value for key, value in payload.items() if value}


def _cloud_scope(provider: str, payload: dict) -> dict:
    if provider == "aws":
        return {"region": payload.get("aws_region")}
    if provider == "azure":
        return {
            "subscription_configured": bool(payload.get("azure_subscription_id")),
            "region": payload.get("azure_region"),
            "iot_hub_region": payload.get("azure_region_iothub"),
            "digital_twin_region": payload.get("azure_region_digital_twin"),
        }
    if provider == "gcp":
        return {
            "project_id": payload.get("gcp_project_id"),
            "billing_account_configured": bool(payload.get("gcp_billing_account")),
            "region": payload.get("gcp_region"),
        }
    return {}


def _create_seed_cloud_connections(
    db,
    user: User,
    aws_creds: dict,
    azure_creds: dict,
    gcp_creds: dict,
    gcp_sa_json: str | None,
) -> dict[str, CloudConnection]:
    """Create one encrypted CloudConnection per seeded provider."""
    service = CloudConnectionService(db)
    payloads = {
        "aws": _build_aws_payload(aws_creds),
        "azure": _build_azure_payload(azure_creds),
        "gcp": _build_gcp_payload(gcp_creds, gcp_sa_json),
    }
    auth_types = {
        "aws": "access_key",
        "azure": "service_principal",
        "gcp": "service_account_key",
    }
    connections: dict[str, CloudConnection] = {}
    for provider, payload in payloads.items():
        if not payload:
            continue
        connection_id = str(uuid.uuid4())
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        connection = CloudConnection(
            id=connection_id,
            user_id=user.id,
            provider=provider,
            display_name=f"Seed {provider.upper()} Cloud Connection",
            cloud_scope=json.dumps(_cloud_scope(provider, payload), sort_keys=True),
            auth_type=auth_types[provider],
            encrypted_payload=encrypt_scoped(payload_json, user.id, connection_id),
            payload_fingerprint=service._fingerprint(provider, payload),
            validation_status="untested",
        )
        db.add(connection)
        connections[provider] = connection
    db.flush()
    return connections


def _bind_seed_cloud_connections(config: TwinConfiguration, connections: dict[str, CloudConnection]) -> None:
    """Bind seed twins to provider CloudConnections without copying secret payloads."""
    if aws_connection := connections.get("aws"):
        config.aws_cloud_connection_id = aws_connection.id
    if azure_connection := connections.get("azure"):
        config.azure_cloud_connection_id = azure_connection.id
    if gcp_connection := connections.get("gcp"):
        config.gcp_cloud_connection_id = gcp_connection.id


def _sync_non_secret_regions(config: TwinConfiguration, aws_creds: dict, azure_creds: dict, gcp_creds: dict) -> None:
    """Keep non-secret region fields populated for UI summaries and fallbacks."""
    config.aws_region = aws_creds.get("aws_region", "eu-central-1")
    config.aws_sso_region = _or_none(aws_creds.get("aws_sso_region", ""))
    config.azure_region = azure_creds.get("azure_region", "westeurope")
    config.azure_region_iothub = _or_none(azure_creds.get("azure_region_iothub", ""))
    config.azure_region_digital_twin = _or_none(azure_creds.get("azure_region_digital_twin", ""))
    config.gcp_project_id = gcp_creds.get("gcp_project_id", "")
    config.gcp_region = gcp_creds.get("gcp_region", "europe-west1")


def _seed_legacy_twin_credentials(
    config: TwinConfiguration,
    user: User,
    twin_id: str,
    aws_creds: dict,
    azure_creds: dict,
    gcp_creds: dict,
    gcp_sa_json: str | None,
) -> None:
    """Compatibility-only path for old demos that still require per-twin fields."""
    if aws_creds:
        config.aws_access_key_id = encrypt(aws_creds.get("aws_access_key_id", ""), user.id, twin_id)
        config.aws_secret_access_key = encrypt(aws_creds.get("aws_secret_access_key", ""), user.id, twin_id)
        config.aws_region = aws_creds.get("aws_region", "eu-central-1")
        config.aws_sso_region = _or_none(aws_creds.get("aws_sso_region", ""))
        session_token = _or_none(aws_creds.get("aws_session_token", ""))
        config.aws_session_token = encrypt(session_token, user.id, twin_id) if session_token else None

    if azure_creds:
        config.azure_subscription_id = encrypt(azure_creds.get("azure_subscription_id", ""), user.id, twin_id)
        config.azure_client_id = encrypt(azure_creds.get("azure_client_id", ""), user.id, twin_id)
        config.azure_client_secret = encrypt(azure_creds.get("azure_client_secret", ""), user.id, twin_id)
        config.azure_tenant_id = encrypt(azure_creds.get("azure_tenant_id", ""), user.id, twin_id)
        config.azure_region = azure_creds.get("azure_region", "westeurope")
        config.azure_region_iothub = _or_none(azure_creds.get("azure_region_iothub", ""))
        config.azure_region_digital_twin = _or_none(azure_creds.get("azure_region_digital_twin", ""))

    if gcp_creds:
        config.gcp_project_id = gcp_creds.get("gcp_project_id", "")
        billing = _or_none(gcp_creds.get("gcp_billing_account", ""))
        config.gcp_billing_account = encrypt(billing, user.id, twin_id) if billing else None
        config.gcp_region = gcp_creds.get("gcp_region", "europe-west1")
        if gcp_sa_json:
            config.gcp_service_account_json = encrypt(gcp_sa_json, user.id, twin_id)


# ============================================================================
# Credential Validation
# ============================================================================

async def _validate_provider(provider: str, creds: dict) -> tuple[bool, str]:
    """
    Call Deployer + Optimizer /permissions/verify/{provider} endpoints.
    Retries up to 3 times with 5s delay (Deployer may not be ready yet).
    Returns (valid: bool, message: str).
    """
    # Build provider-specific credential payloads
    creds_opt = dict(creds)
    creds_dep = dict(creds)

    # Azure deployer needs extra region fields
    if provider == "azure":
        creds_dep["azure_region_iothub"] = creds.get("azure_region", "westeurope")
        creds_dep["azure_region_digital_twin"] = creds.get("azure_region", "westeurope")

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                opt_task = client.post(
                    f"{settings.OPTIMIZER_URL}/permissions/verify/{provider}",
                    json=creds_opt,
                )
                dep_task = client.post(
                    f"{settings.DEPLOYER_URL}/permissions/verify/{provider}",
                    json=creds_dep,
                )
                results = await asyncio.gather(opt_task, dep_task, return_exceptions=True)

                # Check optimizer result
                opt_valid = False
                opt_msg = "Unknown error"
                if isinstance(results[0], Exception):
                    opt_msg = f"Optimizer error: {results[0]}"
                elif results[0].status_code == 200:
                    data = results[0].json()
                    opt_valid = data.get("valid", False) or data.get("status") == "valid"
                    opt_msg = data.get("message", "OK")
                else:
                    opt_msg = f"Optimizer HTTP {results[0].status_code}"

                # Check deployer result
                dep_valid = False
                dep_msg = "Unknown error"
                if isinstance(results[1], Exception):
                    dep_msg = f"Deployer error: {results[1]}"
                elif results[1].status_code == 200:
                    data = results[1].json()
                    dep_valid = data.get("valid", False) or data.get("status") == "valid"
                    dep_msg = data.get("message", "OK")
                else:
                    dep_msg = f"Deployer HTTP {results[1].status_code}"

                overall_valid = opt_valid and dep_valid
                msg_parts = []
                if not opt_valid:
                    msg_parts.append(f"Optimizer: {opt_msg}")
                if not dep_valid:
                    msg_parts.append(f"Deployer: {dep_msg}")

                return overall_valid, "; ".join(msg_parts) if msg_parts else "Valid"

        except (httpx.ConnectError, httpx.RequestError) as e:
            if attempt < 2:
                print(
                    f"SEED: {provider.upper()} validation attempt {attempt + 1} failed ({e}), retrying in 5s..."
                )
                await asyncio.sleep(5)
                continue
            return False, f"Connection failed after 3 attempts: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"

    return False, "Failed after 3 attempts"


# ============================================================================
# Main Seed Function
# ============================================================================

async def seed_if_needed():
    """Seed test digital twins if seed user doesn't exist yet."""
    db = SessionLocal()
    try:
        # Idempotency check
        existing = db.query(User).filter(User.email == SEED_USER_EMAIL).first()
        if existing:
            print("SEED: Seed data already exists, skipping.")
            return

        print("SEED: Starting seed data creation...")

        # Read credential files
        try:
            with open(settings.SEED_CREDENTIALS_FILE, "r") as f:
                creds_data = json.load(f)
        except FileNotFoundError:
            print(f"SEED: Credentials file not found at {settings.SEED_CREDENTIALS_FILE} — skipping seed.")
            return

        gcp_sa_json = None
        try:
            with open(settings.SEED_GCP_CREDENTIALS_FILE, "r") as f:
                gcp_sa_json = f.read()
        except FileNotFoundError:
            print(f"SEED: GCP credentials file not found at {settings.SEED_GCP_CREDENTIALS_FILE} — GCP twins will not have service account.")

        # Extract credential sets
        aws_creds = creds_data.get("aws", {})
        azure_creds = creds_data.get("azure", {})
        gcp_creds = creds_data.get("gcp", {})

        # Create seed user
        user = User(
            id=str(uuid.uuid4()),
            email=SEED_USER_EMAIL,
            name="Seed User",
            auth_provider="seed",
        )
        db.add(user)
        db.flush()  # Get user ID without committing
        print(f"SEED: Created seed user: {user.email} (id={user.id})")

        cloud_connections = _create_seed_cloud_connections(
            db,
            user,
            aws_creds,
            azure_creds,
            gcp_creds,
            gcp_sa_json,
        )
        print(f"SEED: Created {len(cloud_connections)} provider Cloud Connections.")

        # Create twins
        for twin_def in TWIN_DEFINITIONS:
            twin_id = str(uuid.uuid4())
            layers = twin_def["layers"]
            required = twin_def["required_providers"]

            # --- DigitalTwin ---
            twin = DigitalTwin(
                id=twin_id,
                user_id=user.id,
                name=twin_def["name"],
                state=TwinState.DRAFT,
            )
            db.add(twin)

            # --- TwinConfiguration (CloudConnection bindings) ---
            config = TwinConfiguration(
                id=str(uuid.uuid4()),
                twin_id=twin_id,
                debug_mode=False,
                highest_step_reached=5,
            )

            _bind_seed_cloud_connections(config, cloud_connections)
            _sync_non_secret_regions(config, aws_creds, azure_creds, gcp_creds)
            if settings.SEED_LEGACY_TWIN_CREDENTIALS:
                _seed_legacy_twin_credentials(
                    config,
                    user,
                    twin_id,
                    aws_creds,
                    azure_creds,
                    gcp_creds,
                    gcp_sa_json,
                )

            db.add(config)

            # --- OptimizerConfiguration ---
            opt_config = OptimizerConfiguration(
                id=str(uuid.uuid4()),
                twin_id=twin_id,
                cheapest_l1=layers["l1"],
                cheapest_l2=layers["l2"],
                cheapest_l3_hot=layers["l3_hot"],
                cheapest_l3_cool=layers["l3_cool"],
                cheapest_l3_archive=layers["l3_archive"],
                cheapest_l4=layers["l4"],
                cheapest_l5=layers["l5"],
                params=_build_params_json(),
                result_json=_build_result_json(layers),
            )
            db.add(opt_config)

            # --- DeployerConfiguration ---
            l2_provider = layers["l2"]
            l4_provider = layers["l4"]

            dep_config = DeployerConfiguration(
                id=str(uuid.uuid4()),
                twin_id=twin_id,
                deployer_digital_twin_name="digital-twin",
                config_events_json=CONFIG_EVENTS_JSON,
                config_iot_devices_json=CONFIG_IOT_DEVICES_JSON,
                payloads_json=PAYLOADS_JSON,
                processor_contents=_processor_contents(l2_provider),
                processor_validated=PROCESSOR_VALIDATED,
                processor_requirements=json.dumps({d: "" for d in DEVICE_IDS}),
                event_feedback_content=_feedback_content(l2_provider),
                event_feedback_validated=True,
                event_feedback_requirements="",
                event_action_contents=_action_contents(l2_provider),
                event_action_validated=EVENT_ACTION_VALIDATED,
                event_action_requirements=json.dumps({n: "" for n in EVENT_ACTION_NAMES}),
                state_machine_content=STATE_MACHINES.get(l2_provider, STATE_MACHINES["AWS"]),
                state_machine_validated=True,
                hierarchy_content=HIERARCHY_AWS if l4_provider == "AWS" else HIERARCHY_AZURE,
                hierarchy_validated=True,
                user_config_content=USER_CONFIG_JSON,
                user_config_validated=True,
                config_json_validated=True,
                config_events_validated=True,
                config_iot_devices_validated=True,
                payloads_validated=True,
                scene_glb_uploaded=False,
                scene_config_content=None,
                scene_config_validated=False,
            )
            db.add(dep_config)

            print(f"SEED: Created twin '{twin_def['name']}' (id={twin_id})")

        # Commit all DB records before validation
        db.commit()
        print("SEED: All 5 twins created. Starting credential validation...")

        # --- Validate credentials per provider (once, shared across twins) ---
        validation_results = {}  # provider -> (valid, message)

        # Build plaintext credential payloads for validation. These are request
        # scoped and are not copied into per-twin legacy credential fields.
        if aws_payload := _build_aws_payload(aws_creds):
            validation_results["aws"] = await _validate_provider("aws", aws_payload)

        if azure_payload := _build_azure_payload(azure_creds):
            validation_results["azure"] = await _validate_provider("azure", azure_payload)

        if gcp_payload := _build_gcp_payload(gcp_creds, gcp_sa_json):
            validation_results["gcp"] = await _validate_provider("gcp", gcp_payload)

        for provider, connection in cloud_connections.items():
            valid, msg = validation_results.get(provider, (False, "No credentials"))
            connection.validation_status = "valid" if valid else "invalid"
            connection.validation_message = msg

        # --- Apply validation results to twins ---
        twins = db.query(DigitalTwin).filter(DigitalTwin.user_id == user.id).all()
        for twin in twins:
            twin_def = next(d for d in TWIN_DEFINITIONS if d["name"] == twin.name)
            required = twin_def["required_providers"]
            config = twin.configuration

            all_valid = True
            for provider in required:
                valid, msg = validation_results.get(provider, (False, "No credentials"))
                # Update per-provider validated flag
                if provider == "aws":
                    config.aws_validated = valid
                elif provider == "azure":
                    config.azure_validated = valid
                elif provider == "gcp":
                    config.gcp_validated = valid

                if not valid:
                    all_valid = False
                    print(
                        f"⚠️ SEED: Twin '{twin.name}' — {provider.upper()} credentials INVALID ({msg})"
                    )

            if all_valid:
                twin.state = TwinState.CONFIGURED
                print(f"✅ SEED: Twin '{twin.name}' — all credentials valid. State: CONFIGURED")
            else:
                print(
                    f"⚠️ SEED: Twin '{twin.name}' — some credentials invalid. State: DRAFT"
                )

        db.commit()
        print(f"SEED: Seed complete. {len(TWIN_DEFINITIONS)} twins created.")

    except Exception as e:
        print(f"SEED: Error during seeding: {e}", flush=True)
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
