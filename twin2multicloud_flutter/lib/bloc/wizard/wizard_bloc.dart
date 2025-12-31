// lib/bloc/wizard/wizard_bloc.dart
// BLoC for wizard state machine

import 'package:flutter_bloc/flutter_bloc.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';
import '../../services/api_service.dart';
import 'wizard_event.dart';
import 'wizard_state.dart';

/// WizardBloc - State machine for the multi-step wizard
/// 
/// Manages:
/// - Step navigation with validation gates
/// - Transient UI state (notifications) that clear on step change
/// - Persistent data (credentials, calc results) that survives navigation
/// - Create vs Edit mode distinction
class WizardBloc extends Bloc<WizardEvent, WizardState> {
  final ApiService _api;
  
  WizardBloc({required ApiService api}) 
    : _api = api, 
      super(const WizardState()) {
    
    // === Initialization ===
    on<WizardInitCreate>(_onInitCreate);
    on<WizardInitEdit>(_onInitEdit);
    
    // === Navigation ===
    on<WizardNextStep>(_onNextStep);
    on<WizardPreviousStep>(_onPreviousStep);
    on<WizardGoToStep>(_onGoToStep);
    
    // === Step 1: Configuration ===
    on<WizardTwinNameChanged>(_onTwinNameChanged);
    on<WizardDebugModeChanged>(_onDebugModeChanged);
    on<WizardCredentialsChanged>(_onCredentialsChanged);
    on<WizardCredentialsValidated>(_onCredentialsValidated);
    on<WizardCredentialsCleared>(_onCredentialsCleared);
    
    // === Step 2: Optimizer ===
    on<WizardCalcParamsChanged>(_onCalcParamsChanged);
    on<WizardCalcFormValidChanged>(_onCalcFormValidChanged);
    on<WizardCalculateRequested>(_onCalculateRequested);
    
    // === Persistence ===
    on<WizardSaveDraft>(_onSaveDraft);
    on<WizardFinish>(_onFinish);
    
    // === UI Feedback ===
    on<WizardClearNotifications>(_onClearNotifications);
    on<WizardDismissError>(_onDismissError);
    
    // === Step 3 Invalidation ===
    on<WizardSection3DataChanged>(_onSection3DataChanged);
    on<WizardProceedWithNewResults>(_onProceedWithNewResults);
    on<WizardRestoreOldResults>(_onRestoreOldResults);
    on<WizardProceedAndSave>(_onProceedAndSave);
    on<WizardProceedAndNext>(_onProceedAndNext);
    on<WizardClearInvalidation>(_onClearInvalidation);
    
    // === Step 3 Section 2: Config Files ===
    on<WizardDeployerTwinNameChanged>(_onDeployerTwinNameChanged);
    on<WizardConfigEventsChanged>(_onConfigEventsChanged);
    on<WizardConfigIotDevicesChanged>(_onConfigIotDevicesChanged);
    on<WizardValidateDeployerConfig>(_onValidateDeployerConfig);
    on<WizardConfigValidationCompleted>(_onConfigValidationCompleted);
  }
  
  // ============================================================
  // INITIALIZATION HANDLERS
  // ============================================================
  
  void _onInitCreate(WizardInitCreate event, Emitter<WizardState> emit) {
    emit(const WizardState(
      mode: WizardMode.create,
      status: WizardStatus.ready,
    ));
  }
  
