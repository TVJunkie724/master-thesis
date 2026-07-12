// lib/bloc/wizard/services/wizard_init_service.dart
// Handles wizard initialization for both create and edit modes.
// STATELESS SERVICE: receives data, returns state (no API calls)

import '../../../models/calc_params.dart';
import '../../../models/calc_result.dart';
import '../../../models/architecture_path.dart';
import '../../../models/cloud_connection.dart';
import '../../../models/deployer_config.dart';
import '../helpers/credentials_helper.dart';
import '../wizard_state.dart';

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

    final selectedCloudConnectionIds = <CloudProvider, String?>{
      CloudProvider.aws: config['aws_cloud_connection_id'] as String?,
      CloudProvider.azure: config['azure_cloud_connection_id'] as String?,
      CloudProvider.gcp: config['gcp_cloud_connection_id'] as String?,
    };
    final credentials = CredentialsHelper.hydrateCredentials(config);

    // Determine starting step
    int startStep = config['highest_step_reached'] as int? ?? 0;

    // Workload configuration depends on identity, not deployment credentials.
    if (startStep >= 1 && (twin['name']?.toString().trim().isEmpty ?? true)) {
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
        selectedCloudConnectionIds: selectedCloudConnectionIds,
        credentials: credentials,
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
        aws: credentials['aws'] ?? const ProviderCredentials(),
        azure: credentials['azure'] ?? const ProviderCredentials(),
        gcp: credentials['gcp'] ?? const ProviderCredentials(),
        selectedCloudConnectionIds: selectedCloudConnectionIds,
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
    required Map<CloudProvider, String?> selectedCloudConnectionIds,
    required Map<String, ProviderCredentials> credentials,
  }) {
    final configuredProviders = _configuredProviderNames(
      selectedCloudConnectionIds,
      credentials,
    );

    final resultProviders = <String>{};
    for (final segment in loadedResult.cheapestPath) {
      final provider = ArchitecturePath.providerForSegment(segment);
      if (provider != null) resultProviders.add(provider);
    }
    final unconfigured = resultProviders.difference(configuredProviders);
    if (unconfigured.isNotEmpty) {
      return 'Deployment access is missing for: ${unconfigured.join(", ")}. Open Cloud access to bind the required connections.';
    }
    return null;
  }

  Set<String> _configuredProviderNames(
    Map<CloudProvider, String?> selectedCloudConnectionIds,
    Map<String, ProviderCredentials> credentials,
  ) {
    return {
      if (selectedCloudConnectionIds[CloudProvider.aws] != null ||
          (credentials['aws']?.isValid ?? false))
        'AWS',
      if (selectedCloudConnectionIds[CloudProvider.azure] != null ||
          (credentials['azure']?.isValid ?? false))
        'AZURE',
      if (selectedCloudConnectionIds[CloudProvider.gcp] != null ||
          (credentials['gcp']?.isValid ?? false))
        'GCP',
    };
  }
}
