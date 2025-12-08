"""
Tests for GCP Self-Hosted Toggle Feature.

These tests verify that the allowGcpSelfHostedL4 and allowGcpSelfHostedL5 
parameters correctly control whether GCP is included in the L4/L5 optimization.
"""
import pytest
from backend.calculation.engine import calculate_cheapest_costs
from backend.config_loader import load_combined_pricing


@pytest.fixture(scope="module")
def pricing():
    """Load actual pricing data for tests."""
    return load_combined_pricing()


# Standard test params
BASE_PARAMS = {
    "numberOfDevices": 100,
    "deviceSendingIntervalInMinutes": 5,
    "averageSizeOfMessageInKb": 0.25,
    "hotStorageDurationInMonths": 1,
    "coolStorageDurationInMonths": 3,
    "archiveStorageDurationInMonths": 12,
    "needs3DModel": False,
    "entityCount": 1,
    "amountOfActiveEditors": 1,
    "amountOfActiveViewers": 2,
    "dashboardRefreshesPerHour": 2,
    "dashboardActiveHoursPerDay": 8,
    "average3DModelSizeInMB": 100.0,
    "useEventChecking": False,
    "triggerNotificationWorkflow": False,
    "returnFeedbackToDevice": False,
    "eventsPerMessage": 1,
    "orchestrationActionsPerMessage": 3,
    "apiCallsPerDashboardRefresh": 1,
}


def test_l4_excludes_gcp_when_toggle_false(pricing):
    """GCP should NOT be selected for L4 when allowGcpSelfHostedL4=False."""
    params = {**BASE_PARAMS, "allowGcpSelfHostedL4": False, "allowGcpSelfHostedL5": True}
    result = calculate_cheapest_costs(params, pricing=pricing)
    
    # cheapestPath should not contain L4_GCP
    cheapest_path = result.get("cheapestPath", [])
    l4_selection = [p for p in cheapest_path if p.startswith("L4_")]
    
    assert len(l4_selection) == 1, "There should be exactly one L4 in cheapest path"
    assert l4_selection[0] != "L4_GCP", "L4 should not be GCP when toggle is False"
    assert l4_selection[0] in ["L4_AWS", "L4_Azure", "L4_None"], "L4 should be AWS, Azure, or None when GCP is excluded"


def test_l5_excludes_gcp_when_toggle_false(pricing):
    """GCP should NOT be selected for L5 when allowGcpSelfHostedL5=False."""
    params = {**BASE_PARAMS, "allowGcpSelfHostedL4": True, "allowGcpSelfHostedL5": False}
    result = calculate_cheapest_costs(params, pricing=pricing)
    
    # cheapestPath should not contain L5_GCP
    cheapest_path = result.get("cheapestPath", [])
    l5_selection = [p for p in cheapest_path if p.startswith("L5_")]
    
    # L5 selection should NOT be GCP
    assert len(l5_selection) == 1, "There should be exactly one L5 in cheapest path"
    assert l5_selection[0] != "L5_GCP", "L5 should not be GCP when toggle is False"
    assert l5_selection[0] in ["L5_AWS", "L5_Azure"], "L5 should be AWS or Azure when GCP is excluded"


def test_both_toggles_false_excludes_gcp_from_l4_and_l5(pricing):
    """When both toggles are False, GCP should be excluded from both L4 and L5."""
    params = {**BASE_PARAMS, "allowGcpSelfHostedL4": False, "allowGcpSelfHostedL5": False}
    result = calculate_cheapest_costs(params, pricing=pricing)
    
    cheapest_path = result.get("cheapestPath", [])
    
    # L4 in cheapest path should not be GCP
    l4_selection = [p for p in cheapest_path if p.startswith("L4_")]
    assert len(l4_selection) == 1
    assert l4_selection[0] != "L4_GCP", "L4 should not be GCP when toggle is False"
    
    # L5 in cheapest path should not be GCP
    l5_selection = [p for p in cheapest_path if p.startswith("L5_")]
    assert len(l5_selection) == 1
    assert l5_selection[0] != "L5_GCP", "L5 should not be GCP when toggle is False"


def test_gcp_costs_still_returned_when_excluded(pricing):
    """GCP costs should still be in the response even when excluded from optimization."""
    params = {**BASE_PARAMS, "allowGcpSelfHostedL4": False, "allowGcpSelfHostedL5": False}
    result = calculate_cheapest_costs(params, pricing=pricing)
    
    # GCP costs should still be present for display purposes
    gcp_costs = result.get("gcpCosts", {})
    assert "resultL4" in gcp_costs, "GCP L4 costs should still be present in response"
    assert "resultL5" in gcp_costs, "GCP L5 costs should still be present in response"


def test_calculation_result_reflects_l4_exclusion(pricing):
    """calculationResult.L4 should not be 'GCP' when toggle is False."""
    params = {**BASE_PARAMS, "allowGcpSelfHostedL4": False, "allowGcpSelfHostedL5": True}
    result = calculate_cheapest_costs(params, pricing=pricing)
    
    calc_result = result.get("calculationResult", {})
    l4_provider = calc_result.get("L4", "")
    
    assert l4_provider != "GCP", "calculationResult.L4 should not be GCP when toggle is False"


def test_calculation_result_reflects_l5_exclusion(pricing):
    """calculationResult.L5 should not be 'GCP' when toggle is False."""
    params = {**BASE_PARAMS, "allowGcpSelfHostedL4": True, "allowGcpSelfHostedL5": False}
    result = calculate_cheapest_costs(params, pricing=pricing)
    
    calc_result = result.get("calculationResult", {})
    l5_provider = calc_result.get("L5", "")
    
    assert l5_provider != "GCP", "calculationResult.L5 should not be GCP when toggle is False"
