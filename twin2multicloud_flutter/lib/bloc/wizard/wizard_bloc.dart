// lib/bloc/wizard/wizard_bloc.dart
// BLoC for wizard state machine

import 'package:flutter_bloc/flutter_bloc.dart';
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
    on<WizardCalculateRequested>(_onCalculateRequested);
    
    // === Persistence ===
    on<WizardSaveDraft>(_onSaveDraft);
    on<WizardFinish>(_onFinish);
    
    // === UI Feedback ===
    on<WizardClearNotifications>(_onClearNotifications);
    on<WizardDismissError>(_onDismissError);
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
      
      // Determine starting step based on data completeness
      int startStep = 0;
      if (awsCreds.isValid || azureCreds.isValid || gcpCreds.isValid) {
        startStep = 1;
      }
      // Check for optimizer result to jump to step 2
      CalcResult? loadedResult;
      if (config['optimizer_result'] != null) {
        loadedResult = CalcResult.fromJson({'result': config['optimizer_result']});
        startStep = 2;
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
        calcResult: loadedResult,
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
    emit(newState.copyWith(
      currentStep: nextStep,
      highestStepReached: nextStep > state.highestStepReached 
        ? nextStep 
        : state.highestStepReached,
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
      
      emit(state.copyWith(
        isCalculating: false,
        calcResult: result,
        calcResultRaw: response,
        hasUnsavedChanges: true,
        warningMessage: unconfigured.isNotEmpty 
          ? 'Unconfigured provider(s) in optimal path: ${unconfigured.join(", ")}. Return to Step 1 to add credentials.'
          : null,
      ));
    } catch (e) {
      emit(state.copyWith(
        isCalculating: false,
        errorMessage: 'Calculation failed: $e',
      ));
    }
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
      
      await _api.updateTwinConfig(twinId!, config);
      
      emit(state.copyWith(
        status: WizardStatus.ready,
        twinId: twinId,
        hasUnsavedChanges: false,
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
}
