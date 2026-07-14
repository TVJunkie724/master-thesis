"""Fail-closed AWS SDK-owned post-deployment resources."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING
from urllib.parse import unquote

from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.runtime_outcome import RuntimeRun

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)


def _simulator_iot_policy(*, region: str, account_id: str, device_id: str, topic: str) -> dict:
    """Return the exact runtime permissions needed by one simulator device."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ConnectAsDevice",
                "Effect": "Allow",
                "Action": "iot:Connect",
                "Resource": f"arn:aws:iot:{region}:{account_id}:client/{device_id}",
            },
            {
                "Sid": "PublishDeviceTelemetry",
                "Effect": "Allow",
                "Action": "iot:Publish",
                "Resource": f"arn:aws:iot:{region}:{account_id}:topic/{topic}",
            },
        ],
    }


def _policy_document(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise RuntimeError("AWS IoT policy response did not contain a valid document")
    parsed = json.loads(unquote(value))
    if not isinstance(parsed, dict):
        raise RuntimeError("AWS IoT policy response did not contain an object")
    return parsed


def _ensure_iot_policy(iot, *, policy_name: str, policy_document: dict) -> None:
    """Create or atomically update an IoT policy to the required document."""
    serialized = json.dumps(policy_document, separators=(",", ":"), sort_keys=True)
    try:
        policy = iot.get_policy(policyName=policy_name)
    except iot.exceptions.ResourceNotFoundException:
        iot.create_policy(policyName=policy_name, policyDocument=serialized)
        return

    current = iot.get_policy_version(
        policyName=policy_name,
        policyVersionId=policy["defaultVersionId"],
    )
    if _policy_document(current["policyDocument"]) == policy_document:
        return

    versions = iot.list_policy_versions(policyName=policy_name).get("policyVersions", [])
    if len(versions) >= 5:
        removable = sorted(
            (version for version in versions if not version.get("isDefaultVersion")),
            key=lambda version: str(version.get("createDate") or ""),
        )
        if not removable:
            raise RuntimeError(f"AWS IoT policy '{policy_name}' has no removable version")
        iot.delete_policy_version(
            policyName=policy_name,
            policyVersionId=removable[0]["versionId"],
        )
    iot.create_policy_version(
        policyName=policy_name,
        policyDocument=serialized,
        setAsDefault=True,
    )


def _require_aws_provider(context: "DeploymentContext"):
    provider = context.providers.get("aws")
    if provider is None:
        raise RuntimeError("AWS provider not initialized")
    return provider


def _resolve_lambda_arn(lambda_client, outputs: dict, output_key: str, name: str) -> str | None:
    arn = outputs.get(output_key)
    if arn:
        return str(arn)
    try:
        return lambda_client.get_function(FunctionName=name)["Configuration"]["FunctionArn"]
    except lambda_client.exceptions.ResourceNotFoundException:
        return None


def _hierarchy_contains_component(nodes: list[dict]) -> bool:
    return any(
        node.get("type") == "component"
        or _hierarchy_contains_component(node.get("children", []))
        for node in nodes
    )


def create_twinmaker_entities(
    context: "DeploymentContext",
    project_path: Path,
    terraform_outputs: dict,
) -> None:
    """Create every configured TwinMaker entity and component fail-closed."""
    del project_path
    provider = _require_aws_provider(context)
    workspace_id = terraform_outputs.get("aws_twinmaker_workspace_id")
    if not workspace_id:
        raise RuntimeError("Terraform output aws_twinmaker_workspace_id is required")
    hierarchy = context.config.hierarchy
    if not isinstance(hierarchy, list) or not hierarchy:
        raise ValueError("AWS TwinMaker hierarchy must be a non-empty list")

    twinmaker = provider.clients["twinmaker"]
    lambda_client = provider.clients["lambda"]
    twin_name = context.config.digital_twin_name
    connector_arn = _resolve_lambda_arn(
        lambda_client,
        terraform_outputs,
        "aws_l4_connector_function_arn",
        f"{twin_name}-l4-connector",
    )
    connector_last_entry_arn = _resolve_lambda_arn(
        lambda_client,
        terraform_outputs,
        "aws_l4_connector_last_entry_function_arn",
        f"{twin_name}-l4-connector-last-entry",
    ) or connector_arn
    if _hierarchy_contains_component(hierarchy) and not connector_arn:
        raise RuntimeError("TwinMaker hierarchy contains components but no L4 connector exists")

    run = RuntimeRun("AWS", "TwinMaker", logger)
    for root in hierarchy:
        _create_twinmaker_node(
            run,
            twinmaker,
            workspace_id=str(workspace_id),
            twin_name=twin_name,
            node=root,
            parent_id=None,
            connector_arn=connector_arn,
            connector_last_entry_arn=connector_last_entry_arn,
        )
    run.raise_if_failed()


def _create_twinmaker_node(
    run: RuntimeRun,
    twinmaker,
    *,
    workspace_id: str,
    twin_name: str,
    node: dict,
    parent_id: str | None,
    connector_arn: str | None,
    connector_last_entry_arn: str | None,
) -> None:
    node_type = node.get("type")
    if node_type == "entity":
        entity_id = node.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            run.attempt("invalid entity", lambda: (_ for _ in ()).throw(
                ValueError("TwinMaker entity is missing a non-empty id")
            ))
            return
        if not _create_entity(run, twinmaker, workspace_id, entity_id, parent_id):
            return
        for child in node.get("children", []):
            _create_twinmaker_node(
                run,
                twinmaker,
                workspace_id=workspace_id,
                twin_name=twin_name,
                node=child,
                parent_id=entity_id,
                connector_arn=connector_arn,
                connector_last_entry_arn=connector_last_entry_arn,
            )
        return
    if node_type == "component":
        _create_component(
            run,
            twinmaker,
            workspace_id=workspace_id,
            twin_name=twin_name,
            node=node,
            parent_id=parent_id,
            connector_arn=connector_arn,
            connector_last_entry_arn=connector_last_entry_arn,
        )
        return
    run.attempt(
        str(node.get("id") or node.get("name") or "invalid node"),
        lambda: (_ for _ in ()).throw(
            ValueError(f"Unsupported TwinMaker hierarchy node type: {node_type!r}")
        ),
    )


def _create_entity(run, twinmaker, workspace_id: str, entity_id: str, parent_id: str | None) -> bool:
    def create() -> bool:
        params = {
            "workspaceId": workspace_id,
            "entityId": entity_id,
            "entityName": entity_id,
            "description": f"Twin entity for {entity_id}",
        }
        if parent_id:
            params["parentEntityId"] = parent_id
        try:
            twinmaker.create_entity(**params)
        except twinmaker.exceptions.ConflictException:
            logger.info("TwinMaker entity already exists: %s", entity_id)
        return True

    return bool(run.attempt(entity_id, create, default=False))


def _component_properties(node: dict) -> dict:
    properties = {
        prop["name"]: {
            "dataType": {"type": prop.get("dataType", "STRING")},
            "isTimeSeries": True,
            "isStoredExternally": True,
        }
        for prop in node.get("properties", [])
    }
    for prop in node.get("constProperties", []):
        data_type = prop.get("dataType", "STRING")
        properties[prop["name"]] = {
            "dataType": {"type": data_type},
            "defaultValue": {f"{data_type.lower()}Value": prop.get("value")},
            "isTimeSeries": False,
            "isStoredExternally": False,
        }
    if not any(not prop.get("isTimeSeries") for prop in properties.values()):
        raise ValueError("TwinMaker component requires at least one constProperty")
    return properties


def _create_component(
    run: RuntimeRun,
    twinmaker,
    *,
    workspace_id: str,
    twin_name: str,
    node: dict,
    parent_id: str | None,
    connector_arn: str | None,
    connector_last_entry_arn: str | None,
) -> None:
    name = node.get("name", node.get("componentTypeId"))
    if not isinstance(name, str) or not name:
        run.attempt("invalid component", lambda: (_ for _ in ()).throw(
            ValueError("TwinMaker component is missing a non-empty name")
        ))
        return
    if not parent_id:
        run.attempt(name, lambda: (_ for _ in ()).throw(
            ValueError("TwinMaker component must be nested below an entity")
        ))
        return
    component_type_id = f"{twin_name}-{name}"

    def create_and_attach() -> bool:
        functions = {"dataReader": {"implementedBy": {"lambda": {"arn": connector_arn}}}}
        if connector_last_entry_arn:
            functions["attributePropertyValueReaderByEntity"] = {
                "implementedBy": {"lambda": {"arn": connector_last_entry_arn}}
            }
        try:
            twinmaker.create_component_type(
                workspaceId=workspace_id,
                componentTypeId=component_type_id,
                propertyDefinitions=_component_properties(node),
                functions=functions,
            )
        except twinmaker.exceptions.ConflictException:
            logger.info("TwinMaker component type already exists: %s", component_type_id)
        else:
            _wait_for_component_type(twinmaker, workspace_id, component_type_id)
        try:
            twinmaker.update_entity(
                workspaceId=workspace_id,
                entityId=parent_id,
                componentUpdates={name: {"componentTypeId": component_type_id}},
            )
        except twinmaker.exceptions.ConflictException:
            logger.info("TwinMaker component already attached: %s", name)
        return True

    run.attempt(component_type_id, create_and_attach, default=False)


def _wait_for_component_type(twinmaker, workspace_id: str, component_type_id: str) -> None:
    for _ in range(30):
        response = twinmaker.get_component_type(
            workspaceId=workspace_id,
            componentTypeId=component_type_id,
        )
        state = response.get("status", {}).get("state")
        if state == "ACTIVE":
            return
        if state in {"ERROR", "DELETING"}:
            raise RuntimeError(f"TwinMaker component entered terminal state {state}")
        time.sleep(1)
    raise TimeoutError("TwinMaker component did not become active within 30 seconds")


def register_aws_iot_devices(
    context: "DeploymentContext",
    project_path: Path,
    terraform_outputs: dict | None = None,
) -> None:
    """Register all configured AWS IoT devices with exact simulator policies."""
    del terraform_outputs
    provider = _require_aws_provider(context)
    devices = context.config.iot_devices
    if not devices:
        return
    iot = provider.clients["iot"]
    account_id = provider.clients["sts"].get_caller_identity()["Account"]
    endpoint = iot.describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]
    if not endpoint:
        raise RuntimeError("AWS IoT Data-ATS endpoint is empty")

    run = RuntimeRun("AWS", "IoT device registration", logger)
    for device in devices:
        device_id = device.get("id")
        if not isinstance(device_id, str) or not device_id:
            run.attempt("invalid device", lambda: (_ for _ in ()).throw(
                ValueError("IoT device is missing a non-empty id")
            ))
            continue
        run.attempt(
            device_id,
            lambda device=device: _register_iot_device(
                provider,
                project_path,
                device,
                context.config.digital_twin_name,
                account_id,
                endpoint,
            ),
        )
    run.raise_if_failed()


