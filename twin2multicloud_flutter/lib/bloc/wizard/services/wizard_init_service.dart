// lib/bloc/wizard/services/wizard_init_service.dart
// Handles wizard initialization for both create and edit modes.
// STATELESS SERVICE: receives data, returns state (no API calls)

import '../../../models/calc_params.dart';
import '../../../models/calc_result.dart';
import '../wizard_state.dart';
import '../helpers/helpers.dart';

/// Result of initialization operation.
/// Simplified: error handling is done in BLoC via try/catch.
class WizardInitResult {
  final WizardState state;
  final bool success;

  const WizardInitResult._({required this.state, required this.success});

  /// Factory for successful result
  factory WizardInitResult.ok(WizardState state) =>
      WizardInitResult._(state: state, success: true);
}

/// Data class to hold fetched twin data for edit mode initialization.
/// Public for testing.
class TwinEditData {
  final Map<String, dynamic> twin;
  final Map<String, dynamic> config;
  final DeployerConfigData? deployerConfig;

  const TwinEditData({
    required this.twin,
    required this.config,
    this.deployerConfig,
  });
}

/// Data class to hold deployer config fields.
/// Public for testing.
class DeployerConfigData {
  final String? deployerDigitalTwinName;
  final String? configEventsJson;
  final String? configIotDevicesJson;
  final bool configJsonValidated;
  final bool configEventsValidated;
  final bool configIotDevicesValidated;
  // Section 3 L1
  final String? payloadsJson;
  final bool payloadsValidated;
  // Section 3 L2
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
  // L4/L5 fields
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

  /// Parse deployer config from API response
  factory DeployerConfigData.fromJson(Map<String, dynamic> json) {
    return DeployerConfigData(
      deployerDigitalTwinName: json['deployer_digital_twin_name'] as String?,
      configEventsJson: json['config_events_json'] as String?,
      configIotDevicesJson: json['config_iot_devices_json'] as String?,
      configJsonValidated: json['config_json_validated'] as bool? ?? false,
      configEventsValidated: json['config_events_validated'] as bool? ?? false,
      configIotDevicesValidated:
          json['config_iot_devices_validated'] as bool? ?? false,
      payloadsJson: json['payloads_json'] as String?,
      payloadsValidated: json['payloads_validated'] as bool? ?? false,
      processorContents: json['processor_contents'] != null
          ? Map<String, String>.from(json['processor_contents'] as Map)
          : const {},
      processorValidated: json['processor_validated'] != null
          ? Map<String, bool>.from(json['processor_validated'] as Map)
          : const {},
      processorRequirements: json['processor_requirements'] != null
          ? Map<String, String>.from(json['processor_requirements'] as Map)
          : const {},
      eventFeedbackContent: json['event_feedback_content'] as String?,
      eventFeedbackValidated:
          json['event_feedback_validated'] as bool? ?? false,
      eventFeedbackRequirements: json['event_feedback_requirements'] as String?,
      eventActionContents: json['event_action_contents'] != null
          ? Map<String, String>.from(json['event_action_contents'] as Map)
          : const {},
      eventActionValidated: json['event_action_validated'] != null
          ? Map<String, bool>.from(json['event_action_validated'] as Map)
          : const {},
      eventActionRequirements: json['event_action_requirements'] != null
          ? Map<String, String>.from(json['event_action_requirements'] as Map)
          : const {},
      stateMachineContent: json['state_machine_content'] as String?,
      stateMachineValidated: json['state_machine_validated'] as bool? ?? false,
      hierarchyContent: json['hierarchy_content'] as String?,
      hierarchyValidated: json['hierarchy_validated'] as bool? ?? false,
      sceneGlbUploaded: json['scene_glb_uploaded'] as bool? ?? false,
      sceneConfigContent: json['scene_config_content'] as String?,
      sceneConfigValidated: json['scene_config_validated'] as bool? ?? false,
      userConfigContent: json['user_config_content'] as String?,
      userConfigValidated: json['user_config_validated'] as bool? ?? false,
    );
  }
}

/// STATELESS service for initializing wizard state.
/// Receives pre-fetched data, returns new state (no API calls).
class WizardInitService {
  /// Initialize wizard for creating a new twin.
  /// Returns a fresh WizardState ready for input.
  WizardState initializeCreateMode() {
    return const WizardState(
      mode: WizardMode.create,
      status: WizardStatus.ready,
    );
  }

