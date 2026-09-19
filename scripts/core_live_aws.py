"""AWS-only operations used by the supervised Core research runner."""

from datetime import datetime, timedelta, timezone
import json
import time

import boto3
from botocore.config import Config


def session(values):
    return boto3.Session(
        aws_access_key_id=values["aws_access_key_id"],
        aws_secret_access_key=values["aws_secret_access_key"],
        region_name=values["aws_region"],
    )


def inventory(values, prefix):
    """Read every retained AWS Core service; missing API access fails closed."""
    aws = session(values)
    result = {}

    def listing(service, operation, key, **kwargs):
        client = aws.client(service, config=Config(connect_timeout=10, read_timeout=20))
        if client.can_paginate(operation):
            return [item for page in client.get_paginator(operation).paginate(**kwargs)
                    for item in page.get(key, [])]
        return getattr(client, operation)(**kwargs).get(key, [])

    def owned(value):
        return (str(value).startswith(prefix + "-")
                or str(value).startswith(prefix + "_")
                or str(value).startswith(prefix.replace("-", "_") + "_"))

    selections = (
        ("lambda", "list_functions", "Functions", "FunctionName", {}),
        ("dynamodb", "list_tables", "TableNames", None, {}),
        ("kinesis", "list_streams", "StreamNames", None, {}),
        ("ecr", "describe_repositories", "repositories", "repositoryName", {}),
        ("codebuild", "list_projects", "projects", None, {}),
        ("iot", "list_things", "things", "thingName", {}),
        ("iot", "list_topic_rules", "rules", "ruleName", {}),
        ("stepfunctions", "list_state_machines", "stateMachines", "name", {}),
        ("s3", "list_buckets", "Buckets", "Name", {}),
        ("iam", "list_roles", "Roles", "RoleName", {}),
        ("iam", "list_policies", "Policies", "PolicyName", {"Scope": "Local"}),
    )
    for service, operation, key, field, kwargs in selections:
        items = listing(service, operation, key, **kwargs)
        result[service + ":" + operation] = sum(
            owned(item[field] if field else item) for item in items
        )
    iot = aws.client("iot")
    commands = [iot.get_command(commandId=item["commandId"])
                for item in listing("iot", "list_commands", "commands") if owned(item["commandId"])]
    result["iot:active_commands"] = sum(not item.get("pendingDeletion") for item in commands)
    result["pending_deletion:iot_commands"] = sum(bool(item.get("pendingDeletion")) for item in commands)
    for service, operation, key, field in (
        ("sns", "list_topics", "Topics", "TopicArn"),
        ("sqs", "list_queues", "QueueUrls", None),
        ("ecs", "list_clusters", "clusterArns", None),
        ("ecs", "list_task_definitions", "taskDefinitionArns", None),
    ):
        items = listing(service, operation, key)
        names = [item[field] if field else item for item in items]
        result[service + ":" + operation] = sum(
            owned(name.rsplit("/", 1)[-1].rsplit(":", 1)[-1])
            or owned(name.rsplit("/", 1)[-1]) for name in names
        )
    result["scheduler"] = sum(
        owned(x["Name"]) for x in listing("scheduler", "list_schedules", "Schedules", NamePrefix=prefix)
    )
    result["logs"] = sum(
        prefix in item["logGroupName"]
        for item in listing("logs", "describe_log_groups", "logGroups")
    )
    ec2 = aws.client("ec2")
    result["vpcs"] = len(ec2.describe_vpcs(
        Filters=[{"Name": "tag:DigitalTwin", "Values": [prefix]}]
    )["Vpcs"])
    return result


def stop_builds(values, outputs):
    project = outputs.get("aws_six_layer_codebuild_project")
    if not project:
        return
    client = session(values).client("codebuild")
    ids = client.list_builds_for_project(projectName=project).get("ids", [])
    for offset in range(0, len(ids), 100):
        for build in client.batch_get_builds(ids=ids[offset:offset + 100]).get("builds", []):
            if build["buildStatus"] == "IN_PROGRESS":
                client.stop_build(id=build["id"])


def before_destroy(values, state):
    """SNS rejects deletion with active archives; touch only owned state topics."""
    sns = session(values).client("sns")
    prefix = values["digital_twin_name"] + "-"
    for resource in state.get("resources", []):
        if resource.get("mode") != "managed" or resource["type"] != "aws_sns_topic":
            continue
        for instance in resource.get("instances", []):
            arn = instance["attributes"]["arn"]
            if not arn.rsplit(":", 1)[-1].startswith(prefix):
                raise RuntimeError("CORE_CLEANUP_OWNERSHIP_MISMATCH")
            if instance["attributes"].get("archive_policy"):
                sns.set_topic_attributes(TopicArn=arn, AttributeName="ArchivePolicy", AttributeValue="{}")


