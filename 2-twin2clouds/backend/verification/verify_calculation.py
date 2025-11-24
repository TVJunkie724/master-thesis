import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from py.calculation.engine import calculate_cheapest_costs
from py.logger import logger

# Mock params
params = {
    "numberOfDevices": 100,
    "deviceSendingIntervalInMinutes": 2,
    "averageSizeOfMessageInKb": 0.25,
    "hotStorageDurationInMonths": 1,
    "coolStorageDurationInMonths": 3,
    "archiveStorageDurationInMonths": 12,
    "needs3DModel": False,
    "entityCount": 0,
    "amountOfActiveEditors": 2,
    "amountOfActiveViewers": 10,
    "dashboardRefreshesPerHour": 4,
    "dashboardActiveHoursPerDay": 8,
    "currency": "USD"
}

try:
    print("--- Starting Calculation Verification ---")
    result = calculate_cheapest_costs(params)
    
    if "calculationResult" in result and "cheapestPath" in result:
        print("✅ Calculation successful!")
        print(f"Cheapest Path: {result['cheapestPath']}")
        print(f"L1 Provider: {result['calculationResult']['L1']}")
        print(f"Currency: {result.get('currency')}")
    else:
        print("❌ Calculation result structure is incorrect!")
        print(result.keys())

    # Test EUR conversion
    print("\n--- Testing EUR Conversion ---")
    params["currency"] = "EUR"
    result_eur = calculate_cheapest_costs(params)
    if result_eur.get("currency") == "EUR":
        print("✅ EUR conversion flag present.")
        # Check if costs are different (simple check)
        aws_cost_usd = result["awsCosts"]["dataAquisition"]["totalMonthlyCost"]
        aws_cost_eur = result_eur["awsCosts"]["dataAquisition"]["totalMonthlyCost"]
        print(f"USD Cost: {aws_cost_usd}, EUR Cost: {aws_cost_eur}")
        if aws_cost_usd != aws_cost_eur:
             print("✅ Costs are converted.")
        else:
             print("❌ Costs appear identical (conversion might have failed or rate is 1.0).")

except Exception as e:
    print(f"❌ Calculation failed with error: {e}")
    import traceback
    traceback.print_exc()
