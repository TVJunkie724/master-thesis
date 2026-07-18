// lib/bloc/wizard/wizard_state.dart
// State for the Wizard BLoC state machine

import 'dart:convert';
import 'package:equatable/equatable.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';
import '../../models/architecture_path.dart';
import '../../models/cloud_connection.dart';
import '../../models/deployer_artifact_validation.dart';
import '../../models/deployer_config.dart';
import '../../models/optimizer_config.dart';
import '../../models/pricing_health.dart';
import '../../models/provider_capability.dart';
import '../../models/resolved_deployment_specification.dart';
import '../../utils/twin_state_utils.dart';

// ============================================================
// ENUMS
// ============================================================

/// Wizard mode - creating new twin or editing existing
enum WizardMode { create, edit }

/// Overall wizard status
enum WizardStatus { initial, loading, ready, saving, error }

enum SceneGlbCommandPhase { idle, uploading, deleting }

/// Source of credential data
enum CredentialSource {
  /// No credentials configured
  none,

  /// Credentials inherited from database (masked, should not be sent on update)
  inherited,

  /// Credentials newly entered by user (should be sent on update)
  newlyEntered,

  /// Credentials were cleared (should be deleted from database on save)
  cleared,
}

// ============================================================
// HELPER CLASSES
// ============================================================

/// Credentials for a single cloud provider
class ProviderCredentials extends Equatable {
  final Map<String, String> values;
  final bool isValid;
  final CredentialSource source;

  const ProviderCredentials({
    this.values = const {},
    this.isValid = false,
    this.source = CredentialSource.none,
  });

  ProviderCredentials copyWith({
    Map<String, String>? values,
    bool? isValid,
    CredentialSource? source,
  }) {
    return ProviderCredentials(
      values: values ?? this.values,
      isValid: isValid ?? this.isValid,
      source: source ?? this.source,
    );
  }

  @override
  List<Object?> get props => [values, isValid, source];
}

class SceneGlbCommandState extends Equatable {
  final SceneGlbCommandPhase phase;
  final String? message;

  const SceneGlbCommandState({
    this.phase = SceneGlbCommandPhase.idle,
    this.message,
  });

  bool get isBusy => phase != SceneGlbCommandPhase.idle;

  @override
  List<Object?> get props => [phase, message];
}

// ============================================================
// MAIN STATE CLASS
// ============================================================

/// Immutable state for the wizard BLoC
class WizardState extends Equatable {
  static const requiredPricingProviders = {'aws', 'azure', 'gcp'};
  // === Mode & Navigation ===
  final WizardMode mode;
  final int currentStep; // 0, 1, 2
  final int highestStepReached; // For step indicator gating
  final WizardStatus status;
  final String? twinState; // Lifecycle state: draft, deployed, etc.

  // === Transient UI (cleared on step change) ===
  final String? errorMessage;
  final String? successMessage;
  final String? warningMessage;
  final bool isCalculating;

  // === Persistent Data: Step 1 ===
  final String? twinId;
  final String? twinName;
  final bool debugMode;
  final ProviderCredentials aws;
  final ProviderCredentials azure;
  final ProviderCredentials gcp;
  final String? gcpServiceAccountJson;
  final Map<CloudProvider, List<CloudConnection>> cloudConnections;
  final Map<CloudProvider, String?> selectedCloudConnectionIds;
  final Map<CloudProvider, bool> cloudConnectionLoading;
  final Map<CloudProvider, String?> cloudConnectionErrors;
  final Map<CloudProvider, CloudConnectionValidationResult?>
  cloudConnectionValidation;

  // === Persistent Data: Step 2 ===
  final CalcParams? calcParams;
  final CalcParams? savedCalcParams;
  final bool isCalcFormValid; // Whether the calculation form passes validation
  final CalcResult? calcResult;
  final CalcResult? savedCalcResult; // Last saved result from DB (for revert)
  final OptimizationResultData? optimizationResultData;
  final OptimizationResultData? savedOptimizationResultData;
  final OptimizerDeploymentRunData? deploymentRun;
  final OptimizerDeploymentRunData? savedDeploymentRun;
  final bool isSelectingDeploymentRun;
  final String? deploymentRunSelectionError;
  final PricingHealthResponse? pricingHealth;
  final bool isPricingHealthLoading;
  final String? pricingHealthError;
  final PlatformProviderCapabilities? providerCapabilities;
  final bool providerCapabilitiesLoading;
  final String? providerCapabilitiesError;

