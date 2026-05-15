import 'package:equatable/equatable.dart';

class TwinConfigUpdateRequest extends Equatable {
  final bool? debugMode;
  final int? highestStepReached;
  final Map<String, String?>? cloudConnections;
  final Map<String, dynamic>? aws;
  final Map<String, dynamic>? azure;
  final Map<String, dynamic>? gcp;
  final bool clearAws;
  final bool clearAzure;
  final bool clearGcp;
  final Map<String, dynamic>? optimizerParams;
  final Map<String, dynamic>? optimizerResult;

  const TwinConfigUpdateRequest({
    this.debugMode,
    this.highestStepReached,
    this.cloudConnections,
    this.aws,
    this.azure,
    this.gcp,
    this.clearAws = false,
    this.clearAzure = false,
    this.clearGcp = false,
    this.optimizerParams,
    this.optimizerResult,
  });

  Map<String, dynamic> toJson() {
    return {
      if (debugMode != null) 'debug_mode': debugMode,
      if (cloudConnections != null) 'cloud_connections': cloudConnections,
      if (aws != null || clearAws) 'aws': clearAws ? null : aws,
      if (azure != null || clearAzure) 'azure': clearAzure ? null : azure,
      if (gcp != null || clearGcp) 'gcp': clearGcp ? null : gcp,
      if (optimizerParams != null) 'optimizer_params': optimizerParams,
      if (optimizerResult != null) 'optimizer_result': optimizerResult,
      if (highestStepReached != null)
        'highest_step_reached': highestStepReached,
    };
  }

  @override
  List<Object?> get props => [
    debugMode,
    highestStepReached,
    cloudConnections,
    aws,
    azure,
    gcp,
    clearAws,
    clearAzure,
    clearGcp,
    optimizerParams,
    optimizerResult,
  ];
}

class DeployerConfigUpdateRequest extends Equatable {
  final String? deployerDigitalTwinName;
  final String? configEventsJson;
  final String? configIotDevicesJson;
  final bool configJsonValidated;
  final bool configEventsValidated;
  final bool configIotDevicesValidated;
  final String? payloadsJson;
  final bool payloadsValidated;
  final Map<String, String> processorContents;
  final Map<String, bool> processorValidated;
  final Map<String, String> processorRequirements;
  final String? eventFeedbackContent;
  final bool eventFeedbackValidated;
  final String? eventFeedbackRequirements;
  final Map<String, String> eventActionContents;
  final Map<String, bool> eventActionValidated;
  final Map<String, String> eventActionRequirements;
  final String? stateMachineContent;
  final bool stateMachineValidated;
  final String? hierarchyContent;
  final bool hierarchyValidated;
  final bool sceneGlbUploaded;
  final String? sceneConfigContent;
  final bool sceneConfigValidated;
  final String? userConfigContent;
  final bool userConfigValidated;

  const DeployerConfigUpdateRequest({
    this.deployerDigitalTwinName,
    this.configEventsJson,
    this.configIotDevicesJson,
    this.configJsonValidated = false,
    this.configEventsValidated = false,
    this.configIotDevicesValidated = false,
    this.payloadsJson,
    this.payloadsValidated = false,
    this.processorContents = const {},
    this.processorValidated = const {},
    this.processorRequirements = const {},
    this.eventFeedbackContent,
    this.eventFeedbackValidated = false,
    this.eventFeedbackRequirements,
    this.eventActionContents = const {},
    this.eventActionValidated = const {},
    this.eventActionRequirements = const {},
    this.stateMachineContent,
    this.stateMachineValidated = false,
    this.hierarchyContent,
    this.hierarchyValidated = false,
    this.sceneGlbUploaded = false,
    this.sceneConfigContent,
    this.sceneConfigValidated = false,
    this.userConfigContent,
    this.userConfigValidated = false,
  });

  Map<String, dynamic> toJson() {
    return {
      'deployer_digital_twin_name': deployerDigitalTwinName,
      'config_events_json': configEventsJson,
      'config_iot_devices_json': configIotDevicesJson,
      'config_json_validated': configJsonValidated,
      'config_events_validated': configEventsValidated,
      'config_iot_devices_validated': configIotDevicesValidated,
      'payloads_json': payloadsJson,
      'payloads_validated': payloadsValidated,
      'processor_contents': processorContents,
      'processor_validated': processorValidated,
      'processor_requirements': processorRequirements,
      'event_feedback_content': eventFeedbackContent,
      'event_feedback_validated': eventFeedbackValidated,
      'event_feedback_requirements': eventFeedbackRequirements,
      'event_action_contents': eventActionContents,
      'event_action_validated': eventActionValidated,
      'event_action_requirements': eventActionRequirements,
      'state_machine_content': stateMachineContent,
      'state_machine_validated': stateMachineValidated,
      'hierarchy_content': hierarchyContent,
      'hierarchy_validated': hierarchyValidated,
      'scene_glb_uploaded': sceneGlbUploaded,
      'scene_config_content': sceneConfigContent,
      'scene_config_validated': sceneConfigValidated,
      'user_config_content': userConfigContent,
      'user_config_validated': userConfigValidated,
    };
  }

  bool get hasMeaningfulValues => toJson().values.any((value) {
    if (value == null) return false;
    if (value is bool) return value;
    if (value is String) return value.isNotEmpty;
    if (value is Map) return value.isNotEmpty;
    return true;
  });

  @override
  List<Object?> get props => [
    deployerDigitalTwinName,
    configEventsJson,
    configIotDevicesJson,
    configJsonValidated,
    configEventsValidated,
    configIotDevicesValidated,
    payloadsJson,
    payloadsValidated,
    processorContents,
    processorValidated,
    processorRequirements,
    eventFeedbackContent,
    eventFeedbackValidated,
    eventFeedbackRequirements,
    eventActionContents,
    eventActionValidated,
    eventActionRequirements,
    stateMachineContent,
    stateMachineValidated,
    hierarchyContent,
    hierarchyValidated,
    sceneGlbUploaded,
    sceneConfigContent,
    sceneConfigValidated,
    userConfigContent,
    userConfigValidated,
  ];
}
