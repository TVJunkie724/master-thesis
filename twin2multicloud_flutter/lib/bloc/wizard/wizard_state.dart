// lib/bloc/wizard/wizard_state.dart
// State for the Wizard BLoC state machine

import 'dart:convert';
import 'package:equatable/equatable.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';

// ============================================================
// ENUMS
// ============================================================

/// Wizard mode - creating new twin or editing existing
enum WizardMode { create, edit }

/// Overall wizard status
enum WizardStatus { initial, loading, ready, saving, error }

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

// ============================================================
// MAIN STATE CLASS
// ============================================================

/// Immutable state for the wizard BLoC
class WizardState extends Equatable {
  // === Mode & Navigation ===
  final WizardMode mode;
  final int currentStep;        // 0, 1, 2
  final int highestStepReached; // For step indicator gating
  final WizardStatus status;
  
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
  
  // === Persistent Data: Step 2 ===
  final CalcParams? calcParams;
  final bool isCalcFormValid;  // Whether the calculation form passes validation
  final CalcResult? calcResult;
  final CalcResult? savedCalcResult;  // Last saved result from DB (for revert)
  final Map<String, dynamic>? calcResultRaw;
  final Map<String, dynamic>? savedCalcResultRaw;  // Last saved raw result (for revert)
  final Map<String, dynamic>? pricingSnapshots;
  final Map<String, String?>? pricingTimestamps;
  
  // === Persistent Data: Step 3 Section 2 ===
  final String? deployerDigitalTwinName;  // config.json digital_twin_name (separate from Step 1 name)
  final String? configEventsJson;         // config_events.json content
  final String? configIotDevicesJson;     // config_iot_devices.json content
  final bool configJsonValidated;         // config.json validation state
  final bool configEventsValidated;       // Validation state (gates save)
  final bool configIotDevicesValidated;   // Validation state (gates save)
  
  // === Persistent Data: Step 3 Section 3 (L1) ===
  final Map<String, dynamic>? deployerConfig;
  final String? payloadsJson;       // L1: payloads.json content
  final bool payloadsValidated;     // L1: validation state
  
  // === Persistent Data: Step 3 Section 3 (L2) ===
  final Map<String, String> processorContents;       // device_id -> process.py content
  final Map<String, bool> processorValidated;        // device_id -> validation state
  final String? eventFeedbackContent;                // event-feedback/process.py
  final bool eventFeedbackValidated;
  final Map<String, String> eventActionContents;     // functionName -> code content
  final Map<String, bool> eventActionValidated;      // functionName -> validation state
  final String? stateMachineContent;                 // AWS/Azure/GCP workflow JSON/YAML
  final bool stateMachineValidated;
  
  // === State Tracking ===
  final bool hasUnsavedChanges;
  final bool step3Invalidated;  // True when new calc invalidates Section 3 data
  
  const WizardState({
    this.mode = WizardMode.create,
    this.currentStep = 0,
    this.highestStepReached = 0,
    this.status = WizardStatus.initial,
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
    this.calcParams,
    this.isCalcFormValid = true,  // Default to valid
    this.calcResult,
    this.savedCalcResult,
    this.calcResultRaw,
    this.savedCalcResultRaw,
    this.pricingSnapshots,
    this.pricingTimestamps,
    this.deployerDigitalTwinName,
    this.configEventsJson,
    this.configIotDevicesJson,
    this.configJsonValidated = false,
    this.configEventsValidated = false,
    this.configIotDevicesValidated = false,
    this.deployerConfig,
    this.payloadsJson,
    this.payloadsValidated = false,
    // L2 fields
    this.processorContents = const {},
    this.processorValidated = const {},
    this.eventFeedbackContent,
    this.eventFeedbackValidated = false,
    this.eventActionContents = const {},
    this.eventActionValidated = const {},
    this.stateMachineContent,
    this.stateMachineValidated = false,
    this.hasUnsavedChanges = false,
    this.step3Invalidated = false,
  });
  
  // ============================================================
  // DERIVED GETTERS
  // ============================================================
  
  /// Can proceed from Step 1 to Step 2?
  bool get canProceedToStep2 => 
    (twinName?.isNotEmpty ?? false) && 
    (aws.isValid || azure.isValid || gcp.isValid);
  
  /// Can proceed from Step 2 to Step 3?
  bool get canProceedToStep3 => calcResult != null;
  
  /// Set of configured provider names (uppercase)
  Set<String> get configuredProviders => {
    if (aws.isValid) 'AWS',
    if (azure.isValid) 'AZURE',
    if (gcp.isValid) 'GCP',
  };
  
