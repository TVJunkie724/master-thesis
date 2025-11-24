import pytest
import math
from backend.calculation import aws

def test_aws_iot_core_formula():
    # Formula: CM = c_m * N_m
    # N_m = Devices * (60/Interval) * 24 * 30
    
    # Setup
    devices = 100
    interval = 1 # minute
    msg_size = 1 # KB
    
    # Expected Messages: 100 * 60 * 24 * 30 = 4,320,000
    expected_messages = 4320000
    
    pricing = {
        "aws": {
            "iotCore": {
                "pricePerDeviceAndMonth": 0, # Simplified for formula check
                "priceRulesTriggered": 0,
                "pricing_tiers": {
                    "tier1": {"limit": 5000000000, "price": 1.0}, # $1 per million messages (simplified)
                    "tier2": {"limit": 5000000000, "price": 0.8},
                    "tier3": {"limit": 5000000000, "price": 0.7}
                }
            }
        }
    }
    
    # Execution
    result = aws.calculate_aws_cost_data_acquisition(devices, interval, msg_size, pricing)
    
    # Verification
    # Cost = 4,320,000 * 1.0 = 4,320,000 (Wait, price is usually per million or similar, let's check implementation)
    # The implementation in aws.py lines 44-48:
    # monthly_cost += remaining_messages * price_tier1
    # So if price is 1.0, cost is 4,320,000.
    
    assert result["totalMessagesPerMonth"] == expected_messages
    assert result["totalMonthlyCost"] == expected_messages * 1.0

def test_aws_lambda_formula():
    # Formula: CE = c_e * (N_e - free) + c_t * (T_e - free)
    
    devices = 10
    interval = 60 # 1 per hour
    msg_size = 1
    
    # Executions: 10 * 1 * 730 = 7,300
    expected_executions = 7300
    
    pricing = {
        "aws": {
            "lambda": {
                "freeRequests": 0,
                "requestPrice": 0.20, # Per 1M usually, but code multiplies directly? 
                # aws.py line 99: (executions - free) * requestPrice. 
                # So requestPrice in JSON must be per request.
                
                "freeComputeTime": 0,
                "durationPrice": 0.0000166667, # Per GB-second
            }
        }
    }
    
    # Execution
    result = aws.calculate_aws_cost_data_processing(devices, interval, msg_size, pricing)
    
    # Verification
    # Request Cost: 7300 * 0.20 = 1460
    # Compute: 7300 * 0.1s (100ms) * 0.001 = 730 seconds
    # GB-Seconds: 730 * (128/1024) = 91.25 GB-s
    # Duration Cost: 91.25 * 0.0000166667 = 0.00152
    
    expected_cost = (7300 * 0.20) + (91.25 * 0.0000166667)
    
    assert result["totalMessagesPerMonth"] == expected_executions
    assert result["totalMonthlyCost"] == pytest.approx(expected_cost, rel=1e-5)

def test_aws_dynamodb_formula():
    # Formula: CA + CS
    # Storage: V * D * c_s
    # Writes: N * c_w
    # Reads: N/2 * c_r
    
    data_size = 10 # GB
    messages = 1000
    msg_size = 1 # KB
    duration = 1 # Month
    
    pricing = {
        "aws": {
            "dynamoDB": {
                "writePrice": 1.25, # Per unit
                "readPrice": 0.25,
                "storagePrice": 0.25,
                "freeStorage": 0
            }
        }
    }
    
    # Execution
    result = aws.calculate_dynamodb_cost(data_size, messages, msg_size, duration, pricing)
    
    # Verification
    # Storage: 10 * (1 + 0.5) = 15 GB-Months (Code adds 0.5 buffer)
    # Cost Storage: ceil(15 * 0.25) = ceil(3.75) = 4.0 (Code uses math.ceil)
    
    # Write Units: 1000 * 1 = 1000
    # Cost Write: 1000 * 1.25 = 1250
    
    # Read Units: 1000 / 2 = 500
    # Cost Read: 500 * 0.25 = 125
    
    expected_cost = 4.0 + 1250 + 125
    
    assert result["totalMonthlyCost"] == expected_cost

def test_aws_s3_formula():
    # Formula: CS + CA
    
    data_size = 100 # GB
    duration = 1
    
    pricing = {
        "aws": {
            "s3InfrequentAccess": {
                "storagePrice": 0.0125,
                "upfrontPrice": 0,
                "requestPrice": 0.01,
                "dataRetrievalPrice": 0.01
            }
        }
    }
    
    # Execution
    result = aws.calculate_s3_infrequent_access_cost(data_size, duration, pricing)
    
    # Verification
    # Storage: 100 * 1 * 0.0125 = 1.25
    
    # Requests: ceil(100 * 1024 / 100) * 2 = ceil(1024) * 2 = 1024 * 2 = 2048
    # Cost Requests: 2048 * 0.01 = 20.48
    
    # Retrieval: (100 * 1 * 0.1) + 100 = 10 + 100 = 110 GB
    # Cost Retrieval: 110 * 0.01 = 1.10
    
    expected_cost = 1.25 + 20.48 + 1.10
    
    assert result["totalMonthlyCost"] == pytest.approx(expected_cost, rel=1e-5)