def _register_iot_device(provider, project_path: Path, device: dict, twin_name: str, account_id: str, endpoint: str) -> None:
    iot = provider.clients["iot"]
    device_id = device["id"]
    thing_name = f"{twin_name}-{device_id}"
    policy_name = f"{thing_name}-policy"
    topic = f"dt/{twin_name}/{device_id}/telemetry"
    try:
        iot.create_thing(thingName=thing_name)
    except iot.exceptions.ResourceAlreadyExistsException:
        pass

    cert_dir = project_path / "iot_devices_auth" / device_id
    cert_path = cert_dir / "certificate.pem.crt"
    key_path = cert_dir / "private.pem.key"
    created_certificate_id: str | None = None
    if cert_path.is_file() and key_path.is_file():
        principals = iot.list_thing_principals(thingName=thing_name).get("principals", [])
        certificate_arns = [principal for principal in principals if ":cert/" in principal]
        if len(certificate_arns) != 1:
            raise RuntimeError(f"Cannot prove exactly one certificate for '{device_id}'")
        certificate_arn = certificate_arns[0]
        certificate_id = certificate_arn.rsplit("/", 1)[-1]
        remote_certificate = iot.describe_certificate(certificateId=certificate_id)[
            "certificateDescription"
        ]["certificatePem"]
        if cert_path.read_text(encoding="utf-8").strip() != remote_certificate.strip():
            raise RuntimeError(
                f"Local certificate does not match the attached identity for '{device_id}'"
            )
        cert_path.chmod(0o600)
        key_path.chmod(0o600)
    else:
        certificate = iot.create_keys_and_certificate(setAsActive=True)
        certificate_arn = certificate["certificateArn"]
        created_certificate_id = certificate_arn.rsplit("/", 1)[-1]
        try:
            atomic_write_private_bytes(
                cert_path,
                certificate["certificatePem"].encode("utf-8"),
            )
            atomic_write_private_bytes(
                key_path,
                certificate["keyPair"]["PrivateKey"].encode("utf-8"),
            )
            atomic_write_private_bytes(
                cert_dir / "public.pem.key",
                certificate["keyPair"]["PublicKey"].encode("utf-8"),
            )
        except Exception:
            _rollback_created_certificate(iot, created_certificate_id, certificate_arn)
            _remove_local_device_identity(cert_dir)
            raise

    try:
        _ensure_iot_policy(
            iot,
            policy_name=policy_name,
            policy_document=_simulator_iot_policy(
                region=provider.region,
                account_id=account_id,
                device_id=device_id,
                topic=topic,
            ),
        )
        iot.attach_thing_principal(thingName=thing_name, principal=certificate_arn)
        iot.attach_policy(policyName=policy_name, target=certificate_arn)
        _generate_aws_simulator_config(project_path, device, twin_name, endpoint)
    except Exception:
        if created_certificate_id:
            _rollback_created_certificate(
                iot,
                created_certificate_id,
                certificate_arn,
                thing_name=thing_name,
                policy_name=policy_name,
            )
            _remove_local_device_identity(cert_dir)
        raise


