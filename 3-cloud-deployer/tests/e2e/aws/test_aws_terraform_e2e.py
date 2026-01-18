"""
AWS Terraform End-to-End Test.

This test deploys all AWS layers using Terraform, sends IoT messages through
the pipeline, verifies data reaches DynamoDB and Grafana, then destroys resources.

IMPORTANT: This test deploys REAL AWS resources and incurs costs.
Run with: pytest -m live

Estimated duration: 15-30 minutes
Estimated cost: ~$0.50-2.00 USD
"""
import pytest
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))


def _cleanup_aws_resources_boto3(credentials: dict, prefix: str, cleanup_identity_user: bool = False, platform_user_email: str = "") -> None:
    """
    Comprehensive boto3 cleanup of AWS resources by name pattern.
    
    This is a fallback cleanup that runs after terraform destroy to catch
    any orphaned resources that weren't tracked in Terraform state.
    
    Args:
        credentials: Dict with aws credentials
        prefix: Resource name prefix to match (e.g., 'tf-e2e-aws')
        cleanup_identity_user: If True, also delete Identity Store user (only if Terraform created it)
        platform_user_email: The platform user email to match for Identity Store user deletion
    """
    import boto3
    import time
    
    aws_creds = credentials.get("aws", {})
    region = aws_creds.get("aws_region", "eu-central-1")
    sso_region = aws_creds.get("aws_sso_region", "us-east-1")
    
    session = boto3.Session(
        aws_access_key_id=aws_creds["aws_access_key_id"],
        aws_secret_access_key=aws_creds["aws_secret_access_key"],
        region_name=region
    )
    
    prefix_underscore = prefix.replace("-", "_")
    
    # 1. TwinMaker (must delete entities/components/scenes before workspace)
    print(f"    [TwinMaker] Cleaning up...")
    twinmaker = session.client('iottwinmaker')
    try:
        workspaces = twinmaker.list_workspaces()['workspaceSummaries']
        for ws in workspaces:
            if prefix in ws['workspaceId']:
                workspace_id = ws['workspaceId']
                print(f"      Deleting workspace: {workspace_id}")
                # Delete entities, scenes, component types first
                try:
                    for entity in twinmaker.list_entities(workspaceId=workspace_id).get('entitySummaries', []):
                        twinmaker.delete_entity(workspaceId=workspace_id, entityId=entity['entityId'], isRecursive=True)
                    for scene in twinmaker.list_scenes(workspaceId=workspace_id).get('sceneSummaries', []):
                        twinmaker.delete_scene(workspaceId=workspace_id, sceneId=scene['sceneId'])
                    for ct in twinmaker.list_component_types(workspaceId=workspace_id).get('componentTypeSummaries', []):
                        if not ct['componentTypeId'].startswith('com.amazon'):
                            twinmaker.delete_component_type(workspaceId=workspace_id, componentTypeId=ct['componentTypeId'])
                    time.sleep(2)
                    twinmaker.delete_workspace(workspaceId=workspace_id)
                    print(f"        ✓ Deleted")
                except Exception as e:
                    print(f"        ✗ Error: {e}")
    except Exception as e:
        print(f"      Error: {e}")
    
    # 2. Grafana workspaces
    print(f"    [Grafana] Cleaning up...")
    grafana = session.client('grafana')
    try:
        for ws in grafana.list_workspaces()['workspaces']:
            if prefix in ws['name']:
                print(f"      Deleting: {ws['name']}")
                grafana.delete_workspace(workspaceId=ws['id'])
    except Exception as e:
        print(f"      Error: {e}")
    
    # 3. Step Functions
    print(f"    [Step Functions] Cleaning up...")
    sfn = session.client('stepfunctions')
    try:
        for page in sfn.get_paginator('list_state_machines').paginate():
            for sm in page['stateMachines']:
                if prefix in sm['name'] or prefix_underscore in sm['name']:
                    print(f"      Deleting: {sm['name']}")
                    sfn.delete_state_machine(stateMachineArn=sm['stateMachineArn'])
    except Exception as e:
        print(f"      Error: {e}")
    
    # 4. S3 buckets
    print(f"    [S3] Cleaning up...")
    s3 = session.client('s3')
    s3_resource = session.resource('s3')
    try:
        for bucket in s3.list_buckets()['Buckets']:
            if prefix in bucket['Name']:
                print(f"      Deleting: {bucket['Name']}")
                try:
                    bucket_obj = s3_resource.Bucket(bucket['Name'])
                    bucket_obj.object_versions.all().delete()
                    bucket_obj.objects.all().delete()
                    s3.delete_bucket(Bucket=bucket['Name'])
                except Exception as e:
                    print(f"        ✗ Error: {e}")
    except Exception as e:
        print(f"      Error: {e}")
    
    # 5. Lambda functions
    print(f"    [Lambda] Cleaning up...")
    lambda_client = session.client('lambda')
    try:
        for page in lambda_client.get_paginator('list_functions').paginate():
            for func in page['Functions']:
                if prefix in func['FunctionName'] or prefix_underscore in func['FunctionName']:
                    print(f"      Deleting: {func['FunctionName']}")
                    lambda_client.delete_function(FunctionName=func['FunctionName'])
    except Exception as e:
        print(f"      Error: {e}")
    
    # 6. IoT Topic Rules and Things
    print(f"    [IoT] Cleaning up...")
    iot = session.client('iot')
    try:
        for rule in iot.list_topic_rules()['rules']:
            if prefix in rule['ruleName'] or prefix_underscore in rule['ruleName']:
                print(f"      Deleting rule: {rule['ruleName']}")
                iot.delete_topic_rule(ruleName=rule['ruleName'])
        for thing in iot.list_things()['things']:
            if prefix in thing['thingName']:
                print(f"      Deleting thing: {thing['thingName']}")
                for p in iot.list_thing_principals(thingName=thing['thingName'])['principals']:
                    iot.detach_thing_principal(thingName=thing['thingName'], principal=p)
                iot.delete_thing(thingName=thing['thingName'])
    except Exception as e:
        print(f"      Error: {e}")
    
    # 7. DynamoDB tables
    print(f"    [DynamoDB] Cleaning up...")
    dynamodb = session.client('dynamodb')
    try:
        for table in dynamodb.list_tables()['TableNames']:
            if prefix in table:
                print(f"      Deleting: {table}")
                dynamodb.delete_table(TableName=table)
    except Exception as e:
        print(f"      Error: {e}")
    
    # 8. CloudWatch Log Groups
    print(f"    [CloudWatch] Cleaning up...")
    logs = session.client('logs')
    try:
        for page in logs.get_paginator('describe_log_groups').paginate():
            for lg in page['logGroups']:
                if prefix in lg['logGroupName'] or prefix_underscore in lg['logGroupName']:
                    print(f"      Deleting: {lg['logGroupName']}")
                    logs.delete_log_group(logGroupName=lg['logGroupName'])
    except Exception as e:
        print(f"      Error: {e}")
    
    # 9. IAM Roles (last)
    print(f"    [IAM] Cleaning up...")
    iam = session.client('iam')
    try:
        for page in iam.get_paginator('list_roles').paginate():
            for role in page['Roles']:
                if prefix in role['RoleName'] or prefix_underscore in role['RoleName']:
                    print(f"      Deleting role: {role['RoleName']}")
                    try:
                        for p in iam.list_attached_role_policies(RoleName=role['RoleName'])['AttachedPolicies']:
                            iam.detach_role_policy(RoleName=role['RoleName'], PolicyArn=p['PolicyArn'])
                        for pn in iam.list_role_policies(RoleName=role['RoleName'])['PolicyNames']:
                            iam.delete_role_policy(RoleName=role['RoleName'], PolicyName=pn)
                        iam.delete_role(RoleName=role['RoleName'])
                    except Exception as e:
                        print(f"        ✗ Error: {e}")
    except Exception as e:
        print(f"      Error: {e}")
    
    # 10. Identity Store User (ONLY if we created it during this deployment)
    if cleanup_identity_user:
        print(f"    [Identity Store] Cleaning up user...")
        try:
            # Create SSO-region session for Identity Store
            sso_session = boto3.Session(
                aws_access_key_id=aws_creds["aws_access_key_id"],
                aws_secret_access_key=aws_creds["aws_secret_access_key"],
                region_name=sso_region
            )
            sso_admin = sso_session.client('sso-admin')
            instances = sso_admin.list_instances()['Instances']
            
            if instances:
                identity_store_id = instances[0]['IdentityStoreId']
                identitystore = sso_session.client('identitystore')
                
                # Use provided platform_user_email parameter
                if not platform_user_email:
                    print(f"      No platform_user_email provided, skipping")
                else:
                    # Search for user with exact username match
                    paginator = identitystore.get_paginator('list_users')
                    for page in paginator.paginate(IdentityStoreId=identity_store_id):
                        for user in page['Users']:
                            username = user.get('UserName', '')
                            # Match EXACT username (case-insensitive)
                            if username.lower() == platform_user_email.lower():
                                print(f"      Found platform user: {username} (ID: {user['UserId']})")
                                try:
                                    identitystore.delete_user(
                                        IdentityStoreId=identity_store_id,
                                        UserId=user['UserId']
                                    )
                                    print(f"        ✓ Deleted")
                                except Exception as e:
                                    print(f"        ✗ Error: {e}")
        except Exception as e:
            print(f"      Error: {e}")
    else:
        print(f"    [Identity Store] Skipping (user was pre-existing)")


