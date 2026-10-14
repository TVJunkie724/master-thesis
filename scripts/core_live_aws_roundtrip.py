"""One real AWS simulator roundtrip using the existing Core lifecycle.

No alternate runtime, new infrastructure profile or direct command injection.
The private certificate journal also covers registration failures before attach.
"""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import time
from types import SimpleNamespace
import uuid

from botocore.exceptions import ClientError

from scripts import core_live_aws as core
from scripts.run_core_evaluation import save

session = core.session
stop_builds = core.stop_builds
diagnostics = core.diagnostics
DEVICE = "core-sensor"


def configure(values, root):
    values["events"] = [{"rule_id": "command-check", "condition": "value == INTEGER(42)", "action": {
        "type": "function", "functionName": "poc-command-check",
        "feedback": {"device_id": DEVICE, "payload": "roundtrip-confirmed"},
    }}]
    save(root / "config_events.json", values["events"])
    save(root / "config_iot_devices.json", [{"id": DEVICE}])


def _journal(values):
    return Path(values["project_path"]) / "command-device-identity.json"


def _absent(call, **kwargs):
    try:
        return call(**kwargs)
    except ClientError as error:
        if error.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        return None


class JournaledIoT:
    def __init__(self, client, values):
        self.client, self.values = client, values

    def __getattr__(self, name):
        return getattr(self.client, name)

    def create_keys_and_certificate(self, **kwargs):
        result = self.client.create_keys_and_certificate(**kwargs)
        try:
            save(_journal(self.values), {"certificate_id": result["certificateId"],
                                        "certificate_arn": result["certificateArn"]})
        except BaseException:
            self.client.update_certificate(certificateId=result["certificateId"], newStatus="INACTIVE")
            self.client.delete_certificate(certificateId=result["certificateId"], forceDelete=True)
            raise
        return result


def inventory(values, prefix):
    result = core.inventory(values, prefix)
    iot = session(values).client("iot")
    policy = f"{prefix}-{DEVICE}-policy"
    result["simulator_policy"] = int(_absent(iot.get_policy, policyName=policy) is not None)
    path = _journal(values)
    result["simulator_certificate"] = 0
    if path.exists():
        identity = json.loads(path.read_text())
        result["simulator_certificate"] = int(_absent(
            iot.describe_certificate, certificateId=identity["certificate_id"]) is not None)
    return result


def cleanup_device(values):
    iot = session(values).client("iot")
    thing = f"{values['digital_twin_name']}-{DEVICE}"
    policy = thing + "-policy"
    path = _journal(values)
    identity = json.loads(path.read_text()) if path.exists() else None
    principals = _absent(iot.list_thing_principals, thingName=thing) or {}
    if principals.get("nextToken"):
        raise RuntimeError("COMMAND_DEVICE_INVENTORY_TRUNCATED")
    attached = principals.get("principals", [])
    if attached and (not identity or attached != [identity["certificate_arn"]]):
        raise RuntimeError("COMMAND_DEVICE_OWNERSHIP_MISMATCH")
    if identity and _absent(iot.describe_certificate, certificateId=identity["certificate_id"]):
        arn = identity["certificate_arn"]
        thing_page = iot.list_principal_things(principal=arn)
        policy_page = iot.list_attached_policies(target=arn)
        if thing_page.get("nextToken") or policy_page.get("nextMarker"):
            raise RuntimeError("COMMAND_DEVICE_INVENTORY_TRUNCATED")
        things = thing_page.get("things", [])
        policies = policy_page.get("policies", [])
        if any(name != thing for name in things) or any(p["policyName"] != policy for p in policies):
            raise RuntimeError("COMMAND_CERTIFICATE_OWNERSHIP_MISMATCH")
        for item in policies:
            iot.detach_policy(policyName=item["policyName"], target=arn)
        for name in things:
            iot.detach_thing_principal(thingName=name, principal=arn)
        iot.update_certificate(certificateId=identity["certificate_id"], newStatus="INACTIVE")
        iot.delete_certificate(certificateId=identity["certificate_id"], forceDelete=True)
    _absent(iot.delete_thing, thingName=thing)
    _absent(iot.delete_policy, policyName=policy)


