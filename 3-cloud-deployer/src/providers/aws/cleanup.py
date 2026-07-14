"""
AWS SDK Cleanup Module.

Provides fallback cleanup for AWS resources that may be orphaned after
Terraform destroy fails or misses resources.

Note: This includes cleanup of IAM policies created for E2E testing,
specifically the {prefix}-e2e-iot-publish policy that grants iot:Publish
permission to the IAM user running Terraform. This policy is only created
when Terraform is run by an IAM User (not assumed roles).
"""
import logging
import time

from src.providers.cleanup_registry import resource_name_owned_by_prefix

logger = logging.getLogger(__name__)


def _create_session(aws_creds: dict, region: str):
    import boto3

    session_args = {
        "aws_access_key_id": aws_creds["aws_access_key_id"],
        "aws_secret_access_key": aws_creds["aws_secret_access_key"],
        "region_name": region,
    }
    if aws_creds.get("aws_session_token"):
        session_args["aws_session_token"] = aws_creds["aws_session_token"]
    return boto3.Session(**session_args)


def _items(client, operation: str, result_key: str, **kwargs):
    """Yield every item from a paginated or single-page boto3 list operation."""
    can_paginate = getattr(client, "can_paginate", lambda _operation: False)
    if can_paginate(operation):
        for page in client.get_paginator(operation).paginate(**kwargs):
            yield from page.get(result_key, [])
        return
    response = getattr(client, operation)(**kwargs)
    yield from response.get(result_key, [])