  /// Is Section 2 validated? (gates save)
  bool get isSection2Valid =>
      configJsonValidated && configEventsValidated && configIotDevicesValidated;
  
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
        devices = data;  // Direct array format: [{id:...}, ...]
      } else if (data is Map && data['devices'] is List) {
        devices = data['devices'];  // Wrapped format: {devices: [...]}
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
        events = data;  // Direct array format
      } else if (data is Map && data['events'] is List) {
        events = data['events'];  // Wrapped format
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
    final result = <String, String>{};
    for (final segment in path) {
      final parts = segment.split('_');
      if (parts.length >= 2) {
        final layer = parts[0].toUpperCase(); // L1, L2, L3, L4, L5
        // Provider is the last part (handles L3_hot_AWS format)
        final provider = parts.last.toUpperCase();
        result[layer] = provider;
      }
    }
    return result;
  }
  
  /// Get the L2 provider from calculation result
  String? get layer2Provider => layerProviders['L2'];
  
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
      configIotDevicesValidated && (calcParams?.returnFeedbackToDevice ?? false);

  /// Should show state machine input?
  bool get shouldShowStateMachine =>
      configIotDevicesValidated && (calcParams?.triggerNotificationWorkflow ?? false);
  
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
    CalcParams? calcParams,
    bool? isCalcFormValid,
    CalcResult? calcResult,
    CalcResult? savedCalcResult,
    Map<String, dynamic>? calcResultRaw,
    Map<String, dynamic>? savedCalcResultRaw,
    Map<String, dynamic>? pricingSnapshots,
    Map<String, String?>? pricingTimestamps,
    String? deployerDigitalTwinName,
    String? configEventsJson,
    String? configIotDevicesJson,
    bool? configJsonValidated,
    bool? configEventsValidated,
    bool? configIotDevicesValidated,
    Map<String, dynamic>? deployerConfig,
    String? payloadsJson,
    bool? payloadsValidated,
    // L2 fields
    Map<String, String>? processorContents,
    Map<String, bool>? processorValidated,
    String? eventFeedbackContent,
    bool? eventFeedbackValidated,
    Map<String, String>? eventActionContents,
    Map<String, bool>? eventActionValidated,
    String? stateMachineContent,
    bool? stateMachineValidated,
    bool? hasUnsavedChanges,
    bool? step3Invalidated,
    // Special flags to explicitly clear nullable fields
    bool clearError = false,
    bool clearSuccess = false,
    bool clearWarning = false,
  }) {
    return WizardState(
      mode: mode ?? this.mode,
      currentStep: currentStep ?? this.currentStep,
      highestStepReached: highestStepReached ?? this.highestStepReached,
      status: status ?? this.status,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      successMessage: clearSuccess ? null : (successMessage ?? this.successMessage),
      warningMessage: clearWarning ? null : (warningMessage ?? this.warningMessage),
      isCalculating: isCalculating ?? this.isCalculating,
      twinId: twinId ?? this.twinId,
      twinName: twinName ?? this.twinName,
      debugMode: debugMode ?? this.debugMode,
      aws: aws ?? this.aws,
      azure: azure ?? this.azure,
      gcp: gcp ?? this.gcp,
      gcpServiceAccountJson: gcpServiceAccountJson ?? this.gcpServiceAccountJson,
      calcParams: calcParams ?? this.calcParams,
      isCalcFormValid: isCalcFormValid ?? this.isCalcFormValid,
      calcResult: calcResult ?? this.calcResult,
      savedCalcResult: savedCalcResult ?? this.savedCalcResult,
      calcResultRaw: calcResultRaw ?? this.calcResultRaw,
      savedCalcResultRaw: savedCalcResultRaw ?? this.savedCalcResultRaw,
      pricingSnapshots: pricingSnapshots ?? this.pricingSnapshots,
      pricingTimestamps: pricingTimestamps ?? this.pricingTimestamps,
      deployerDigitalTwinName: deployerDigitalTwinName ?? this.deployerDigitalTwinName,
      configEventsJson: configEventsJson ?? this.configEventsJson,
      configIotDevicesJson: configIotDevicesJson ?? this.configIotDevicesJson,
      configJsonValidated: configJsonValidated ?? this.configJsonValidated,
      configEventsValidated: configEventsValidated ?? this.configEventsValidated,
      configIotDevicesValidated: configIotDevicesValidated ?? this.configIotDevicesValidated,
      deployerConfig: deployerConfig ?? this.deployerConfig,
      payloadsJson: payloadsJson ?? this.payloadsJson,
      payloadsValidated: payloadsValidated ?? this.payloadsValidated,
      // L2 fields
      processorContents: processorContents ?? this.processorContents,
      processorValidated: processorValidated ?? this.processorValidated,
      eventFeedbackContent: eventFeedbackContent ?? this.eventFeedbackContent,
      eventFeedbackValidated: eventFeedbackValidated ?? this.eventFeedbackValidated,
      eventActionContents: eventActionContents ?? this.eventActionContents,
      eventActionValidated: eventActionValidated ?? this.eventActionValidated,
      stateMachineContent: stateMachineContent ?? this.stateMachineContent,
      stateMachineValidated: stateMachineValidated ?? this.stateMachineValidated,
      hasUnsavedChanges: hasUnsavedChanges ?? this.hasUnsavedChanges,
      step3Invalidated: step3Invalidated ?? this.step3Invalidated,
    );
  }
  
  /// Clear all transient notifications (called on step navigation)
  WizardState clearNotifications() => copyWith(
    clearError: true,
    clearSuccess: true,
    clearWarning: true,
  );
  
  @override
  List<Object?> get props => [
    mode,
    currentStep,
    highestStepReached,
    status,
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
    calcParams,
    isCalcFormValid,
    calcResult,
    savedCalcResult,
    calcResultRaw,
    savedCalcResultRaw,
    pricingSnapshots,
    pricingTimestamps,
    deployerDigitalTwinName,  // FIXED: was missing
    configEventsJson,
    configIotDevicesJson,
    configJsonValidated,      // FIXED: was missing
    configEventsValidated,
    configIotDevicesValidated,
    deployerConfig,
    payloadsJson,
    payloadsValidated,
    // L2 fields
    processorContents,
    processorValidated,
    eventFeedbackContent,
    eventFeedbackValidated,
    eventActionContents,
    eventActionValidated,
    stateMachineContent,
    stateMachineValidated,
    hasUnsavedChanges,
    step3Invalidated,
  ];
}
