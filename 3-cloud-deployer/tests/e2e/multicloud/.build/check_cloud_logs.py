"""
Check ALL cloud logs for EVERY function in both E2E scenarios.
Saves output to file for investigation.
"""
import os
import json
import sys
from datetime import datetime, timedelta

OUTPUT_FILE = "/app/tests/e2e/multicloud/.build/cloud_logs_investigation.txt"

class LogCapture:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "w")
    
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
    
    def flush(self):
        self.terminal.flush()
        self.log.flush()
    
    def close(self):
        self.log.close()

def check_all_aws_lambda_logs(scenario_prefix):
    """Check ALL AWS Lambda log groups for a scenario."""
    import boto3
    
    print(f"\n{'='*80}")
    print(f"AWS CLOUDWATCH - ALL LAMBDAS FOR {scenario_prefix}")
    print('='*80)
    
    client = boto3.client('logs', region_name='eu-central-1')
    start_time = int((datetime.now() - timedelta(days=2)).timestamp() * 1000)
    
    # List all log groups matching the scenario
    try:
        paginator = client.get_paginator('describe_log_groups')
        for page in paginator.paginate(logGroupNamePrefix=f"/aws/lambda/{scenario_prefix}"):
            for lg in page['logGroups']:
                log_group = lg['logGroupName']
                print(f"\n{'─'*60}")
                print(f"📦 {log_group}")
                print('─'*60)
                
                try:
                    # Get ALL recent messages (not just errors)
                    response = client.filter_log_events(
                        logGroupName=log_group,
                        startTime=start_time,
                        limit=20
                    )
                    
                    if response['events']:
                        for event in response['events']:
                            ts = datetime.fromtimestamp(event['timestamp']/1000)
                            msg = event['message'].strip()
                            # Highlight errors
                            if any(x in msg.lower() for x in ['error', 'fail', 'exception', 'denied']):
                                print(f"❌ [{ts}] {msg[:300]}")
                            else:
                                print(f"   [{ts}] {msg[:200]}")
                    else:
                        print("   ⚠️ No logs in last 2 days")
                        
                except Exception as e:
                    print(f"   Error reading logs: {e}")
                    
    except Exception as e:
        print(f"Error listing log groups: {e}")


def check_all_gcp_function_logs(scenario_prefix):
    """Check ALL GCP Cloud Function logs for a scenario."""
    from google.cloud import logging as gcp_logging
    from google.cloud import functions_v1
    
    print(f"\n{'='*80}")
    print(f"GCP CLOUD FUNCTIONS - ALL FOR {scenario_prefix}")
    print('='*80)
    
    log_client = gcp_logging.Client()
    
    # List all functions matching the scenario
    try:
        func_client = functions_v1.CloudFunctionsServiceClient()
        parent = "projects/digital-twin-dev-481720/locations/europe-west1"
        
        for func in func_client.list_functions(parent=parent):
            func_name = func.name.split('/')[-1]
            if not func_name.startswith(scenario_prefix):
                continue
                
            print(f"\n{'─'*60}")
            print(f"📦 {func_name}")
            print('─'*60)
            
            try:
                # Get ALL recent logs
                filter_str = f'resource.type="cloud_function" resource.labels.function_name="{func_name}"'
                entries = list(log_client.list_entries(filter_=filter_str, max_results=20))
                
                if entries:
                    for entry in entries:
                        ts = entry.timestamp
                        msg = str(entry.payload)[:300] if entry.payload else "No message"
                        severity = entry.severity if hasattr(entry, 'severity') else 'INFO'
                        
                        if severity in ['ERROR', 'CRITICAL', 'WARNING']:
                            print(f"❌ [{ts}] [{severity}] {msg}")
                        else:
                            print(f"   [{ts}] {msg[:200]}")
                else:
                    print("   ⚠️ No logs in last 2 days")
                    
            except Exception as e:
                print(f"   Error reading logs: {e}")
                
    except Exception as e:
        print(f"Error listing functions: {e}")


