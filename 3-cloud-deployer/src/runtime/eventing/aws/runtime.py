"""AWS Lambda wrapper for source-owned Phase 8 event bridge routes."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Mapping

from ..bridge_application import BridgeApplication, build_bridge_application
from ..bridge_core import BridgeContractError, BridgeRoute, RouteCircuitBreaker
from .bridge import handle_batch


AWS_REGION = "eu-central-1"
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_FIFO_URL = re.compile(
    rf"^https://sqs\.{AWS_REGION}\.amazonaws\.com/\d{{12}}/[A-Za-z0-9_-]+\.fifo$"
)
_APPLICATION: BridgeApplication | None = None
_FAILURE_WRITER: "AwsFailureWriter | None" = None
_CIRCUITS: dict[str, RouteCircuitBreaker] = {}


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class AwsFailureWriter:
    """Store safe telemetry failures in S3 and control failures in SQS FIFO."""

    def __init__(
        self,
        routes: tuple[BridgeRoute, ...],
        *,
        telemetry_bucket: str,
        control_queue_url: str,
        s3_client: object,
        sqs_client: object,
    ) -> None:
        channels = {route.route_id: route.channel_class for route in routes}
        if (
            not channels
            or ("telemetry" in channels.values() and not _BUCKET.fullmatch(telemetry_bucket))
            or ("control" in channels.values() and not _FIFO_URL.fullmatch(control_queue_url))
        ):
            raise BridgeContractError("INVALID_FAILURE_DESTINATION_CONFIGURATION")
        self._channels = channels
        self._telemetry_bucket = telemetry_bucket
        self._control_queue_url = control_queue_url
        self._s3 = s3_client
        self._sqs = sqs_client

    def __call__(self, failure: Mapping[str, Any]) -> bool:
        route_id = failure.get("route_id")
        channel = self._channels.get(str(route_id))
        if channel not in {"telemetry", "control"}:
            raise BridgeContractError("INVALID_FAILURE_DESTINATION_CONFIGURATION")
        data = _canonical_bytes(failure)
        digest = hashlib.sha256(data).hexdigest()
        if channel == "telemetry":
            result = self._s3.put_object(
                Bucket=self._telemetry_bucket,
                Key=f"bridge-failures/{digest}.json",
                Body=data,
                ContentType="application/json",
            )
            return isinstance(result, Mapping) and isinstance(result.get("ETag"), str)
        source_id = failure.get("canonical_envelope", {}).get("source_id")
        if not isinstance(source_id, str) or not source_id:
            source_id = "invalid"
        result = self._sqs.send_message(
            QueueUrl=self._control_queue_url,
            MessageBody=data.decode("utf-8"),
            MessageGroupId=hashlib.sha256(source_id.encode("utf-8")).hexdigest(),
            MessageDeduplicationId=digest,
        )
        return isinstance(result, Mapping) and isinstance(result.get("MessageId"), str)


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or len(value.encode("utf-8")) > 128 * 1024:
        raise BridgeContractError("INVALID_BRIDGE_RUNTIME_CONFIGURATION")
    return value


def _application() -> BridgeApplication:
    global _APPLICATION
    if _APPLICATION is None:
        _APPLICATION = build_bridge_application(
            source_provider="aws",
            routes_json=_required_environment("BRIDGE_ROUTES_JSON"),
            destinations_json=_required_environment("BRIDGE_DESTINATIONS_JSON"),
            identities_json=_required_environment("BRIDGE_IDENTITIES_JSON"),
        )
    return _APPLICATION


def _failure_writer(app: BridgeApplication) -> AwsFailureWriter:
    global _FAILURE_WRITER
    if _FAILURE_WRITER is None:
        import boto3

        _FAILURE_WRITER = AwsFailureWriter(
            app.routes,
            telemetry_bucket=os.environ.get("BRIDGE_TELEMETRY_FAILURE_BUCKET", ""),
            control_queue_url=os.environ.get("BRIDGE_CONTROL_FAILURE_QUEUE_URL", ""),
            s3_client=boto3.client("s3", region_name=AWS_REGION),
            sqs_client=boto3.client("sqs", region_name=AWS_REGION),
        )
    return _FAILURE_WRITER


def lambda_handler(event: Mapping[str, Any], _context: object) -> dict:
    """Acknowledge Kinesis/SQS records only after target or source DLQ acceptance."""

    app = _application()
    return handle_batch(
        event,
        routes_json=_required_environment("BRIDGE_ROUTES_JSON"),
        publish=app.publish,
        write_dlq=_failure_writer(app),
        circuit_breakers=_CIRCUITS,
    )


__all__ = ["AwsFailureWriter", "lambda_handler"]
