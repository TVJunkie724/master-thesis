"""One isolated L4 service check using the actual application seed and adapter.

Infrastructure lifecycle is deliberately separate: this module is called only
inside a supervised, explicitly approved L4 run. It never provisions Terraform
resources or claims deployed Event-Layer delivery. Clients are supplied by the
runner with bounded retries; identifiers/results remain in private evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

from src.providers.terraform.aws_deployer import create_twinmaker_entities, _six_layer_seed
from src.providers.azure.layers.layer_4_adt import six_layer_seed

ROOT = Path(__file__).resolve().parents[1] / "3-cloud-deployer" / "src" / "providers"
DEVICE = "poc-device-001"


def fixture(run_id):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": run_id + "-projection", "event_type": "twin.state.upserted",
        "deployment_id": run_id, "source_id": DEVICE,
        "source_sequence": run_id + "-1", "occurred_at": now,
        "correlation_id": run_id, "causation_id": run_id + "-telemetry",
        "producer": "component.historical-persistence",
        "payload": {"twin_id": DEVICE, "source_id": DEVICE,
                    "source_sequence": run_id + "-1", "observed_at": now,
                    "state_patch": {"temperature": 20.5}},
    }


def load_adapter(provider):
    directory = (ROOT / "aws/lambda_functions/six-layer-domain" if provider == "aws"
                 else ROOT / "azure/azure_functions/six-layer-domain")
    path = directory / ("handler.py" if provider == "aws" else "function_app.py")
    previous = sys.modules.get("core")
    sys.path.insert(0, str(directory))
    try:
        if provider == "azure":
            spec = importlib.util.spec_from_file_location("core", directory / "core.py")
            core = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(core)
            sys.modules["core"] = core
        spec = importlib.util.spec_from_file_location("l4_" + provider, path)
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
    finally:
        sys.path.remove(str(directory))
        if previous is None:
            sys.modules.pop("core", None)
        else:
            sys.modules["core"] = previous
    return runtime, hashlib.sha256(path.read_bytes()).hexdigest()


class BoundedClient:
    """Count this experiment's SDK calls and reject oversized data responses."""
    def __init__(self, client, limit=300):
        self.client, self.limit, self.calls, self.response_bytes = client, limit, 0, 0

    def __getattr__(self, name):
        attr = getattr(self.client, name)
        if not callable(attr) or name == "exceptions":
            return attr

        def call(*args, **kwargs):
            if self.calls >= self.limit:
                raise RuntimeError("L4_SDK_CALL_LIMIT")
            self.calls += 1
            response = attr(*args, **kwargs)
            size = len(json.dumps(response, default=str).encode())
            self.response_bytes += size
            if size > 16 * 1024:
                raise RuntimeError("L4_RESPONSE_SIZE_LIMIT")
            return response
        return call


def wait_for(check, attempts=60, interval=2):
    for attempt in range(attempts):
        if check():
            return attempt + 1
        if attempt + 1 < attempts:
            time.sleep(interval)
    raise TimeoutError("L4_READINESS_OR_PROJECTION_TIMEOUT")


def native_snapshot(response):
    if response.get("status", {}).get("state") != "ACTIVE":
        return {}
    properties = response.get("components", {}).get("telemetry", {}).get("properties", {})
    return {key: prop.get("value", {}).get("doubleValue" if key == "value" else "stringValue")
            for key, prop in properties.items()}


def matches(snapshot, event, provider):
    try:
        observed = datetime.fromisoformat(str(snapshot.get(
            "observedAt" if provider == "aws" else "lastUpdate", "")).replace("Z", "+00:00"))
    except ValueError:
        return False
    return (snapshot.get("metric") == "temperature"
            and type(snapshot.get("value")) in (int, float)
            and snapshot["value"] == 20.5
            and snapshot.get("sourceSequence") == event["source_sequence"]
            and snapshot.get("lastEventId") == event["event_id"]
            and observed == datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00")))


def check(provider, client, run_id, *, workspace_id=None, report=None):
    """Seed two nodes, invoke real adapter, read exact state, replay and recheck."""
    bounded = BoundedClient(client)
    config = SimpleNamespace(digital_twin_name=run_id, hierarchy=[],
                             iot_devices=[{"id": DEVICE}])
    runtime, digest = load_adapter(provider)
    event = fixture(run_id)
    report = report if report is not None else {}
    report.update({"provider": provider, "scope": "isolated_l4_local_adapter",
              "adapter_sha256": digest,
              "fixture_sha256": hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest(),
              "fixture": event, "phases": [], "functional_pass": False})

    def measure(name, action):
        started = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        succeeded = False
        try:
            result = action()
            succeeded = True
            return result
        finally:
            report["phases"].append({"phase": name, "passed": succeeded,
                                    "started_at": started_at,
                                    "finished_at": datetime.now(timezone.utc).isoformat(),
                                    "seconds": round(time.monotonic() - started, 3)})

    previous_workspace = os.environ.get("TWINMAKER_WORKSPACE")
    try:
        if provider == "aws":
            if not workspace_id or not workspace_id.startswith(run_id + "-"):
                raise ValueError("L4_WORKSPACE_OWNERSHIP_REQUIRED")
            context = SimpleNamespace(
                providers={"aws": SimpleNamespace(clients={"twinmaker": bounded})}, config=config,
                resolved_deployment_graph=SimpleNamespace(profile_ref={"id": "six-layer-eventing", "version": "1"}),
            )
            report["model_sha256"] = hashlib.sha256(json.dumps(_six_layer_seed(context), sort_keys=True).encode()).hexdigest()
            measure("seed", lambda: create_twinmaker_entities(context, Path("."), {
                "aws_component_twin_state_output": {"workspace_id": workspace_id}}))
            os.environ["TWINMAKER_WORKSPACE"] = workspace_id
            runtime._client = lambda service: bounded if service == "iottwinmaker" else None
            def read():
                return native_snapshot(bounded.get_entity(workspaceId=workspace_id, entityId=DEVICE))
        else:
            seed = six_layer_seed(config)
            report["model_sha256"] = hashlib.sha256(json.dumps(seed["models"], sort_keys=True).encode()).hexdigest()
            def seed_azure():
                bounded.create_models(seed["models"])
                for twin in seed["twins"]:
                    bounded.upsert_digital_twin(twin["$dtId"], {k: v for k, v in twin.items() if k != "$dtId"})
                for relation in seed["relationships"]:
                    bounded.upsert_relationship(relation["$dtId"], relation["$relationshipId"],
                        {k: v for k, v in relation.items() if k != "$dtId"})
            measure("seed", seed_azure)
            runtime._adt_client = lambda: bounded
            def read():
                return bounded.get_digital_twin(DEVICE)
        for phase in ("projection", "replay"):
            measure(phase + "_acknowledgement", lambda: runtime._materialize_twin_projection(event))
            def confirmed():
                snapshot = read()
                if matches(snapshot, event, provider):
                    report[phase + "_snapshot"] = snapshot
                    return True
                return False
            attempts = measure(phase + "_readback", lambda: wait_for(confirmed))
            report[phase + "_readback_attempts"] = attempts
        report["functional_pass"] = True
        return report
    finally:
        report["sdk_calls"] = bounded.calls
        report["sdk_response_bytes"] = bounded.response_bytes
        if previous_workspace is None:
            os.environ.pop("TWINMAKER_WORKSPACE", None)
        else:
            os.environ["TWINMAKER_WORKSPACE"] = previous_workspace
