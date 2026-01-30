// lib/bloc/wizard/services/wizard_init_service.dart
// Handles wizard initialization for both create and edit modes.
// This service extracts all the initialization logic from WizardBloc
// to make it testable and reduce BLoC size.

import '../../../models/calc_params.dart';
import '../../../models/calc_result.dart';
import '../../../services/api_service.dart';
import '../../../utils/api_error_handler.dart';
import '../wizard_state.dart';
import '../helpers/helpers.dart';

/// Result of initialization operation
class WizardInitResult {
  final WizardState state;
  final bool success;

  const WizardInitResult({required this.state, required this.success});
}

/// Service for initializing wizard state.
/// Handles both create mode (fresh state) and edit mode (hydrated from backend).
class WizardInitService {
  final ApiService _api;

  WizardInitService({required ApiService api}) : _api = api;

  /// Initialize wizard for creating a new twin.
  /// Returns a fresh WizardState ready for input.
  WizardState initializeCreateMode() {
    return const WizardState(
      mode: WizardMode.create,
      status: WizardStatus.ready,
    );
  }

  /// Initialize wizard for editing an existing twin.
  /// Fetches twin data, config, and deployer config from the API,
  /// then hydrates a WizardState with all existing values.
  Future<WizardInitResult> initializeEditMode({
    required String twinId,
    required WizardState currentState,
  }) async {
    try {
      final twin = await _api.getTwin(twinId);
      final config = await _api.getTwinConfig(twinId);

      // Hydrate credentials (marked as inherited - masked from DB)
      ProviderCredentials awsCreds = const ProviderCredentials();
      ProviderCredentials azureCreds = const ProviderCredentials();
      ProviderCredentials gcpCreds = const ProviderCredentials();

      if (config['aws_configured'] == true) {
        awsCreds = ProviderCredentials(
          isValid: true,
          source: CredentialSource.inherited,
          values: _extractMaskedCredentials(config['aws']),
        );
      }
      if (config['azure_configured'] == true) {
        azureCreds = ProviderCredentials(
          isValid: true,
          source: CredentialSource.inherited,
          values: _extractMaskedCredentials(config['azure']),
        );
      }
      if (config['gcp_configured'] == true) {
        gcpCreds = ProviderCredentials(
          isValid: true,
          source: CredentialSource.inherited,
          values: _extractMaskedCredentials(config['gcp']),
        );
      }

      // Determine starting step: use persisted value, fallback to data-based detection
      int startStep = config['highest_step_reached'] as int? ?? 0;

      // Validate startStep against actual data (can't go to step without prerequisites)
      if (startStep >= 1 &&
          !(awsCreds.isValid || azureCreds.isValid || gcpCreds.isValid)) {
        startStep = 0; // Need at least one provider for Step 2
      }

      // Load optimizer result if available
      CalcResult? loadedResult;
      Map<String, dynamic>? loadedResultRaw;
      if (config['optimizer_result'] != null) {
        loadedResultRaw = {'result': config['optimizer_result']};
        loadedResult = CalcResult.fromJson(loadedResultRaw);
      } else if (startStep >= 2) {
        startStep = 1; // Can't be on Step 3 without calc result
      }

      // Load optimizer params if available
      CalcParams? loadedParams;
      if (config['optimizer_params'] != null) {
        loadedParams = CalcParams.fromJson(config['optimizer_params']);
      }

      // Load deployer config (Section 2 data) if available
      final deployerData = await _loadDeployerConfig(twinId);

      // Generate warning for unconfigured providers in loaded result
      String? warningMessage;
      if (loadedResult != null) {
        warningMessage = _generateUnconfiguredProviderWarning(
          loadedResult: loadedResult,
          awsCreds: awsCreds,
          azureCreds: azureCreds,
          gcpCreds: gcpCreds,
        );
      }

      return WizardInitResult(
        success: true,
        state: WizardState(
          mode: WizardMode.edit,
          status: WizardStatus.ready,
          currentStep: startStep,
          highestStepReached: startStep,
          twinId: twinId,
          twinName: twin['name'],
          twinState: twin['state'], // Lifecycle state: draft, deployed, etc.
          debugMode: config['debug_mode'] ?? true,
          aws: awsCreds,
          azure: azureCreds,
          gcp: gcpCreds,
          calcParams: loadedParams,
          calcResult: loadedResult,
          savedCalcResult: loadedResult, // Store for revert capability
          calcResultRaw: loadedResultRaw,
          savedCalcResultRaw: loadedResultRaw, // Store raw for revert
          // Section 2: Deployer config (hydrated from backend)
          deployerDigitalTwinName: deployerData.deployerDigitalTwinName,
          configEventsJson: deployerData.configEventsJson,
          configIotDevicesJson: deployerData.configIotDevicesJson,
          configJsonValidated: deployerData.configJsonValidated,
          configEventsValidated: deployerData.configEventsValidated,
          configIotDevicesValidated: deployerData.configIotDevicesValidated,
          // Section 3 L1 (hydrated)
          payloadsJson: deployerData.payloadsJson,
          payloadsValidated: deployerData.payloadsValidated,
          // Section 3 L2 (hydrated)
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
          // L4/L5 fields (hydrated)
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
    } catch (e) {
      return WizardInitResult(
        success: false,
        state: currentState.copyWith(
          status: WizardStatus.error,
          errorMessage:
              'Failed to load twin: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  /// Extract masked credentials from config.
  Map<String, String> _extractMaskedCredentials(dynamic config) {
    return CredentialsHelper.extractMaskedCredentials(config);
  }

  /// Generate warning message if loaded result contains providers without credentials.
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

  /// Load deployer config from the backend.
  Future<_DeployerConfigData> _loadDeployerConfig(String twinId) async {
    try {
      final deployerConfig = await _api.getDeployerConfig(twinId);
      return _DeployerConfigData(
        deployerDigitalTwinName:
            deployerConfig['deployer_digital_twin_name'] as String?,
        configEventsJson: deployerConfig['config_events_json'] as String?,
        configIotDevicesJson:
            deployerConfig['config_iot_devices_json'] as String?,
        configJsonValidated:
            deployerConfig['config_json_validated'] as bool? ?? false,
        configEventsValidated:
            deployerConfig['config_events_validated'] as bool? ?? false,
        configIotDevicesValidated:
            deployerConfig['config_iot_devices_validated'] as bool? ?? false,
        // Section 3 L1
        payloadsJson: deployerConfig['payloads_json'] as String?,
        payloadsValidated:
            deployerConfig['payloads_validated'] as bool? ?? false,
        // Section 3 L2
        processorContents: deployerConfig['processor_contents'] != null
            ? Map<String, String>.from(
                deployerConfig['processor_contents'] as Map,
              )
            : {},
        processorValidated: deployerConfig['processor_validated'] != null
            ? Map<String, bool>.from(
                deployerConfig['processor_validated'] as Map,
              )
            : {},
        processorRequirements: deployerConfig['processor_requirements'] != null
            ? Map<String, String>.from(
                deployerConfig['processor_requirements'] as Map,
              )
            : {},
        eventFeedbackContent:
            deployerConfig['event_feedback_content'] as String?,
        eventFeedbackValidated:
            deployerConfig['event_feedback_validated'] as bool? ?? false,
        eventFeedbackRequirements:
            deployerConfig['event_feedback_requirements'] as String?,
        eventActionContents: deployerConfig['event_action_contents'] != null
            ? Map<String, String>.from(
                deployerConfig['event_action_contents'] as Map,
              )
            : {},
        eventActionValidated: deployerConfig['event_action_validated'] != null
            ? Map<String, bool>.from(
                deployerConfig['event_action_validated'] as Map,
              )
            : {},
        eventActionRequirements:
            deployerConfig['event_action_requirements'] != null
            ? Map<String, String>.from(
                deployerConfig['event_action_requirements'] as Map,
              )
            : {},
        stateMachineContent: deployerConfig['state_machine_content'] as String?,
        stateMachineValidated:
            deployerConfig['state_machine_validated'] as bool? ?? false,
        // L4/L5 fields
        hierarchyContent: deployerConfig['hierarchy_content'] as String?,
        hierarchyValidated:
            deployerConfig['hierarchy_validated'] as bool? ?? false,
        sceneGlbUploaded:
            deployerConfig['scene_glb_uploaded'] as bool? ?? false,
        sceneConfigContent: deployerConfig['scene_config_content'] as String?,
        sceneConfigValidated:
            deployerConfig['scene_config_validated'] as bool? ?? false,
        userConfigContent: deployerConfig['user_config_content'] as String?,
        userConfigValidated:
            deployerConfig['user_config_validated'] as bool? ?? false,
      );
    } catch (e) {
      // No deployer config yet, that's fine - return empty data
      return const _DeployerConfigData();
    }
  }
}

/// Internal data class to hold deployer config fields.
class _DeployerConfigData {
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

  const _DeployerConfigData({
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
}