def cleanup_aws_resources(
    credentials: dict, 
    prefix: str, 
    cleanup_identity_user: bool = False, 
    platform_user_email: str = "",
    dry_run: bool = False
) -> None:
    """
    Clean up AWS resources matching prefix.
    
    Args:
        credentials: Dict with AWS credentials
        prefix: Resource name prefix (e.g., 'tf-e2e-aws')
        cleanup_identity_user: Delete Identity Store user if True
        platform_user_email: Email for Identity Store user lookup
        dry_run: Log what would be deleted without deleting
        
    Resources cleaned:
        - TwinMaker workspaces
        - Grafana workspaces
        - Step Functions state machines
        - S3 buckets
        - Lambda functions
        - IoT things/policies
        - DynamoDB tables
        - CloudWatch log groups
        - IAM roles
        - IAM policies
        - Identity Store users (conditional)
    """
    aws_creds = credentials.get("aws", {})
    region = aws_creds.get("aws_region", "eu-central-1")
    sso_region = aws_creds.get("aws_sso_region", "us-east-1")
    
    session = _create_session(aws_creds, region)
    
    logger.info(f"[AWS SDK] Fallback cleanup for prefix: {prefix}")
    if dry_run:
        logger.info("[AWS SDK] DRY RUN MODE - no resources will be deleted")
    
    # 1. TwinMaker (must delete entities/components/scenes before workspace)
    logger.info("[TwinMaker] Checking for orphans...")
    twinmaker = session.client('iottwinmaker')
    try:
        for ws in _items(twinmaker, "list_workspaces", "workspaceSummaries"):
            if resource_name_owned_by_prefix(ws['workspaceId'], prefix):
                workspace_id = ws['workspaceId']
                logger.info(f"  Found orphan: {workspace_id}")
                if dry_run:
                    logger.info("    [DRY RUN] Would delete workspace and contents")
                else:
                    try:
                        # Delete entities (async operation)
                        for entity in _items(
                            twinmaker,
                            "list_entities",
                            "entitySummaries",
                            workspaceId=workspace_id,
                        ):
                            twinmaker.delete_entity(workspaceId=workspace_id, entityId=entity['entityId'], isRecursive=True)
                        
                        # Wait for entities to be fully deleted (timeout-based)
                        start_time = time.time()
                        max_wait = 60  # seconds
                        while time.time() - start_time < max_wait:
                            remaining = list(
                                _items(
                                    twinmaker,
                                    "list_entities",
                                    "entitySummaries",
                                    workspaceId=workspace_id,
                                )
                            )
                            if not remaining:
                                break
                            remaining_time = int(max_wait - (time.time() - start_time))
                            logger.info(f"    Waiting for {len(remaining)} entities ({remaining_time}s remaining)...")
                            time.sleep(3)
                        else:
                            logger.warning("    Timeout waiting for entities, proceeding anyway")
                        
                        # Delete scenes
                        for scene in _items(
                            twinmaker,
                            "list_scenes",
                            "sceneSummaries",
                            workspaceId=workspace_id,
                        ):
                            twinmaker.delete_scene(workspaceId=workspace_id, sceneId=scene['sceneId'])
                        
                        # Delete component types with retry (may still be referenced)
                        for ct in _items(
                            twinmaker,
                            "list_component_types",
                            "componentTypeSummaries",
                            workspaceId=workspace_id,
                        ):
                            if not ct['componentTypeId'].startswith('com.amazon'):
                                ct_id = ct['componentTypeId']
                                for attempt in range(3):
                                    try:
                                        twinmaker.delete_component_type(workspaceId=workspace_id, componentTypeId=ct_id)
                                        break
                                    except Exception as e:
                                        if "being used by entities" in str(e) and attempt < 2:
                                            wait = 2 ** attempt
                                            logger.warning(f"    Retry {attempt+1}/3 for {ct_id}: waiting {wait}s")
                                            time.sleep(wait)
                                        else:
                                            logger.warning(f"    ✗ Failed to delete {ct_id}: {e}")
                                            break
                        
                        time.sleep(2)
                        twinmaker.delete_workspace(workspaceId=workspace_id)
                        logger.info("    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 2. Grafana workspaces
    logger.info("[Grafana] Checking for orphans...")
    grafana = session.client('grafana')
    try:
        for ws in _items(grafana, "list_workspaces", "workspaces"):
            if resource_name_owned_by_prefix(ws['name'], prefix):
                logger.info(f"  Found orphan: {ws['name']}")
                if dry_run:
                    logger.info("    [DRY RUN] Would delete")
                else:
                    grafana.delete_workspace(workspaceId=ws['id'])
                    logger.info("    ✓ Deleted")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 3. Step Functions
    logger.info("[Step Functions] Checking for orphans...")
    sfn = session.client('stepfunctions')
    try:
        for page in sfn.get_paginator('list_state_machines').paginate():
            for sm in page['stateMachines']:
                if resource_name_owned_by_prefix(sm['name'], prefix):
                    logger.info(f"  Found orphan: {sm['name']}")
                    if dry_run:
                        logger.info("    [DRY RUN] Would delete")
                    else:
                        sfn.delete_state_machine(stateMachineArn=sm['stateMachineArn'])
                        logger.info("    ✓ Deleted")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 4. S3 buckets
    logger.info("[S3] Checking for orphans...")
    s3 = session.client('s3')
    s3_resource = session.resource('s3')
    try:
        for bucket in _items(s3, "list_buckets", "Buckets"):
            if resource_name_owned_by_prefix(bucket['Name'], prefix):
                logger.info(f"  Found orphan: {bucket['Name']}")
                if dry_run:
                    logger.info("    [DRY RUN] Would delete bucket and contents")
                else:
                    try:
                        bucket_obj = s3_resource.Bucket(bucket['Name'])
                        bucket_obj.object_versions.all().delete()
                        bucket_obj.objects.all().delete()
                        s3.delete_bucket(Bucket=bucket['Name'])
                        logger.info("    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 5. Lambda functions
    logger.info("[Lambda] Checking for orphans...")
    lambda_client = session.client('lambda')
    try:
        for page in lambda_client.get_paginator('list_functions').paginate():
            for func in page['Functions']:
                if resource_name_owned_by_prefix(func['FunctionName'], prefix):
                    logger.info(f"  Found orphan: {func['FunctionName']}")
                    if dry_run:
                        logger.info("    [DRY RUN] Would delete")
                    else:
                        lambda_client.delete_function(FunctionName=func['FunctionName'])
                        logger.info("    ✓ Deleted")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 6. IoT Topic Rules and Things
    logger.info("[IoT] Checking for orphans...")
    iot = session.client('iot')
    try:
        for rule in _items(iot, "list_topic_rules", "rules"):
            if resource_name_owned_by_prefix(rule['ruleName'], prefix):
                logger.info(f"  Found orphan rule: {rule['ruleName']}")
                if dry_run:
                    logger.info("    [DRY RUN] Would delete")
                else:
                    iot.delete_topic_rule(ruleName=rule['ruleName'])
                    logger.info("    ✓ Deleted")
        for thing in _items(iot, "list_things", "things"):
            if resource_name_owned_by_prefix(thing['thingName'], prefix):
                logger.info(f"  Found orphan thing: {thing['thingName']}")
                if dry_run:
                    logger.info("    [DRY RUN] Would delete")
                else:
                    for p in _items(
                        iot,
                        "list_thing_principals",
                        "principals",
                        thingName=thing['thingName'],
                    ):
                        iot.detach_thing_principal(thingName=thing['thingName'], principal=p)
                    iot.delete_thing(thingName=thing['thingName'])
                    logger.info("    ✓ Deleted")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 7. DynamoDB tables
    logger.info("[DynamoDB] Checking for orphans...")
    dynamodb = session.client('dynamodb')
    try:
        for table in _items(dynamodb, "list_tables", "TableNames"):
            if resource_name_owned_by_prefix(table, prefix):
                logger.info(f"  Found orphan: {table}")
                if dry_run:
                    logger.info("    [DRY RUN] Would delete")
                else:
                    dynamodb.delete_table(TableName=table)
                    logger.info("    ✓ Deleted")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 8. CloudWatch Log Groups
    logger.info("[CloudWatch] Checking for orphans...")
    logs = session.client('logs')
    try:
        for page in logs.get_paginator('describe_log_groups').paginate():
            for lg in page['logGroups']:
                if resource_name_owned_by_prefix(
                    lg['logGroupName'],
                    prefix,
                    allow_embedded=True,
                ):
                    logger.info(f"  Found orphan: {lg['logGroupName']}")
                    if dry_run:
                        logger.info("    [DRY RUN] Would delete")
                    else:
                        logs.delete_log_group(logGroupName=lg['logGroupName'])
                        logger.info("    ✓ Deleted")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 9. IAM Roles (last)
    logger.info("[IAM] Checking for orphans...")
    iam = session.client('iam')
    try:
        for page in iam.get_paginator('list_roles').paginate():
            for role in page['Roles']:
                if resource_name_owned_by_prefix(role['RoleName'], prefix):
                    logger.info(f"  Found orphan role: {role['RoleName']}")
                    if dry_run:
                        logger.info("    [DRY RUN] Would delete")
                    else:
                        try:
                            for p in _items(
                                iam,
                                "list_attached_role_policies",
                                "AttachedPolicies",
                                RoleName=role['RoleName'],
                            ):
                                iam.detach_role_policy(RoleName=role['RoleName'], PolicyArn=p['PolicyArn'])
                            for pn in _items(
                                iam,
                                "list_role_policies",
                                "PolicyNames",
                                RoleName=role['RoleName'],
                            ):
                                iam.delete_role_policy(RoleName=role['RoleName'], PolicyName=pn)
                            iam.delete_role(RoleName=role['RoleName'])
                            logger.info("    ✓ Deleted")
                        except Exception as e:
                            logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 10. IAM Policies (must detach from all entities before deletion)
    logger.info("[IAM Policies] Checking for orphans...")
    try:
        for page in iam.get_paginator('list_policies').paginate(Scope='Local'):
            for policy in page['Policies']:
                if resource_name_owned_by_prefix(policy['PolicyName'], prefix):
                    logger.info(f"  Found orphan policy: {policy['PolicyName']}")
                    if dry_run:
                        logger.info("    [DRY RUN] Would delete")
                    else:
                        try:
                            policy_arn = policy['Arn']
                            # Detach from all users
                            for user in _items(
                                iam,
                                "list_entities_for_policy",
                                "PolicyUsers",
                                PolicyArn=policy_arn,
                                EntityFilter="User",
                            ):
                                iam.detach_user_policy(UserName=user['UserName'], PolicyArn=policy_arn)
                                logger.info(f"    Detached from user: {user['UserName']}")
                            # Detach from all roles
                            for role in _items(
                                iam,
                                "list_entities_for_policy",
                                "PolicyRoles",
                                PolicyArn=policy_arn,
                                EntityFilter="Role",
                            ):
                                iam.detach_role_policy(RoleName=role['RoleName'], PolicyArn=policy_arn)
                                logger.info(f"    Detached from role: {role['RoleName']}")
                            # Detach from all groups
                            for group in _items(
                                iam,
                                "list_entities_for_policy",
                                "PolicyGroups",
                                PolicyArn=policy_arn,
                                EntityFilter="Group",
                            ):
                                iam.detach_group_policy(GroupName=group['GroupName'], PolicyArn=policy_arn)
                                logger.info(f"    Detached from group: {group['GroupName']}")
                            # Delete all non-default versions
                            for version in iam.list_policy_versions(PolicyArn=policy_arn)['Versions']:
                                if not version['IsDefaultVersion']:
                                    iam.delete_policy_version(PolicyArn=policy_arn, VersionId=version['VersionId'])
                            # Delete policy
                            iam.delete_policy(PolicyArn=policy_arn)
                            logger.info("    ✓ Deleted")
                        except Exception as e:
                            logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 11. AWS Resource Groups (used for tagging/organizing resources)
    logger.info("[Resource Groups] Checking for orphans...")
    try:
        rg = session.client('resource-groups')
        for page in rg.get_paginator('list_groups').paginate():
            for group in page['Groups']:
                group_name = group['Name']
                if resource_name_owned_by_prefix(group_name, prefix):
                    logger.info(f"  Found orphan: {group_name}")
                    if dry_run:
                        logger.info("    [DRY RUN] Would delete")
                    else:
                        try:
                            rg.delete_group(Group=group_name)
                            logger.info("    ✓ Deleted")
                        except Exception as e:
                            logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 12. Identity Store User (ONLY if we created it during this deployment)
    if cleanup_identity_user:
        logger.info("[Identity Store] Checking for user to clean up...")
        try:
            sso_session = _create_session(aws_creds, sso_region)
            sso_admin = sso_session.client('sso-admin')
            instances = list(_items(sso_admin, "list_instances", "Instances"))
            
            if instances:
                identity_store_id = instances[0]['IdentityStoreId']
                identitystore = sso_session.client('identitystore')
                
                if not platform_user_email:
                    logger.info("  No platform_user_email provided, skipping")
                else:
                    paginator = identitystore.get_paginator('list_users')
                    for page in paginator.paginate(IdentityStoreId=identity_store_id):
                        for user in page['Users']:
                            username = user.get('UserName', '')
                            if username.lower() == platform_user_email.lower():
                                logger.info(f"  Found platform user: {username} (ID: {user['UserId']})")
                                if dry_run:
                                    logger.info("    [DRY RUN] Would delete")
                                else:
                                    identitystore.delete_user(
                                        IdentityStoreId=identity_store_id,
                                        UserId=user['UserId']
                                    )
                                    logger.info("    ✓ Deleted")
        except Exception as e:
            logger.warning(f"  Error: {e}")
    else:
        logger.info("[Identity Store] Skipping (user was pre-existing)")
    
    logger.info("[AWS SDK] Fallback cleanup complete")
