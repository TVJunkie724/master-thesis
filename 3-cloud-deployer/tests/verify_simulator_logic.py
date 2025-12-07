import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import validator
import iot_device_simulator.aws.globals as sim_globals

class TestSimulatorLogic(unittest.TestCase):

    def test_payload_validation_valid(self):
        payload = json.dumps([{"iotDeviceId": "device1", "data": 123}])
        valid, errors, warnings = validator.validate_simulator_payloads(payload)
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)

    def test_payload_validation_invalid_json(self):
        payload = "{ invalid json }"
        valid, errors, _ = validator.validate_simulator_payloads(payload)
        self.assertFalse(valid)
        self.assertIn("Invalid JSON", errors[0])

    def test_payload_validation_missing_id(self):
        payload = json.dumps([{"data": 123}])
        valid, errors, _ = validator.validate_simulator_payloads(payload)
        self.assertFalse(valid)
        self.assertIn("missing required key 'iotDeviceId'", errors[0])

    def test_payload_validation_not_list(self):
        payload = json.dumps({"iotDeviceId": "device1"})
        valid, errors, _ = validator.validate_simulator_payloads(payload)
        self.assertFalse(valid)
        self.assertIn("Must be a JSON array", errors[0])

if __name__ == '__main__':
    unittest.main()
