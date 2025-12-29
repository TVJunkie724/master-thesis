/// Example content for Step 3 file editors.
/// Centralized to keep step3_deployer.dart clean.
class Step3Examples {
  Step3Examples._();

  // ============================================================
  // SECTION 2: Configuration File Examples
  // ============================================================

  static const configEvents = '''[
  {
    "condition": "entity.temperature-sensor-1.temperature >= 30",
    "action": {
      "type": "lambda",
      "functionName": "high-temperature-callback",
      "autoDeploy": true,
      "feedback": {
        "type": "mqtt",
        "iotDeviceId": "temperature-sensor-1",
        "payload": "High Temperature Warning"
      }
    }
  }
]''';

  static const configIotDevices = '''[
  {
    "id": "temperature-sensor-1",
    "properties": [
      {"name": "temperature", "dataType": "DOUBLE", "initValue": 25.0}
    ],
    "constProperties": [
      {"name": "serial-number", "dataType": "STRING", "value": "SN12345"}
    ]
  },
  {
    "id": "pressure-sensor-1",
    "properties": [
      {"name": "pressure", "dataType": "DOUBLE", "initValue": 1000.0}
    ]
  }
]''';

  // ============================================================
  // SECTION 3: User Functions & Assets Examples
  // ============================================================

  static const payloads = '''{
  "devices": [
    {
      "device_id": "temp-sensor-01",
      "payload_schema": {
        "temperature": "float",
        "humidity": "float",
        "timestamp": "datetime"
      }
    }
  ]
}''';

  static const processors = '''# processor_temp.py
def process(payload: dict) -> dict:
    """Process temperature sensor data."""
    temp_c = payload.get("temperature", 0)
    temp_f = (temp_c * 9/5) + 32
    
    return {
        **payload,
        "temperature_f": temp_f,
        "status": "normal" if temp_c < 30 else "high"
    }
''';

  static const stateMachine = '''{
  "Comment": "IoT Event Processing Workflow",
  "StartAt": "CheckEvent",
  "States": {
    "CheckEvent": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "\$.eventType",
          "StringEquals": "alert",
          "Next": "SendNotification"
        }
      ],
      "Default": "LogEvent"
    },
    "SendNotification": {
      "Type": "Task",
      "Resource": "arn:aws:sns:...",
      "End": true
    },
    "LogEvent": {
      "Type": "Pass",
      "End": true
    }
  }
}''';

  static const sceneAssets = '''{
  "scenes": [
    {
      "id": "factory-floor",
      "displayName": "Factory Floor",
      "elements": [
        {
          "type": "TemperatureSensor",
          "twinId": "temp-sensor-01",
          "position": {"x": 100, "y": 50}
        }
      ]
    }
  ]
}''';

  static const grafanaConfig = '''{
  "dashboard": {
    "title": "IoT Monitoring",
    "panels": [
      {
        "title": "Temperature",
        "type": "timeseries",
        "datasource": "InfluxDB",
        "targets": [
          {
            "measurement": "temperature",
            "field": "value"
          }
        ]
      }
    ]
  }
}''';
}