  Future<void> _onInitEdit(WizardInitEdit event, Emitter<WizardState> emit) async {
    emit(state.copyWith(status: WizardStatus.loading));
    
    try {
      final twin = await _api.getTwin(event.twinId);
      final config = await _api.getTwinConfig(event.twinId);
      
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
      if (startStep >= 1 && !(awsCreds.isValid || azureCreds.isValid || gcpCreds.isValid)) {
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
      
      // Generate warning for unconfigured providers in loaded result
      String? warningMessage;
      if (loadedResult != null) {
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
          warningMessage = 'Unconfigured provider(s) in optimal path: ${unconfigured.join(", ")}. Return to Step 1 to add credentials.';
        }
      }
      
      emit(WizardState(
        mode: WizardMode.edit,
        status: WizardStatus.ready,
        currentStep: startStep,
        highestStepReached: startStep,
        twinId: event.twinId,
        twinName: twin['name'],
        debugMode: config['debug_mode'] ?? true,
        aws: awsCreds,
        azure: azureCreds,
        gcp: gcpCreds,
        calcParams: loadedParams,
        calcResult: loadedResult,
        savedCalcResult: loadedResult,  // Store for revert capability
        calcResultRaw: loadedResultRaw,
        savedCalcResultRaw: loadedResultRaw,  // Store raw for revert
        warningMessage: warningMessage,
      ));
    } catch (e) {
      emit(state.copyWith(
        status: WizardStatus.error,
        errorMessage: 'Failed to load twin: $e',
      ));
    }
  }
  
  Map<String, String> _extractMaskedCredentials(dynamic config) {
    if (config == null || config is! Map) return {};
    final result = <String, String>{};
    for (final entry in config.entries) {
      if (entry.value != null) {
        result[entry.key.toString()] = '••••••••'; // Masked
      }
    }
    return result;
  }
  
  // ============================================================
  // NAVIGATION HANDLERS
  // ============================================================
  
  void _onNextStep(WizardNextStep event, Emitter<WizardState> emit) {
    // Clear notifications first
    var newState = state.clearNotifications();
    
    // Validate current step
    switch (state.currentStep) {
      case 0:
        if (!state.canProceedToStep2) {
          emit(newState.copyWith(
            errorMessage: 'Enter twin name and validate at least one provider',
          ));
          return;
        }
        break;
      case 1:
        if (!state.canProceedToStep3) {
          emit(newState.copyWith(
            errorMessage: 'Run calculation before proceeding',
          ));
          return;
        }
        break;
      case 2:
        // Last step - finishing is handled by WizardFinish event
        return;
    }
    
    // Advance step
    final nextStep = state.currentStep + 1;
    
    // Issue 3 fix: When advancing from Step 2 to Step 3 for first time,
    // snapshot current calcResult as savedCalcResult for revert capability
    CalcResult? snapshotCalcResult;
    Map<String, dynamic>? snapshotCalcResultRaw;
    if (state.currentStep == 1 && nextStep == 2 && state.savedCalcResult == null) {
      snapshotCalcResult = state.calcResult;
      snapshotCalcResultRaw = state.calcResultRaw;
    }
    
    emit(newState.copyWith(
      currentStep: nextStep,
      highestStepReached: nextStep > state.highestStepReached 
        ? nextStep 
        : state.highestStepReached,
      savedCalcResult: snapshotCalcResult,
      savedCalcResultRaw: snapshotCalcResultRaw,
    ));
  }
  
  void _onPreviousStep(WizardPreviousStep event, Emitter<WizardState> emit) {
    if (state.currentStep > 0) {
      emit(state.clearNotifications().copyWith(
        currentStep: state.currentStep - 1,
      ));
    }
  }
  
  void _onGoToStep(WizardGoToStep event, Emitter<WizardState> emit) {
    // Only allow jumping to already-reached steps
    if (event.step <= state.highestStepReached && event.step >= 0) {
      emit(state.clearNotifications().copyWith(
        currentStep: event.step,
      ));
    }
  }
  
  // ============================================================
  // STEP 1 HANDLERS
  // ============================================================
  
  void _onTwinNameChanged(WizardTwinNameChanged event, Emitter<WizardState> emit) {
    emit(state.copyWith(
      twinName: event.name,
      hasUnsavedChanges: true,
    ));
  }
  
  void _onDebugModeChanged(WizardDebugModeChanged event, Emitter<WizardState> emit) {
    emit(state.copyWith(
      debugMode: event.debugMode,
      hasUnsavedChanges: true,
    ));
  }
  
