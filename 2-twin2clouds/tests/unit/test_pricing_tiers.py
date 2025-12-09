
import pytest
from unittest.mock import MagicMock
from backend.calculation import aws

# -----------------------------------------------------------------------------
# 1. Boundary Conditions
# -----------------------------------------------------------------------------

def test_aws_data_acquisition_tier_boundaries():
    """Test exact boundary conditions for AWS IoT Core tiered pricing."""
    
    # Setup standard pricing mock with cumulative limits
    # tier1: first 1000 messages @ $1.00 each
    # tier2: next 4000 messages @ $0.50 each (cumulative limit = 5000)
    # tier3: everything beyond @ $0.10 each
    pricing = {
        "aws": {
            "iotCore": {
                "pricing_tiers": {
                    "tier1": {"limit": 1000, "price": 1.0},
                    "tier2": {"limit": 5000, "price": 0.5},
                    "tier3": {"limit": "Infinity", "price": 0.1}
                },
                "pricePerDeviceAndMonth": 0.0,
                "priceRulesTriggered": 0.0
            }
        }
    }
    
    # Case A: Exactly hitting tier 2 boundary (1001 messages spill 1 into tier 2)
    # Due to float precision with ceil(), 1 device at 43.8 min interval = 1001 messages
    # Cost: 1000 * $1.0 + 1 * $0.5 = $1000.50
    res_tier1_boundary = aws.calculate_aws_cost_data_acquisition(1, 43.8, 1, pricing)
    assert res_tier1_boundary["totalMonthlyCost"] == 1000.5
    assert res_tier1_boundary["provider"] == "AWS"
    
    # Case B: Verify structure of result
    assert "totalMessagesPerMonth" in res_tier1_boundary
    assert "dataSizeInGB" in res_tier1_boundary

def test_aws_data_acquisition_high_volume():
    """Test high volume scenario that hits tier 3."""
    pricing = {
        "aws": {
            "iotCore": {
                "pricing_tiers": {
                    "tier1": {"limit": 100, "price": 1.0},
                    "tier2": {"limit": 200, "price": 0.5},
                    "tier3": {"limit": "Infinity", "price": 0.1}
                },
                "pricePerDeviceAndMonth": 0.0,
                "priceRulesTriggered": 0.0
            }
        }
    }
    
    # 1000 messages: 100 @ $1 + 100 @ $0.5 + 800 @ $0.1 = $100 + $50 + $80 = $230
    # Devices=1, Interval to get 1000 messages: 1000 = 1 * (60/x) * 730 => x = 43.8
    res = aws.calculate_aws_cost_data_acquisition(1, 43.8, 1, pricing)
    # Due to ceil() it might be 1001 messages
    # 100 @ $1 + 100 @ $0.5 + 801 @ $0.1 = $100 + $50 + $80.1 = $230.1
    assert res["totalMonthlyCost"] == pytest.approx(230.1, abs=0.5)

def test_zero_messages_handling():
    """Test behavior when device count is 0 (zero messages)."""
    pricing = {
        "aws": {
            "iotCore": {
                "pricing_tiers": {
                    "tier1": {"limit": 100, "price": 1}
                },
                "pricePerDeviceAndMonth": 10.0,
                "priceRulesTriggered": 0.1
            }
        }
    }
    # 0 devices => 0 messages => $0 cost
    res = aws.calculate_aws_cost_data_acquisition(0, 10, 1, pricing)
    assert res["totalMonthlyCost"] == 0.0

# -----------------------------------------------------------------------------
# 2. Missing Tiers
# -----------------------------------------------------------------------------

def test_missing_tier_keys():
    """Test graceful handling when tier3 is missing from pricing."""
    pricing = {
        "aws": {
            "iotCore": {
                "pricing_tiers": {
                    "tier1": {"limit": 10, "price": 1.0},
                    "tier2": {"limit": 20, "price": 0.5}
                    # Missing tier3
                },
                "pricePerDeviceAndMonth": 0,
                "priceRulesTriggered": 0
            }
        }
    }
    
    # 21 messages: 10 @ $1 + 10 @ $0.5 + 1 @ $0 (missing tier3 defaults to 0) = $15
    # Devices=1, Interval=2085 => 21 messages (approx)
    res = aws.calculate_aws_cost_data_acquisition(1, 2085, 1, pricing)
    assert res["totalMonthlyCost"] == 15.0
