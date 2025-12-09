"""
Layer 1 (IoT) Deployment for AWS.

This module handles deployment and destruction of Layer 1 components:
- Dispatcher IAM Role
- Dispatcher Lambda Function  
- IoT Topic Rule

All functions accept provider and config parameters explicitly.
"""

import json
import os
import time
from typing import TYPE_CHECKING
from logger import logger
from datetime import datetime, timezone
import src.providers.aws.util_aws as util_aws
from botocore.exceptions import ClientError
import shutil
import constants as CONSTANTS

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider
    from src.core.context import ProjectConfig


# ==========================================
# 2. Dispatcher IAM Role
# ==========================================

def create_dispatcher_iam_role(provider: 'AWSProvider') -> None:
    """
    Creates the IAM Role for the L1 Dispatcher Lambda.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
    """
    role_name = provider.naming.dispatcher_iam_role()
    iam_client = provider.clients["iam"]

    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )

    logger.info(f"Created IAM role: {role_name}")

    policy_arns = [
        CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
        CONSTANTS.AWS_POLICY_LAMBDA_ROLE
    ]

    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        logger.info(f"Attached IAM policy ARN: {policy_arn}")

    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_dispatcher_iam_role(provider: 'AWSProvider') -> None:
    """
    Destroys the IAM Role for the L1 Dispatcher Lambda.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
    """
    role_name = provider.naming.dispatcher_iam_role()
    iam_client = provider.clients["iam"]

    try:
        # Detach managed policies
        response = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in response["AttachedPolicies"]:
            iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

        # Delete inline policies
        response = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in response["PolicyNames"]:
            iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

        # Remove from instance profiles
        response = iam_client.list_instance_profiles_for_role(RoleName=role_name)
        for profile in response["InstanceProfiles"]:
            iam_client.remove_role_from_instance_profile(
                InstanceProfileName=profile["InstanceProfileName"],
                RoleName=role_name
            )

        # Delete the role
        iam_client.delete_role(RoleName=role_name)
        logger.info(f"Deleted IAM role: {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise


# ==========================================
# 3. Dispatcher Lambda Function
# ==========================================

def create_dispatcher_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """
    Creates the L1 Dispatcher Lambda Function.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
        config: ProjectConfig with digital_twin_name and providers
        project_path: Path to project directory for Lambda source code
    """
    function_name = provider.naming.dispatcher_lambda_function()
    role_name = provider.naming.dispatcher_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']

    # Determine target function suffix based on L2 provider
    l2_provider = config.providers.get("layer_2_provider", "aws")
    target_suffix = "-connector" if l2_provider != "aws" else "-processor"

    # Build digital twin info for Lambda environment
    digital_twin_info = {
        "config": {
            "digital_twin_name": config.digital_twin_name,
            "hot_storage_size_in_days": config.hot_storage_size_in_days,
            "cold_storage_size_in_days": config.cold_storage_size_in_days,
            "mode": config.mode,
        },
        "config_iot_devices": config.iot_devices,
        "config_events": config.events
    }

    # Lambda source path
    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

    # Lazy import to avoid circular dependency
    import util
    
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "dispatcher"))},
        Description="Core Dispatcher Function for Layer 1 Data Acquisition",
        Timeout=3,
        MemorySize=128,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(digital_twin_info),
                "TARGET_FUNCTION_SUFFIX": target_suffix
            }
        }
    )

    logger.info(f"Created Lambda function: {function_name}")


def destroy_dispatcher_lambda_function(provider: 'AWSProvider') -> None:
    """
    Destroys the L1 Dispatcher Lambda Function.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
    """
    function_name = provider.naming.dispatcher_lambda_function()
    lambda_client = provider.clients["lambda"]

    try:
        lambda_client.delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 4. Dispatcher IoT Rule
# ==========================================