def before_destroy(values, state):
    try:
        cleanup_device(values)
    finally:
        core.before_destroy(values, state)


def smoke(values, outputs):
    from src.providers.terraform.aws_deployer import _register_iot_device
    from src.iot_device_simulator.aws import globals as simulator_config, transmission

    aws = session(values)
    iot = JournaledIoT(aws.client("iot"), values)
    account = aws.client("sts").get_caller_identity()["Account"]
    endpoint = iot.describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]
    root = Path(values["project_path"])
    registration_started = time.monotonic()
    _register_iot_device(SimpleNamespace(clients={"iot": iot}, region=values["aws_region"]),
                         root, {"id": DEVICE}, values["digital_twin_name"], account, endpoint)
    registration_seconds = time.monotonic() - registration_started
    generated = root / "iot_device_simulator/aws" / DEVICE / "config_generated.json"
    config = json.loads(generated.read_text())
    for key in ("cert_path", "key_path", "root_ca_path"):
        config[key] = str((generated.parent / config[key]).resolve())
    trace = "TRACE-" + uuid.uuid4().hex.upper()
    now = datetime.now(timezone.utc)
    telemetry = {"event_id": trace, "source_id": DEVICE, "source_sequence": trace,
                 "correlation_id": trace, "payload": {"device_id": DEVICE,
                 "metric": "temperature", "value": 42, "event_time": now.isoformat()}}
    capture = io.StringIO()
    previous = simulator_config.config
    started = time.monotonic()
    try:
        simulator_config.config = config
        with redirect_stdout(capture), redirect_stderr(capture):
            received = transmission.listen_for_command(300, telemetry_payload=telemetry)
    finally:
        simulator_config.config = previous
        from src.core.secure_files import atomic_write_private_bytes
        atomic_write_private_bytes(root / "simulator.log", capture.getvalue().encode())
    if not received:
        raise RuntimeError("COMMAND_RECEIPT_TIMEOUT")
    checkpoints = [json.loads(line.removeprefix("T2MC_CHECKPOINT "))
                   for line in capture.getvalue().splitlines() if line.startswith("T2MC_CHECKPOINT ")]
    correlated = {point["stage"]: point for point in checkpoints if point.get("trace_id") == trace}
    if not {"simulator_sent", "simulator_command_received"} <= correlated.keys():
        raise RuntimeError("COMMAND_CHECKPOINTS_MISSING")
    elapsed = (datetime.fromisoformat(correlated["simulator_command_received"]["observed_at"].replace("Z", "+00:00"))
               - datetime.fromisoformat(correlated["simulator_sent"]["observed_at"].replace("Z", "+00:00"))).total_seconds()
    if elapsed < 0:
        raise RuntimeError("COMMAND_CHECKPOINT_ORDER_INVALID")
    reader = aws.client("lambda")
    query = {"queryStringParameters": {"device_id": DEVICE, "metric": "temperature",
             "bucket_seconds": "0", "limit": "20", "from": (now - timedelta(minutes=1)).isoformat(),
             "to": (now + timedelta(minutes=10)).isoformat()}}
    for _ in range(60):
        result = reader.invoke(FunctionName=outputs["aws_component_storage_read_access_output"]["reader_function_name"],
                               Payload=json.dumps(query).encode())
        response = json.loads(result["Payload"].read())
        points = json.loads(response.get("body", "{}")).get("points", [])
        if response.get("statusCode") == 200 and any(
            p.get("value") == 42 and datetime.fromisoformat(p["event_time"].replace("Z", "+00:00")) == now
            for p in points if p.get("event_time")
        ):
            return {"sent": 1, "read_back": 1, "command_received": 1,
                    "roundtrip_seconds": elapsed, "verification_seconds": time.monotonic() - started,
                    "device_registration_seconds": registration_seconds,
                    "checkpoints": checkpoints, "scope": "local_aws_simulator_command_and_l3"}
        time.sleep(2)
    raise RuntimeError("COMMAND_L3_READBACK_TIMEOUT")
