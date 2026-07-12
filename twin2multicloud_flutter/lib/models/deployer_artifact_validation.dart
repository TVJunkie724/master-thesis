import 'package:equatable/equatable.dart';

enum DeployerValidationBoundary { config, layer2, layer4Or5 }

enum DeployerArtifactType {
  config,
  events,
  iotDevices,
  payloads,
  processor,
  eventFeedback,
  eventAction,
  stateMachine,
  hierarchy,
  sceneConfig,
  userConfig;

  DeployerValidationBoundary get boundary => switch (this) {
    config ||
    events ||
    iotDevices ||
    payloads => DeployerValidationBoundary.config,
    processor ||
    eventFeedback ||
    eventAction ||
    stateMachine => DeployerValidationBoundary.layer2,
    hierarchy ||
    sceneConfig ||
    userConfig => DeployerValidationBoundary.layer4Or5,
  };

  String get validationType => switch (this) {
    config => 'config',
    events => 'events',
    iotDevices => 'iot',
    payloads => 'payloads',
    processor || eventFeedback || eventAction => 'function-code',
    stateMachine => 'state-machine',
    hierarchy => 'hierarchy',
    sceneConfig => 'scene-config',
    userConfig => 'user-config',
  };

  bool get requiresProvider => boundary != DeployerValidationBoundary.config;
  bool get requiresEntityId => this == processor || this == eventAction;
}

class DeployerArtifactValidationRequest extends Equatable {
  final DeployerArtifactType type;
  final String content;
  final String? provider;
  final String? entityId;

  const DeployerArtifactValidationRequest({
    required this.type,
    required this.content,
    this.provider,
    this.entityId,
  });

  String get artifactId => switch (type) {
    DeployerArtifactType.config => 'config:core',
    DeployerArtifactType.events => 'config:events',
    DeployerArtifactType.iotDevices => 'config:iot-devices',
    DeployerArtifactType.payloads => 'payloads',
    DeployerArtifactType.processor => 'processor:${entityId ?? ''}',
    DeployerArtifactType.eventFeedback => 'event-feedback',
    DeployerArtifactType.eventAction => 'event-action:${entityId ?? ''}',
    DeployerArtifactType.stateMachine => 'state-machine',
    DeployerArtifactType.hierarchy => 'hierarchy',
    DeployerArtifactType.sceneConfig => 'scene-config',
    DeployerArtifactType.userConfig => 'user-config',
  };

  DeployerValidationBoundary get boundary => type.boundary;
  String get validationType => type.validationType;

  String? get validationError {
    if (content.trim().isEmpty) return 'No content to validate';
    if (type.requiresEntityId && (entityId?.trim().isEmpty ?? true)) {
      return 'Artifact identity is missing';
    }
    if (type.requiresProvider && (provider?.trim().isEmpty ?? true)) {
      return 'Provider context is missing';
    }
    return null;
  }

  @override
  List<Object?> get props => [type, content, provider, entityId];
}

class DeployerArtifactValidationFeedback extends Equatable {
  final bool valid;
  final String message;

  const DeployerArtifactValidationFeedback({
    required this.valid,
    required this.message,
  });

  @override
  List<Object?> get props => [valid, message];
}