  // === Persistent Data: Step 3 Section 2 ===
  final String?
  deployerDigitalTwinName; // config.json digital_twin_name (separate from Step 1 name)
  final String? configEventsJson; // config_events.json content
  final String? configIotDevicesJson; // config_iot_devices.json content
  final bool configJsonValidated; // config.json validation state
  final bool configEventsValidated; // Validation state (gates save)
  final bool configIotDevicesValidated; // Validation state (gates save)
  final Set<String> validatingArtifactIds;
  final Map<String, DeployerArtifactValidationFeedback>
  artifactValidationFeedback;

  // === Persistent Data: Step 3 Section 3 (L1) ===
  final String? payloadsJson; // L1: payloads.json content
  final bool payloadsValidated; // L1: validation state

  // === Persistent Data: Step 3 Section 3 (L2) ===
  final Map<String, String>
  processorContents; // device_id -> process.py content
  final Map<String, bool> processorValidated; // device_id -> validation state
  final Map<String, String>
  processorRequirements; // device_id -> requirements.txt content
  final String? eventFeedbackContent; // event-feedback/process.py
  final bool eventFeedbackValidated;
  final String? eventFeedbackRequirements; // requirements.txt content
  final Map<String, String> eventActionContents; // functionName -> code content
  final Map<String, bool>
  eventActionValidated; // functionName -> validation state
  final Map<String, String>
  eventActionRequirements; // functionName -> requirements.txt
  final String? stateMachineContent; // AWS/Azure/GCP workflow JSON/YAML
  final bool stateMachineValidated;

  // === Persistent Data: Step 3 Section 2 (L4 Hierarchy) ===
  final String? hierarchyContent; // aws_hierarchy.json or azure_hierarchy.json
  final bool hierarchyValidated;

  // === Persistent Data: Step 3 Section 3 (L4 Scene) ===
  final bool sceneGlbUploaded; // True if GLB file exists on server
  final SceneGlbCommandState sceneGlbCommand;
  final String? sceneConfigContent; // scene.json or 3DScenesConfiguration.json
  final bool sceneConfigValidated;

  // === Persistent Data: Step 3 Section 3 (L4/L5 User Config) ===
  final String? userConfigContent; // config_user.json content
  final bool userConfigValidated;

  // === Zip Upload State ===
  final bool zipUploadInProgress; // True during upload/extraction
  final bool
  forceCollapseSections; // Triggers section collapse after zip success

  // === State Tracking ===
  final bool hasUnsavedChanges;
  final bool step3Invalidated; // True when new calc invalidates Section 3 data

  const WizardState({
    this.mode = WizardMode.create,
    this.currentStep = 0,
    this.highestStepReached = 0,
    this.status = WizardStatus.initial,
    this.twinState,
    this.errorMessage,
    this.successMessage,
    this.warningMessage,
    this.isCalculating = false,
    this.twinId,
    this.twinName,
    this.debugMode = true,
    this.aws = const ProviderCredentials(),
    this.azure = const ProviderCredentials(),
    this.gcp = const ProviderCredentials(),
    this.gcpServiceAccountJson,
    this.cloudConnections = const {},
    this.selectedCloudConnectionIds = const {},
    this.cloudConnectionLoading = const {},
    this.cloudConnectionErrors = const {},
    this.cloudConnectionValidation = const {},
    this.calcParams,
    this.savedCalcParams,
    this.isCalcFormValid = true, // Default to valid
    this.calcResult,
    this.savedCalcResult,
    this.optimizationResultData,
    this.savedOptimizationResultData,
    this.deploymentRun,
    this.savedDeploymentRun,
    this.isSelectingDeploymentRun = false,
    this.deploymentRunSelectionError,
    this.pricingHealth,
    this.isPricingHealthLoading = false,
    this.pricingHealthError,
    this.providerCapabilities,
    this.providerCapabilitiesLoading = false,
    this.providerCapabilitiesError,
    this.deployerDigitalTwinName,
    this.configEventsJson,
    this.configIotDevicesJson,
    this.configJsonValidated = false,
    this.configEventsValidated = false,
    this.configIotDevicesValidated = false,
    this.validatingArtifactIds = const {},
    this.artifactValidationFeedback = const {},
    this.payloadsJson,
    this.payloadsValidated = false,
    // L2 fields
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
    // L4/L5 fields
    this.hierarchyContent,
    this.hierarchyValidated = false,
    this.sceneGlbUploaded = false,
    this.sceneGlbCommand = const SceneGlbCommandState(),
    this.sceneConfigContent,
    this.sceneConfigValidated = false,
    this.userConfigContent,
    this.userConfigValidated = false,
    // Zip upload state
    this.zipUploadInProgress = false,
    this.forceCollapseSections = false,
    this.hasUnsavedChanges = false,
    this.step3Invalidated = false,
  });