def stream_evidence(values):
    """Verify the same ten correlation IDs in received and processed streams."""
    kinesis = session(values).client("kinesis")
    prefix = values["digital_twin_name"]
    expected = {f"{prefix}-{n}" for n in range(10)}
    counts = {}
    for kind in ("received", "processed"):
        name = prefix + "-domain-" + kind
        found = set()
        for shard in kinesis.list_shards(StreamName=name)["Shards"]:
            iterator = kinesis.get_shard_iterator(StreamName=name, ShardId=shard["ShardId"],
                                                 ShardIteratorType="TRIM_HORIZON")["ShardIterator"]
            for _ in range(5):
                page = kinesis.get_records(ShardIterator=iterator, Limit=100)
                for record in page["Records"]:
                    event = json.loads(record["Data"])
                    correlation = event.get("correlation_id")
                    if correlation in expected and event.get("event_type") == "telemetry." + kind + ".v1":
                        number = int(correlation.rsplit("-", 1)[-1])
                        assert event["payload"]["value"] == number
                        if kind == "processed":
                            assert event["payload"]["quality"] == "accepted"
                        found.add(correlation)
                if not page["Records"]:
                    break
                iterator = page["NextShardIterator"]
        counts[kind] = len(found)
    return counts


def diagnostics(values, outputs):
    logs = session(values).client("logs")
    result = {}
    for page in logs.get_paginator("describe_log_groups").paginate():
        for group in page["logGroups"]:
            name = group["logGroupName"]
            if values["digital_twin_name"] in name:
                result[name] = logs.filter_log_events(logGroupName=name, limit=1000).get("events", [])
    return result


def smoke(values, outputs):
    """Ten IoT ingress messages, real Event/L2/L3 delivery, IAM reader invocation."""
    aws = session(values)
    iot = aws.client("iot")
    endpoint = iot.describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]
    publisher = aws.client("iot-data", endpoint_url="https://" + endpoint)
    now = datetime.now(timezone.utc)
    device = "core-sensor"
    sent_at = time.monotonic()
    for number in range(10):
        publisher.publish(
            topic=f"dt/{values['digital_twin_name']}/{device}/telemetry", qos=1,
            payload=json.dumps({
                "event_id": f"{values['digital_twin_name']}-{number}",
                "source_id": device, "source_sequence": "TRACE-" + values["digital_twin_name"].replace("-", "").upper() + str(number),
                "correlation_id": f"{values['digital_twin_name']}-{number}",
                "payload": {"device_id": device, "metric": "temperature", "value": number,
                            "event_time": (now + timedelta(milliseconds=number)).isoformat()},
            }).encode(),
        )
    return readback(values, outputs, now, sent_at)


def readback(values, outputs, now, sent_at):
    """Same AWS Event/L3 verification for local or cross-cloud ingress."""
    reader = session(values).client("lambda")
    device = "core-sensor"
    query = {"queryStringParameters": {
        "device_id": device, "metric": "temperature", "bucket_seconds": "0", "limit": "100",
        "from": (now - timedelta(minutes=1)).isoformat(),
        "to": (now + timedelta(minutes=10)).isoformat(),
    }}
    for _ in range(100):
        response = reader.invoke(
            FunctionName=outputs["aws_component_storage_read_access_output"]["reader_function_name"],
            Payload=json.dumps(query).encode(),
        )
        body = json.loads(response["Payload"].read())
        payload = json.loads(body.get("body", "{}"))
        points = payload.get("points", [])
        if body.get("statusCode") == 200 and len(points) == 10:
            assert sorted(float(p["value"]) for p in points) == list(range(10))
            streams = stream_evidence(values)
            assert streams == {"received": 10, "processed": 10}
            return {"sent": 10, "read_back": 10, "event_streams": streams,
                    "message_persistence_latency_ms": [round((datetime.fromisoformat(p["stored_at"].replace("Z", "+00:00")) -
                        datetime.fromisoformat(p["event_time"].replace("Z", "+00:00"))).total_seconds() * 1000, 3) for p in points],
                    "delivery_seconds": time.monotonic() - sent_at}
        time.sleep(3)
    raise RuntimeError("CORE_READBACK_TIMEOUT")
