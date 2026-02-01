"""
Unit tests for adt_helper.py functions.

Tests for Azure Digital Twins helper functions that handle:
- Device-to-twin ID mapping
- JSON Patch document building for twin updates
"""

import unittest
from unittest.mock import MagicMock, patch


class TestBuildAdtPatch(unittest.TestCase):
    """Tests for build_adt_patch()."""
    
    def test_single_property_creates_patch(self):
        """Happy path: single property creates valid JSON Patch."""
        from src.providers.azure.azure_functions._shared.adt_helper import build_adt_patch
        result = build_adt_patch({"temperature": 23.5})
        self.assertEqual(result, [{"op": "replace", "path": "/temperature", "value": 23.5}])
    
    def test_multiple_properties_creates_multiple_patches(self):
        """Happy path: multiple properties create multiple patch operations."""
        from src.providers.azure.azure_functions._shared.adt_helper import build_adt_patch
        result = build_adt_patch({"temperature": 23.5, "humidity": 60})
        self.assertEqual(len(result), 2)
        paths = {p["path"] for p in result}
        self.assertEqual(paths, {"/temperature", "/humidity"})
    
    def test_empty_telemetry_raises(self):
        """Validation: empty telemetry dict raises ValueError."""
        from src.providers.azure.azure_functions._shared.adt_helper import build_adt_patch
        with self.assertRaises(ValueError) as cm:
            build_adt_patch({})
        self.assertIn("cannot be empty", str(cm.exception))

    def test_patch_uses_replace_operation(self):
        """Verification: patch operations use 'replace' for updates."""
        from src.providers.azure.azure_functions._shared.adt_helper import build_adt_patch
        result = build_adt_patch({"pressure": 101.3})
        self.assertEqual(result[0]["op"], "replace")


class TestGetTwinIdForDevice(unittest.TestCase):
    """Tests for get_twin_id_for_device()."""
    
    def test_returns_mapped_twin_id(self):
        """Happy path: returns twin ID from mapping."""
        from src.providers.azure.azure_functions._shared.adt_helper import get_twin_id_for_device
        info = {"devices": {"device-1": {"twin_id": "sensor-twin-1"}}}
        result = get_twin_id_for_device("device-1", info)
        self.assertEqual(result, "sensor-twin-1")
    
    def test_returns_device_id_when_no_mapping(self):
        """Fallback: returns device_id when no mapping exists for device."""
        from src.providers.azure.azure_functions._shared.adt_helper import get_twin_id_for_device
        info = {"devices": {"other-device": {"twin_id": "other-twin"}}}
        result = get_twin_id_for_device("device-1", info)
        self.assertEqual(result, "device-1")

    def test_raises_when_empty_info(self):
        """Error: raises ValueError when digital_twin_info is empty."""
        from src.providers.azure.azure_functions._shared.adt_helper import get_twin_id_for_device
        with self.assertRaises(ValueError) as cm:
            get_twin_id_for_device("temperature-sensor-1", {})
        self.assertIn("required", str(cm.exception))

    def test_returns_device_id_when_twins_not_in_mapping(self):
        """Fallback: returns device_id when device not in devices dict."""
        from src.providers.azure.azure_functions._shared.adt_helper import get_twin_id_for_device
        info = {"devices": {}}
        result = get_twin_id_for_device("device-1", info)
        self.assertEqual(result, "device-1")


if __name__ == "__main__":
    unittest.main()