  // ============================================================
  // DERIVED GETTERS
  // ============================================================

  /// Can modifications (save draft, finish config) be made?
  /// Returns false for deployed/deploying/destroying twins.
  bool get canModify => TwinStateUtils.canEdit(twinState);

  /// Legacy persistence gate for entering workload configuration.
  bool get canProceedToStep2 => twinName?.trim().isNotEmpty == true;

  /// Can proceed from Step 2 to Step 3?
  bool get canProceedToStep3 =>
      calcResult != null &&
      !isCalculating &&
      !isSelectingDeploymentRun &&
      deploymentReview.ready;

  ResolvedDeploymentReview get deploymentReview =>
      ResolvedDeploymentReview.fromRun(
        deploymentRun,
        isSelecting: isSelectingDeploymentRun,
        selectionFailed: deploymentRunSelectionError != null,
      );

  bool isArtifactValidating(String artifactId) =>
      validatingArtifactIds.contains(artifactId);

  DeployerArtifactValidationFeedback? artifactFeedback(String artifactId) =>
      artifactValidationFeedback[artifactId];

  Map<String, DeployerArtifactValidationFeedback> feedbackWithout(
    String artifactId,
  ) => Map.unmodifiable(
    Map<String, DeployerArtifactValidationFeedback>.from(
      artifactValidationFeedback,
    )..remove(artifactId),
  );

  bool get pricingCanCalculate {
    if (isPricingHealthLoading || pricingHealthError != null) return false;
    final health = pricingHealth;
    if (health?.schemaVersion != PricingHealthResponse.supportedSchemaVersion) {
      return false;
    }
    final providers = health?.providers;
    if (providers == null) return false;
    return requiredPricingProviders.every(
      (provider) => providers[provider]?.canCalculate == true,
    );
  }

  List<String> get pricingBlockingProviders => requiredPricingProviders
      .where(
        (provider) => pricingHealth?.providers[provider]?.canCalculate != true,
      )
      .toList(growable: false);

  bool get canRequestCalculation =>
      calcParams != null &&
      isCalcFormValid &&
      !isCalculating &&
      !isSelectingDeploymentRun &&
      pricingCanCalculate;

  PlatformLayerCapability? providerCapability(String? provider, String layer) {
    if (provider == null || providerCapabilitiesError != null) return null;
    try {
      return providerCapabilities?.capability(provider, layer);
    } on StateError {
      return null;
    }
  }

  bool isLayerSelectable(String? provider, String layer) =>
      providerCapability(provider, layer)?.selectable == true;

  /// Set of configured provider names (uppercase)
  Set<String> get configuredProviders => {
    if (selectedCloudConnectionIds[CloudProvider.aws] != null || aws.isValid)
      'AWS',
    if (selectedCloudConnectionIds[CloudProvider.azure] != null ||
        azure.isValid)
      'AZURE',
    if (selectedCloudConnectionIds[CloudProvider.gcp] != null || gcp.isValid)
      'GCP',
  };

  /// Set of required provider names (from optimizer result) that are NOT configured
  Set<String> get unconfiguredProviders {
    final required = layerProviders.values.toSet();
    return required.difference(configuredProviders);
  }

