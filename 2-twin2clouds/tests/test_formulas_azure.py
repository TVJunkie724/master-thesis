import pytest
import math
from backend.calculation import azure

def test_azure_iot_hub_formula():
    # Formula: CM = c_m * N_m (Tiered)
    
    devices = 100
    interval = 1
    msg_size = 1
    
    expected_messages = 4320000
    
    pricing = {
        "azure": {
            "iotHub": {
                "pricing_tiers": {
                    "tier1": {"limit": 400000, "threshold": 400000, "price": 10.0}, # Basic B1
                    "tier2": {"limit": 6000000, "threshold": 6000000, "price": 50.0}, # Basic B2
                    "tier3": {"limit": 300000000, "threshold": 300000000, "price": 500.0} # Basic B3
                }
            }
        }
    }
    
    # Execution
    result = azure.calculate_azure_cost_data_acquisition(devices, interval, msg_size, pricing)
    
    # Verification
    # Messages = 4,320,000
    # Fits in Tier 2 (Limit 6,000,000)
    # Threshold = 6,000,000 units per unit? No, threshold is daily/monthly limit per unit.
    # azure.py logic:
    # if total <= tier1.limit: ...
    # elif total <= tier2.limit: threshold = tier2.threshold, price = tier2.price
    # cost = ceil(total / threshold) * price
    
    # Here: 4.32M <= 6M. Threshold = 6M. Price = 50.
    # Cost = ceil(4.32M / 6M) * 50 = 1 * 50 = 50.
    
    assert result["totalMessagesPerMonth"] == expected_messages
    assert result["totalMonthlyCost"] == 50.0

def test_azure_functions_formula():
    # Formula: CE (Same as AWS in this implementation)
    
    devices = 10
    interval = 60
    msg_size = 1
    
    expected_executions = 7300
    
    pricing = {
        "azure": {
            "functions": {
                "freeRequests": 0,
                "requestPrice": 0.20,
                "freeComputeTime": 0,
                "durationPrice": 0.000016
            }
        }
    }
    
    # Execution
    result = azure.calculate_azure_cost_data_processing(devices, interval, msg_size, pricing)
    
    # Verification
    # Request Cost: 7300 * 0.20 = 1460
    # Compute: 7300 * 0.1 * 0.001 * (128/1024) = 91.25 GB-s
    # Duration Cost: 91.25 * 0.000016 = 0.00146
    
    expected_cost = 1460 + 0.00146
    
    assert result["totalMonthlyCost"] == pytest.approx(expected_cost, rel=1e-5)

def test_azure_cosmos_db_formula():
    # Formula: CA + CS
    # RUs calculation is complex here.
    
    data_size = 10
    messages = 1000
    msg_size = 1
    duration = 1
    
    pricing = {
        "azure": {
            "cosmosDB": {
                "minimumRequestUnits": 400,
                "RUsPerWrite": 5,
                "RUsPerRead": 1,
                "storagePrice": 0.25,
                "requestPrice": 0.008 # Per 100 RU/s hour? No, usually hourly price per 100 RU/s.
            }
        }
    }
    
    # Execution
    result = azure.calculate_cosmos_db_cost(data_size, messages, msg_size, duration, pricing)
    
    # Verification
    # Storage: 10 * (1 + 0.5) = 15 GB-Months
    # Storage Cost: 15 * 0.25 = 3.75
    
    # Writes/sec = 1000 / (30*24*3600) = 0.00038
    # Reads/sec = 0.00038
    # Total RUs = (0.00038 * 5 * 1) + (0.00038 * 1) = 0.00228
    
    # Min RUs = 400
    # Max(0.00228, 400) = 400
    
    # Cost = 400 * 0.008 = 3.2 (Wait, is requestPrice per RU or per 100 RU? Code says: request_units_needed * request_price)
    # If requestPrice is per RU, then 400 * 0.008 = 3.2.
    
    expected_cost = 3.75 + 3.2
    
    assert result["totalMonthlyCost"] == pytest.approx(expected_cost, rel=1e-5)

def test_azure_blob_formula():
    # Formula: CS + CA
    
    data_size = 100
    duration = 1
    
    pricing = {
        "azure": {
            "blobStorageCool": {
                "storagePrice": 0.01,
                "writePrice": 0.05,
                "readPrice": 0.004,
                "dataRetrievalPrice": 0.01
            }
        }
    }
    
    # Execution
    result = azure.calculate_azure_blob_storage_cost(data_size, duration, pricing)
    
    # Verification
    # Storage: 100 * 1 * 0.01 = 1.0
    
    # Writes: ceil(100 * 1024 / 100) = 1024
    # Cost Writes: 1024 * 0.05 = 51.2
    
    # Reads: 1024 * 0.1 = 102.4
    # Cost Reads: 102.4 * 0.004 = 0.4096
    
    # Retrieval: (100 * 0.1) + 100 = 110
    # Cost Retrieval: 110 * 0.01 = 1.1
    
    expected_cost = 1.0 + 51.2 + 0.4096 + 1.1
    
    assert result["totalMonthlyCost"] == pytest.approx(expected_cost, rel=1e-5)