def _rollback_created_certificate(
    iot,
    certificate_id: str,
    certificate_arn: str,
    *,
    thing_name: str | None = None,
    policy_name: str | None = None,
) -> None:
    """Best-effort compensation for a certificate created by the current attempt."""
    operations = []
    if policy_name:
        operations.append(
            lambda: iot.detach_policy(policyName=policy_name, target=certificate_arn)
        )
    if thing_name:
        operations.append(
            lambda: iot.detach_thing_principal(
                thingName=thing_name,
                principal=certificate_arn,
            )
        )
    operations.extend(
        (
            lambda: iot.update_certificate(
                certificateId=certificate_id,
                newStatus="INACTIVE",
            ),
            lambda: iot.delete_certificate(certificateId=certificate_id, forceDelete=True),
        )
    )
    for operation in operations:
        try:
            operation()
        except Exception:
            logger.warning("AWS IoT certificate compensation step was incomplete")


def _remove_local_device_identity(cert_dir: Path) -> None:
    for name in ("certificate.pem.crt", "private.pem.key", "public.pem.key"):
        (cert_dir / name).unlink(missing_ok=True)


def _generate_aws_simulator_config(
    project_path: Path,
    iot_device: dict,
    digital_twin_name: str,
    iot_endpoint: str,
) -> None:
    """Generate non-secret simulator metadata after certificate registration."""
    device_id = iot_device["id"]
    config_data = {
        "endpoint": iot_endpoint,
        "topic": f"dt/{digital_twin_name}/{device_id}/telemetry",
        "device_id": device_id,
        "cert_path": f"../../../iot_devices_auth/{device_id}/certificate.pem.crt",
        "key_path": f"../../../iot_devices_auth/{device_id}/private.pem.key",
        "root_ca_path": str(
            Path(__file__).parents[2]
            / "iot_device_simulator"
            / "aws"
            / "AmazonRootCA1.pem"
        ),
        "payload_path": "../../payloads.json",
        "credential_class": "aws_iot_device_certificate",
        "credential_contract_version": 1,
        "permission_scope": "exact_client_and_telemetry_topic",
    }
    target = (
        project_path
        / "iot_device_simulator"
        / "aws"
        / device_id
        / "config_generated.json"
    )
    atomic_write_private_bytes(
        target,
        json.dumps(config_data, indent=2).encode("utf-8"),
    )


def configure_aws_grafana(
    context: "DeploymentContext",
    terraform_outputs: dict,
) -> None:
    """Create the required Grafana datasource or fail the deployment."""
    import requests

    _require_aws_provider(context)
    required = {
        "endpoint": terraform_outputs.get("aws_grafana_endpoint"),
        "api_key": terraform_outputs.get("aws_grafana_api_key"),
        "hot_reader": terraform_outputs.get("aws_l3_hot_reader_url"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError("Missing AWS Grafana outputs: " + ", ".join(missing))
    response = requests.post(
        f"{required['endpoint']}/api/datasources",
        headers={
            "Authorization": f"Bearer {required['api_key']}",
            "Content-Type": "application/json",
        },
        json={
            "name": "Hot Storage API",
            "type": "marcusolsson-json-datasource",
            "url": required["hot_reader"],
            "access": "proxy",
            "isDefault": True,
        },
        timeout=30,
    )
    if response.status_code not in {200, 201, 409}:
        raise RuntimeError(f"Grafana API returned HTTP {response.status_code}")