  void _onCredentialsChanged(WizardCredentialsChanged event, Emitter<WizardState> emit) {
    final updated = state.copyWith(hasUnsavedChanges: true);
    
    switch (event.provider) {
      case 'aws':
        emit(updated.copyWith(
          aws: state.aws.copyWith(
            values: event.credentials,
            source: CredentialSource.newlyEntered,
          ),
        ));
        break;
      case 'azure':
        emit(updated.copyWith(
          azure: state.azure.copyWith(
            values: event.credentials,
            source: CredentialSource.newlyEntered,
          ),
        ));
        break;
      case 'gcp':
        emit(updated.copyWith(
          gcp: state.gcp.copyWith(
            values: event.credentials,
            source: CredentialSource.newlyEntered,
          ),
        ));
        break;
    }
  }
  
  void _onCredentialsValidated(WizardCredentialsValidated event, Emitter<WizardState> emit) {
    switch (event.provider) {
      case 'aws':
        emit(state.copyWith(
          aws: state.aws.copyWith(
            isValid: event.isValid,
            source: event.isValid ? CredentialSource.newlyEntered : state.aws.source,
          ),
          hasUnsavedChanges: true,
        ));
        break;
      case 'azure':
        emit(state.copyWith(
          azure: state.azure.copyWith(
            isValid: event.isValid,
            source: event.isValid ? CredentialSource.newlyEntered : state.azure.source,
          ),
          hasUnsavedChanges: true,
        ));
        break;
      case 'gcp':
        emit(state.copyWith(
          gcp: state.gcp.copyWith(
            isValid: event.isValid,
            source: event.isValid ? CredentialSource.newlyEntered : state.gcp.source,
          ),
          hasUnsavedChanges: true,
        ));
        break;
    }
  }
  
  void _onCredentialsCleared(WizardCredentialsCleared event, Emitter<WizardState> emit) {
    switch (event.provider) {
      case 'aws':
        emit(state.copyWith(
          aws: const ProviderCredentials(source: CredentialSource.cleared),
          hasUnsavedChanges: true,
        ));
        break;
      case 'azure':
        emit(state.copyWith(
          azure: const ProviderCredentials(source: CredentialSource.cleared),
          hasUnsavedChanges: true,
        ));
        break;
      case 'gcp':
        emit(state.copyWith(
          gcp: const ProviderCredentials(source: CredentialSource.cleared),
          hasUnsavedChanges: true,
        ));
        break;
    }
  }
  
  // ============================================================
  // STEP 2 HANDLERS
  // ============================================================
  
  void _onCalcParamsChanged(WizardCalcParamsChanged event, Emitter<WizardState> emit) {
    emit(state.copyWith(
      calcParams: event.params,
      hasUnsavedChanges: true,
    ));
  }
  
  void _onCalcFormValidChanged(WizardCalcFormValidChanged event, Emitter<WizardState> emit) {
    emit(state.copyWith(isCalcFormValid: event.isValid));
  }
  
