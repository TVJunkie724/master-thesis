// lib/bloc/wizard/services/wizard_init_service.dart
// Handles wizard initialization for both create and edit modes.
// STATELESS SERVICE: receives data, returns state (no API calls)

import '../../../models/calc_params.dart';
import '../../../models/calc_result.dart';
import '../../../models/architecture_path.dart';
import '../../../models/cloud_connection.dart';
import '../../../models/deployer_config.dart';
import '../../../models/resolved_deployment_specification.dart';
import '../../../models/twin.dart';
import '../../../models/twin_config.dart';
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
  final Twin twin;
  final TwinConfigData config;
  final DeployerConfigData? deployerConfig;
  final OptimizerDeploymentRunData? deploymentRun;

  const TwinEditData({
    required this.twin,
    required this.config,
    this.deployerConfig,
    this.deploymentRun,
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
      for (final provider in CloudProvider.values)
        provider: config.provider(provider).cloudConnectionId,
    };
    final credentials = CredentialsHelper.hydrateCredentials(config);

    // Determine starting step
    int startStep = config.highestStepReached;

    // Workload configuration depends on identity, not deployment credentials.
    if (startStep >= 1 && twin.name.trim().isEmpty) {
      startStep = 0;
    }

    // Load optimizer result if available
    CalcResult? loadedResult;
    final loadedOptimization = config.optimization;
    if (loadedOptimization != null) {
      loadedResult = loadedOptimization.result;
    } else if (startStep >= 2) {
      startStep = 1;
    }

    // Load optimizer params if available
    CalcParams? loadedParams;
    loadedParams = config.optimizerParams;
    _validateDeploymentRunAgainstOptimization(data.deploymentRun, loadedResult);
    if (startStep >= 2 &&
        !ResolvedDeploymentReview.fromRun(data.deploymentRun).ready) {
      startStep = 1;
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
        twinName: twin.name,
        twinState: twin.state,
        debugMode: config.debugMode,
        aws: credentials['aws'] ?? const ProviderCredentials(),
        azure: credentials['azure'] ?? const ProviderCredentials(),
        gcp: credentials['gcp'] ?? const ProviderCredentials(),
        selectedCloudConnectionIds: selectedCloudConnectionIds,
        calcParams: loadedParams,
        savedCalcParams: loadedParams,
        calcResult: loadedResult,
        savedCalcResult: loadedResult,
        optimizationResultData: loadedOptimization,
        savedOptimizationResultData: loadedOptimization,
        deploymentRun: data.deploymentRun,
        savedDeploymentRun: data.deploymentRun,
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

  void _validateDeploymentRunAgainstOptimization(
    OptimizerDeploymentRunData? run,
    CalcResult? optimization,
  ) {
    final specification = run?.specification;
    if (specification is! ResolvedDeploymentSpecificationV1 ||
        optimization == null) {
      return;
    }
    const pathPrefixBySlot = {
      ResolvedDeploymentSlot.l1Ingestion: 'L1_',
      ResolvedDeploymentSlot.l2Processing: 'L2_',
      ResolvedDeploymentSlot.l3HotStorage: 'L3_hot_',
      ResolvedDeploymentSlot.l3CoolStorage: 'L3_cool_',
      ResolvedDeploymentSlot.l3ArchiveStorage: 'L3_archive_',
      ResolvedDeploymentSlot.l4TwinState: 'L4_',
      ResolvedDeploymentSlot.l5Visualization: 'L5_',
    };
    for (final entry in pathPrefixBySlot.entries) {
      final segment = optimization.cheapestPath.cast<String?>().firstWhere(
        (candidate) =>
            candidate?.toLowerCase().startsWith(entry.value.toLowerCase()) ==
            true,
        orElse: () => null,
      );
      final expectedProvider = segment == null
          ? null
          : ArchitecturePath.providerForSegment(segment);
      final actualProviders = specification.components
          .where((component) => component.slot == entry.key)
          .map((component) => component.provider.apiValue.toUpperCase())
          .toSet();
      if (expectedProvider == null ||
          actualProviders.length != 1 ||
          actualProviders.single != expectedProvider) {
        throw const FormatException(
          'Invalid API contract: optimizer projection and deployment specification differ.',
        );
      }
    }
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
