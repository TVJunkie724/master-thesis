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

  static const payloads = '''[
  {
    "iotDeviceId": "temperature-sensor-1",
    "time": "",
    "temperature": 28
  },
  {
    "iotDeviceId": "pressure-sensor-1",
    "time": "",
    "pressure": 1000
  }
]''';

  /// AWS Lambda processor example
  static const processors = '''"""User Processor Lambda Function."""
import json


def lambda_handler(event, context):
    """Process incoming IoT event."""
    
    # === YOUR PROCESSING LOGIC HERE ===
    processed_event = event
    # ==================================
    
    return processed_event
''';

  /// Azure Functions processor example
  static const azureProcessors = '''"""User Processor Azure Function."""
import azure.functions as func
import json


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Process incoming IoT event."""
    event = req.get_json()
    
    # === YOUR PROCESSING LOGIC HERE ===
    processed_event = event
    # ==================================
    
    return func.HttpResponse(
        json.dumps(processed_event),
        mimetype="application/json"
    )
''';

  /// GCP Cloud Functions processor example
  static const gcpProcessors = '''"""User Processor Cloud Function."""
import json
from flask import jsonify


def process_event(request):
    """Process incoming IoT event."""
    event = request.get_json()
    
    # === YOUR PROCESSING LOGIC HERE ===
    processed_event = event
    # ==================================
    
    return jsonify(processed_event)
''';

  static const stateMachine = '''{
  "Comment": "Sequential Lambda Execution",
  "StartAt": "ProcessEvent",
  "States": {
    "ProcessEvent": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName.\$": "\$.LambdaArn",
        "Payload.\$": "\$.InputData"
      },
      "End": true
    }
  }
}''';

  /// AWS Step Functions state machine example
  static const awsStateMachine = '''{
  "Comment": "Sequential Lambda Execution",
  "StartAt": "LambdaA",
  "States": {
    "LambdaA": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName.\$": "\$.LambdaAArn",
        "Payload.\$": "\$.InputData"
      },
      "ResultPath": "\$.LambdaAResult",
      "Next": "LambdaB"
    },
    "LambdaB": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName.\$": "\$.LambdaBArn",
        "Payload": {
          "fromA.\$": "\$.LambdaAResult.Payload",
          "event.\$": "\$.InputData"
        }
      },
      "OutputPath": "\$.Payload",
      "End": true
    }
  }
}''';

  /// Azure Logic App workflow example
  static const azureStateMachine = '''{
  "definition": {
    "\$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
    "contentVersion": "1.0.0.0",
    "triggers": {
      "manual": {
        "type": "Request",
        "kind": "Http"
      }
    },
    "actions": {
      "Call_Function": {
        "type": "Http",
        "inputs": {
          "method": "POST",
          "uri": "@triggerBody()['FunctionURL']",
          "body": "@triggerBody()['InputData']"
        }
      }
    }
  }
}''';

  /// Google Cloud Workflows YAML example
  static const gcpStateMachine = '''main:
  params: [args]
  steps:
    - init:
        assign:
          - inputData: \${args.InputData}
          - funcUrl: \${args.FunctionURL}
    - callFunction:
        call: http.post
        args:
          url: \${funcUrl}
          body:
            input: \${inputData}
        result: response
    - returnResult:
        return: \${response.body}''';

  // ============================================================
  // L4: Hierarchy & Scene Config Examples
  // ============================================================

  /// AWS TwinMaker hierarchy example
  static const awsHierarchy = '''{
  "entities": [
    {
      "entityId": "room-1",
      "entityName": "Main Room",
      "components": [
        {
          "componentName": "temperature-sensor-1",
          "componentTypeId": "com.example.temperature"
        }
      ]
    },
    {
      "entityId": "machine-1",
      "entityName": "Pump Motor",
      "parentEntityId": "room-1",
      "components": [
        {
          "componentName": "pressure-sensor-1",
          "componentTypeId": "com.example.pressure"
        }
      ]
    }
  ]
}''';

  /// Azure Digital Twins hierarchy example
  static const azureHierarchy = '''{
  "twins": [
    {
      "\$dtId": "room-1",
      "\$etag": "W/\\"auto\\"",
      "\$metadata": {
        "\$model": "dtmi:example:Room;1"
      }
    },
    {
      "\$dtId": "machine-1",
      "\$etag": "W/\\"auto\\"",
      "\$metadata": {
        "\$model": "dtmi:example:Machine;1"
      }
    }
  ],
  "relationships": [
    {
      "\$relationshipId": "machine1-in-room1",
      "\$sourceId": "machine-1",
      "\$targetId": "room-1",
      "\$relationshipName": "isLocatedIn"
    }
  ]
}''';

  /// AWS TwinMaker scene.json example
  static const awsSceneConfig = '''{
  "specVersion": "1.0",
  "version": "1",
  "unit": "meters",
  "nodes": [
    {
      "name": "room-1",
      "components": [
        {
          "type": "ModelRef",
          "uri": "s3://YOUR_TWINMAKER_S3_BUCKET/scene_assets/digital_twin_scene.glb",
          "modelType": "GLB"
        }
      ]
    }
  ],
  "rootNodeIndexes": [0]
}''';

  /// Azure 3D Scenes Studio configuration example  
  static const azureSceneConfig = '''{
  "\$schema": "https://azureiotsolutions.com/3DScenes/1.0.0/schema.json",
  "configuration": {
    "scenes": [
      {
        "id": "scene-1",
        "displayName": "Factory Floor",
        "elements": [
          {"primaryTwinID": "room-1", "type": "TwinToObjectMapping"},
          {"primaryTwinID": "machine-1", "type": "TwinToObjectMapping"}
        ],
        "assets": [
          {"url": "{{STORAGE_URL}}/scene.glb", "type": "Unity3D"}
        ]
      }
    ]
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

  static const userConfig = '''{
  "admin_email": "your-email@example.com",
  "admin_first_name": "Platform",
  "admin_last_name": "Admin"
}''';

  /// Azure-specific user config (requires tenant format email)
  static const azureUserConfig = '''{
  "admin_email": "user@yourtenant.onmicrosoft.com",
  "admin_first_name": "Platform",
  "admin_last_name": "Admin"
}''';
}