  /// Is Section 2 validated? (gates save)
  bool get isSection2Valid {
    final assets = deployerReadiness.section(
      DeployerSectionId.digitalTwinAssets,
    );
    final hierarchy = assets.artifacts.firstWhere(
      (artifact) => artifact.id == 'hierarchy',
    );
    return deployerReadiness.configurationReady && hierarchy.ready;
  }

  /// Is Section 3 validated? (all required L1-L5 fields complete)
  bool get isSection3Valid => deployerReadiness.deploymentArtifactsReady;

  bool get isConfigurationReadyForFinish =>
      twinName?.trim().isNotEmpty == true &&
      calcResult != null &&
      deploymentReview.ready &&
      unconfiguredProviders.isEmpty &&
      deployerReadiness.ready &&
      !step3Invalidated;

  DeployerConfigData get deployerConfigData => DeployerConfigData(
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

  DeployerConfigRequirements get deployerRequirements =>
      DeployerConfigRequirements.fromContext(
        calcParams: calcParams,
        layer4Provider: layer4Provider,
        layer5Provider: layer5Provider,
        deviceIds: deviceIds,
        eventActionNames: eventActionFunctionNames,
      );

  DeployerConfigReadiness get deployerReadiness =>
      DeployerConfigReadiness.fromData(
        data: deployerConfigData,
        requirements: deployerRequirements,
      );

  // ============================================================
  // L2 DERIVED GETTERS
  // ============================================================

  /// Get device IDs from validated config_iot_devices.json
  /// Handles both array format [{id:...}] and object format {devices:[{device_id:...}]}
  List<String> get deviceIds {
    if (!configIotDevicesValidated || configIotDevicesJson == null) return [];
    try {
      final data = jsonDecode(configIotDevicesJson!);
      final List<dynamic> devices;
      if (data is List) {
        devices = data; // Direct array format: [{id:...}, ...]
      } else if (data is Map && data['devices'] is List) {
        devices = data['devices']; // Wrapped format: {devices: [...]}
      } else {
        return [];
      }
      return devices
          .map((d) => (d['id'] ?? d['device_id'])?.toString() ?? '')
          .where((id) => id.isNotEmpty)
          .toList();
    } catch (_) {
      return [];
    }
  }

  /// Get event action function names from validated config_events.json
  /// Handles both singular 'action' and plural 'actions' formats
  List<String> get eventActionFunctionNames {
    if (!configEventsValidated || configEventsJson == null) return [];
    if (calcParams?.useEventChecking != true) return [];
    try {
      final data = jsonDecode(configEventsJson!);
      final List<dynamic> events;
      if (data is List) {
        events = data; // Direct array format
      } else if (data is Map && data['events'] is List) {
        events = data['events']; // Wrapped format
      } else {
        return [];
      }
      final names = <String>{};
      for (final event in events) {
        // Handle singular 'action' (from example format)
        final action = event['action'];
        if (action is Map) {
          final funcName = action['functionName']?.toString();
          if (funcName != null && funcName.isNotEmpty) names.add(funcName);
        }
        // Handle plural 'actions' (alternative format)
        final actions = event['actions'];
        if (actions is List) {
          for (final a in actions) {
            final funcName = a['functionName']?.toString();
            if (funcName != null && funcName.isNotEmpty) names.add(funcName);
          }
        }
      }
      return names.toList();
    } catch (_) {
      return [];
    }
  }

  /// Get layer providers from calculation result (L1-L5)
  /// Parses cheapestPath format: ['L1_AWS', 'L2_Azure', 'L3_hot_GCP', ...]
  Map<String, String> get layerProviders {
    final path = calcResult?.cheapestPath;
    if (path == null || path.isEmpty) return {};
    return ArchitecturePath.layerProviders(path);
  }

  /// Get the L2 provider from calculation result
  String? get layer2Provider => layerProviders['L2'];

  /// Get the L4 provider from calculation result
  String? get layer4Provider => layerProviders['L4'];

  /// Get the L5 provider from calculation result
  String? get layer5Provider => layerProviders['L5'];

  /// Get state machine filename based on L2 provider
  String? get stateMachineFilename {
    final l2 = layer2Provider?.toLowerCase();
    if (l2 == null) return null;
    switch (l2) {
      case 'aws':
        return 'state_machines/aws_step_function.json';
      case 'azure':
        return 'state_machines/azure_logic_app.json';
      case 'gcp':
        return 'state_machines/google_cloud_workflow.yaml';
      default:
        return null;
    }
  }

  /// Should show feedback function input?
  bool get shouldShowFeedbackFunction =>
      configIotDevicesValidated &&
      (calcParams?.returnFeedbackToDevice ?? false);

  /// Should show state machine input?
  bool get shouldShowStateMachine =>
      configIotDevicesValidated &&
      (calcParams?.triggerNotificationWorkflow ?? false);

  /// Computed: true if any Section 3 field has content (L1 + L2)
  bool get hasSection3Data =>
      (payloadsJson?.isNotEmpty ?? false) ||
      processorContents.isNotEmpty ||
      (eventFeedbackContent?.isNotEmpty ?? false) ||
      eventActionContents.isNotEmpty ||
      (stateMachineContent?.isNotEmpty ?? false);

  // ============================================================
  // COPY WITH
  // ============================================================

  WizardState copyWith({
    WizardMode? mode,
    int? currentStep,
    int? highestStepReached,
    WizardStatus? status,
    String? twinState,
    String? errorMessage,
    String? successMessage,
    String? warningMessage,
    bool? isCalculating,
    String? twinId,
    String? twinName,
    bool? debugMode,
    ProviderCredentials? aws,
    ProviderCredentials? azure,
    ProviderCredentials? gcp,
    String? gcpServiceAccountJson,
    Map<CloudProvider, List<CloudConnection>>? cloudConnections,
    Map<CloudProvider, String?>? selectedCloudConnectionIds,
    Map<CloudProvider, bool>? cloudConnectionLoading,
    Map<CloudProvider, String?>? cloudConnectionErrors,
    Map<CloudProvider, CloudConnectionValidationResult?>?
    cloudConnectionValidation,
    CalcParams? calcParams,
    CalcParams? savedCalcParams,
    bool? isCalcFormValid,
    CalcResult? calcResult,
    CalcResult? savedCalcResult,
    OptimizationResultData? optimizationResultData,
    OptimizationResultData? savedOptimizationResultData,
    OptimizerDeploymentRunData? deploymentRun,
    OptimizerDeploymentRunData? savedDeploymentRun,
    bool? isSelectingDeploymentRun,
    String? deploymentRunSelectionError,
    PricingHealthResponse? pricingHealth,
    bool? isPricingHealthLoading,
    String? pricingHealthError,
    bool clearPricingHealthError = false,
    PlatformProviderCapabilities? providerCapabilities,
    bool? providerCapabilitiesLoading,
    String? providerCapabilitiesError,
    bool clearProviderCapabilitiesError = false,
    String? deployerDigitalTwinName,
    String? configEventsJson,
    String? configIotDevicesJson,
    bool? configJsonValidated,
    bool? configEventsValidated,
    bool? configIotDevicesValidated,
    Set<String>? validatingArtifactIds,
    Map<String, DeployerArtifactValidationFeedback>? artifactValidationFeedback,
    String? payloadsJson,
    bool? payloadsValidated,
    // L2 fields
    Map<String, String>? processorContents,
    Map<String, bool>? processorValidated,
    Map<String, String>? processorRequirements,
    String? eventFeedbackContent,
    bool? eventFeedbackValidated,
    String? eventFeedbackRequirements,
    Map<String, String>? eventActionContents,
    Map<String, bool>? eventActionValidated,
    Map<String, String>? eventActionRequirements,
    String? stateMachineContent,
    bool? stateMachineValidated,
    // L4/L5 fields
    String? hierarchyContent,
    bool? hierarchyValidated,
    bool? sceneGlbUploaded,
    SceneGlbCommandState? sceneGlbCommand,
    String? sceneConfigContent,
    bool? sceneConfigValidated,
    String? userConfigContent,
    bool? userConfigValidated,
    bool? hasUnsavedChanges,
    bool? step3Invalidated,
    // Special flags to explicitly clear nullable fields
    bool clearError = false,
    bool clearSuccess = false,
    bool clearWarning = false,
    bool clearCalcResult = false,
    bool clearOptimizationResultData = false,
    bool clearDeploymentRun = false,
    bool clearSavedDeploymentRun = false,
    bool clearDeploymentRunSelectionError = false,
    // L4 content clear flags
    bool clearHierarchyContent = false,
    bool clearSceneConfigContent = false,
    bool clearUserConfigContent = false,
    // Zip upload fields
    bool? zipUploadInProgress,
    bool? forceCollapseSections,
  }) {
    return WizardState(
      mode: mode ?? this.mode,
      currentStep: currentStep ?? this.currentStep,
      highestStepReached: highestStepReached ?? this.highestStepReached,
      status: status ?? this.status,
      twinState: twinState ?? this.twinState,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      successMessage: clearSuccess
          ? null
          : (successMessage ?? this.successMessage),
      warningMessage: clearWarning
          ? null
          : (warningMessage ?? this.warningMessage),
      isCalculating: isCalculating ?? this.isCalculating,
      twinId: twinId ?? this.twinId,
      twinName: twinName ?? this.twinName,
      debugMode: debugMode ?? this.debugMode,
      aws: aws ?? this.aws,
      azure: azure ?? this.azure,
      gcp: gcp ?? this.gcp,
      gcpServiceAccountJson:
          gcpServiceAccountJson ?? this.gcpServiceAccountJson,
      cloudConnections: cloudConnections ?? this.cloudConnections,
      selectedCloudConnectionIds:
          selectedCloudConnectionIds ?? this.selectedCloudConnectionIds,
      cloudConnectionLoading:
          cloudConnectionLoading ?? this.cloudConnectionLoading,
      cloudConnectionErrors:
          cloudConnectionErrors ?? this.cloudConnectionErrors,
      cloudConnectionValidation:
          cloudConnectionValidation ?? this.cloudConnectionValidation,
      calcParams: calcParams ?? this.calcParams,
      savedCalcParams: savedCalcParams ?? this.savedCalcParams,
      isCalcFormValid: isCalcFormValid ?? this.isCalcFormValid,
      calcResult: clearCalcResult ? null : (calcResult ?? this.calcResult),
      savedCalcResult: savedCalcResult ?? this.savedCalcResult,
      optimizationResultData: clearOptimizationResultData
          ? null
          : (optimizationResultData ?? this.optimizationResultData),
      savedOptimizationResultData:
          savedOptimizationResultData ?? this.savedOptimizationResultData,
      deploymentRun: clearDeploymentRun
          ? null
          : (deploymentRun ?? this.deploymentRun),
      savedDeploymentRun: clearSavedDeploymentRun
          ? null
          : (savedDeploymentRun ?? this.savedDeploymentRun),
      isSelectingDeploymentRun:
          isSelectingDeploymentRun ?? this.isSelectingDeploymentRun,
      deploymentRunSelectionError: clearDeploymentRunSelectionError
          ? null
          : (deploymentRunSelectionError ?? this.deploymentRunSelectionError),
      pricingHealth: pricingHealth ?? this.pricingHealth,
      isPricingHealthLoading:
          isPricingHealthLoading ?? this.isPricingHealthLoading,
      pricingHealthError: clearPricingHealthError
          ? null
          : (pricingHealthError ?? this.pricingHealthError),
      providerCapabilities: providerCapabilities ?? this.providerCapabilities,
      providerCapabilitiesLoading:
          providerCapabilitiesLoading ?? this.providerCapabilitiesLoading,
      providerCapabilitiesError: clearProviderCapabilitiesError
          ? null
          : (providerCapabilitiesError ?? this.providerCapabilitiesError),
      deployerDigitalTwinName:
          deployerDigitalTwinName ?? this.deployerDigitalTwinName,
      configEventsJson: configEventsJson ?? this.configEventsJson,
      configIotDevicesJson: configIotDevicesJson ?? this.configIotDevicesJson,
      configJsonValidated: configJsonValidated ?? this.configJsonValidated,
      configEventsValidated:
          configEventsValidated ?? this.configEventsValidated,
      configIotDevicesValidated:
          configIotDevicesValidated ?? this.configIotDevicesValidated,
      validatingArtifactIds:
          validatingArtifactIds ?? this.validatingArtifactIds,
      artifactValidationFeedback:
          artifactValidationFeedback ?? this.artifactValidationFeedback,
      payloadsJson: payloadsJson ?? this.payloadsJson,
      payloadsValidated: payloadsValidated ?? this.payloadsValidated,
      // L2 fields
      processorContents: processorContents ?? this.processorContents,
      processorValidated: processorValidated ?? this.processorValidated,
      processorRequirements:
          processorRequirements ?? this.processorRequirements,
      eventFeedbackContent: eventFeedbackContent ?? this.eventFeedbackContent,
      eventFeedbackValidated:
          eventFeedbackValidated ?? this.eventFeedbackValidated,
      eventFeedbackRequirements:
          eventFeedbackRequirements ?? this.eventFeedbackRequirements,
      eventActionContents: eventActionContents ?? this.eventActionContents,
      eventActionValidated: eventActionValidated ?? this.eventActionValidated,
      eventActionRequirements:
          eventActionRequirements ?? this.eventActionRequirements,
      stateMachineContent: stateMachineContent ?? this.stateMachineContent,
      stateMachineValidated:
          stateMachineValidated ?? this.stateMachineValidated,
      // L4/L5 fields
      hierarchyContent: clearHierarchyContent
          ? null
          : (hierarchyContent ?? this.hierarchyContent),
      hierarchyValidated: hierarchyValidated ?? this.hierarchyValidated,
      sceneGlbUploaded: sceneGlbUploaded ?? this.sceneGlbUploaded,
      sceneGlbCommand: sceneGlbCommand ?? this.sceneGlbCommand,
      sceneConfigContent: clearSceneConfigContent
          ? null
          : (sceneConfigContent ?? this.sceneConfigContent),
      sceneConfigValidated: sceneConfigValidated ?? this.sceneConfigValidated,
      userConfigContent: clearUserConfigContent
          ? null
          : (userConfigContent ?? this.userConfigContent),
      userConfigValidated: userConfigValidated ?? this.userConfigValidated,
      zipUploadInProgress: zipUploadInProgress ?? this.zipUploadInProgress,
      forceCollapseSections:
          forceCollapseSections ?? this.forceCollapseSections,
      hasUnsavedChanges: hasUnsavedChanges ?? this.hasUnsavedChanges,
      step3Invalidated: step3Invalidated ?? this.step3Invalidated,
    );
  }

  /// Clear all transient notifications (called on step navigation)
  WizardState clearNotifications() =>
      copyWith(clearError: true, clearSuccess: true, clearWarning: true);

  @override
  List<Object?> get props => [
    mode,
    currentStep,
    highestStepReached,
    status,
    twinState,
    errorMessage,
    successMessage,
    warningMessage,
    isCalculating,
    twinId,
    twinName,
    debugMode,
    aws,
    azure,
    gcp,
    gcpServiceAccountJson,
    cloudConnections,
    selectedCloudConnectionIds,
    cloudConnectionLoading,
    cloudConnectionErrors,
    cloudConnectionValidation,
    calcParams,
    savedCalcParams,
    isCalcFormValid,
    calcResult,
    savedCalcResult,
    optimizationResultData,
    savedOptimizationResultData,
    deploymentRun,
    savedDeploymentRun,
    isSelectingDeploymentRun,
    deploymentRunSelectionError,
    pricingHealth,
    isPricingHealthLoading,
    pricingHealthError,
    providerCapabilities,
    providerCapabilitiesLoading,
    providerCapabilitiesError,
    deployerDigitalTwinName, // FIXED: was missing
    configEventsJson,
    configIotDevicesJson,
    configJsonValidated, // FIXED: was missing
    configEventsValidated,
    configIotDevicesValidated,
    validatingArtifactIds,
    artifactValidationFeedback,
    payloadsJson,
    payloadsValidated,
    // L2 fields
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
    // L4/L5 fields
    hierarchyContent,
    hierarchyValidated,
    sceneGlbUploaded,
    sceneGlbCommand,
    sceneConfigContent,
    sceneConfigValidated,
    userConfigContent,
    userConfigValidated,
    zipUploadInProgress,
    forceCollapseSections,
    hasUnsavedChanges,
    step3Invalidated,
  ];
}