def create_dispatcher_iot_rule(provider: 'AWSProvider', config: 'ProjectConfig') -> None:
    """
    Creates the IoT Topic Rule that triggers the Dispatcher.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
        config: ProjectConfig with digital_twin_name
    """
    rule_name = provider.naming.dispatcher_iot_rule()
    function_name = provider.naming.dispatcher_lambda_function()
    lambda_client = provider.clients["lambda"]
    iot_client = provider.clients["iot"]
    sts_client = provider.clients["sts"]

    sql = f"SELECT * FROM '{config.digital_twin_name}/iot-data'"

    response = lambda_client.get_function(FunctionName=function_name)
    function_arn = response['Configuration']['FunctionArn']

    iot_client.create_topic_rule(
        ruleName=rule_name,
        topicRulePayload={
            "sql": sql,
            "description": "Routes all Digital Twin IoT data to the Dispatcher Lambda",
            "actions": [{"lambda": {"functionArn": function_arn}}],
            "ruleDisabled": False
        }
    )

    logger.info(f"Created IoT rule: {rule_name}")

    region = iot_client.meta.region_name
    account_id = sts_client.get_caller_identity()['Account']

    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId="iot-invoke",
        Action="lambda:InvokeFunction",
        Principal="iot.amazonaws.com",
        SourceArn=f"arn:aws:iot:{region}:{account_id}:rule/{rule_name}"
    )

    logger.info("Added permission to Lambda function so the rule can invoke the function.")


def destroy_dispatcher_iot_rule(provider: 'AWSProvider') -> None:
    """
    Destroys the IoT Topic Rule for the Dispatcher.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
    """
    function_name = provider.naming.dispatcher_lambda_function()
    rule_name = provider.naming.dispatcher_iot_rule()
    lambda_client = provider.clients["lambda"]
    iot_client = provider.clients["iot"]

    try:
        lambda_client.remove_permission(FunctionName=function_name, StatementId="iot-invoke")
        logger.info(f"Removed permission from Lambda function: {rule_name}, {function_name}")
    except lambda_client.exceptions.ResourceNotFoundException:
        pass

    # Check if rule exists before deleting
    try:
        iot_client.get_topic_rule(ruleName=rule_name)
        iot_client.delete_topic_rule(ruleName=rule_name)
        logger.info(f"Deleted IoT Rule: {rule_name}")
    except iot_client.exceptions.ResourceNotFoundException:
        pass


# ==========================================
# 5. Initialization Values
# ==========================================

def post_init_values_to_iot_core(
    provider: 'AWSProvider',
    iot_devices: list,
    topic: str = None
) -> None:
    """Post initial values to IoT Core for all configured devices."""
    if provider is None:
        raise ValueError("provider is required")
    if iot_devices is None:
        raise ValueError("iot_devices is required")

    iot_data_client = provider.clients["iot_data"]
    if topic is None:
        # Assuming provider.naming has twin_name properly set
        topic = f"{provider.naming.twin_name}/iot-data"
    
    for iot_device in iot_devices:
        # Check for initValue in properties
        has_init = any("initValue" in prop for prop in iot_device.get("properties", []))
        if not has_init:
            continue
        
        payload = {
            "iotDeviceId": iot_device["id"],
            "time": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        }
        
        for prop in iot_device.get("properties", []):
            payload[prop["name"]] = prop.get("initValue", None)
        
        iot_data_client.publish(
            topic=topic,
            qos=1,
            payload=json.dumps(payload).encode("utf-8")
        )
        logger.info(f"Posted init values for IoT device id: {iot_device['id']}")


        iot_data_client.publish(
            topic=topic,
            qos=1,
            payload=json.dumps(payload).encode("utf-8")
        )
        logger.info(f"Posted init values for IoT device id: {iot_device['id']}")


# ==========================================
# 6. IoT Things & Simulator Config
# ==========================================

