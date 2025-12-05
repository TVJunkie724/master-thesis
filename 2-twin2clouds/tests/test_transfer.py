import pytest
from backend.calculation import transfer

def test_calculate_egress_cost_generic():
    # Test calculate_egress_cost logic
    
    # Case 1: Empty pricing
    assert transfer.calculate_egress_cost(100, {}) == 0
    
    # Case 2: Free Tier
    config_free = {
        "pricing_tiers": {
            "freeTier": {"limit": 100, "price": 0},
            "tier1": {"limit": "Infinity", "price": 0.1}
        }
    }
    # Within free tier
    assert transfer.calculate_egress_cost(50, config_free) == 0
    # Exceeding free tier (150 total, 50 chargeable)
    # Cost = 50 * 0.1 = 5.0
    assert transfer.calculate_egress_cost(150, config_free) == pytest.approx(5.0)
    
    # Case 3: Multiple Tiers
    config_multi = {
        "pricing_tiers": {
            "tier1": {"limit": 10, "price": 1.0},
            "tier2": {"limit": 20, "price": 0.5},
            "tier3": {"limit": "Infinity", "price": 0.1}
        }
    }
    # 5GB: 5 * 1.0 = 5.0
    assert transfer.calculate_egress_cost(5, config_multi) == 5.0
    
    # 15GB: (10 * 1.0) + (5 * 0.5) = 10 + 2.5 = 12.5
    assert transfer.calculate_egress_cost(15, config_multi) == 12.5
    
    # 40GB: (10 * 1.0) + (20 * 0.5) + (10 * 0.1) = 10 + 10 + 1 = 21.0
    assert transfer.calculate_egress_cost(40, config_multi) == 21.0

def test_calculate_transfer_cost_from_aws_to_internet():
    pricing = {
        "aws": {
            "transfer": {
                "pricing_tiers": {
                    "freeTier": {"limit": 100, "price": 0.0},
                    "tier1": {"limit": 10240, "price": 0.09},
                    "tier2": {"limit": 40960, "price": 0.085},
                    "tier3": {"limit": 102400, "price": 0.07},
                    "tier4": {"limit": "Infinity", "price": 0.05}
                }
            }
        }
    }
    
    # Under free limit (100)
    assert transfer.calculate_transfer_cost_from_aws_to_internet(50, pricing) == 0
    
    # Over free limit (200 total -> 100 charged at tier 1)
    # Cost = 100 * 0.09 = 9.0
    assert transfer.calculate_transfer_cost_from_aws_to_internet(200, pricing) == pytest.approx(9.0)

def test_calculate_transfer_cost_from_azure_to_internet():
    pricing = {
        "azure": {
            "transfer": {
                "pricing_tiers": {
                    "freeTier": {"limit": 100, "price": 0.0},
                    "tier1": {"limit": 10, "price": 0.087}, # artificially small for testing
                    "tier2": {"limit": 10, "price": 0.083},
                    "tier3": {"limit": 10, "price": 0.07},
                    "tier4": {"limit": "Infinity", "price": 0.05}
                }
            }
        }
    }
    
    # Under free limit
    assert transfer.calculate_transfer_cost_from_azure_to_internet(50, pricing) == 0
    
    # Complex case: 100 (free) + 10 (tier1) + 10 (tier2) + 10 (tier3) + 10 (tier4) = 140 GB
    # Cost = (10 * 0.087) + (10 * 0.083) + (10 * 0.07) + (10 * 0.05)
    #      = 0.87 + 0.83 + 0.70 + 0.50 = 2.90
    assert transfer.calculate_transfer_cost_from_azure_to_internet(140, pricing) == pytest.approx(2.9, rel=1e-5)

def test_transfer_wrappers():
    # Verify a few wrappers return 0 or call logic correctly (implicit verify via logic checks above)
    assert transfer.calculate_transfer_cost_from_l2_aws_to_aws_hot(100) == 0
    assert transfer.calculate_transfer_cost_from_l2_gcp_to_gcp_hot(100) == 0
    assert transfer.calculate_transfer_cost_from_gcp_hot_to_gcp_cool(100, {}) == 0