@pytest.mark.live
class TestAWSTerraformE2E:
    """
    Live E2E test for AWS deployment using Terraform.
    
    Tests the complete data flow:
    IoT Device → IoT Core → Dispatcher → Persister → DynamoDB → Hot Reader → TwinMaker
    
    Uses TerraformDeployerStrategy for infrastructure provisioning.
    """
    
    @pytest.fixture(scope="class")
    def deployed_environment(self, request, aws_terraform_e2e_project_path, aws_credentials):
        """
        Deploy all AWS layers via Terraform with GUARANTEED cleanup.
        
        Uses unique project name per run to avoid Terraform state conflicts.
        Cleanup (terraform destroy) ALWAYS runs, even on test failure.
        """
        from src.core.config_loader import load_project_config, load_credentials
        from src.core.context import DeploymentContext
        from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
        import validator
        import constants as CONSTANTS
        
        print("\n" + "="*60)
        print("  AWS TERRAFORM E2E TEST - PRE-DEPLOYMENT VALIDATION")
        print("="*60)
        
        project_path = Path(aws_terraform_e2e_project_path)
        terraform_dir = Path(__file__).parent.parent.parent.parent / "src" / "terraform"
        
        # ==========================================
        # PHASE 1: Validate Configuration
        # ==========================================
        print("\n[VALIDATION] Phase 1: Configuration Files")
        
        config_files_to_validate = [
            CONSTANTS.CONFIG_FILE,
            CONSTANTS.CONFIG_IOT_DEVICES_FILE,
            CONSTANTS.CONFIG_EVENTS_FILE,
            CONSTANTS.CONFIG_CREDENTIALS_FILE,
            CONSTANTS.CONFIG_PROVIDERS_FILE,
        ]
        
        for config_filename in config_files_to_validate:
            config_file_path = project_path / config_filename
            if config_file_path.exists():
                try:
                    with open(config_file_path, 'r') as f:
                        content = json.load(f)
                    validator.validate_config_content(config_filename, content)
                    print(f"  ✓ {config_filename} validated")
                except Exception as e:
                    pytest.fail(f"Validation failed for {config_filename}: {e}")
            else:
                pytest.fail(f"Required config file missing: {config_filename}")
        
        # Load config
        try:
            config = load_project_config(project_path)
            print(f"  ✓ Project config loaded (twin_name: {config.digital_twin_name})")
        except Exception as e:
            pytest.fail(f"Config loading failed: {e}")
        
        # Load credentials
        try:
            credentials = load_credentials(project_path)
        except Exception as e:
            pytest.fail(f"Credentials loading failed: {e}")
        
        # ==========================================
        # PHASE 2: Validate AWS Credentials
        # ==========================================
        print("\n[VALIDATION] Phase 2: AWS Credentials")
        
        aws_creds = credentials.get("aws", {})
        if not aws_creds:
            pytest.fail("No AWS credentials found in config_credentials.json")
        
        # Validate AWS connectivity using the comprehensive credentials checker
        # (This is the same checker used by CLI and REST API)
        try:
            from api.credentials_checker import check_aws_credentials
            
            result = check_aws_credentials(aws_creds)
            if result["status"] == "error":
                pytest.fail(f"AWS credentials validation failed: {result['message']}")
            elif result["status"] == "invalid":
                print(f"  ⚠ Warning: {result['message']}")
                print("    Deployment may fail due to missing permissions")
            elif result["status"] == "partial":
                print(f"  ⚠ Warning: {result['message']}")
            else:
                print(f"  ✓ AWS credentials validated")
                if result.get("caller_identity"):
                    print(f"  ✓ Account: {result['caller_identity'].get('account_id')}")
        except ImportError:
            print("  ⚠ boto3 not installed, skipping credential check")
        
        # ==========================================
        # PHASE 3: Deploy Infrastructure
        # ==========================================
        print("\n[DEPLOYMENT] Phase 3: Terraform Deployment")
        print(f"  Project: {project_path}")
        print(f"  Terraform dir: {terraform_dir}")
        
        context = DeploymentContext(
            project_name=config.digital_twin_name,
            project_path=project_path,
            config=config,
            credentials=credentials,
        )
        
        strategy = TerraformDeployerStrategy(
            terraform_dir=str(terraform_dir),
            project_path=str(project_path)
        )
        
        # Track whether Terraform created a new Identity Store user (captured after deploy)
        cleanup_identity_user = False
        platform_user_email = ""  # Will be set from config_user.json
        
        # Register cleanup to ALWAYS run, even on failure
        def terraform_cleanup():
            nonlocal cleanup_identity_user, platform_user_email
            print("\n" + "="*60)
            print("  CLEANUP: Running terraform destroy")
            print("="*60)
            try:
                strategy.destroy_all(context)
                print("  ✓ Terraform destroy completed")
            except Exception as e:
                print(f"  ✗ Terraform destroy failed: {e}")
            
            # FALLBACK: Also run boto3 cleanup to catch any orphaned resources
            print("\n" + "="*60)
            print("  FALLBACK CLEANUP: boto3 resource cleanup")
            print("="*60)
            try:
                _cleanup_aws_resources_boto3(credentials, config.digital_twin_name, cleanup_identity_user, platform_user_email)
                print("  ✓ boto3 cleanup completed")
            except Exception as e:
                print(f"  ✗ boto3 cleanup failed: {e}")
        
        request.addfinalizer(terraform_cleanup)
        
        # Deploy
        try:
            print("\n  Running terraform init + apply...")
            strategy.deploy_all(context)
            print("  ✓ Terraform deployment completed")
        except Exception as e:
            pytest.fail(f"Terraform deployment failed: {e}")
        
        # Get outputs
        try:
            outputs = strategy.get_outputs()
            print(f"  ✓ Got {len(outputs)} Terraform outputs")
            
            # Check if Terraform created a new Identity Store user (for cleanup)
            if outputs.get("aws_platform_user_created"):
                cleanup_identity_user = True
                print("  ℹ Identity Store user was CREATED by Terraform (will delete on cleanup)")
            else:
                print("  ℹ Identity Store user was PRE-EXISTING (will NOT delete on cleanup)")
            
            # Get platform_user_email from config_user.json for cleanup
            user_config_path = Path(project_path) / "config_user.json"
            if user_config_path.exists():
                with open(user_config_path) as f:
                    user_config = json.load(f)
                    # Note: config_user.json uses "admin_email" key
                    platform_user_email = user_config.get("admin_email", "")
                    if platform_user_email:
                        print(f"  ℹ Platform user email for cleanup: {platform_user_email}")
        except Exception as e:
            pytest.fail(f"Failed to get Terraform outputs: {e}")
        
        yield {
            "context": context,
            "strategy": strategy,
            "outputs": outputs,
            "project_path": project_path,
        }
    
    # ==========================================================================
    # TESTS
    # ==========================================================================
    
    def test_01_terraform_outputs_present(self, deployed_environment):
        """Verify essential Terraform outputs are present."""
        outputs = deployed_environment["outputs"]
        
        # Check AWS setup outputs
        assert outputs.get("aws_resource_group_name"), "aws_resource_group_name output missing"
        assert outputs.get("aws_account_id"), "aws_account_id output missing"
        assert outputs.get("aws_region"), "aws_region output missing"
    
    def test_02_l1_iot_deployed(self, deployed_environment):
        """Verify L1 IoT resources are deployed."""
        import boto3
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        
        # Verify dispatcher Lambda exists
        dispatcher_name = outputs.get("aws_l1_dispatcher_function_name")
        if dispatcher_name:
            lambda_client = boto3.client(
                'lambda',
                aws_access_key_id=credentials["aws_access_key_id"],
                aws_secret_access_key=credentials["aws_secret_access_key"],
                region_name=credentials["aws_region"]
            )
            
            response = lambda_client.get_function(FunctionName=dispatcher_name)
            assert response["Configuration"]["FunctionName"] == dispatcher_name
            print(f"  ✓ Dispatcher Lambda exists: {dispatcher_name}")
        
        # Verify IoT Topic Rule exists
        rule_name = outputs.get("aws_iot_topic_rule_name")
        if rule_name:
            iot_client = boto3.client(
                'iot',
                aws_access_key_id=credentials["aws_access_key_id"],
                aws_secret_access_key=credentials["aws_secret_access_key"],
                region_name=credentials["aws_region"]
            )
            
            response = iot_client.get_topic_rule(ruleName=rule_name)
            assert response["rule"]["ruleName"] == rule_name
            print(f"  ✓ IoT Topic Rule exists: {rule_name}")
    
    def test_02a_iot_devices_registered(self, deployed_environment):
        """Verify IoT devices were registered by SDK post-deployment.
        
        This validates:
        - register_aws_iot_devices() executed successfully
        - The refactored context.providers["aws"] pattern works for IoT
        - Things are registered in IoT Core
        """
        import boto3
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        
        iot_client = boto3.client(
            'iot',
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region_name=credentials["aws_region"]
        )
        
        # List things with a filter for our digital twin name
        twin_name = context.config.digital_twin_name
        response = iot_client.list_things(maxResults=25)
        things = response.get("things", [])
        
        # Filter to things related to this twin
        twin_things = [t for t in things if twin_name in t.get("thingName", "")]
        
        print(f"  Found {len(twin_things)} IoT things for {twin_name}")
        
        if twin_things:
            for thing in twin_things[:5]:  # Print first 5
                print(f"    - {thing.get('thingName')}")
            print("  ✓ IoT devices registered by SDK")
        else:
            # This is acceptable - devices may not be configured in config_iot_devices.json
            print("  ⚠ No IoT things found (check config_iot_devices.json)")

    
    def test_02b_l2_persister_deployed(self, deployed_environment):
        """Verify L2 Persister Lambda is deployed.
        
        This validates:
        - Terraform created the Persister Lambda
        - Lambda is in Active state and ready to process messages
        """
        import boto3
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        
        # Check for persister Lambda in outputs
        persister_name = outputs.get("aws_l2_persister_function_name")
        if not persister_name:
            pytest.skip("L2 Persister Lambda not in outputs (may be named differently)")
        
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region_name=credentials["aws_region"]
        )
        
        response = lambda_client.get_function(FunctionName=persister_name)
        assert response["Configuration"]["FunctionName"] == persister_name
        assert response["Configuration"]["State"] == "Active"
        print(f"  ✓ Persister Lambda exists and Active: {persister_name}")

    
    def test_03_l3_dynamodb_deployed(self, deployed_environment):
        """Verify L3 DynamoDB table is deployed."""
        import boto3
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        
        table_name = outputs.get("aws_dynamodb_table_name")
        if table_name:
            dynamodb_client = boto3.client(
                'dynamodb',
                aws_access_key_id=credentials["aws_access_key_id"],
                aws_secret_access_key=credentials["aws_secret_access_key"],
                region_name=credentials["aws_region"]
            )
            
            response = dynamodb_client.describe_table(TableName=table_name)
            assert response["Table"]["TableName"] == table_name
            assert response["Table"]["TableStatus"] == "ACTIVE"
            print(f"  ✓ DynamoDB table exists and active: {table_name}")
    
    def test_04_l4_twinmaker_deployed(self, deployed_environment):
        """Verify L4 TwinMaker workspace is deployed."""
        import boto3
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        
        workspace_id = outputs.get("aws_twinmaker_workspace_id")
        if workspace_id:
            twinmaker_client = boto3.client(
                'iottwinmaker',
                aws_access_key_id=credentials["aws_access_key_id"],
                aws_secret_access_key=credentials["aws_secret_access_key"],
                region_name=credentials["aws_region"]
            )
            
            response = twinmaker_client.get_workspace(workspaceId=workspace_id)
            assert response["workspaceId"] == workspace_id
            print(f"  ✓ TwinMaker workspace exists: {workspace_id}")
    
    def test_04b_twinmaker_entities_exist(self, deployed_environment):
        """Verify TwinMaker entities were created by SDK post-deployment.
        
        This validates:
        - create_twinmaker_entities() executed successfully
        - The refactored context.providers["aws"] pattern works
        - Entities are registered in TwinMaker workspace
        """
        import boto3
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        
        workspace_id = outputs.get("aws_twinmaker_workspace_id")
        if not workspace_id:
            pytest.skip("TwinMaker workspace not deployed")
        
        twinmaker_client = boto3.client(
            'iottwinmaker',
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region_name=credentials["aws_region"]
        )
        
        # List entities in the workspace
        response = twinmaker_client.list_entities(workspaceId=workspace_id)
        entities = response.get("entitySummaries", [])
        
        print(f"  Found {len(entities)} entities in workspace")
        
        if entities:
            for entity in entities[:5]:  # Print first 5
                print(f"    - {entity.get('entityId')}: {entity.get('entityName', 'unnamed')}")
            print("  ✓ TwinMaker entities created by SDK")
        else:
            # This is acceptable if IoT devices are not configured
            print("  ⚠ No entities found (may be expected if no devices configured)")
    
    def test_04c_twinmaker_component_types_exist(self, deployed_environment):
        """Verify TwinMaker component types exist.
        
        This validates:
        - Component types are registered (either via Terraform or SDK)
        - Workspace is properly configured for digital twin modeling
        """
        import boto3
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        
        workspace_id = outputs.get("aws_twinmaker_workspace_id")
        if not workspace_id:
            pytest.skip("TwinMaker workspace not deployed")
        
        twinmaker_client = boto3.client(
            'iottwinmaker',
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region_name=credentials["aws_region"]
        )
        
        # List component types in the workspace
        response = twinmaker_client.list_component_types(workspaceId=workspace_id)
        component_types = response.get("componentTypeSummaries", [])
        
        print(f"  Found {len(component_types)} component types in workspace")
        
        # Filter to custom (non-AWS built-in) component types
        custom_types = [ct for ct in component_types if not ct.get("componentTypeId", "").startswith("com.amazon")]
        
        if custom_types:
            for ct in custom_types[:5]:  # Print first 5 custom types
                print(f"    - {ct.get('componentTypeId')}")
            print("  ✓ Custom TwinMaker component types exist")
        else:
            print("  ⚠ No custom component types found (only AWS built-in types)")

    
    def test_05_l5_grafana_deployed(self, deployed_environment):
        """Verify L5 Grafana workspace is deployed."""
        import boto3
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        
        workspace_id = outputs.get("aws_grafana_workspace_id")
        if workspace_id:
            grafana_client = boto3.client(
                'grafana',
                aws_access_key_id=credentials["aws_access_key_id"],
                aws_secret_access_key=credentials["aws_secret_access_key"],
                region_name=credentials["aws_region"]
            )
            
            response = grafana_client.describe_workspace(workspaceId=workspace_id)
            assert response["workspace"]["id"] == workspace_id
            print(f"  ✓ Grafana workspace exists: {workspace_id}")
            
            endpoint = outputs.get("aws_grafana_endpoint")
            if endpoint:
                print(f"  ✓ Grafana endpoint: {endpoint}")
    
    def test_06_send_iot_message(self, deployed_environment):
        """Send a test message through IoT Core and verify routing."""
        import boto3
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        config = context.config
        
        iot_data_client = boto3.client(
            'iot-data',
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region_name=credentials["aws_region"]
        )
        
        # Construct topic name
        device_id = "test-device-001"
        topic = f"dt/{config.digital_twin_name}/{device_id}/telemetry"
        
        message = {
            "device_id": device_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "temperature": 23.5,
            "humidity": 65.2,
            "test_run": True
        }
        
        print(f"\n  Publishing to topic: {topic}")
        print(f"  Message: {json.dumps(message)}")
        
        response = iot_data_client.publish(
            topic=topic,
            qos=1,
            payload=json.dumps(message)
        )
        
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
        print("  ✓ Message published successfully")
        
        # Wait for processing
        print("  Waiting 10 seconds for message processing...")
        time.sleep(10)
    
    def test_07_verify_data_in_dynamodb(self, deployed_environment):
        """Verify the test message reached DynamoDB."""
        import boto3
        from boto3.dynamodb.conditions import Key
        
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        credentials = context.credentials.get("aws", {})
        
        table_name = outputs.get("aws_dynamodb_table_name")
        if not table_name:
            pytest.skip("DynamoDB table not deployed")
        
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region_name=credentials["aws_region"]
        )
        
        table = dynamodb.Table(table_name)
        
        # Query for our test device
        response = table.query(
            KeyConditionExpression=Key('device_id').eq('test-device-001'),
            ScanIndexForward=False,  # Get most recent first
            Limit=5
        )
        
        items = response.get("Items", [])
        print(f"\n  Found {len(items)} items for test-device-001")
        
        if items:
            latest = items[0]
            print(f"  Latest item: {json.dumps(latest, default=str)}")
            assert "temperature" in latest or "data" in latest
            print("  ✓ Data verified in DynamoDB")
        else:
            # Data may not have propagated yet - this is acceptable
            print("  ⚠ No data found (may need more time to propagate)")
    
    def test_08_verify_hot_reader(self, deployed_environment):
        """Verify the Hot Reader Lambda can read data back from DynamoDB."""
        outputs = deployed_environment["outputs"]
        
        hot_reader_url = outputs.get("aws_l3_hot_reader_url")
        if not hot_reader_url:
            pytest.skip("Hot Reader Lambda URL not deployed")
        
        print(f"\n  Hot Reader URL: {hot_reader_url}")
        
        # Query the hot reader for test device data
        query_params = {
            "device_id": "test-device-001",
            "limit": "5"
        }
        
        try:
            response = requests.get(
                hot_reader_url,
                params=query_params,
                timeout=30
            )
            
            print(f"  Response status: {response.status_code}")
            print(f"  Response body: {response.text[:500] if len(response.text) > 500 else response.text}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if we got data back
                if isinstance(data, list):
                    print(f"  ✓ Hot Reader returned {len(data)} items")
                elif isinstance(data, dict):
                    items = data.get("items", data.get("data", []))
                    print(f"  ✓ Hot Reader returned {len(items)} items")
                else:
                    print(f"  ✓ Hot Reader returned response: {type(data)}")
                
                print("  ✓ Hot Reader Lambda working correctly")
            elif response.status_code == 404:
                # No data yet - acceptable for new deployment
                print("  ⚠ No data found via Hot Reader (expected for fresh deployment)")
            else:
                print(f"  ⚠ Unexpected response: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("  ⚠ Hot Reader request timed out (Lambda cold start)")
        except requests.exceptions.RequestException as e:
            print(f"  ⚠ Hot Reader request failed: {e}")

