// lib/screens/wizard/helpers/step3_constraints.dart
// Provider-specific constraint and example text for Step 3

import '../../../config/step3_examples.dart';

/// Provider-specific constraint and example text for Step 3.
/// Extracted from step3_deployer.dart to reduce file size.
class Step3Constraints {
  
  /// Get provider-specific function constraints for UI
  static String getFunctionConstraints(String? provider) {
    switch (provider?.toLowerCase()) {
      case 'aws':
        return '• AWS Lambda with lambda_handler(event, context)\n• Returns dict with statusCode';
      case 'azure':
        return '• Azure Function with main(req)\n• Returns HttpResponse';
      case 'gcp':
      case 'google':
        return '• Cloud Function with any entry point\n• HTTP request handler';
      default:
        return '• Provider-specific function entry point';
    }
  }

  /// Get provider-specific processor example
  static String getProcessorExample(String? provider) {
    switch (provider?.toLowerCase()) {
      case 'aws': return Step3Examples.processors;
      case 'azure': return Step3Examples.azureProcessors;
      case 'gcp':
      case 'google': return Step3Examples.gcpProcessors;
      default: return Step3Examples.processors;
    }
  }

  /// Get state machine constraints
  static String getStateMachineConstraints(String? provider) {
    switch (provider?.toLowerCase()) {
      case 'aws':
        return '• AWS Step Functions JSON\n• Amazon States Language';
      case 'azure':
        return '• Azure Logic App JSON\n• Workflow definition';
      case 'gcp':
        return '• Google Workflows YAML\n• Workflow syntax';
      default:
        return '• Provider-specific workflow definition';
    }
  }

  /// Get state machine example
  static String getStateMachineExample(String? provider) {
    switch (provider?.toLowerCase()) {
      case 'aws': return Step3Examples.awsStateMachine;
      case 'azure': return Step3Examples.azureStateMachine;
      case 'gcp': return Step3Examples.gcpStateMachine;
      default: return Step3Examples.stateMachine;
    }
  }
  
  /// Get L4 hierarchy constraints
  static String getHierarchyConstraints(String provider) {
    final isAws = provider.toLowerCase() == 'aws';
    return isAws
        ? '• Define entities with components\n• Match entity IDs to scene config'
        : '• Define twins with DTDL model\n• Match twin IDs to scene config';
  }
  
  /// Get L4 scene config constraints
  static String getSceneConfigConstraints(String provider) {
    final isAws = provider.toLowerCase() == 'aws';
    return isAws
        ? '• References entities from hierarchy\n• GLB model URIs'
        : '• primaryTwinID must exist in hierarchy\n• {{STORAGE_URL}} for asset URLs';
  }
}