  Future<void> _onCalculateRequested(WizardCalculateRequested event, Emitter<WizardState> emit) async {
    if (state.calcParams == null) {
      emit(state.copyWith(errorMessage: 'Configure calculation parameters first'));
      return;
    }
    
    emit(state.copyWith(isCalculating: true, clearError: true));
    
    try {
      final response = await _api.calculateCosts(state.calcParams!.toJson());
      final result = CalcResult.fromJson(response);
      
      // Check for unconfigured providers in optimal path
      final unconfigured = _getUnconfiguredProviders(result.cheapestPath);
      
      // Check if new result invalidates Step 3 config
      // Invalidation occurs when: hasSection3Data AND inputParamsUsed changed
      bool invalidatesStep3 = false;
      
      
      if (state.hasSection3Data && state.highestStepReached >= 2) {
        invalidatesStep3 = _calculationInvalidatesStep3(state.calcResult, result);
      }
      
      // Build warning message - prioritize invalidation warning, then unconfigured providers
      String? warning;
      if (invalidatesStep3) {
        warning = 'Calculation Changed: Step 3 configuration may need review. Proceeding will require confirmation.';
      } else if (unconfigured.isNotEmpty) {
        warning = 'Unconfigured provider(s) in optimal path: ${unconfigured.join(", ")}. Return to Step 1 to add credentials.';
      }
      
      emit(state.copyWith(
        isCalculating: false,
        calcResult: result,
        calcResultRaw: response,
        hasUnsavedChanges: true,
        step3Invalidated: invalidatesStep3,
        warningMessage: warning,
        clearSuccess: invalidatesStep3,  // Clear success message when warning appears
      ));
    } catch (e) {
      emit(state.copyWith(
        isCalculating: false,
        errorMessage: 'Calculation failed: $e',
      ));
    }
  }
  
  /// Check if calculation result differs in ways that affect Step 3
  /// Invalidates if inputParamsUsed changed OR cheapestPath changed
  bool _calculationInvalidatesStep3(CalcResult? oldResult, CalcResult newResult) {
    if (oldResult == null) return false;
    
    // Check inputParamsUsed
    final oldParams = oldResult.inputParamsUsed;
    final newParams = newResult.inputParamsUsed;
    
    final paramsChanged = 
           oldParams.useEventChecking != newParams.useEventChecking ||
           oldParams.triggerNotificationWorkflow != newParams.triggerNotificationWorkflow ||
           oldParams.returnFeedbackToDevice != newParams.returnFeedbackToDevice ||
           oldParams.integrateErrorHandling != newParams.integrateErrorHandling ||
           oldParams.needs3DModel != newParams.needs3DModel;
    
    // Check cheapestPath
    final pathChanged = !_listEquals(oldResult.cheapestPath, newResult.cheapestPath);
    
    
    return paramsChanged || pathChanged;
  }
  
