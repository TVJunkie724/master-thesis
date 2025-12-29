// lib/bloc/wizard/wizard_state.dart
// State for the Wizard BLoC state machine

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
  final CalcResult? calcResult;
  final Map<String, dynamic>? calcResultRaw;
  final Map<String, dynamic>? pricingSnapshots;
  final Map<String, String?>? pricingTimestamps;
  
  // === Persistent Data: Step 3 ===
  final Map<String, dynamic>? deployerConfig;
  
  // === State Tracking ===
  final bool hasUnsavedChanges;
  
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
    this.calcResult,
    this.calcResultRaw,
    this.pricingSnapshots,
    this.pricingTimestamps,
    this.deployerConfig,
    this.hasUnsavedChanges = false,
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
    CalcResult? calcResult,
    Map<String, dynamic>? calcResultRaw,
    Map<String, dynamic>? pricingSnapshots,
    Map<String, String?>? pricingTimestamps,
    Map<String, dynamic>? deployerConfig,
    bool? hasUnsavedChanges,
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
      calcResult: calcResult ?? this.calcResult,
      calcResultRaw: calcResultRaw ?? this.calcResultRaw,
      pricingSnapshots: pricingSnapshots ?? this.pricingSnapshots,
      pricingTimestamps: pricingTimestamps ?? this.pricingTimestamps,
      deployerConfig: deployerConfig ?? this.deployerConfig,
      hasUnsavedChanges: hasUnsavedChanges ?? this.hasUnsavedChanges,
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
    calcResult,
    calcResultRaw,
    pricingSnapshots,
    pricingTimestamps,
    deployerConfig,
    hasUnsavedChanges,
  ];
}