def check_all_azure_function_logs(scenario_prefix):
    """Check ALL Azure Function logs for a scenario."""
    from azure.identity import ClientSecretCredential
    from azure.monitor.query import LogsQueryClient
    
    print(f"\n{'='*80}")
    print(f"AZURE FUNCTIONS - ALL FOR {scenario_prefix}")
    print('='*80)
    
    # Load credentials
    creds_file = "/app/upload/template/config_credentials.json"
    with open(creds_file) as f:
        creds = json.load(f)["azure"]
    
    credential = ClientSecretCredential(
        tenant_id=creds["azure_tenant_id"],
        client_id=creds["azure_client_id"],
        client_secret=creds["azure_client_secret"]
    )
    
    client = LogsQueryClient(credential)
    
    # Get workspace ID from terraform state
    tf_state_file = f"/app/tests/e2e/multicloud/e2e_state/{scenario_prefix}/terraform.tfstate"
    try:
        with open(tf_state_file) as f:
            tf_state = json.load(f)
        
        outputs = tf_state.get("outputs", {})
        workspace_id = outputs.get("azure_log_analytics_workspace_id", {}).get("value")
        
        if not workspace_id:
            print("⚠️ Log Analytics workspace ID not found")
            return
            
        print(f"Workspace ID: {workspace_id}")
        
        # Query for ALL function logs
        queries = [
            ("FunctionAppLogs", f"""
                FunctionAppLogs
                | where _ResourceId contains "{scenario_prefix}" or FunctionName contains "{scenario_prefix}"
                | order by TimeGenerated desc
                | take 30
                | project TimeGenerated, FunctionName, Level, Message
            """),
            ("AppTraces", f"""
                AppTraces
                | where AppRoleName contains "{scenario_prefix}"
                | order by TimeGenerated desc
                | take 30
                | project TimeGenerated, AppRoleName, SeverityLevel, Message
            """),
        ]
        
        for query_name, query in queries:
            print(f"\n{'─'*60}")
            print(f"📋 {query_name}")
            print('─'*60)
            
            try:
                response = client.query_workspace(
                    workspace_id=workspace_id,
                    query=query,
                    timespan=timedelta(days=2)
                )
                
                if response.tables and response.tables[0].rows:
                    for row in response.tables[0].rows:
                        level = str(row[2]) if len(row) > 2 else 'INFO'
                        if level in ['Error', 'Critical', 'Warning', '3', '4']:
                            print(f"❌ {row}")
                        else:
                            print(f"   {row}")
                else:
                    print("   ⚠️ No logs found")
                    
            except Exception as e:
                print(f"   Query error: {e}")
                
    except FileNotFoundError:
        print(f"⚠️ Terraform state not found: {tf_state_file}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Capture output to file
    sys.stdout = LogCapture(OUTPUT_FILE)
    
    print("="*80)
    print("COMPLETE E2E CLOUD LOG INVESTIGATION - ALL FUNCTIONS")
    print(f"Time: {datetime.now()}")
    print(f"Output saved to: {OUTPUT_FILE}")
    print("="*80)
    
    # ======================================
    # AWS-GCP Scenario
    # ======================================
    print("\n\n" + "#"*80)
    print("# SCENARIO: sc-aws-gcp")
    print("# L1=AWS IoT, L2=GCP, L3-Hot=AZURE CosmosDB, L4=AWS TwinMaker")
    print("#"*80)
    
    check_all_aws_lambda_logs("sc-aws-gcp")
    check_all_gcp_function_logs("sc-aws-gcp")
    check_all_azure_function_logs("sc-aws-gcp")
    
    # ======================================
    # Azure-AWS Scenario  
    # ======================================
    print("\n\n" + "#"*80)
    print("# SCENARIO: sc-azure-aws")
    print("# L1=AZURE IoT Hub, L2=AWS, L3-Hot=GCP Firestore, L4=AWS TwinMaker")
    print("#"*80)
    
    check_all_azure_function_logs("sc-azure-aws")
    check_all_aws_lambda_logs("sc-azure-aws")
    check_all_gcp_function_logs("sc-azure-aws")
    
    print("\n\n" + "="*80)
    print(f"INVESTIGATION COMPLETE - Output saved to: {OUTPUT_FILE}")
    print("="*80)
    
    sys.stdout.close()