  bool _listEquals<T>(List<T> a, List<T> b) {
    if (a.length != b.length) return false;
    for (int i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
  
  Set<String> _getUnconfiguredProviders(List<String> path) {
    final resultProviders = <String>{};
    for (final segment in path) {
      final parts = segment.split('_');
      if (parts.length >= 3 && segment.startsWith('L3')) {
        resultProviders.add(parts[2].toUpperCase());
      } else if (parts.length >= 2) {
        resultProviders.add(parts[1].toUpperCase());
      }
    }
    return resultProviders.difference(state.configuredProviders);
  }
  
  // ============================================================
  // PERSISTENCE HANDLERS
  // ============================================================
  
  Future<void> _onSaveDraft(WizardSaveDraft event, Emitter<WizardState> emit) async {
    emit(state.copyWith(status: WizardStatus.saving, clearError: true));
    
    try {
      String? twinId = state.twinId;
      
      // Create twin if new
      if (state.mode == WizardMode.create && twinId == null) {
        if (state.twinName?.isEmpty ?? true) {
          emit(state.copyWith(
            status: WizardStatus.ready,
            errorMessage: 'Twin name is required',
          ));
          return;
        }
        final result = await _api.createTwin(state.twinName!);
        twinId = result['id'];
      }
      
      // Build config payload - only send credentials that need updating
      final config = <String, dynamic>{'debug_mode': state.debugMode};
      
      if (state.aws.source == CredentialSource.newlyEntered) {
        config['aws'] = state.aws.values;
      } else if (state.aws.source == CredentialSource.cleared) {
        config['aws'] = null; // Delete from DB
      }
      
      if (state.azure.source == CredentialSource.newlyEntered) {
        config['azure'] = state.azure.values;
      } else if (state.azure.source == CredentialSource.cleared) {
        config['azure'] = null;
      }
      
      if (state.gcp.source == CredentialSource.newlyEntered) {
        config['gcp'] = state.gcp.values;
      } else if (state.gcp.source == CredentialSource.cleared) {
        config['gcp'] = null;
      }
      
      // Include optimizer data if present
      if (state.calcParams != null) {
        config['optimizer_params'] = state.calcParams!.toJson();
      }
      if (state.calcResultRaw != null) {
        config['optimizer_result'] = state.calcResultRaw!['result'];
      }
      
      // Persist current step position for resume on edit
      config['highest_step_reached'] = state.highestStepReached;
      
      await _api.updateTwinConfig(twinId!, config);
      
      emit(state.copyWith(
        status: WizardStatus.ready,
        twinId: twinId,
        hasUnsavedChanges: false,
        savedCalcResult: state.calcResult,  // Update saved result on successful save
        savedCalcResultRaw: state.calcResultRaw,  // Update saved raw result
        step3Invalidated: false,  // Clear invalidation after save
        successMessage: 'Draft saved!',
      ));
    } catch (e) {
      emit(state.copyWith(
        status: WizardStatus.ready,
        errorMessage: 'Save failed: $e',
      ));
    }
  }
  
  Future<void> _onFinish(WizardFinish event, Emitter<WizardState> emit) async {
    emit(state.copyWith(status: WizardStatus.saving));
    
    try {
      String? twinId = state.twinId;
      
      // Create twin if new
      if (state.mode == WizardMode.create && twinId == null) {
        if (state.twinName?.isEmpty ?? true) {
          emit(state.copyWith(status: WizardStatus.ready, errorMessage: 'Twin name is required'));
          return;
        }
        final result = await _api.createTwin(state.twinName!);
        twinId = result['id'];
      }
      
      // Build config payload
      final config = <String, dynamic>{'debug_mode': state.debugMode};
      if (state.aws.source == CredentialSource.newlyEntered) config['aws'] = state.aws.values;
      if (state.azure.source == CredentialSource.newlyEntered) config['azure'] = state.azure.values;
      if (state.gcp.source == CredentialSource.newlyEntered) config['gcp'] = state.gcp.values;
      if (state.calcParams != null) config['optimizer_params'] = state.calcParams!.toJson();
      if (state.calcResultRaw != null) config['optimizer_result'] = state.calcResultRaw!['result'];
      config['highest_step_reached'] = state.highestStepReached;  // Issue 4 fix
      
      await _api.updateTwinConfig(twinId!, config);
      
      emit(state.copyWith(
        status: WizardStatus.ready,
        twinId: twinId,
        hasUnsavedChanges: false,
        successMessage: 'Configuration complete!',
      ));
    } catch (e) {
      emit(state.copyWith(status: WizardStatus.ready, errorMessage: 'Failed to finish: $e'));
    }
  }
  
  // ============================================================
  // UI FEEDBACK HANDLERS
  // ============================================================
  
  void _onClearNotifications(WizardClearNotifications event, Emitter<WizardState> emit) {
    emit(state.clearNotifications());
  }
  
  void _onDismissError(WizardDismissError event, Emitter<WizardState> emit) {
    emit(state.copyWith(clearError: true));
  }
  
  // ============================================================
  // STEP 3 INVALIDATION HANDLERS
  // ============================================================
  
  void _onSection3DataChanged(WizardSection3DataChanged event, Emitter<WizardState> emit) {
    emit(state.copyWith(hasSection3Data: event.hasData));
  }
  
  void _onProceedWithNewResults(WizardProceedWithNewResults event, Emitter<WizardState> emit) {
    // User chose to keep new calculation - clear invalidation flag
    // Section 3 data will be cleared by UI
    emit(state.copyWith(
      step3Invalidated: false,
      hasSection3Data: false,
    ));
  }
  
  void _onRestoreOldResults(WizardRestoreOldResults event, Emitter<WizardState> emit) {
    // User chose to discard changes - revert to last saved calc result
    emit(state.copyWith(
      step3Invalidated: false,
      calcResult: state.savedCalcResult,  // Visually revert to saved result
      calcResultRaw: state.savedCalcResultRaw,  // Revert raw data for persistence
      hasUnsavedChanges: false,
      successMessage: 'Changes discarded',
    ));
  }
  
  // Combined handlers to avoid race condition
  Future<void> _onProceedAndSave(WizardProceedAndSave event, Emitter<WizardState> emit) async {
    // Atomically: clear invalidation + save
    emit(state.copyWith(
      step3Invalidated: false,
      hasSection3Data: false,
    ));
    await _onSaveDraft(const WizardSaveDraft(), emit);
  }
  
  void _onProceedAndNext(WizardProceedAndNext event, Emitter<WizardState> emit) {
    // Atomically: clear invalidation + next
    emit(state.copyWith(
      step3Invalidated: false,
      hasSection3Data: false,
    ));
    _onNextStep(const WizardNextStep(), emit);
  }
  
  void _onClearInvalidation(WizardClearInvalidation event, Emitter<WizardState> emit) {
    // Just clear the invalidation flag (user chose to proceed with new results)
    emit(state.copyWith(
      step3Invalidated: false,
      hasSection3Data: false,
      clearWarning: true,
    ));
  }

  // ============================================================
  // STEP 3 SECTION 2: CONFIG FILE HANDLERS
  // ============================================================

  void _onConfigEventsChanged(WizardConfigEventsChanged event, Emitter<WizardState> emit) {
    emit(state.copyWith(
      configEventsJson: event.content,
      configEventsValidated: false, // Reset validation on content change
      hasUnsavedChanges: true,
    ));
  }

  void _onConfigIotDevicesChanged(WizardConfigIotDevicesChanged event, Emitter<WizardState> emit) {
    emit(state.copyWith(
      configIotDevicesJson: event.content,
      configIotDevicesValidated: false, // Reset validation on content change
      hasUnsavedChanges: true,
    ));
  }

  void _onDeployerTwinNameChanged(WizardDeployerTwinNameChanged event, Emitter<WizardState> emit) {
    emit(state.copyWith(
      deployerDigitalTwinName: event.name,
      hasUnsavedChanges: true,
    ));
  }

  Future<void> _onValidateDeployerConfig(WizardValidateDeployerConfig event, Emitter<WizardState> emit) async {
    final twinId = state.twinId;
    if (twinId == null) {
      emit(state.copyWith(errorMessage: 'No twin ID. Save draft first.'));
      return;
    }

    final configType = event.configType;
    final content = configType == 'events' 
        ? state.configEventsJson 
        : state.configIotDevicesJson;

    if (content == null || content.trim().isEmpty) {
      emit(state.copyWith(errorMessage: 'No content to validate.'));
      return;
    }

    try {
      final result = await _api.validateDeployerConfig(twinId, configType, content);
      final valid = result['valid'] == true;
      final message = result['message']?.toString() ?? (valid ? 'Valid' : 'Invalid');

      if (configType == 'events') {
        emit(state.copyWith(
          configEventsValidated: valid,
          successMessage: valid ? message : null,
          errorMessage: valid ? null : message,
        ));
      } else {
        emit(state.copyWith(
          configIotDevicesValidated: valid,
          successMessage: valid ? message : null,
          errorMessage: valid ? null : message,
        ));
      }
    } catch (e) {
      emit(state.copyWith(errorMessage: 'Validation failed: $e'));
    }
  }

  /// Handle validation result from widget (direct API call)
  void _onConfigValidationCompleted(WizardConfigValidationCompleted event, Emitter<WizardState> emit) {
    if (event.configType == 'events') {
      emit(state.copyWith(configEventsValidated: event.valid));
    } else {
      emit(state.copyWith(configIotDevicesValidated: event.valid));
    }
  }
}
