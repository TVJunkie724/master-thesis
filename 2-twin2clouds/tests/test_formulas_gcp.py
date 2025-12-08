import pytest
import math
from backend.calculation import gcp

def test_gcp_iot_formula():
    # Formula: CM = c_m * N_m (Volume based)
    # Note: GCP implementation uses 730 hours/month, not 24*30=720
    
    devices = 100
    interval = 1
    msg_size = 1
    
    # Expected Messages: 100 * (60/1) * 730 = 4,380,000
    expected_messages = 4380000
    
    pricing = {
        "gcp": {
            "iot": {
                "pricePerGiB": 1.0 
            }
        }
    }
    
    # Execution
    result = gcp.calculate_gcp_cost_data_acquisition(devices, interval, msg_size, pricing)
    
    # Verification
    # Messages = 4,380,000
    # Data Volume (GB) = (4,380,000 * 1) / (1024 * 1024) = 4.1771484375
    # Cost = 4.1771484375 * 1.0 = 4.1771484375
    
    expected_cost = (expected_messages * msg_size) / (1024 * 1024) * 1.0

    assert result["totalMessagesPerMonth"] == expected_messages
    assert result["totalMonthlyCost"] == pytest.approx(expected_cost, rel=1e-5)

def test_gcp_functions_formula():
    # Formula: CE
    
    devices = 10
    interval = 60
    msg_size = 1
    
    expected_executions = 7300
    
    pricing = {
        "gcp": {
            "functions": {
                "freeRequests": 0,
                "requestPrice": 0.40, # Per million usually
                "freeComputeTime": 0,
                "durationPrice": 0.0000025
            }
        }
    }
    
    # Execution
    result = gcp.calculate_gcp_cost_data_processing(devices, interval, msg_size, pricing)
    
    # Verification
    # Request Cost: 7300 * 0.40 = 2920
    
    # Compute: 7300 * 0.1 * 0.001 = 0.73 seconds
    # GB-Seconds: 0.73 * (128/1024) = 0.09125
    # Duration Cost: 0.09125 * 0.0000025 = 0.000000228
    
    expected_cost = 2920 + 0.000000228
    
    assert result["totalMonthlyCost"] == pytest.approx(expected_cost, rel=1e-5)

def test_gcp_firestore_formula():
    # Formula: CS + CA
    # Read ratio: 1 read per 2 writes (0.5x) - aligned with AWS DynamoDB
    # Storage buffer: +0.5 months for mid-month accumulation
    
    data_size = 10
    messages = 1000
    msg_size = 1
    duration = 1
    
    pricing = {
        "gcp": {
            "storage_hot": {
                "storagePrice": 0.18,
                "freeStorage": 0,
                "writePrice": 1.0, # Per unit
                "readPrice": 0.5
            }
        }
    }
    
    # Execution
    result = gcp.calculate_firestore_cost(data_size, messages, msg_size, duration, pricing)
    
    # Verification
    # Storage: 10 * 0.18 * (1 + 0.5) = 10 * 0.18 * 1.5 = 2.7 (includes buffer)
    # Writes: 1000 * 1.0 = 1000
    # Reads: 1000 / 2 = 500 (0.5x ratio - aligned with AWS)
    # Cost Reads: 500 * 0.5 = 250
    
    expected_cost = 2.7 + 1000 + 250
    
    assert result["totalMonthlyCost"] == expected_cost

def test_gcp_storage_formula():
    # Formula: CS + CA (includes operation costs for equivalency with AWS/Azure)
    
    data_size = 100
    duration = 1
    
    pricing = {
        "gcp": {
            "storage_cool": {
                "storagePrice": 0.02,
                "writePrice": 0.05,  # Per operation
                "readPrice": 0.004,
                "dataRetrievalPrice": 0.01
            }
        }
    }
    
    # Execution
    result = gcp.calculate_gcp_storage_cool_cost(data_size, duration, pricing)
    
    # Verification
    # Storage: 100 * 0.02 * 1 = 2.0
    # Writes: ceil(100 * 1024 / 100) = 1024
    # Cost Writes: 1024 * 0.05 = 51.2
    # Reads: 1024 * 0.1 = 102.4
    # Cost Reads: 102.4 * 0.004 = 0.4096
    # Retrieval: (100 * 0.1) + 100 = 110
    # Cost Retrieval: 110 * 0.01 = 1.1
    
    expected_cost = 2.0 + 51.2 + 0.4096 + 1.1
    
    assert result["totalMonthlyCost"] == pytest.approx(expected_cost, rel=1e-5)

def test_gcp_twin_maker_formula():
    # Formula: Instance + Storage + Model Storage
    
    entity_count = 100
    devices = 10
    interval = 1
    dashboard_refreshes = 1
    active_hours = 1
    avg_3d_model_size_mb = 100
    
    pricing = {
        "gcp": {
            "twinmaker": {
                "e2MediumPrice": 0.04, # Hourly
                "storagePrice": 0.05   # Disk GB
            },
            "storage_cool": {
                "storagePrice": 0.02   # Bucket GB
            }
        }
    }
    
    result = gcp.calculate_gcp_twin_maker_cost(
        entity_count, devices, interval,
        dashboard_refreshes, active_hours,
        avg_3d_model_size_mb, pricing
    )
    
    # Cost Calc:
    # Instance: 0.04 * 730 = 29.2
    # Disk: 50 * 0.05 = 2.5
    # Model Storage: (100 * 100 / 1024) * 0.02 = 9.765625 * 0.02 = 0.1953125
    
    expected_cost = 29.2 + 2.5 + 0.1953125
    
    assert result["totalMonthlyCost"] == pytest.approx(expected_cost, rel=1e-5)
