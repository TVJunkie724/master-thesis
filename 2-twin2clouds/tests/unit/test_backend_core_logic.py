
import pytest
import os
from unittest.mock import patch
from backend import config_loader, pricing_utils

# -----------------------------------------------------------------------------
# 1. Pricing Utils & Math Precision
# -----------------------------------------------------------------------------

def test_currency_conversion_precision():
    """Test standard conversion with high precision requirements."""
    with patch("backend.pricing_utils.get_currency_rates") as mock_rates:
        mock_rates.return_value = {"usd_to_eur_rate": 0.92, "eur_to_usd_rate": 1.09}
        
        # Test small value
        val_usd = 0.000000000001
        res_eur = pricing_utils.usd_to_eur(val_usd)
        assert res_eur > 0
        
        # Test large value
        val_usd_large = 1_000_000_000.0
        res_eur_large = pricing_utils.usd_to_eur(val_usd_large)
        assert res_eur_large == 920_000_000.0

def test_validate_pricing_schema_empty_data():
    """Test validation when data is empty/None."""
    res = pricing_utils.validate_pricing_schema("aws", {})
    assert res["status"] == "missing"
    assert res["missing_keys"] == []

def test_validate_pricing_schema_unknown_provider():
    """Test validation with unknown provider name."""
    data = {"bogus": "data"}
    res = pricing_utils.validate_pricing_schema("bogus_provider", data)
    assert res["status"] == "unknown_provider"

def test_validate_pricing_schema_service_not_dict():
    """Test validation when a service key exists but its value is not a dict."""
    # Based on implementation: if service is not dict, it continues (skips key checks).
    # The service keys inside iotCore won't be found, so it should return 'incomplete'.
    data = {"iotCore": "NotADict"}
    res = pricing_utils.validate_pricing_schema("aws", data)
    # Since iotCore is not a dict, keys like 'pricing_tiers' are missing
    assert res["status"] == "incomplete"
    assert len(res["missing_keys"]) > 0

# -----------------------------------------------------------------------------
# 2. Config Loader Robustness
# -----------------------------------------------------------------------------

@patch("backend.config_loader.logger")
def test_load_json_file_race_condition(mock_logger):
    """Test that file loading correctly raises and logs errors."""
    with patch("builtins.open", side_effect=FileNotFoundError("Gone!")):
        with pytest.raises(FileNotFoundError):
             config_loader.load_json_file("ghost.json")
    
    assert mock_logger.error.called

@patch("backend.config_loader.load_json_file_optional")
def test_load_combined_pricing_partial_failure(mock_load_opt):
    """Test behavior when one provider fails to load (returns empty dict)."""
    def side_effect(path):
        s_path = str(path)
        if "gcp" in s_path: 
            return {}
        return {"some": "data"}
    
    mock_load_opt.side_effect = side_effect
    
    combined = config_loader.load_combined_pricing()
    assert combined["aws"] == {"some": "data"}
    assert combined["azure"] == {"some": "data"}
    assert combined["gcp"] == {}


@patch("backend.config_loader.logger")
def test_load_config_file_uses_default_when_config_mount_missing(mock_logger):
    """Optimizer should start without the optional /config/config.json mount."""
    with patch("backend.config_loader.os.path.exists", return_value=False):
        with patch.dict(os.environ, {"TWIN2CLOUDS_MODE": "DEBUG"}):
            assert config_loader.load_config_file() == {"mode": "DEBUG"}

    assert mock_logger.warning.called
