"""
Test Core Formulas
==================

Unit tests for the provider-independent cost formulas.
"""

import pytest
from backend.calculation_v2.formulas import (
    message_based_cost,
    execution_based_cost,
    action_based_cost,
    storage_based_cost,
    user_based_cost,
    transfer_cost,
    tiered_message_cost,
    tiered_transfer_cost,
)


class TestMessageBasedCost:
    """Tests for CM formula."""
    
    def test_basic_calculation(self):
        """CM: c_m × N_m"""
        result = message_based_cost(
            price_per_message=0.001,
            num_messages=1_000_000
        )
        assert result == 1000.0
    
    def test_zero_messages(self):
        """Zero messages should return zero cost."""
        result = message_based_cost(
            price_per_message=0.001,
            num_messages=0
        )
        assert result == 0.0


class TestExecutionBasedCost:
    """Tests for CE formula."""
    
    def test_basic_calculation(self):
        """CE: c_e × max(0, N_e - free) + c_t × max(0, T_e - free)"""
        result = execution_based_cost(
            price_per_execution=0.0000002,
            num_executions=2_000_000,
            free_executions=1_000_000,
            price_per_compute_unit=0.0000166667,
            total_compute_units=500_000,
            free_compute_units=400_000
        )
        # Request cost: 0.0000002 * 1_000_000 = 0.20
        # Compute cost: 0.0000166667 * 100_000 = 1.66667
        expected = 0.20 + (0.0000166667 * 100_000)
        assert abs(result - expected) < 0.01
    
    def test_within_free_tier(self):
        """Usage within free tier should be zero cost."""
        result = execution_based_cost(
            price_per_execution=0.0000002,
            num_executions=500_000,
            free_executions=1_000_000,
            price_per_compute_unit=0.0000166667,
            total_compute_units=200_000,
            free_compute_units=400_000
        )
        assert result == 0.0


class TestActionBasedCost:
    """Tests for CA formula."""
    
    def test_basic_calculation(self):
        """CA: c_a × N_a"""
        result = action_based_cost(
            price_per_action=0.000001,
            num_actions=1_000_000
        )
        assert result == 1.0
    
    def test_zero_actions(self):
        """Zero actions should be zero cost."""
        result = action_based_cost(
            price_per_action=0.000001,
            num_actions=0
        )
        assert result == 0.0


class TestStorageBasedCost:
    """Tests for CS formula."""
    
    def test_basic_calculation(self):
        """CS: c_s × V × D"""
        result = storage_based_cost(
            price_per_gb_month=0.023,
            volume_gb=100,
            duration_months=1.0
        )
        assert result == 2.30
    
    def test_default_duration(self):
        """Default duration should be 1 month."""
        result = storage_based_cost(
            price_per_gb_month=0.023,
            volume_gb=100
        )
        assert result == 2.30


class TestUserBasedCost:
    """Tests for CU formula."""
    
    def test_seat_based_only(self):
        """Test seat-based pricing (Grafana)."""
        result = user_based_cost(
            price_per_editor=9.0,
            num_editors=2,
            price_per_viewer=5.0,
            num_viewers=5
        )
        assert result == (9.0 * 2) + (5.0 * 5)  # 18 + 25 = 43
    
    def test_time_based_only(self):
        """Test time-based pricing (VMs)."""
        result = user_based_cost(
            price_per_editor=0,
            num_editors=0,
            price_per_viewer=0,
            num_viewers=0,
            price_per_hour=0.05,
            total_hours=730
        )
        assert result == 0.05 * 730  # 36.50


class TestTransferCost:
    """Tests for CTransfer formula."""
    
    def test_basic_calculation(self):
        """CTransfer: c_transfer × GB_transferred"""
        result = transfer_cost(
            price_per_gb=0.09,
            gb_transferred=100
        )
        assert result == 9.0


class TestTieredMessageCost:
    """Tests for tiered message pricing."""
    
    def test_single_tier(self):
        """Single tier pricing."""
        tiers = [{"limit": float('inf'), "price": 0.001}]
        result = tiered_message_cost(1_000_000, tiers)
        assert result == 1000.0
    
    def test_multi_tier(self):
        """Multi-tier pricing crossing tiers."""
        tiers = [
            {"limit": 1_000_000, "price": 1.0},
            {"limit": 2_000_000, "price": 0.8},
            {"limit": float('inf'), "price": 0.6}
        ]
        # 1.5M messages: 1M at $1 + 0.5M at $0.8
        result = tiered_message_cost(1_500_000, tiers)
        expected = (1_000_000 * 1.0) + (500_000 * 0.8)
        assert result == expected