def _generate_simulator_config(iot_device, provider, config, project_path):
    """
    Generates config_generated.json for the IoT device simulator.
    Called after device certificate creation.
    """
    # 1. Fetch IoT Endpoint
    iot_client = provider.clients["iot"]
    endpoint_response = iot_client.describe_endpoint(endpointType='iot:Data-ATS')
    endpoint = endpoint_response['endpointAddress']
    
    # 2. Derive topic
    digital_twin_name = config.digital_twin_name
    topic = digital_twin_name + "/iot-data"
    
    # 3. Paths
    device_id = iot_device['id']
    
    # Resolve Root CA path (bundled in src)
    # This logic assumes we are in src/providers/aws/layers/
    # We need to reach src/iot_device_simulator/aws/AmazonRootCA1.pem
    # Go up 4 levels: layers -> aws -> providers -> src
    root_ca_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "iot_device_simulator", "aws", "AmazonRootCA1.pem"
    ))
    
    config_data = {
        "endpoint": endpoint,
        "topic": topic,
        "device_id": device_id,
        "cert_path": f"../../iot_devices_auth/{device_id}/certificate.pem.crt",
        "key_path": f"../../iot_devices_auth/{device_id}/private.pem.key",
        "root_ca_path": root_ca_path,
        "payload_path": "payloads.json"
    }
    
    # 4. Write to upload/{project}/iot_device_simulator/aws/
    sim_dir = os.path.join(project_path, "iot_device_simulator", "aws")
    os.makedirs(sim_dir, exist_ok=True)
    config_path = os.path.join(sim_dir, "config_generated.json")
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    logger.info(f"Generated simulator config: {config_path}")


def create_iot_thing(iot_device, provider, config, project_path):
    """Create IoT Thing, Certificates, and Policy."""
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    if project_path is None:
        raise ValueError("project_path is required")

    iot_client = provider.clients["iot"]
    thing_name = provider.naming.iot_thing(iot_device["id"])
    policy_name = provider.naming.iot_thing_policy(iot_device["id"])

    iot_client.create_thing(thingName=thing_name)
    logger.info(f"Created IoT Thing: {thing_name}")

    cert_response = iot_client.create_keys_and_certificate(setAsActive=True)
    certificate_arn = cert_response['certificateArn']
    logger.info(f"Created IoT Certificate: {cert_response['certificateId']}")

    dir = f"{project_path}/{CONSTANTS.IOT_DATA_DIR_NAME}/{iot_device['id']}/"
    os.makedirs(os.path.dirname(dir), exist_ok=True)

    with open(f"{dir}certificate.pem.crt", "w") as f:
        f.write(cert_response["certificatePem"])
    with open(f"{dir}private.pem.key", "w") as f:
        f.write(cert_response["keyPair"]["PrivateKey"])
    with open(f"{dir}public.pem.key", "w") as f:
        f.write(cert_response["keyPair"]["PublicKey"])

    logger.info(f"Stored certificate and keys to {dir}")

    policy_document = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["iot:*"],
            "Resource": "*"
        }]
    }

    iot_client.create_policy(policyName=policy_name, policyDocument=json.dumps(policy_document))
    logger.info(f"Created IoT Policy: {policy_name}")

    iot_client.attach_thing_principal(thingName=thing_name, principal=certificate_arn)
    logger.info(f"Attached IoT Certificate to Thing")

    iot_client.attach_policy(policyName=policy_name, target=certificate_arn)
    logger.info(f"Attached IoT Policy to Certificate")

    _generate_simulator_config(iot_device, provider, config, project_path)


