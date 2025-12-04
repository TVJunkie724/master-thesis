import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from backend.calculation.engine import calculate_cheapest_costs
from backend.config_loader import load_combined_pricing

# Preset 2 Parameters (approximate based on typical "High Data" scenario)
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

print("--- Debugging Calculation ---")
try:
    pricing = load_combined_pricing()
    result = calculate_cheapest_costs(params, pricing)
    
    print("\n--- Results ---")
    print(f"Cheapest Path: {result['cheapestPath']}")
    
    l2_hot_aws = result['awsCosts']['resultHot']['totalMonthlyCost']
    l2_hot_azure = result['azureCosts']['resultHot']['totalMonthlyCost']
    l2_hot_gcp = result['gcpCosts']['resultHot']['totalMonthlyCost']
    
    l3_aws = result['awsCosts']['dataProcessing']['totalMonthlyCost']
    l3_azure = result['azureCosts']['dataProcessing']['totalMonthlyCost']
    l3_gcp = result['gcpCosts']['dataProcessing']['totalMonthlyCost']
    
    print(f"\nL2 Hot Costs: AWS=${l2_hot_aws:.2f}, Azure=${l2_hot_azure:.2f}, GCP=${l2_hot_gcp:.2f}")
    print(f"L3 Processing Costs: AWS=${l3_aws:.2f}, Azure=${l3_azure:.2f}, GCP=${l3_gcp:.2f}")
    
    print(f"\nCombined AWS: ${l2_hot_aws + l3_aws:.2f}")
    print(f"Combined Azure: ${l2_hot_azure + l3_azure:.2f}")
    print(f"Combined GCP: ${l2_hot_gcp + l3_gcp:.2f}")
    
    if result.get('l2OptimizationOverride'):
        print(f"\nL2 Override Triggered: {result['l2OptimizationOverride']}")
    else:
        print("\nNo L2 Optimization Override triggered.")

    if result.get('l3OptimizationOverride'):
        print(f"L3 Override Triggered: {result['l3OptimizationOverride']}")
        
    if result.get('l4OptimizationOverride'):
        print(f"L4 Override Triggered: {result['l4OptimizationOverride']}")
        
    if result.get('l2CoolOptimizationOverride'):
        print(f"L2 Cool Override Triggered: {result['l2CoolOptimizationOverride']}")
        
    l4_aws = result['awsCosts']['resultL4']['totalMonthlyCost'] if result['awsCosts']['resultL4'] else 0
    l4_azure = result['azureCosts']['resultL4']['totalMonthlyCost'] if result['azureCosts']['resultL4'] else 0
    l4_gcp = result['gcpCosts']['resultL4']['totalMonthlyCost'] if result['gcpCosts']['resultL4'] else 0
    
    print(f"\nL4 Costs: AWS=${l4_aws:.2f}, Azure=${l4_azure:.2f}, GCP=${l4_gcp:.2f}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