  /// Initialize wizard for editing an existing twin.
  /// STATELESS: receives pre-fetched data, returns state.
  WizardInitResult initializeEditMode({
    required String twinId,
    required TwinEditData data,
  }) {
    final twin = data.twin;
    final config = data.config;
    final deployerData = data.deployerConfig ?? const DeployerConfigData();

    // Hydrate credentials (marked as inherited - masked from DB)
    ProviderCredentials awsCreds = const ProviderCredentials();
    ProviderCredentials azureCreds = const ProviderCredentials();
    ProviderCredentials gcpCreds = const ProviderCredentials();

    if (config['aws_configured'] == true) {
      awsCreds = ProviderCredentials(
        isValid: true,
        source: CredentialSource.inherited,
        values: CredentialsHelper.extractCredentialsFromFlatConfig(config, 'aws'),
      );
    }
    if (config['azure_configured'] == true) {
      azureCreds = ProviderCredentials(
        isValid: true,
        source: CredentialSource.inherited,
        values: CredentialsHelper.extractCredentialsFromFlatConfig(config, 'azure'),
      );
    }
    if (config['gcp_configured'] == true) {
      gcpCreds = ProviderCredentials(
        isValid: true,
        source: CredentialSource.inherited,
        values: CredentialsHelper.extractCredentialsFromFlatConfig(config, 'gcp'),
      );
    }

    // Determine starting step
    int startStep = config['highest_step_reached'] as int? ?? 0;

    // Validate startStep against actual data
    if (startStep >= 1 &&
        !(awsCreds.isValid || azureCreds.isValid || gcpCreds.isValid)) {
      startStep = 0;
    }

    // Load optimizer result if available
    CalcResult? loadedResult;
    Map<String, dynamic>? loadedResultRaw;
    if (config['optimizer_result'] != null) {
      loadedResultRaw = {'result': config['optimizer_result']};
      loadedResult = CalcResult.fromJson(loadedResultRaw);
    } else if (startStep >= 2) {
      startStep = 1;
    }

    // Load optimizer params if available
    CalcParams? loadedParams;
    if (config['optimizer_params'] != null) {
      loadedParams = CalcParams.fromJson(config['optimizer_params']);
    }

    // Generate warning for unconfigured providers
    String? warningMessage;
    if (loadedResult != null) {
      warningMessage = _generateUnconfiguredProviderWarning(
        loadedResult: loadedResult,
        awsCreds: awsCreds,
        azureCreds: azureCreds,
        gcpCreds: gcpCreds,
      );
    }

    return WizardInitResult.ok(
      WizardState(
        mode: WizardMode.edit,
        status: WizardStatus.ready,
        currentStep: startStep,
        highestStepReached: startStep,
        twinId: twinId,
        twinName: twin['name'],
        twinState: twin['state'],
        debugMode: config['debug_mode'] ?? true,
        aws: awsCreds,
        azure: azureCreds,
        gcp: gcpCreds,
        calcParams: loadedParams,
        calcResult: loadedResult,
        savedCalcResult: loadedResult,
        calcResultRaw: loadedResultRaw,
        savedCalcResultRaw: loadedResultRaw,
        // Deployer config
        deployerDigitalTwinName: deployerData.deployerDigitalTwinName,
        configEventsJson: deployerData.configEventsJson,
        configIotDevicesJson: deployerData.configIotDevicesJson,
        configJsonValidated: deployerData.configJsonValidated,
        configEventsValidated: deployerData.configEventsValidated,
        configIotDevicesValidated: deployerData.configIotDevicesValidated,
        payloadsJson: deployerData.payloadsJson,
        payloadsValidated: deployerData.payloadsValidated,
        processorContents: deployerData.processorContents,
        processorValidated: deployerData.processorValidated,
        processorRequirements: deployerData.processorRequirements,
        eventFeedbackContent: deployerData.eventFeedbackContent,
        eventFeedbackValidated: deployerData.eventFeedbackValidated,
        eventFeedbackRequirements: deployerData.eventFeedbackRequirements,
        eventActionContents: deployerData.eventActionContents,
        eventActionValidated: deployerData.eventActionValidated,
        eventActionRequirements: deployerData.eventActionRequirements,
        stateMachineContent: deployerData.stateMachineContent,
        stateMachineValidated: deployerData.stateMachineValidated,
        hierarchyContent: deployerData.hierarchyContent,
        hierarchyValidated: deployerData.hierarchyValidated,
        sceneGlbUploaded: deployerData.sceneGlbUploaded,
        sceneConfigContent: deployerData.sceneConfigContent,
        sceneConfigValidated: deployerData.sceneConfigValidated,
        userConfigContent: deployerData.userConfigContent,
        userConfigValidated: deployerData.userConfigValidated,
        warningMessage: warningMessage,
      ),
    );
  }

  /// Generate warning for unconfigured providers in optimal path.
  String? _generateUnconfiguredProviderWarning({
    required CalcResult loadedResult,
    required ProviderCredentials awsCreds,
    required ProviderCredentials azureCreds,
    required ProviderCredentials gcpCreds,
  }) {
    final configuredProviders = <String>{};
    if (awsCreds.isValid) configuredProviders.add('AWS');
    if (azureCreds.isValid) configuredProviders.add('AZURE');
    if (gcpCreds.isValid) configuredProviders.add('GCP');

    final resultProviders = <String>{};
    for (final segment in loadedResult.cheapestPath) {
      final parts = segment.split('_');
      if (parts.length >= 3 && segment.startsWith('L3')) {
        resultProviders.add(parts[2].toUpperCase());
      } else if (parts.length >= 2) {
        resultProviders.add(parts[1].toUpperCase());
      }
    }
    final unconfigured = resultProviders.difference(configuredProviders);
    if (unconfigured.isNotEmpty) {
      return 'Unconfigured provider(s) in optimal path: ${unconfigured.join(", ")}. Return to Step 1 to add credentials.';
    }
    return null;
  }
}