def destroy_iot_thing(iot_device, provider, project_path):
    """Destroy IoT Thing and related resources."""
    if provider is None:
        raise ValueError("provider is required")

    thing_name = provider.naming.iot_thing(iot_device["id"])
    policy_name = provider.naming.iot_thing_policy(iot_device["id"])
    iot_client = provider.clients["iot"]

    try:
        principals_resp = iot_client.list_thing_principals(thingName=thing_name)
        principals = principals_resp.get('principals', [])

        if len(principals) > 1:
            logger.warning(f"Too many principals for {thing_name}. Proceeding to detach all.")

        for principal in principals:
            iot_client.detach_thing_principal(thingName=thing_name, principal=principal)
            logger.info(f"Detached IoT Certificate")

            policies = iot_client.list_attached_policies(target=principal)
            for p in policies.get('policies', []):
                iot_client.detach_policy(policyName=p['policyName'], target=principal)
                logger.info(f"Detached IoT Policy")

            cert_id = principal.split('/')[-1]
            iot_client.update_certificate(certificateId=cert_id, newStatus='INACTIVE')
            iot_client.delete_certificate(certificateId=cert_id, forceDelete=True)
            logger.info(f"Deleted IoT Certificate: {cert_id}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    try:
        versions = iot_client.list_policy_versions(policyName=policy_name).get('policyVersions', [])
        for version in versions:
            if not version['isDefaultVersion']:
                try:
                    iot_client.delete_policy_version(policyName=policy_name, policyVersionId=version['versionId'])
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ResourceNotFoundException":
                        raise
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    try:
        iot_client.delete_policy(policyName=policy_name)
        logger.info(f"Deleted IoT Policy: {policy_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    try:
        iot_client.describe_thing(thingName=thing_name)
        iot_client.delete_thing(thingName=thing_name)
        logger.info(f"Deleted IoT Thing: {thing_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    try:
        # Import lazily or use available util_aws. However, logic uses util.get_path_in_project.
        # We can implement basic path join here or use project_path directly as it's passed as str of project root.
        # project_path is passed as 'upload/PROJECT_NAME' usually.
        # iot_deployer_aws used util.get_path_in_project(CONSTANTS.IOT_DATA_DIR_NAME, project_path=project_path)
        # which basically joins project_path + IOT_DATA_DIR_NAME.
        target_dir = os.path.join(project_path, CONSTANTS.IOT_DATA_DIR_NAME, iot_device['id'])
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
            logger.info(f"Removed local certificates directory: {target_dir}")
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to remove local dir {target_dir}: {e}")


# ==========================================
# 7. Info / Status Checks
# ==========================================

def _links():
    return util_aws

def check_dispatcher_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.dispatcher_iam_role()
    client = provider.clients["iam"]

    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Dispatcher IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Dispatcher IAM Role missing: {role_name}")
        else:
            raise

def check_dispatcher_lambda_function(provider: 'AWSProvider'):
    function_name = provider.naming.dispatcher_lambda_function()
    client = provider.clients["lambda"]

    try:
        client.get_function(FunctionName=function_name)
        logger.info(f"✅ Dispatcher Lambda Function exists: {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Dispatcher Lambda Function missing: {function_name}")
        else:
            raise

def check_dispatcher_iot_rule(provider: 'AWSProvider'):
    rule_name = provider.naming.dispatcher_iot_rule()
    client = provider.clients["iot"]

    try:
        client.get_topic_rule(ruleName=rule_name)
        logger.info(f"✅ Dispatcher Iot Rule exists: {_links().link_to_iot_rule(rule_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "UnauthorizedException":
            logger.error(f"❌ Dispatcher IoT Rule missing: {rule_name}")
        else:
            raise

def check_iot_thing(iot_device, provider: 'AWSProvider'):
    thing_name = provider.naming.iot_thing(iot_device.get('name', 'unknown'))
    client = provider.clients["iot"]

    try:
        client.describe_thing(thingName=thing_name)
        logger.info(f"✅ Iot Thing {thing_name} exists: {_links().link_to_iot_thing(thing_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ IoT Thing {thing_name} missing: {thing_name}")
        else:
            raise

def info_l1(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Check status of all L1 components."""
    check_dispatcher_iam_role(provider)
    check_dispatcher_lambda_function(provider)
    check_dispatcher_iot_rule(provider)
    
    if context.config.iot_devices:
        for device in context.config.iot_devices:
            check_iot_thing(device, provider)

