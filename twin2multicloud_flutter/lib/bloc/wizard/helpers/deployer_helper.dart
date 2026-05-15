// lib/bloc/wizard/helpers/deployer_helper.dart
// Extracted deployer/Step 3 config logic

import '../wizard_state.dart';
import '../../../models/wizard_config_requests.dart';

/// Helper class for deployer configuration operations
/// Extracts logic from WizardBloc to improve maintainability
class DeployerHelper {
  /// Build deployer config payload for API update
  static Map<String, dynamic> buildDeployerConfigPayload(WizardState state) {
    return buildDeployerConfigRequest(state).toJson();
  }

  /// Build typed deployer config request for API update.
  static DeployerConfigUpdateRequest buildDeployerConfigRequest(
    WizardState state,
  ) {
    return DeployerConfigUpdateRequest(
      deployerDigitalTwinName: state.deployerDigitalTwinName,
      configEventsJson: state.configEventsJson,
      configIotDevicesJson: state.configIotDevicesJson,
      configJsonValidated: state.configJsonValidated,
      configEventsValidated: state.configEventsValidated,
      configIotDevicesValidated: state.configIotDevicesValidated,
      payloadsJson: state.payloadsJson,
      payloadsValidated: state.payloadsValidated,
      processorContents: state.processorContents,
      processorValidated: state.processorValidated,
      processorRequirements: state.processorRequirements,
      eventFeedbackContent: state.eventFeedbackContent,
      eventFeedbackValidated: state.eventFeedbackValidated,
      eventFeedbackRequirements: state.eventFeedbackRequirements,
      eventActionContents: state.eventActionContents,
      eventActionValidated: state.eventActionValidated,
      eventActionRequirements: state.eventActionRequirements,
      stateMachineContent: state.stateMachineContent,
      stateMachineValidated: state.stateMachineValidated,
      hierarchyContent: state.hierarchyContent,
      hierarchyValidated: state.hierarchyValidated,
      sceneGlbUploaded: state.sceneGlbUploaded,
      sceneConfigContent: state.sceneConfigContent,
      sceneConfigValidated: state.sceneConfigValidated,
      userConfigContent: state.userConfigContent,
      userConfigValidated: state.userConfigValidated,
    );
  }

  /// Check if any Section 2 config is present
  static bool hasSection2Data(WizardState state) {
    return state.deployerDigitalTwinName != null ||
        state.configEventsJson != null ||
        state.configIotDevicesJson != null;
  }

  /// Check if Section 2 validation is complete
  static bool isSection2Valid(WizardState state) {
    return state.configJsonValidated &&
        state.configEventsValidated &&
        state.configIotDevicesValidated;
  }

  /// Check if any L2 content is present
  static bool hasL2Data(WizardState state) {
    return state.processorContents.isNotEmpty ||
        state.eventFeedbackContent != null ||
        state.eventActionContents.isNotEmpty ||
        state.stateMachineContent != null;
  }

  /// Check if any L4/L5 content is present
  static bool hasL4L5Data(WizardState state) {
    return state.hierarchyContent != null ||
        state.sceneGlbUploaded ||
        state.sceneConfigContent != null ||
        state.userConfigContent != null;
  }

  /// Hydrate deployer config from API response
  static Map<String, dynamic> hydrateDeployerState(
    Map<String, dynamic> deployerConfig,
  ) {
    return {
      'deployerDigitalTwinName':
          deployerConfig['deployer_digital_twin_name'] as String?,
      'configEventsJson': deployerConfig['config_events_json'] as String?,
      'configIotDevicesJson':
          deployerConfig['config_iot_devices_json'] as String?,
      'configJsonValidated':
          deployerConfig['config_json_validated'] as bool? ?? false,
      'configEventsValidated':
          deployerConfig['config_events_validated'] as bool? ?? false,
      'configIotDevicesValidated':
          deployerConfig['config_iot_devices_validated'] as bool? ?? false,
      // Section 3 L1
      'payloadsJson': deployerConfig['payloads_json'] as String?,
      'payloadsValidated':
          deployerConfig['payloads_validated'] as bool? ?? false,
      // Section 3 L2
      'processorContents': deployerConfig['processor_contents'] != null
          ? Map<String, String>.from(
              deployerConfig['processor_contents'] as Map,
            )
          : <String, String>{},
      'processorValidated': deployerConfig['processor_validated'] != null
          ? Map<String, bool>.from(deployerConfig['processor_validated'] as Map)
          : <String, bool>{},
      'processorRequirements': deployerConfig['processor_requirements'] != null
          ? Map<String, String>.from(
              deployerConfig['processor_requirements'] as Map,
            )
          : <String, String>{},
      'eventFeedbackContent':
          deployerConfig['event_feedback_content'] as String?,
      'eventFeedbackValidated':
          deployerConfig['event_feedback_validated'] as bool? ?? false,
      'eventFeedbackRequirements':
          deployerConfig['event_feedback_requirements'] as String?,
      'eventActionContents': deployerConfig['event_action_contents'] != null
          ? Map<String, String>.from(
              deployerConfig['event_action_contents'] as Map,
            )
          : <String, String>{},
      'eventActionValidated': deployerConfig['event_action_validated'] != null
          ? Map<String, bool>.from(
              deployerConfig['event_action_validated'] as Map,
            )
          : <String, bool>{},
      'eventActionRequirements':
          deployerConfig['event_action_requirements'] != null
          ? Map<String, String>.from(
              deployerConfig['event_action_requirements'] as Map,
            )
          : <String, String>{},
      'stateMachineContent': deployerConfig['state_machine_content'] as String?,
      'stateMachineValidated':
          deployerConfig['state_machine_validated'] as bool? ?? false,
      // L4/L5 fields
      'hierarchyContent': deployerConfig['hierarchy_content'] as String?,
      'hierarchyValidated':
          deployerConfig['hierarchy_validated'] as bool? ?? false,
      'sceneGlbUploaded':
          deployerConfig['scene_glb_uploaded'] as bool? ?? false,
      'sceneConfigContent': deployerConfig['scene_config_content'] as String?,
      'sceneConfigValidated':
          deployerConfig['scene_config_validated'] as bool? ?? false,
      'userConfigContent': deployerConfig['user_config_content'] as String?,
      'userConfigValidated':
          deployerConfig['user_config_validated'] as bool? ?? false,
    };
  }

  /// Clear all L2 validation states (for cascade reset on Section 2 change)
  static WizardState clearL2Validation(WizardState state) {
    final clearedValidation = state.processorValidated.map(
      (k, v) => MapEntry(k, false),
    );
    final clearedEventActionValidation = state.eventActionValidated.map(
      (k, v) => MapEntry(k, false),
    );

    return state.copyWith(
      processorValidated: clearedValidation,
      eventFeedbackValidated: false,
      eventActionValidated: clearedEventActionValidation,
      stateMachineValidated: false,
    );
  }
}
