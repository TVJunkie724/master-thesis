import 'package:equatable/equatable.dart';

import 'calc_params.dart';
import 'wizard_config_requests.dart';

class DeployerConfigData extends Equatable {
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

  const DeployerConfigData({
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

  factory DeployerConfigData.fromJson(Map<String, dynamic> json) {
    return DeployerConfigData(
      deployerDigitalTwinName: _string(
        json['deployer_digital_twin_name'],
        'deployer_digital_twin_name',
      ),
      configEventsJson: _string(
        json['config_events_json'],
        'config_events_json',
      ),
      configIotDevicesJson: _string(
        json['config_iot_devices_json'],
        'config_iot_devices_json',
      ),
      configJsonValidated: _bool(
        json['config_json_validated'],
        'config_json_validated',
      ),
      configEventsValidated: _bool(
        json['config_events_validated'],
        'config_events_validated',
      ),
      configIotDevicesValidated: _bool(
        json['config_iot_devices_validated'],
        'config_iot_devices_validated',
      ),
      payloadsJson: _string(json['payloads_json'], 'payloads_json'),
      payloadsValidated: _bool(
        json['payloads_validated'],
        'payloads_validated',
      ),
      processorContents: _stringMap(
        json['processor_contents'],
        'processor_contents',
      ),
      processorValidated: _boolMap(
        json['processor_validated'],
        'processor_validated',
      ),
      processorRequirements: _stringMap(
        json['processor_requirements'],
        'processor_requirements',
      ),
      eventFeedbackContent: _string(
        json['event_feedback_content'],
        'event_feedback_content',
      ),
      eventFeedbackValidated: _bool(
        json['event_feedback_validated'],
        'event_feedback_validated',
      ),
      eventFeedbackRequirements: _string(
        json['event_feedback_requirements'],
        'event_feedback_requirements',
      ),
      eventActionContents: _stringMap(
        json['event_action_contents'],
        'event_action_contents',
      ),
      eventActionValidated: _boolMap(
        json['event_action_validated'],
        'event_action_validated',
      ),
      eventActionRequirements: _stringMap(
        json['event_action_requirements'],
        'event_action_requirements',
      ),
      stateMachineContent: _string(
        json['state_machine_content'],
        'state_machine_content',
      ),
      stateMachineValidated: _bool(
        json['state_machine_validated'],
        'state_machine_validated',
      ),
      hierarchyContent: _string(json['hierarchy_content'], 'hierarchy_content'),
      hierarchyValidated: _bool(
        json['hierarchy_validated'],
        'hierarchy_validated',
      ),
      sceneGlbUploaded: _bool(json['scene_glb_uploaded'], 'scene_glb_uploaded'),
      sceneConfigContent: _string(
        json['scene_config_content'],
        'scene_config_content',
      ),
      sceneConfigValidated: _bool(
        json['scene_config_validated'],
        'scene_config_validated',
      ),
      userConfigContent: _string(
        json['user_config_content'],
        'user_config_content',
      ),
      userConfigValidated: _bool(
        json['user_config_validated'],
        'user_config_validated',
      ),
    );
  }

  DeployerConfigUpdateRequest toUpdateRequest() => DeployerConfigUpdateRequest(
    deployerDigitalTwinName: deployerDigitalTwinName,
    configEventsJson: configEventsJson,
    configIotDevicesJson: configIotDevicesJson,
    configJsonValidated: configJsonValidated,
    configEventsValidated: configEventsValidated,
    configIotDevicesValidated: configIotDevicesValidated,
    payloadsJson: payloadsJson,
    payloadsValidated: payloadsValidated,
    processorContents: processorContents,
    processorValidated: processorValidated,
    processorRequirements: processorRequirements,
    eventFeedbackContent: eventFeedbackContent,
    eventFeedbackValidated: eventFeedbackValidated,
    eventFeedbackRequirements: eventFeedbackRequirements,
    eventActionContents: eventActionContents,
    eventActionValidated: eventActionValidated,
    eventActionRequirements: eventActionRequirements,
    stateMachineContent: stateMachineContent,
    stateMachineValidated: stateMachineValidated,
    hierarchyContent: hierarchyContent,
    hierarchyValidated: hierarchyValidated,
    sceneGlbUploaded: sceneGlbUploaded,
    sceneConfigContent: sceneConfigContent,
    sceneConfigValidated: sceneConfigValidated,
    userConfigContent: userConfigContent,
    userConfigValidated: userConfigValidated,
  );

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

class DeployerConfigRequirements extends Equatable {
  final List<String> deviceIds;
  final List<String> eventActionNames;
  final bool eventFeedbackRequired;
  final bool eventActionsRequired;
  final bool stateMachineRequired;
  final bool hierarchyRequired;
  final bool sceneRequired;
  final bool userConfigRequired;

  const DeployerConfigRequirements({
    this.deviceIds = const [],
    this.eventActionNames = const [],
    this.eventFeedbackRequired = false,
    this.eventActionsRequired = false,
    this.stateMachineRequired = false,
    this.hierarchyRequired = false,
    this.sceneRequired = false,
    this.userConfigRequired = false,
  });

  factory DeployerConfigRequirements.fromContext({
    required CalcParams? calcParams,
    required String? layer4Provider,
    required String? layer5Provider,
    required List<String> deviceIds,
    required List<String> eventActionNames,
  }) {
    final l4UsesManagedAssets = _isAwsOrAzure(layer4Provider);
    return DeployerConfigRequirements(
      deviceIds: List.unmodifiable(deviceIds),
      eventActionNames: List.unmodifiable(eventActionNames),
      eventFeedbackRequired: calcParams?.returnFeedbackToDevice == true,
      eventActionsRequired: calcParams?.useEventChecking == true,
      stateMachineRequired: calcParams?.triggerNotificationWorkflow == true,
      hierarchyRequired: l4UsesManagedAssets,
      sceneRequired: calcParams?.needs3DModel == true && l4UsesManagedAssets,
      userConfigRequired: _isAwsOrAzure(layer5Provider),
    );
  }

  @override
  List<Object?> get props => [
    deviceIds,
    eventActionNames,
    eventFeedbackRequired,
    eventActionsRequired,
    stateMachineRequired,
    hierarchyRequired,
    sceneRequired,
    userConfigRequired,
  ];
}

enum DeployerArtifactSource { generated, userAuthored }

class DeployerArtifactReadiness extends Equatable {
  final String id;
  final String label;
  final DeployerArtifactSource source;
  final bool required;
  final bool hasContent;
  final bool validated;
  final String? dependency;

  const DeployerArtifactReadiness({
    required this.id,
    required this.label,
    required this.source,
    required this.required,
    required this.hasContent,
    required this.validated,
    this.dependency,
  });

  bool get ready => !required || (hasContent && validated);

  @override
  List<Object?> get props => [
    id,
    label,
    source,
    required,
    hasContent,
    validated,
    dependency,
  ];
}

enum DeployerSectionId { configuration, payloads, userLogic, digitalTwinAssets }

class DeployerSectionReadiness extends Equatable {
  final DeployerSectionId id;
  final String label;
  final List<DeployerArtifactReadiness> artifacts;

  const DeployerSectionReadiness({
    required this.id,
    required this.label,
    required this.artifacts,
  });

  bool get ready => artifacts.every((artifact) => artifact.ready);
  List<String> get missingArtifactIds => artifacts
      .where((artifact) => artifact.required && !artifact.hasContent)
      .map((artifact) => artifact.id)
      .toList(growable: false);
  List<String> get invalidArtifactIds => artifacts
      .where(
        (artifact) =>
            artifact.required && artifact.hasContent && !artifact.validated,
      )
      .map((artifact) => artifact.id)
      .toList(growable: false);

  @override
  List<Object?> get props => [id, label, artifacts];
}

class DeployerConfigReadiness extends Equatable {
  final List<DeployerSectionReadiness> sections;

  const DeployerConfigReadiness({required this.sections});

  factory DeployerConfigReadiness.fromData({
    required DeployerConfigData data,
    required DeployerConfigRequirements requirements,
  }) {
    const generated = DeployerArtifactSource.generated;
    const authored = DeployerArtifactSource.userAuthored;
    bool has(String? value) => value?.trim().isNotEmpty == true;
    DeployerArtifactReadiness artifact(
      String id,
      String label,
      DeployerArtifactSource source,
      bool required,
      bool hasContent,
      bool validated, {
      String? dependency,
    }) => DeployerArtifactReadiness(
      id: id,
      label: label,
      source: source,
      required: required,
      hasContent: hasContent,
      validated: validated,
      dependency: dependency,
    );

    return DeployerConfigReadiness(
      sections: [
        DeployerSectionReadiness(
          id: DeployerSectionId.configuration,
          label: 'Deployment Configuration',
          artifacts: [
            artifact(
              'config:core',
              'Core Configuration',
              generated,
              true,
              has(data.deployerDigitalTwinName),
              data.configJsonValidated,
            ),
            artifact(
              'config:events',
              'Event Rules',
              authored,
              true,
              has(data.configEventsJson),
              data.configEventsValidated,
            ),
            artifact(
              'config:iot-devices',
              'IoT Devices',
              authored,
              true,
              has(data.configIotDevicesJson),
              data.configIotDevicesValidated,
            ),
          ],
        ),
        DeployerSectionReadiness(
          id: DeployerSectionId.payloads,
          label: 'L1 Payloads',
          artifacts: [
            artifact(
              'payloads',
              'Payload Definitions',
              authored,
              true,
              has(data.payloadsJson),
              data.payloadsValidated,
            ),
          ],
        ),
        DeployerSectionReadiness(
          id: DeployerSectionId.userLogic,
          label: 'L2 User Logic',
          artifacts: [
            for (final deviceId in requirements.deviceIds)
              artifact(
                'processor:$deviceId',
                'Processor: $deviceId',
                authored,
                true,
                has(data.processorContents[deviceId]),
                data.processorValidated[deviceId] == true,
                dependency: 'config:iot-devices',
              ),
            artifact(
              'event-feedback',
              'Event Feedback',
              authored,
              requirements.eventFeedbackRequired,
              has(data.eventFeedbackContent),
              data.eventFeedbackValidated,
              dependency: 'config:iot-devices',
            ),
            for (final action in requirements.eventActionNames)
              artifact(
                'event-action:$action',
                'Event Action: $action',
                authored,
                requirements.eventActionsRequired,
                has(data.eventActionContents[action]),
                data.eventActionValidated[action] == true,
                dependency: 'config:events',
              ),
            artifact(
              'state-machine',
              'State Machine',
              authored,
              requirements.stateMachineRequired,
              has(data.stateMachineContent),
              data.stateMachineValidated,
              dependency: 'config:iot-devices',
            ),
          ],
        ),
        DeployerSectionReadiness(
          id: DeployerSectionId.digitalTwinAssets,
          label: 'L4/L5 Digital Twin Assets',
          artifacts: [
            artifact(
              'hierarchy',
              'Hierarchy',
              authored,
              requirements.hierarchyRequired,
              has(data.hierarchyContent),
              data.hierarchyValidated,
            ),
            artifact(
              'scene-config',
              'Scene Configuration',
              authored,
              requirements.sceneRequired,
              has(data.sceneConfigContent),
              data.sceneConfigValidated,
              dependency: 'hierarchy',
            ),
            artifact(
              'scene-glb',
              '3D Scene GLB',
              authored,
              requirements.sceneRequired,
              data.sceneGlbUploaded,
              data.sceneGlbUploaded,
              dependency: 'hierarchy',
            ),
            artifact(
              'user-config',
              'User Configuration',
              authored,
              requirements.userConfigRequired,
              has(data.userConfigContent),
              data.userConfigValidated,
            ),
          ],
        ),
      ],
    );
  }

  DeployerSectionReadiness section(DeployerSectionId id) =>
      sections.firstWhere((section) => section.id == id);

  bool get configurationReady => section(DeployerSectionId.configuration).ready;
  bool get deploymentArtifactsReady => sections
      .where((section) => section.id != DeployerSectionId.configuration)
      .every((section) => section.ready);
  bool get ready => configurationReady && deploymentArtifactsReady;

  @override
  List<Object?> get props => [sections];
}

bool _isAwsOrAzure(String? provider) {
  final normalized = provider?.trim().toUpperCase();
  return normalized == 'AWS' || normalized == 'AZURE';
}

String? _string(Object? value, String field) {
  if (value == null) return null;
  if (value is! String) {
    throw FormatException('Invalid API contract: $field must be a string.');
  }
  return value;
}

bool _bool(Object? value, String field) {
  if (value == null) return false;
  if (value is! bool) {
    throw FormatException('Invalid API contract: $field must be a boolean.');
  }
  return value;
}

Map<String, String> _stringMap(dynamic value, String field) {
  if (value == null) return const {};
  if (value is! Map) {
    throw FormatException('Invalid API contract: $field must be an object.');
  }
  return Map.unmodifiable(
    value.map((key, item) {
      if (key is! String || item is! String) {
        throw FormatException(
          'Invalid API contract: $field must contain string entries.',
        );
      }
      return MapEntry(key, item);
    }),
  );
}

Map<String, bool> _boolMap(dynamic value, String field) {
  if (value == null) return const {};
  if (value is! Map) {
    throw FormatException('Invalid API contract: $field must be an object.');
  }
  return Map.unmodifiable(
    value.map((key, item) {
      if (key is! String || item is! bool) {
        throw FormatException(
          'Invalid API contract: $field must contain boolean entries.',
        );
      }
      return MapEntry(key, item);
    }),
  );
}
