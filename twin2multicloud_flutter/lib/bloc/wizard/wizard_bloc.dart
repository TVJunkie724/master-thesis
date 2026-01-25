// lib/bloc/wizard/wizard_bloc.dart
// BLoC for wizard state machine

import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';
import '../../services/api_service.dart';
import '../../utils/api_error_handler.dart';
import 'wizard_event.dart';
import 'wizard_state.dart';
import 'helpers/helpers.dart';

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

    // === Step 3 Section 3: L1 Payloads ===
    on<WizardPayloadsChanged>(_onPayloadsChanged);

    // === Step 3 Section 3: L2 User Functions ===
    on<WizardProcessorContentChanged>(_onProcessorContentChanged);
    on<WizardEventFeedbackContentChanged>(_onEventFeedbackContentChanged);
    on<WizardEventActionContentChanged>(_onEventActionContentChanged);
    on<WizardStateMachineContentChanged>(_onStateMachineContentChanged);

    // === Step 3 Section 3: L2 Requirements ===
    on<WizardProcessorRequirementsChanged>(_onProcessorRequirementsChanged);
    on<WizardEventFeedbackRequirementsChanged>(
      _onEventFeedbackRequirementsChanged,
    );
    on<WizardEventActionRequirementsChanged>(_onEventActionRequirementsChanged);

    // === Step 3 Section 3: L2 Validation ===
    on<WizardProcessorValidationCompleted>(_onProcessorValidationCompleted);
    on<WizardEventFeedbackValidationCompleted>(
      _onEventFeedbackValidationCompleted,
    );
    on<WizardEventActionValidationCompleted>(_onEventActionValidationCompleted);
    on<WizardStateMachineValidationCompleted>(
      _onStateMachineValidationCompleted,
    );

    // === Step 3: L4 Hierarchy ===
    on<WizardHierarchyContentChanged>(_onHierarchyContentChanged);
    on<WizardHierarchyValidationCompleted>(_onHierarchyValidationCompleted);

    // === Step 3: L4 Scene ===
    on<WizardSceneConfigContentChanged>(_onSceneConfigContentChanged);
    on<WizardSceneConfigValidationCompleted>(_onSceneConfigValidationCompleted);
    on<WizardSceneGlbUploadStatusChanged>(_onSceneGlbUploadStatusChanged);

    // === Step 3: L4/L5 User Config ===
    on<WizardUserConfigContentChanged>(_onUserConfigContentChanged);
    on<WizardUserConfigValidationCompleted>(_onUserConfigValidationCompleted);

    // === Step 3: L4 Cleanup ===
    on<WizardL4CleanupRequested>(_onL4CleanupRequested);

    // === Step 3: Zip Upload ===
    on<WizardZipUploadRequested>(_onZipUploadRequested);
    on<WizardZipUploadConfirmed>(_onZipUploadConfirmed);
  }

  // ============================================================
  // INITIALIZATION HANDLERS
  // ============================================================

  void _onInitCreate(WizardInitCreate event, Emitter<WizardState> emit) {
    emit(
      const WizardState(mode: WizardMode.create, status: WizardStatus.ready),
    );
  }

  Future<void> _onInitEdit(
    WizardInitEdit event,
    Emitter<WizardState> emit,
  ) async {
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
      String? deployerDigitalTwinName;
      String? configEventsJson;
      String? configIotDevicesJson;
      bool configJsonValidated = false;
      bool configEventsValidated = false;
      bool configIotDevicesValidated = false;
      // Section 3 L1
      String? payloadsJson;
      bool payloadsValidated = false;
      // Section 3 L2
      Map<String, String> processorContents = {};
      Map<String, bool> processorValidated = {};
      Map<String, String> processorRequirements = {};
      String? eventFeedbackContent;
      bool eventFeedbackValidated = false;
      String? eventFeedbackRequirements;
      Map<String, String> eventActionContents = {};
      Map<String, bool> eventActionValidated = {};
      Map<String, String> eventActionRequirements = {};
      String? stateMachineContent;
      bool stateMachineValidated = false;
      // L4/L5 fields
      String? hierarchyContent;
      bool hierarchyValidated = false;
      bool sceneGlbUploaded = false;
      String? sceneConfigContent;
      bool sceneConfigValidated = false;
      String? userConfigContent;
      bool userConfigValidated = false;

      try {
        final deployerConfig = await _api.getDeployerConfig(event.twinId);
        deployerDigitalTwinName =
            deployerConfig['deployer_digital_twin_name'] as String?;
        configEventsJson = deployerConfig['config_events_json'] as String?;
        configIotDevicesJson =
            deployerConfig['config_iot_devices_json'] as String?;
        configJsonValidated =
            deployerConfig['config_json_validated'] as bool? ?? false;
        configEventsValidated =
            deployerConfig['config_events_validated'] as bool? ?? false;
        configIotDevicesValidated =
            deployerConfig['config_iot_devices_validated'] as bool? ?? false;
        // Section 3 L1
        payloadsJson = deployerConfig['payloads_json'] as String?;
        payloadsValidated =
            deployerConfig['payloads_validated'] as bool? ?? false;
        // Section 3 L2
        if (deployerConfig['processor_contents'] != null) {
          processorContents = Map<String, String>.from(
            deployerConfig['processor_contents'] as Map,
          );
        }
        if (deployerConfig['processor_validated'] != null) {
          processorValidated = Map<String, bool>.from(
            deployerConfig['processor_validated'] as Map,
          );
        }
        if (deployerConfig['processor_requirements'] != null) {
          processorRequirements = Map<String, String>.from(
            deployerConfig['processor_requirements'] as Map,
          );
        }
        eventFeedbackContent =
            deployerConfig['event_feedback_content'] as String?;
        eventFeedbackValidated =
            deployerConfig['event_feedback_validated'] as bool? ?? false;
        eventFeedbackRequirements =
            deployerConfig['event_feedback_requirements'] as String?;
        if (deployerConfig['event_action_contents'] != null) {
          eventActionContents = Map<String, String>.from(
            deployerConfig['event_action_contents'] as Map,
          );
        }
        if (deployerConfig['event_action_validated'] != null) {
          eventActionValidated = Map<String, bool>.from(
            deployerConfig['event_action_validated'] as Map,
          );
        }
        if (deployerConfig['event_action_requirements'] != null) {
          eventActionRequirements = Map<String, String>.from(
            deployerConfig['event_action_requirements'] as Map,
          );
        }
        stateMachineContent =
            deployerConfig['state_machine_content'] as String?;
        stateMachineValidated =
            deployerConfig['state_machine_validated'] as bool? ?? false;
        // L4/L5 fields
        hierarchyContent = deployerConfig['hierarchy_content'] as String?;
        hierarchyValidated =
            deployerConfig['hierarchy_validated'] as bool? ?? false;
        sceneGlbUploaded =
            deployerConfig['scene_glb_uploaded'] as bool? ?? false;
        sceneConfigContent = deployerConfig['scene_config_content'] as String?;
        sceneConfigValidated =
            deployerConfig['scene_config_validated'] as bool? ?? false;
        userConfigContent = deployerConfig['user_config_content'] as String?;
        userConfigValidated =
            deployerConfig['user_config_validated'] as bool? ?? false;
      } catch (e) {
        // No deployer config yet, that's fine
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
          warningMessage =
              'Unconfigured provider(s) in optimal path: ${unconfigured.join(", ")}. Return to Step 1 to add credentials.';
        }
      }

      emit(
        WizardState(
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
          savedCalcResult: loadedResult, // Store for revert capability
          calcResultRaw: loadedResultRaw,
          savedCalcResultRaw: loadedResultRaw, // Store raw for revert
          // Section 2: Deployer config (hydrated from backend)
          deployerDigitalTwinName: deployerDigitalTwinName,
          configEventsJson: configEventsJson,
          configIotDevicesJson: configIotDevicesJson,
          configJsonValidated: configJsonValidated,
          configEventsValidated: configEventsValidated,
          configIotDevicesValidated: configIotDevicesValidated,
          // Section 3 L1 (hydrated)
          payloadsJson: payloadsJson,
          payloadsValidated: payloadsValidated,
          // Section 3 L2 (hydrated)
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
          // L4/L5 fields (hydrated)
          hierarchyContent: hierarchyContent,
          hierarchyValidated: hierarchyValidated,
          sceneGlbUploaded: sceneGlbUploaded,
          sceneConfigContent: sceneConfigContent,
          sceneConfigValidated: sceneConfigValidated,
          userConfigContent: userConfigContent,
          userConfigValidated: userConfigValidated,
          warningMessage: warningMessage,
        ),
      );
    } catch (e) {
      emit(
        state.copyWith(
          status: WizardStatus.error,
          errorMessage:
              'Failed to load twin: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Map<String, String> _extractMaskedCredentials(dynamic config) {
    return CredentialsHelper.extractMaskedCredentials(config);
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
          emit(
            newState.copyWith(
              errorMessage:
                  'Enter twin name and validate at least one provider',
            ),
          );
          return;
        }
        break;
      case 1:
        if (!state.canProceedToStep3) {
          emit(
            newState.copyWith(
              errorMessage: 'Run calculation before proceeding',
            ),
          );
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
    if (state.currentStep == 1 &&
        nextStep == 2 &&
        state.savedCalcResult == null) {
      snapshotCalcResult = state.calcResult;
      snapshotCalcResultRaw = state.calcResultRaw;
    }

    emit(
      newState.copyWith(
        currentStep: nextStep,
        highestStepReached: nextStep > state.highestStepReached
            ? nextStep
            : state.highestStepReached,
        savedCalcResult: snapshotCalcResult,
        savedCalcResultRaw: snapshotCalcResultRaw,
      ),
    );
  }

  void _onPreviousStep(WizardPreviousStep event, Emitter<WizardState> emit) {
    if (state.currentStep > 0) {
      emit(
        state.clearNotifications().copyWith(currentStep: state.currentStep - 1),
      );
    }
  }

  void _onGoToStep(WizardGoToStep event, Emitter<WizardState> emit) {
    // Only allow jumping to already-reached steps
    if (event.step <= state.highestStepReached && event.step >= 0) {
      emit(state.clearNotifications().copyWith(currentStep: event.step));
    }
  }

  // ============================================================
  // STEP 1 HANDLERS
  // ============================================================

  void _onTwinNameChanged(
    WizardTwinNameChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(state.copyWith(twinName: event.name, hasUnsavedChanges: true));
  }

  void _onDebugModeChanged(
    WizardDebugModeChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(state.copyWith(debugMode: event.debugMode, hasUnsavedChanges: true));
  }

  void _onCredentialsChanged(
    WizardCredentialsChanged event,
    Emitter<WizardState> emit,
  ) {
    final updated = state.copyWith(hasUnsavedChanges: true);

    switch (event.provider) {
      case 'aws':
        emit(
          updated.copyWith(
            aws: state.aws.copyWith(
              values: event.credentials,
              source: CredentialSource.newlyEntered,
              isValid: false, // Reset validation when credentials change
            ),
          ),
        );
        break;
      case 'azure':
        emit(
          updated.copyWith(
            azure: state.azure.copyWith(
              values: event.credentials,
              source: CredentialSource.newlyEntered,
              isValid: false, // Reset validation when credentials change
            ),
          ),
        );
        break;
      case 'gcp':
        // IMPORTANT: Merge new values with existing, don't replace entirely.
        // This preserves project_id/region when service_account_json is uploaded separately.
        final mergedValues = <String, String>{
          ...state.gcp.values,
          ...event.credentials.map((k, v) => MapEntry(k, v.toString())),
        };
        emit(
          updated.copyWith(
            gcp: state.gcp.copyWith(
              values: mergedValues,
              source: CredentialSource.newlyEntered,
              isValid: false, // Reset validation when credentials change
            ),
          ),
        );
        break;
    }
  }

  void _onCredentialsValidated(
    WizardCredentialsValidated event,
    Emitter<WizardState> emit,
  ) {
    switch (event.provider) {
      case 'aws':
        emit(
          state.copyWith(
            aws: state.aws.copyWith(
              isValid: event.isValid,
              source: event.isValid
                  ? CredentialSource.newlyEntered
                  : state.aws.source,
            ),
            hasUnsavedChanges: true,
          ),
        );
        break;
      case 'azure':
        emit(
          state.copyWith(
            azure: state.azure.copyWith(
              isValid: event.isValid,
              source: event.isValid
                  ? CredentialSource.newlyEntered
                  : state.azure.source,
            ),
            hasUnsavedChanges: true,
          ),
        );
        break;
      case 'gcp':
        emit(
          state.copyWith(
            gcp: state.gcp.copyWith(
              isValid: event.isValid,
              source: event.isValid
                  ? CredentialSource.newlyEntered
                  : state.gcp.source,
            ),
            hasUnsavedChanges: true,
          ),
        );
        break;
    }
  }

  void _onCredentialsCleared(
    WizardCredentialsCleared event,
    Emitter<WizardState> emit,
  ) {
    switch (event.provider) {
      case 'aws':
        emit(
          state.copyWith(
            aws: const ProviderCredentials(source: CredentialSource.cleared),
            hasUnsavedChanges: true,
          ),
        );
        break;
      case 'azure':
        emit(
          state.copyWith(
            azure: const ProviderCredentials(source: CredentialSource.cleared),
            hasUnsavedChanges: true,
          ),
        );
        break;
      case 'gcp':
        emit(
          state.copyWith(
            gcp: const ProviderCredentials(source: CredentialSource.cleared),
            hasUnsavedChanges: true,
          ),
        );
        break;
    }
  }

  // ============================================================
  // STEP 2 HANDLERS
  // ============================================================

  void _onCalcParamsChanged(
    WizardCalcParamsChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(state.copyWith(calcParams: event.params, hasUnsavedChanges: true));
  }

  void _onCalcFormValidChanged(
    WizardCalcFormValidChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(state.copyWith(isCalcFormValid: event.isValid));
  }

  Future<void> _onCalculateRequested(
    WizardCalculateRequested event,
    Emitter<WizardState> emit,
  ) async {
    if (state.calcParams == null) {
      emit(
        state.copyWith(errorMessage: 'Configure calculation parameters first'),
      );
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
        invalidatesStep3 = _calculationInvalidatesStep3(
          state.calcResult,
          result,
        );
      }

      // Build warning message - prioritize invalidation warning, then unconfigured providers
      String? warning;
      if (invalidatesStep3) {
        warning =
            'Calculation Changed: Step 3 configuration may need review. Proceeding will require confirmation.';
      } else if (unconfigured.isNotEmpty) {
        warning =
            'Unconfigured provider(s) in optimal path: ${unconfigured.join(", ")}. Return to Step 1 to add credentials.';
      }

      emit(
        state.copyWith(
          isCalculating: false,
          calcResult: result,
          calcResultRaw: response,
          hasUnsavedChanges: true,
          step3Invalidated: invalidatesStep3,
          warningMessage: warning,
          clearSuccess:
              invalidatesStep3, // Clear success message when warning appears
        ),
      );
    } catch (e) {
      emit(
        state.copyWith(
          isCalculating: false,
          errorMessage:
              'Calculation failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  /// Check if calculation result differs in ways that affect Step 3
  /// Delegates to CalculationHelper for invalidation logic
  bool _calculationInvalidatesStep3(
    CalcResult? oldResult,
    CalcResult newResult,
  ) {
    return CalculationHelper.calculationInvalidatesStep3(oldResult, newResult);
  }

  Set<String> _getUnconfiguredProviders(List<String> path) {
    return CalculationHelper.getUnconfiguredProviders(
      path,
      state.configuredProviders,
    );
  }

  /// Extract provider name from cheapest path for a given layer prefix
  String? _extractProvider(List<String> path, String prefix) {
    for (final segment in path) {
      if (segment.startsWith(prefix)) {
        return segment.replaceFirst(prefix, '').toLowerCase();
      }
    }
    return null;
  }

  // ============================================================
  // PERSISTENCE HANDLERS
  // ============================================================

  Future<void> _onSaveDraft(
    WizardSaveDraft event,
    Emitter<WizardState> emit,
  ) async {
    emit(state.copyWith(status: WizardStatus.saving, clearError: true));

    try {
      String? twinId = state.twinId;

      // Create twin if new
      if (state.mode == WizardMode.create && twinId == null) {
        if (state.twinName?.isEmpty ?? true) {
          emit(
            state.copyWith(
              status: WizardStatus.ready,
              errorMessage: 'Twin name is required',
            ),
          );
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

      // Save optimizer result with pricing snapshots (if calc result exists)
      if (state.calcParams != null &&
          state.calcResultRaw != null &&
          state.calcResult != null) {
        try {
          // Fetch current pricing snapshots from Optimizer service
          final awsPricing = await _api.exportPricing('aws');
          final azurePricing = await _api.exportPricing('azure');
          final gcpPricing = await _api.exportPricing('gcp');

          // Build cheapest path map from CalcResult
          final cheapestPath = <String, String?>{
            'l1': _extractProvider(state.calcResult!.cheapestPath, 'L1_'),
            'l2': _extractProvider(state.calcResult!.cheapestPath, 'L2_'),
            'l3_hot': _extractProvider(
              state.calcResult!.cheapestPath,
              'L3_hot_',
            ),
            'l3_cool': _extractProvider(
              state.calcResult!.cheapestPath,
              'L3_cool_',
            ),
            'l3_archive': _extractProvider(
              state.calcResult!.cheapestPath,
              'L3_archive_',
            ),
            'l4': _extractProvider(state.calcResult!.cheapestPath, 'L4_'),
            'l5': _extractProvider(state.calcResult!.cheapestPath, 'L5_'),
          };

          // Build pricing timestamps
          final pricingTimestamps = <String, String?>{
            'aws': awsPricing['updated_at'] as String?,
            'azure': azurePricing['updated_at'] as String?,
            'gcp': gcpPricing['updated_at'] as String?,
          };

          await _api.saveOptimizerResult(
            twinId,
            params: state.calcParams!.toJson(),
            result: state.calcResultRaw!['result'] as Map<String, dynamic>,
            cheapestPath: cheapestPath,
            pricingSnapshots: {
              'aws': awsPricing['pricing'],
              'azure': azurePricing['pricing'],
              'gcp': gcpPricing['pricing'],
            },
            pricingTimestamps: pricingTimestamps,
          );
        } catch (e) {
          // Non-fatal: pricing snapshots are optional
          debugPrint('Failed to save pricing snapshots: $e');
        }
      }

      // Save deployer config (Step 3 Section 2 data)
      if (state.deployerDigitalTwinName != null ||
          state.configEventsJson != null ||
          state.configIotDevicesJson != null) {
        await _api.updateDeployerConfig(twinId, {
          'deployer_digital_twin_name': state.deployerDigitalTwinName,
          'config_events_json': state.configEventsJson,
          'config_iot_devices_json': state.configIotDevicesJson,
          'config_json_validated': state.configJsonValidated,
          'config_events_validated': state.configEventsValidated,
          'config_iot_devices_validated': state.configIotDevicesValidated,
          // Section 3 L1
          'payloads_json': state.payloadsJson,
          'payloads_validated': state.payloadsValidated,
          // Section 3 L2
          'processor_contents': state.processorContents,
          'processor_validated': state.processorValidated,
          'processor_requirements': state.processorRequirements,
          'event_feedback_content': state.eventFeedbackContent,
          'event_feedback_validated': state.eventFeedbackValidated,
          'event_feedback_requirements': state.eventFeedbackRequirements,
          'event_action_contents': state.eventActionContents,
          'event_action_validated': state.eventActionValidated,
          'event_action_requirements': state.eventActionRequirements,
          'state_machine_content': state.stateMachineContent,
          'state_machine_validated': state.stateMachineValidated,
          // L4/L5 fields
          'hierarchy_content': state.hierarchyContent,
          'hierarchy_validated': state.hierarchyValidated,
          'scene_glb_uploaded': state.sceneGlbUploaded,
          'scene_config_content': state.sceneConfigContent,
          'scene_config_validated': state.sceneConfigValidated,
          'user_config_content': state.userConfigContent,
          'user_config_validated': state.userConfigValidated,
        });
      }

      emit(
        state.copyWith(
          status: WizardStatus.ready,
          twinId: twinId,
          hasUnsavedChanges: false,
          savedCalcResult:
              state.calcResult, // Update saved result on successful save
          savedCalcResultRaw: state.calcResultRaw, // Update saved raw result
          step3Invalidated: false, // Clear invalidation after save
          successMessage: 'Draft saved!',
        ),
      );
    } catch (e) {
      emit(
        state.copyWith(
          status: WizardStatus.ready,
          errorMessage: 'Save failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onFinish(WizardFinish event, Emitter<WizardState> emit) async {
    emit(state.copyWith(status: WizardStatus.saving));

    try {
      String? twinId = state.twinId;

      // Create twin if new
      if (state.mode == WizardMode.create && twinId == null) {
        if (state.twinName?.isEmpty ?? true) {
          emit(
            state.copyWith(
              status: WizardStatus.ready,
              errorMessage: 'Twin name is required',
            ),
          );
          return;
        }
        final result = await _api.createTwin(state.twinName!);
        twinId = result['id'];
      }

      // Build config payload
      final config = <String, dynamic>{'debug_mode': state.debugMode};
      if (state.aws.source == CredentialSource.newlyEntered) {
        config['aws'] = state.aws.values;
      }
      if (state.azure.source == CredentialSource.newlyEntered) {
        config['azure'] = state.azure.values;
      }
      if (state.gcp.source == CredentialSource.newlyEntered) {
        config['gcp'] = state.gcp.values;
      }
      if (state.calcParams != null) {
        config['optimizer_params'] = state.calcParams!.toJson();
      }
      if (state.calcResultRaw != null) {
        config['optimizer_result'] = state.calcResultRaw!['result'];
      }
      config['highest_step_reached'] = state.highestStepReached;

      await _api.updateTwinConfig(twinId!, config);

      // Save deployer config (Step 3 data) - mirrors _onSaveDraft logic
      await _api.updateDeployerConfig(twinId, {
        'deployer_digital_twin_name': state.deployerDigitalTwinName,
        'config_events_json': state.configEventsJson,
        'config_iot_devices_json': state.configIotDevicesJson,
        'config_json_validated': state.configJsonValidated,
        'config_events_validated': state.configEventsValidated,
        'config_iot_devices_validated': state.configIotDevicesValidated,
        // Section 3 L1
        'payloads_json': state.payloadsJson,
        'payloads_validated': state.payloadsValidated,
        // Section 3 L2
        'processor_contents': state.processorContents,
        'processor_validated': state.processorValidated,
        'processor_requirements': state.processorRequirements,
        'event_feedback_content': state.eventFeedbackContent,
        'event_feedback_validated': state.eventFeedbackValidated,
        'event_feedback_requirements': state.eventFeedbackRequirements,
        'event_action_contents': state.eventActionContents,
        'event_action_validated': state.eventActionValidated,
        'event_action_requirements': state.eventActionRequirements,
        'state_machine_content': state.stateMachineContent,
        'state_machine_validated': state.stateMachineValidated,
        // L4/L5 fields
        'hierarchy_content': state.hierarchyContent,
        'hierarchy_validated': state.hierarchyValidated,
        'scene_glb_uploaded': state.sceneGlbUploaded,
        'scene_config_content': state.sceneConfigContent,
        'scene_config_validated': state.sceneConfigValidated,
        'user_config_content': state.userConfigContent,
        'user_config_validated': state.userConfigValidated,
      });

      // Update twin state to 'configured' (Phase 1 requirement)
      await _api.updateTwin(twinId, state: 'configured');

      emit(
        state.copyWith(
          status: WizardStatus.ready,
          twinId: twinId,
          hasUnsavedChanges: false,
          // Return 'configured' to trigger navigation to overview page
          successMessage: 'configured',
        ),
      );
    } catch (e) {
      emit(
        state.copyWith(
          status: WizardStatus.ready,
          errorMessage:
              'Failed to finish: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  // ============================================================
  // UI FEEDBACK HANDLERS
  // ============================================================

  void _onClearNotifications(
    WizardClearNotifications event,
    Emitter<WizardState> emit,
  ) {
    emit(state.clearNotifications());
  }

  void _onDismissError(WizardDismissError event, Emitter<WizardState> emit) {
    emit(state.copyWith(clearError: true));
  }

  // ============================================================
  // STEP 3 INVALIDATION HANDLERS
  // ============================================================

  void _onProceedWithNewResults(
    WizardProceedWithNewResults event,
    Emitter<WizardState> emit,
  ) {
    // User chose to keep new calculation - clear Section 3 data explicitly
    emit(
      state.copyWith(
        step3Invalidated: false,
        // L1
        payloadsJson: null,
        payloadsValidated: false,
        // L2
        processorContents: const {},
        processorValidated: const {},
        eventFeedbackContent: null,
        eventFeedbackValidated: false,
        eventActionContents: const {},
        eventActionValidated: const {},
        stateMachineContent: null,
        stateMachineValidated: false,
      ),
    );
  }

  void _onRestoreOldResults(
    WizardRestoreOldResults event,
    Emitter<WizardState> emit,
  ) {
    // User chose to discard changes - revert to last saved calc result
    emit(
      state.copyWith(
        step3Invalidated: false,
        calcResult: state.savedCalcResult, // Visually revert to saved result
        calcResultRaw:
            state.savedCalcResultRaw, // Revert raw data for persistence
        hasUnsavedChanges: false,
        successMessage: 'Changes discarded',
      ),
    );
  }

  // Combined handlers to avoid race condition
  Future<void> _onProceedAndSave(
    WizardProceedAndSave event,
    Emitter<WizardState> emit,
  ) async {
    // Atomically: clear invalidation + clear Section 3 data (L1+L2) + save
    emit(
      state.copyWith(
        step3Invalidated: false,
        payloadsJson: null,
        payloadsValidated: false,
        processorContents: const {},
        processorValidated: const {},
        eventFeedbackContent: null,
        eventFeedbackValidated: false,
        eventActionContents: const {},
        eventActionValidated: const {},
        stateMachineContent: null,
        stateMachineValidated: false,
      ),
    );
    await _onSaveDraft(const WizardSaveDraft(), emit);
  }

  void _onProceedAndNext(
    WizardProceedAndNext event,
    Emitter<WizardState> emit,
  ) {
    // Atomically: clear invalidation + clear Section 3 data (L1+L2) + next
    emit(
      state.copyWith(
        step3Invalidated: false,
        payloadsJson: null,
        payloadsValidated: false,
        processorContents: const {},
        processorValidated: const {},
        eventFeedbackContent: null,
        eventFeedbackValidated: false,
        eventActionContents: const {},
        eventActionValidated: const {},
        stateMachineContent: null,
        stateMachineValidated: false,
      ),
    );
    _onNextStep(const WizardNextStep(), emit);
  }

  void _onClearInvalidation(
    WizardClearInvalidation event,
    Emitter<WizardState> emit,
  ) {
    // Clear invalidation and Section 3 data (L1+L2)
    emit(
      state.copyWith(
        step3Invalidated: false,
        payloadsJson: null,
        payloadsValidated: false,
        processorContents: const {},
        processorValidated: const {},
        eventFeedbackContent: null,
        eventFeedbackValidated: false,
        eventActionContents: const {},
        eventActionValidated: const {},
        stateMachineContent: null,
        stateMachineValidated: false,
        clearWarning: true,
      ),
    );
  }

  // ============================================================
  // STEP 3 SECTION 2: CONFIG FILE HANDLERS
  // ============================================================

  void _onConfigEventsChanged(
    WizardConfigEventsChanged event,
    Emitter<WizardState> emit,
  ) {
    // Reset all validation that depends on function names from config_events
    // Content is preserved - user just needs to revalidate after config change
    final resetEventActionValidated = state.eventActionValidated.map(
      (k, v) => MapEntry(k, false),
    );
    emit(
      state.copyWith(
        configEventsJson: event.content,
        configEventsValidated: false, // Reset validation on content change
        // CASCADE: Reset validation for dependent L2 content (keep content)
        eventActionValidated: resetEventActionValidated,
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onConfigIotDevicesChanged(
    WizardConfigIotDevicesChanged event,
    Emitter<WizardState> emit,
  ) {
    // Reset all validation that depends on device IDs from config_iot_devices
    // Content is preserved - user just needs to revalidate after config change
    final resetProcessorValidated = state.processorValidated.map(
      (k, v) => MapEntry(k, false),
    );
    emit(
      state.copyWith(
        configIotDevicesJson: event.content,
        configIotDevicesValidated: false, // Reset validation on content change
        // CASCADE: Reset validation for dependent L2 content (keep content)
        processorValidated: resetProcessorValidated,
        eventFeedbackValidated: false,
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onDeployerTwinNameChanged(
    WizardDeployerTwinNameChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      state.copyWith(
        deployerDigitalTwinName: event.name,
        configJsonValidated:
            false, // Reset validation when name changes (name is part of config.json)
        hasUnsavedChanges: true,
      ),
    );
  }

  Future<void> _onValidateDeployerConfig(
    WizardValidateDeployerConfig event,
    Emitter<WizardState> emit,
  ) async {
    final twinId = state.twinId;
    if (twinId == null) {
      emit(state.copyWith(errorMessage: 'No twin ID. Save draft first.'));
      return;
    }

    final configType = event.configType;
    final content = configType == 'events'
        ? state.configEventsJson
        : configType == 'iot'
        ? state.configIotDevicesJson
        : configType == 'payloads'
        ? state.payloadsJson
        : null;

    if (content == null || content.trim().isEmpty) {
      emit(state.copyWith(errorMessage: 'No content to validate.'));
      return;
    }

    try {
      final result = await _api.validateDeployerConfig(
        twinId,
        configType,
        content,
      );
      final valid = result['valid'] == true;
      final message =
          result['message']?.toString() ?? (valid ? 'Valid' : 'Invalid');

      if (configType == 'events') {
        emit(
          state.copyWith(
            configEventsValidated: valid,
            successMessage: valid ? message : null,
            errorMessage: valid ? null : message,
          ),
        );
      } else {
        emit(
          state.copyWith(
            configIotDevicesValidated: valid,
            successMessage: valid ? message : null,
            errorMessage: valid ? null : message,
          ),
        );
      }
    } catch (e) {
      emit(
        state.copyWith(
          errorMessage:
              'Validation failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  /// Handle validation result from widget (direct API call)
  void _onConfigValidationCompleted(
    WizardConfigValidationCompleted event,
    Emitter<WizardState> emit,
  ) {
    if (event.configType == 'config') {
      emit(state.copyWith(configJsonValidated: event.valid));
    } else if (event.configType == 'events') {
      emit(state.copyWith(configEventsValidated: event.valid));
    } else if (event.configType == 'iot') {
      emit(state.copyWith(configIotDevicesValidated: event.valid));
    } else if (event.configType == 'payloads') {
      emit(state.copyWith(payloadsValidated: event.valid));
    }
  }

  // ============================================================
  // STEP 3 SECTION 3: L1 PAYLOADS HANDLERS
  // ============================================================

  void _onPayloadsChanged(
    WizardPayloadsChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      state.copyWith(
        payloadsJson: event.content,
        payloadsValidated: false, // Reset validation on content change
        hasUnsavedChanges: true,
      ),
    );
  }

  // ============================================================
  // STEP 3 SECTION 3: L2 USER FUNCTION HANDLERS
  // ============================================================

  void _onProcessorContentChanged(
    WizardProcessorContentChanged event,
    Emitter<WizardState> emit,
  ) {
    final updated = Map<String, String>.from(state.processorContents);
    updated[event.deviceId] = event.content;
    final validationUpdated = Map<String, bool>.from(state.processorValidated);
    validationUpdated[event.deviceId] = false; // Clear validation on change
    emit(
      state.copyWith(
        processorContents: updated,
        processorValidated: validationUpdated,
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onEventFeedbackContentChanged(
    WizardEventFeedbackContentChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      state.copyWith(
        eventFeedbackContent: event.content,
        eventFeedbackValidated: false,
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onEventActionContentChanged(
    WizardEventActionContentChanged event,
    Emitter<WizardState> emit,
  ) {
    final updated = Map<String, String>.from(state.eventActionContents);
    updated[event.functionName] = event.content;
    final validationUpdated = Map<String, bool>.from(
      state.eventActionValidated,
    );
    validationUpdated[event.functionName] = false;
    emit(
      state.copyWith(
        eventActionContents: updated,
        eventActionValidated: validationUpdated,
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onStateMachineContentChanged(
    WizardStateMachineContentChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      state.copyWith(
        stateMachineContent: event.content,
        stateMachineValidated: false,
        hasUnsavedChanges: true,
      ),
    );
  }

  // ============================================================
  // STEP 3 SECTION 3: L2 REQUIREMENTS HANDLERS
  // ============================================================

  void _onProcessorRequirementsChanged(
    WizardProcessorRequirementsChanged event,
    Emitter<WizardState> emit,
  ) {
    final updated = Map<String, String>.from(state.processorRequirements);
    if (event.content == null || event.content!.isEmpty) {
      updated.remove(event.deviceId); // Remove from DB on save
    } else {
      updated[event.deviceId] = event.content!;
    }
    emit(
      state.copyWith(processorRequirements: updated, hasUnsavedChanges: true),
    );
  }

  void _onEventFeedbackRequirementsChanged(
    WizardEventFeedbackRequirementsChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      state.copyWith(
        eventFeedbackRequirements: event.content,
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onEventActionRequirementsChanged(
    WizardEventActionRequirementsChanged event,
    Emitter<WizardState> emit,
  ) {
    final updated = Map<String, String>.from(state.eventActionRequirements);
    if (event.content == null || event.content!.isEmpty) {
      updated.remove(event.functionName); // Remove from DB on save
    } else {
      updated[event.functionName] = event.content!;
    }
    emit(
      state.copyWith(eventActionRequirements: updated, hasUnsavedChanges: true),
    );
  }

  // ============================================================
  // STEP 3 SECTION 3: L2 VALIDATION HANDLERS
  // ============================================================

  void _onProcessorValidationCompleted(
    WizardProcessorValidationCompleted event,
    Emitter<WizardState> emit,
  ) {
    final updated = Map<String, bool>.from(state.processorValidated);
    updated[event.deviceId] = event.valid;
    emit(state.copyWith(processorValidated: updated));
  }

  void _onEventFeedbackValidationCompleted(
    WizardEventFeedbackValidationCompleted event,
    Emitter<WizardState> emit,
  ) {
    emit(state.copyWith(eventFeedbackValidated: event.valid));
  }

  void _onEventActionValidationCompleted(
    WizardEventActionValidationCompleted event,
    Emitter<WizardState> emit,
  ) {
    final updated = Map<String, bool>.from(state.eventActionValidated);
    updated[event.functionName] = event.valid;
    emit(state.copyWith(eventActionValidated: updated));
  }

  void _onStateMachineValidationCompleted(
    WizardStateMachineValidationCompleted event,
    Emitter<WizardState> emit,
  ) {
    emit(state.copyWith(stateMachineValidated: event.valid));
  }

  // ============================================================
  // STEP 3: L4 HIERARCHY HANDLERS
  // ============================================================

  void _onHierarchyContentChanged(
    WizardHierarchyContentChanged event,
    Emitter<WizardState> emit,
  ) {
    // Reset validation for dependent scene config (content preserved)
    emit(
      state.copyWith(
        hierarchyContent: event.content,
        hierarchyValidated: false, // Invalidate on content change
        // CASCADE: Reset scene config validation (content preserved)
        sceneConfigValidated: false,
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onHierarchyValidationCompleted(
    WizardHierarchyValidationCompleted event,
    Emitter<WizardState> emit,
  ) {
    emit(state.copyWith(hierarchyValidated: event.valid));
  }

  // ============================================================
  // STEP 3: L4 SCENE HANDLERS
  // ============================================================

  void _onSceneConfigContentChanged(
    WizardSceneConfigContentChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      state.copyWith(
        sceneConfigContent: event.content,
        sceneConfigValidated: false, // Invalidate on content change
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onSceneConfigValidationCompleted(
    WizardSceneConfigValidationCompleted event,
    Emitter<WizardState> emit,
  ) {
    emit(state.copyWith(sceneConfigValidated: event.valid));
  }

  void _onSceneGlbUploadStatusChanged(
    WizardSceneGlbUploadStatusChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      state.copyWith(sceneGlbUploaded: event.uploaded, hasUnsavedChanges: true),
    );
  }

  // ============================================================
  // STEP 3: L4/L5 USER CONFIG HANDLERS
  // ============================================================

  void _onUserConfigContentChanged(
    WizardUserConfigContentChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      state.copyWith(
        userConfigContent: event.content,
        userConfigValidated: false, // Invalidate on content change
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onUserConfigValidationCompleted(
    WizardUserConfigValidationCompleted event,
    Emitter<WizardState> emit,
  ) {
    emit(state.copyWith(userConfigValidated: event.valid));
  }

  // ============================================================
  // STEP 3: L4 CLEANUP HANDLER
  // ============================================================

  /// Handle L4 cleanup request - reset all L4 fields and delete GLB from server
  Future<void> _onL4CleanupRequested(
    WizardL4CleanupRequested event,
    Emitter<WizardState> emit,
  ) async {
    // Capture state BEFORE resetting (to avoid race condition)
    final wasGlbUploaded = state.sceneGlbUploaded;
    final twinId = state.twinId;

    // Reset all L4 state fields using clear flags for nullable content
    emit(
      state.copyWith(
        clearHierarchyContent: true, // Use clear flag instead of null
        hierarchyValidated: false,
        clearSceneConfigContent: true, // Use clear flag instead of null
        sceneConfigValidated: false,
        sceneGlbUploaded: false,
        hasUnsavedChanges: true,
      ),
    );

    // Delete GLB from server if twin exists and GLB was uploaded
    if (twinId != null && wasGlbUploaded) {
      try {
        await _api.deleteSceneGlb(twinId);
      } catch (e) {
        // Log error but don't fail - state is already reset
        // The server cleanup is best-effort
        // ignore: avoid_print
        print('[WizardBloc] GLB cleanup failed (best-effort): $e');
      }
    }
  }

  // ============================================================
  // STEP 3: ZIP UPLOAD HANDLERS
  // ============================================================

  /// Handle zip upload request - check if data exists and needs confirmation
  Future<void> _onZipUploadRequested(
    WizardZipUploadRequested event,
    Emitter<WizardState> emit,
  ) async {
    // If Step 3 already has data, emit state that triggers confirmation dialog
    if (state.hasSection3Data) {
      emit(
        state.copyWith(
          zipUploadPending: true,
          pendingZipFilePath: event.filePath,
          pendingZipFileBytes: event.fileBytes,
          pendingZipFileName: event.fileName,
        ),
      );
      return;
    }

    // No existing data - proceed directly with upload
    await _processZipUpload(event.fileBytes, event.fileName, emit);
  }

  /// Handle confirmed zip upload - user chose to replace existing data
  Future<void> _onZipUploadConfirmed(
    WizardZipUploadConfirmed event,
    Emitter<WizardState> emit,
  ) async {
    // Clear pending state
    emit(
      state.copyWith(
        zipUploadPending: false,
        clearPendingZipFilePath: true,
        clearPendingZipFileBytes: true,
        clearPendingZipFileName: true,
      ),
    );

    await _processZipUpload(event.fileBytes, event.fileName, emit);
  }

  /// Process the actual zip upload and populate fields
  Future<void> _processZipUpload(
    dynamic fileBytes,
    String fileName,
    Emitter<WizardState> emit,
  ) async {
    final twinId = state.twinId;
    if (twinId == null) {
      emit(
        state.copyWith(errorMessage: 'Save twin first before uploading zip'),
      );
      return;
    }

    emit(state.copyWith(zipUploadInProgress: true, clearError: true));

    try {
      final result = await _api.uploadProjectZip(twinId, fileBytes, fileName);

      final success = result['success'] as bool? ?? false;
      final errors = List<String>.from(result['validation_errors'] ?? []);
      final warnings = List<String>.from(result['warnings'] ?? []);
      final files = result['files'] as Map<String, dynamic>? ?? {};
      final functions = result['functions'] as Map<String, dynamic>? ?? {};
      final assets = result['assets'] as Map<String, dynamic>? ?? {};

      if (!success && errors.isNotEmpty) {
        // Show all validation errors
        emit(
          state.copyWith(
            zipUploadInProgress: false,
            errorMessage: 'Validation errors:\n${errors.join('\n')}',
            warningMessage: warnings.isNotEmpty ? warnings.join('\n') : null,
          ),
        );
        return;
      }

      // Populate fields from extraction result
      String? configEvents;
      String? configIotDevices;
      String? payloads;
      String? hierarchy;
      String? sceneConfig;
      String? userConfig;
      Map<String, String> processors = {};
      Map<String, String> eventActions = {};
      String? eventFeedback;
      bool glbUploaded = false;

      // Config files
      if (_fileHasContent(files['config_events.json'])) {
        configEvents = files['config_events.json']['content'];
      }
      if (_fileHasContent(files['config_iot_devices.json'])) {
        configIotDevices = files['config_iot_devices.json']['content'];
      }
      if (_fileHasContent(files['iot_device_simulator/payloads.json'])) {
        payloads = files['iot_device_simulator/payloads.json']['content'];
      }

      // Hierarchy (check both AWS and Azure format)
      if (_fileHasContent(files['twin_hierarchy/aws_hierarchy.json'])) {
        hierarchy = files['twin_hierarchy/aws_hierarchy.json']['content'];
      } else if (_fileHasContent(
        files['twin_hierarchy/azure_hierarchy.json'],
      )) {
        hierarchy = files['twin_hierarchy/azure_hierarchy.json']['content'];
      }

      // Scene config (provider-specific subdirectories)
      // AWS: scene_assets/aws/scene.json, Azure: scene_assets/azure/3DScenesConfiguration.json
      if (_fileHasContent(files['scene_assets/aws/scene.json'])) {
        sceneConfig = files['scene_assets/aws/scene.json']['content'];
      } else if (_fileHasContent(
        files['scene_assets/azure/3DScenesConfiguration.json'],
      )) {
        sceneConfig =
            files['scene_assets/azure/3DScenesConfiguration.json']['content'];
      }

      // User config
      if (_fileHasContent(files['config_user.json'])) {
        userConfig = files['config_user.json']['content'];
      }

      // Processors
      final processorMap =
          functions['processors'] as Map<String, dynamic>? ?? {};
      for (final entry in processorMap.entries) {
        if (_fileHasContent(entry.value)) {
          processors[entry.key] = entry.value['content'];
        }
      }

      // Event actions
      final actionMap =
          functions['event_actions'] as Map<String, dynamic>? ?? {};
      for (final entry in actionMap.entries) {
        if (_fileHasContent(entry.value)) {
          eventActions[entry.key] = entry.value['content'];
        }
      }

      // Event feedback
      if (_fileHasContent(functions['event_feedback'])) {
        eventFeedback = functions['event_feedback']['content'];
      }

      // State machine (check all provider formats)
      String? stateMachine;
      if (_fileHasContent(files['state_machines/aws_step_function.json'])) {
        stateMachine =
            files['state_machines/aws_step_function.json']['content'];
      } else if (_fileHasContent(
        files['state_machines/azure_logic_app.json'],
      )) {
        stateMachine = files['state_machines/azure_logic_app.json']['content'];
      } else if (_fileHasContent(
        files['state_machines/google_cloud_workflow.yaml'],
      )) {
        stateMachine =
            files['state_machines/google_cloud_workflow.yaml']['content'];
      }

      // GLB (already saved by Management API)
      if (assets['scene_glb'] != null) {
        final glbData = assets['scene_glb'] as Map<String, dynamic>;
        glbUploaded = glbData['exists'] == true && glbData['saved'] == true;
      }

      // Build validation maps from backend validation status
      // A file is valid if it exists, has content, and has no validation_error
      bool isFileValid(dynamic file) {
        if (file == null) return false;
        if (file is! Map<String, dynamic>) return false;
        return file['exists'] == true &&
            file['content'] != null &&
            file['validation_error'] == null;
      }

      // Build processor validation map
      Map<String, bool> processorValidation = {};
      for (final entry in processorMap.entries) {
        processorValidation[entry.key] = isFileValid(entry.value);
      }

      // Build event action validation map
      Map<String, bool> eventActionValidation = {};
      for (final entry in actionMap.entries) {
        eventActionValidation[entry.key] = isFileValid(entry.value);
      }

      // Compute validation flags for the individual files
      final configJsonValid = isFileValid(files['config.json']);
      final eventsValid = isFileValid(files['config_events.json']);
      final iotDevicesValid = isFileValid(files['config_iot_devices.json']);
      final payloadsValid = isFileValid(
        files['iot_device_simulator/payloads.json'],
      );
      final hierarchyValid =
          isFileValid(files['twin_hierarchy/aws_hierarchy.json']) ||
          isFileValid(files['twin_hierarchy/azure_hierarchy.json']);
      final sceneConfigValid =
          isFileValid(files['scene_assets/aws/scene.json']) ||
          isFileValid(files['scene_assets/azure/3DScenesConfiguration.json']);
      final userConfigValid = isFileValid(files['config_user.json']);
      final stateMachineValid =
          isFileValid(files['state_machines/aws_step_function.json']) ||
          isFileValid(files['state_machines/azure_logic_app.json']) ||
          isFileValid(files['state_machines/google_cloud_workflow.yaml']);
      final eventFeedbackValid = isFileValid(functions['event_feedback']);

      // Update state with extracted content AND validation status
      final newState = state.copyWith(
        zipUploadInProgress: false,
        configEventsJson: configEvents,
        configIotDevicesJson: configIotDevices,
        payloadsJson: payloads,
        hierarchyContent: hierarchy,
        sceneConfigContent: sceneConfig,
        userConfigContent: userConfig,
        stateMachineContent: stateMachine,
        processorContents: processors.isNotEmpty
            ? processors
            : state.processorContents,
        eventActionContents: eventActions.isNotEmpty
            ? eventActions
            : state.eventActionContents,
        eventFeedbackContent: eventFeedback,
        sceneGlbUploaded: glbUploaded,
        hasUnsavedChanges: true,
        successMessage:
            'Zip extracted! ${_countExtracted(files, functions, assets)} items populated.',
        warningMessage: warnings.isNotEmpty ? warnings.join('\n') : null,
        // Set validation based on backend validation status
        configJsonValidated: configJsonValid,
        configEventsValidated: eventsValid,
        configIotDevicesValidated: iotDevicesValid,
        payloadsValidated: payloadsValid,
        hierarchyValidated: hierarchyValid,
        sceneConfigValidated: sceneConfigValid,
        userConfigValidated: userConfigValid,
        stateMachineValidated: stateMachineValid,
        processorValidated: processorValidation.isNotEmpty
            ? processorValidation
            : state.processorValidated,
        eventActionValidated: eventActionValidation.isNotEmpty
            ? eventActionValidation
            : state.eventActionValidated,
        eventFeedbackValidated: eventFeedbackValid,
      );
      emit(newState);

      // P2-2 Fix: Use the state getters (which have proper conditional logic)
      // to determine if all required fields are valid
      final allSectionsValid =
          newState.isSection2Valid && newState.isSection3Valid;

      // DEBUG: Log validation state to understand why collapse might not trigger
      debugPrint('=== ZIP UPLOAD VALIDATION DEBUG ===');
      debugPrint('Section 2 Valid: ${newState.isSection2Valid}');
      debugPrint('  - configJsonValidated: ${newState.configJsonValidated}');
      debugPrint(
        '  - configEventsValidated: ${newState.configEventsValidated}',
      );
      debugPrint(
        '  - configIotDevicesValidated: ${newState.configIotDevicesValidated}',
      );
      debugPrint('  - hierarchyValidated: ${newState.hierarchyValidated}');
      debugPrint('  - L4 provider: ${newState.layer4Provider}');
      debugPrint('Section 3 Valid: ${newState.isSection3Valid}');
      debugPrint('  - payloadsValidated: ${newState.payloadsValidated}');
      debugPrint('  - processorValidated: ${newState.processorValidated}');
      debugPrint('  - deviceIds: ${newState.deviceIds}');
      debugPrint(
        '  - calcParams.returnFeedbackToDevice: ${newState.calcParams?.returnFeedbackToDevice}',
      );
      debugPrint(
        '  - eventFeedbackValidated: ${newState.eventFeedbackValidated}',
      );
      debugPrint(
        '  - calcParams.useEventChecking: ${newState.calcParams?.useEventChecking}',
      );
      debugPrint('  - eventActionValidated: ${newState.eventActionValidated}');
      debugPrint(
        '  - calcParams.triggerNotificationWorkflow: ${newState.calcParams?.triggerNotificationWorkflow}',
      );
      debugPrint(
        '  - stateMachineValidated: ${newState.stateMachineValidated}',
      );
      debugPrint(
        '  - calcParams.needs3DModel: ${newState.calcParams?.needs3DModel}',
      );
      debugPrint('  - sceneConfigValidated: ${newState.sceneConfigValidated}');
      debugPrint('  - L5 provider: ${newState.layer5Provider}');
      debugPrint('  - userConfigValidated: ${newState.userConfigValidated}');
      debugPrint('All sections valid: $allSectionsValid');
      debugPrint('===================================');

      // P2-1 Fix: If all valid, trigger collapse then immediately reset
      // This ensures the flag transitions from false→true→false, allowing
      // the UI widgets to detect the change and collapse
      if (allSectionsValid) {
        // P3-1: Brief delay so users see validation checkmarks before collapse
        await Future.delayed(const Duration(milliseconds: 400));
        emit(newState.copyWith(forceCollapseSections: true));
        // Wait one frame so the UI widget's didUpdateWidget sees the true state
        await Future.delayed(const Duration(milliseconds: 50));
        // Reset so subsequent uploads can trigger again
        emit(newState.copyWith(forceCollapseSections: false));
      }
    } catch (e) {
      emit(
        state.copyWith(
          zipUploadInProgress: false,
          errorMessage: 'Upload failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  /// Helper to check if a file result has extractable content
  bool _fileHasContent(dynamic file) {
    if (file == null) return false;
    if (file is! Map<String, dynamic>) return false;
    return file['exists'] == true && file['content'] != null;
  }

  /// Count how many items were extracted for success message
  String _countExtracted(
    Map<String, dynamic> files,
    Map<String, dynamic> functions,
    Map<String, dynamic> assets,
  ) {
    int count = 0;
    files.forEach((k, v) {
      if (_fileHasContent(v)) count++;
    });
    (functions['processors'] as Map<String, dynamic>?)?.forEach((k, v) {
      if (_fileHasContent(v)) count++;
    });
    (functions['event_actions'] as Map<String, dynamic>?)?.forEach((k, v) {
      if (_fileHasContent(v)) count++;
    });
    if (_fileHasContent(functions['event_feedback'])) count++;
    if (assets['scene_glb']?['saved'] == true) count++;
    return count.toString();
  }
}
