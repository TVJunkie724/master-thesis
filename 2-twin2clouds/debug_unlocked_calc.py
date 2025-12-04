import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from backend.calculation import aws, azure, gcp, transfer
from backend.config_loader import load_combined_pricing

# Preset 2 Parameters (High Data)
params = {
    "numberOfDevices": 4000,
    "deviceSendingIntervalInMinutes": 0.5,
    "averageSizeOfMessageInKb": 0.5,
    "hotStorageDurationInMonths": 3,
    "coolStorageDurationInMonths": 12,
    "archiveStorageDurationInMonths": 36,
    "needs3DModel": False,
    "entityCount": 0,
    "amountOfActiveEditors": 25,
    "amountOfActiveViewers": 10,
    "dashboardRefreshesPerHour": 60,
    "dashboardActiveHoursPerDay": 4,
    "currency": "USD",
    "useEventChecking": True,
    "triggerNotificationWorkflow": True,
    "returnFeedbackToDevice": True,
    "integrateErrorHandling": True,
    "orchestrationActionsPerMessage": 5,
    "eventsPerMessage": 1,
    "apiCallsPerDashboardRefresh": 10
}

def calculate_unlocked_costs():
    print("--- Investigating Unlocked L2-L3 Calculation ---")
    pricing = load_combined_pricing()
    
    # Calculate Data Volume in GB/month
    messages_per_month = params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730
    data_volume_gb = (messages_per_month * params["averageSizeOfMessageInKb"]) / (1024 * 1024)
    
    print(f"Data Volume: {data_volume_gb:.2f} GB/month")
    # AWS
    aws_l2 = aws.calculate_dynamodb_cost(data_volume_gb, messages_per_month, params["averageSizeOfMessageInKb"], params["hotStorageDurationInMonths"], pricing)
    aws_l3 = aws.calculate_aws_cost_data_processing(params["numberOfDevices"], params["deviceSendingIntervalInMinutes"], params["averageSizeOfMessageInKb"], pricing, params["useEventChecking"], params["triggerNotificationWorkflow"], params["returnFeedbackToDevice"], params["integrateErrorHandling"], params["orchestrationActionsPerMessage"], params["eventsPerMessage"])
    
    # Azure
    azure_l2 = azure.calculate_cosmos_db_cost(data_volume_gb, messages_per_month, params["averageSizeOfMessageInKb"], params["hotStorageDurationInMonths"], pricing)
    azure_l3 = azure.calculate_azure_cost_data_processing(params["numberOfDevices"], params["deviceSendingIntervalInMinutes"], params["averageSizeOfMessageInKb"], pricing, params["useEventChecking"], params["triggerNotificationWorkflow"], params["returnFeedbackToDevice"], params["integrateErrorHandling"], params["orchestrationActionsPerMessage"], params["eventsPerMessage"])
    
    # GCP
    gcp_l2 = gcp.calculate_firestore_cost(data_volume_gb, messages_per_month, params["averageSizeOfMessageInKb"], params["hotStorageDurationInMonths"], pricing)
    gcp_l3 = gcp.calculate_gcp_cost_data_processing(params["numberOfDevices"], params["deviceSendingIntervalInMinutes"], params["averageSizeOfMessageInKb"], pricing, params["useEventChecking"], params["triggerNotificationWorkflow"], params["returnFeedbackToDevice"], params["integrateErrorHandling"], params["orchestrationActionsPerMessage"], params["eventsPerMessage"])

    providers = ["AWS", "Azure", "GCP"]
    l2_costs = {"AWS": aws_l2["totalMonthlyCost"], "Azure": azure_l2["totalMonthlyCost"], "GCP": gcp_l2["totalMonthlyCost"]}
    l3_costs = {"AWS": aws_l3["totalMonthlyCost"], "Azure": azure_l3["totalMonthlyCost"], "GCP": gcp_l3["totalMonthlyCost"]}
    
    # Calculate Transfer Costs (L2 Hot -> L3)
    # We need the data volume being transferred. 
    # Assuming all data stored in Hot Storage is processed by L3? 
    # Or is it the incoming stream? 
    # Usually L3 processes the stream or reads from L2. 
    # Let's assume L3 reads from L2 Hot Storage.
    
    # Calculate Data Volume in GB/month
    messages_per_month = params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730
    data_volume_gb = (messages_per_month * params["averageSizeOfMessageInKb"]) / (1024 * 1024)
    
    print(f"Data Volume: {data_volume_gb:.2f} GB/month")
    
    results = []

    for l2_prov in providers:
        for l3_prov in providers:
            cost = l2_costs[l2_prov] + l3_costs[l3_prov]
            details = f"L2({l2_prov}) + L3({l3_prov})"
            
            transfer_fee = 0
            glue_cost = 0
            
            if l2_prov != l3_prov:
                # 1. Egress from L2 Provider
                # We need to fetch the egress price.
                # Using the transfer module or direct pricing lookup if possible.
                # For simplicity, let's use the transfer module's logic or look up the key.
                
                # Construct key for transfer module (e.g., L2_AWS_Hot_to_L3_Azure)
                # Note: The transfer module usually handles L1->L2, L2->L2(Cool). 
                # We might need to manually calculate egress here if not defined.
                
                # Let's look at how engine.py handles L1->L2 transfer.
                # It uses transfer.calculate_transfer_costs.
                
                # We will simulate the egress cost manually here for clarity.
                # Egress Price Logic
                egress_price = 0
                if l2_prov == "AWS":
                    egress_price = pricing["aws"]["transfer"].get("egressPrice", 0.09) # Fallback if missing
                elif l2_prov == "Azure":
                    # Azure has tiered pricing structure in JSON
                    # Use Tier 1 price (up to 10TB) which covers our use case
                    try:
                        egress_price = pricing["azure"]["transfer"]["pricing_tiers"]["tier1"]["price"]
                    except KeyError:
                        egress_price = 0.087 # Fallback
                elif l2_prov == "GCP":
                    egress_price = pricing["gcp"]["transfer"].get("egressPrice", 0.12) # Fallback if missing
                
                transfer_fee = data_volume_gb * egress_price
                
                # 2. Ingestion/Glue Code at L3 Provider (Connector/Reader Function)
                # If moving from L2 to L3 (different cloud), we likely need a "Reader Function" or similar glue.
                # engine.py adds "Connector Function" cost for L1->L2.
                # Let's assume a similar "Reader Function" cost is needed to pull data from L2 Hot to L3.
                # We can reuse the "connector function" cost calculation as a proxy for this glue code.
                
                if l3_prov == "AWS":
                    glue_cost = aws.calculate_aws_connector_function_cost(messages_per_month, pricing)
                elif l3_prov == "Azure":
                    glue_cost = azure.calculate_azure_connector_function_cost(messages_per_month, pricing)
                elif l3_prov == "GCP":
                    glue_cost = gcp.calculate_gcp_connector_function_cost(messages_per_month, pricing)
            
            total_cost = cost + transfer_fee + glue_cost
            results.append({
                "combination": details,
                "l2_cost": l2_costs[l2_prov],
                "l3_cost": l3_costs[l3_prov],
                "transfer_cost": transfer_fee,
                "glue_cost": glue_cost,
                "total_cost": total_cost
            })

    # Sort results
    results.sort(key=lambda x: x["total_cost"])
    
    print("\n--- Comparison of L2 + L3 Combinations ---")
    print(f"{'Combination':<30} | {'Total':<10} | {'L2':<8} | {'L3':<8} | {'Transfer':<8} | {'Glue':<8}")
    print("-" * 85)
    for r in results:
        print(f"{r['combination']:<30} | ${r['total_cost']:<9.2f} | ${r['l2_cost']:<8.2f} | ${r['l3_cost']:<8.2f} | ${r['transfer_cost']:<8.2f} | ${r['glue_cost']:<8.2f}")

if __name__ == "__main__":
    calculate_unlocked_costs()
