// lib/bloc/wizard/wizard_bloc.dart
// BLoC for wizard state machine
// Refactored to use service extraction pattern for testability

import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../models/calc_result.dart';
import '../../models/cloud_connection.dart';
import '../../models/deployer_artifact_validation.dart';
import '../../services/api_service.dart';
import '../../utils/api_error_handler.dart';
import 'wizard_event.dart';
import 'wizard_state.dart';
import 'helpers/helpers.dart';
import 'services/wizard_glb_cleanup_service.dart';
import 'services/wizard_deployer_validation_service.dart';
import 'services/wizard_init_service.dart';
import 'services/wizard_zip_service.dart';

/// WizardBloc - State machine for the multi-step wizard
///
/// Manages:
/// - Step navigation with validation gates
/// - Transient UI state (notifications) that clear on step change
/// - Persistent data (credentials, calc results) that survives navigation
/// - Create vs Edit mode distinction
class WizardBloc extends Bloc<WizardEvent, WizardState> {
  final WizardInitService _initService;
  final WizardZipService _zipService;
  final WizardGlbCleanupService _glbCleanupService;
  final WizardDeployerValidationService _deployerValidationService;
  final ApiService _api;

  WizardBloc({
    required ApiService api,
    WizardInitService? initService,
    WizardZipService? zipService,
    WizardGlbCleanupService? glbCleanupService,
  }) : _api = api,
       _initService = initService ?? WizardInitService(),
       _zipService = zipService ?? WizardZipService(),
       _glbCleanupService =
           glbCleanupService ?? WizardGlbCleanupService(api: api),
       _deployerValidationService = WizardDeployerValidationService(api: api),
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
    on<WizardCloudConnectionsLoadRequested>(_onCloudConnectionsLoadRequested);
    on<WizardCloudConnectionSelected>(_onCloudConnectionSelected);
    on<WizardCloudConnectionCreateRequested>(_onCloudConnectionCreateRequested);
    on<WizardCloudConnectionValidateRequested>(
      _onCloudConnectionValidateRequested,
    );
    on<WizardCloudConnectionUnbound>(_onCloudConnectionUnbound);
    on<WizardCloudConnectionDeleteRequested>(_onCloudConnectionDeleteRequested);

    // === Step 2: Optimizer ===
    on<WizardPricingHealthLoadRequested>(_onPricingHealthLoadRequested);
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
    on<WizardArtifactValidationRequested>(_onArtifactValidationRequested);
    on<WizardDeployerTwinNameChanged>(_onDeployerTwinNameChanged);
    on<WizardConfigEventsChanged>(_onConfigEventsChanged);
    on<WizardConfigIotDevicesChanged>(_onConfigIotDevicesChanged);

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

    // === Step 3: L4 Hierarchy ===
    on<WizardHierarchyContentChanged>(_onHierarchyContentChanged);

    // === Step 3: L4 Scene ===
    on<WizardSceneConfigContentChanged>(_onSceneConfigContentChanged);
    on<WizardSceneGlbUploadStatusChanged>(_onSceneGlbUploadStatusChanged);

    // === Step 3: L4/L5 User Config ===
    on<WizardUserConfigContentChanged>(_onUserConfigContentChanged);

    // === Step 3: L4 Cleanup ===
    on<WizardL4CleanupRequested>(_onL4CleanupRequested);

    // === Step 3: Zip Upload ===
    on<WizardZipUploadRequested>(_onZipUploadRequested);
    on<WizardZipUploadConfirmed>(_onZipUploadConfirmed);
  }

  // ============================================================
  // INITIALIZATION HANDLERS - Delegated to WizardInitService
  // ============================================================

  Future<void> _onInitCreate(
    WizardInitCreate event,
    Emitter<WizardState> emit,
  ) async {
    emit(_initService.initializeCreateMode());
    await _loadCloudConnections(emit);
  }

  Future<void> _onInitEdit(
    WizardInitEdit event,
    Emitter<WizardState> emit,
  ) async {
    emit(state.copyWith(status: WizardStatus.loading));

    try {
      // Fetch data from API (BLoC owns API calls)
      final twin = await _api.getTwin(event.twinId);
      final config = await _api.getTwinConfig(event.twinId);

      // Fetch deployer config separately (may not exist yet)
      DeployerConfigData? deployerConfig;
      try {
        final deployerJson = await _api.getDeployerConfig(event.twinId);
        deployerConfig = DeployerConfigData.fromJson(deployerJson);
      } catch (e) {
        // No deployer config yet, that's fine
      }

      // Pass to stateless service for state construction
      final result = _initService.initializeEditMode(
        twinId: event.twinId,
        data: TwinEditData(
          twin: twin,
          config: config,
          deployerConfig: deployerConfig,
        ),
      );
      emit(result.state);
      await _loadCloudConnections(emit);
    } catch (e) {
      debugPrint(
        '[WizardBloc] Failed to load twin: ${ApiErrorHandler.extractMessage(e)}',
      );
      emit(
        state.copyWith(
          status: WizardStatus.error,
          errorMessage:
              'Failed to load twin: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onCloudConnectionsLoadRequested(
    WizardCloudConnectionsLoadRequested event,
    Emitter<WizardState> emit,
  ) async {
    await _loadCloudConnections(emit);
  }

  Future<void> _loadCloudConnections(Emitter<WizardState> emit) async {
    final loading = {
      for (final provider in CloudProvider.values) provider: true,
    };
    emit(
      state.copyWith(
        cloudConnectionLoading: loading,
        cloudConnectionErrors: const {},
      ),
    );

    try {
      final connections = await _api.listCloudConnections();
      final grouped = <CloudProvider, List<CloudConnection>>{
        for (final provider in CloudProvider.values)
          provider: connections
              .where((connection) => connection.provider == provider)
              .toList(growable: false),
      };
      emit(
        state.copyWith(
          cloudConnections: grouped,
          cloudConnectionLoading: {
            for (final provider in CloudProvider.values) provider: false,
          },
          cloudConnectionErrors: const {},
        ),
      );
    } catch (e) {
      final message = ApiErrorHandler.extractMessage(e);
      emit(
        state.copyWith(
          cloudConnectionLoading: {
            for (final provider in CloudProvider.values) provider: false,
          },
          cloudConnectionErrors: {
            for (final provider in CloudProvider.values) provider: message,
          },
        ),
      );
    }
  }

  void _onCloudConnectionSelected(
    WizardCloudConnectionSelected event,
    Emitter<WizardState> emit,
  ) {
    final selected = Map<CloudProvider, String?>.from(
      state.selectedCloudConnectionIds,
    );
    selected[event.provider] = event.connectionId;

    final validation =
        Map<CloudProvider, CloudConnectionValidationResult?>.from(
          state.cloudConnectionValidation,
        );
    validation.remove(event.provider);

    emit(
      state.copyWith(
        selectedCloudConnectionIds: selected,
        cloudConnectionValidation: validation,
        hasUnsavedChanges: true,
      ),
    );
  }

  Future<void> _onCloudConnectionCreateRequested(
    WizardCloudConnectionCreateRequested event,
    Emitter<WizardState> emit,
  ) async {
    emit(_providerLoadingState(event.provider, true));

    try {
      final created = await _api.createCloudConnection(event.request);
      final connections = Map<CloudProvider, List<CloudConnection>>.from(
        state.cloudConnections,
      );
      final providerConnections = [
        ...(connections[event.provider] ?? const <CloudConnection>[]),
        created,
      ];
      connections[event.provider] = providerConnections;

      final selected = Map<CloudProvider, String?>.from(
        state.selectedCloudConnectionIds,
      );
      selected[event.provider] = created.id;

      emit(
        _providerLoadingState(event.provider, false).copyWith(
          cloudConnections: connections,
          selectedCloudConnectionIds: selected,
          hasUnsavedChanges: true,
          successMessage: 'Cloud connection created',
          clearError: true,
        ),
      );
    } catch (e) {
      emit(
        _providerLoadingState(event.provider, false).copyWith(
          cloudConnectionErrors: _providerErrorMap(
            event.provider,
            ApiErrorHandler.extractMessage(e),
          ),
        ),
      );
    }
  }

  Future<void> _onCloudConnectionValidateRequested(
    WizardCloudConnectionValidateRequested event,
    Emitter<WizardState> emit,
  ) async {
    emit(_providerLoadingState(event.provider, true));

    try {
      final result = await _api.validateCloudConnection(event.connectionId);
      final validation =
          Map<CloudProvider, CloudConnectionValidationResult?>.from(
            state.cloudConnectionValidation,
          );
      validation[event.provider] = result;

      final connections = _replaceCloudConnectionValidationStatus(
        provider: event.provider,
        connectionId: event.connectionId,
        result: result,
      );

      emit(
        _providerLoadingState(event.provider, false).copyWith(
          cloudConnectionValidation: validation,
          cloudConnections: connections,
          clearError: true,
        ),
      );
    } catch (e) {
      emit(
        _providerLoadingState(event.provider, false).copyWith(
          cloudConnectionErrors: _providerErrorMap(
            event.provider,
            ApiErrorHandler.extractMessage(e),
          ),
        ),
      );
    }
  }

  void _onCloudConnectionUnbound(
    WizardCloudConnectionUnbound event,
    Emitter<WizardState> emit,
  ) {
    final selected = Map<CloudProvider, String?>.from(
      state.selectedCloudConnectionIds,
    );
    selected[event.provider] = null;

    emit(
      state.copyWith(
        selectedCloudConnectionIds: selected,
        hasUnsavedChanges: true,
      ),
    );
  }

  Future<void> _onCloudConnectionDeleteRequested(
    WizardCloudConnectionDeleteRequested event,
    Emitter<WizardState> emit,
  ) async {
    emit(_providerLoadingState(event.provider, true));

    try {
      await _api.deleteCloudConnection(event.connectionId);
      final connections = Map<CloudProvider, List<CloudConnection>>.from(
        state.cloudConnections,
      );
      connections[event.provider] = [
        ...(connections[event.provider] ?? const <CloudConnection>[]),
      ].where((connection) => connection.id != event.connectionId).toList();

      final selected = Map<CloudProvider, String?>.from(
        state.selectedCloudConnectionIds,
      );
      if (selected[event.provider] == event.connectionId) {
        selected[event.provider] = null;
      }

      emit(
        _providerLoadingState(event.provider, false).copyWith(
          cloudConnections: connections,
          selectedCloudConnectionIds: selected,
          successMessage: 'Cloud connection deleted',
        ),
      );
    } catch (e) {
      emit(
        _providerLoadingState(event.provider, false).copyWith(
          cloudConnectionErrors: _providerErrorMap(
            event.provider,
            ApiErrorHandler.extractMessage(e),
          ),
        ),
      );
    }
  }

  WizardState _providerLoadingState(CloudProvider provider, bool loading) {
    final loadingMap = Map<CloudProvider, bool>.from(
      state.cloudConnectionLoading,
    );
    loadingMap[provider] = loading;
    final errorMap = Map<CloudProvider, String?>.from(
      state.cloudConnectionErrors,
    );
    if (loading) {
      errorMap[provider] = null;
    }
    return state.copyWith(
      cloudConnectionLoading: loadingMap,
      cloudConnectionErrors: errorMap,
    );
  }

  Map<CloudProvider, String?> _providerErrorMap(
    CloudProvider provider,
    String message,
  ) {
    final errors = Map<CloudProvider, String?>.from(
      state.cloudConnectionErrors,
    );
    errors[provider] = message;
    return errors;
  }

  Map<CloudProvider, List<CloudConnection>>
  _replaceCloudConnectionValidationStatus({
    required CloudProvider provider,
    required String connectionId,
    required CloudConnectionValidationResult result,
  }) {
    final connections = Map<CloudProvider, List<CloudConnection>>.from(
      state.cloudConnections,
    );
    connections[provider] = [
      for (final connection
          in connections[provider] ?? const <CloudConnection>[])
        if (connection.id == connectionId)
          CloudConnection(
            id: connection.id,
            provider: connection.provider,
            displayName: connection.displayName,
            authType: connection.authType,
            cloudScope: connection.cloudScope,
            payloadFingerprint: connection.payloadFingerprint,
            payloadSummary: connection.payloadSummary,
            validationStatus: result.validationStatus,
            validationMessage: result.message,
            lastValidatedAt: DateTime.now(),
            createdAt: connection.createdAt,
            updatedAt: connection.updatedAt,
          )
        else
          connection,
    ];
    return connections;
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

  Future<void> _onPricingHealthLoadRequested(
    WizardPricingHealthLoadRequested event,
    Emitter<WizardState> emit,
  ) async {
    if (state.isPricingHealthLoading) return;
    emit(
      state.copyWith(
        isPricingHealthLoading: true,
        clearPricingHealthError: true,
      ),
    );
    try {
      final health = await _api.getPricingHealth();
      emit(
        state.copyWith(
          pricingHealth: health,
          isPricingHealthLoading: false,
          clearPricingHealthError: true,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          isPricingHealthLoading: false,
          pricingHealthError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

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
    if (!state.pricingCanCalculate) {
      emit(
        state.copyWith(
          errorMessage:
              'Pricing data is not ready for calculation. Retry pricing readiness.',
        ),
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
      debugPrint(
        '[WizardBloc] Calculation failed: ${ApiErrorHandler.extractMessage(e)}',
      );
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

  bool _shouldPersistDeployerConfig() {
    return WizardConfigRequestBuilder.shouldPersistDeployerConfig(state);
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

      // Save config and capture response for state sync
      final configResponse = await _api.updateTwinConfigRequest(
        twinId!,
        WizardConfigRequestBuilder.buildTwinConfigRequest(state),
      );

      // Track if state was regressed by backend
      final String? newTwinState = configResponse['twin_state'] as String?;
      final bool stateRegressed =
          newTwinState != null &&
          newTwinState != state.twinState &&
          newTwinState == 'draft';

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

      // Save all Step 3 data once the user reached the deployer step.
      if (_shouldPersistDeployerConfig()) {
        await _api.updateDeployerConfigRequest(
          twinId,
          WizardConfigRequestBuilder.buildDeployerConfigRequest(state),
        );
      }

      emit(
        state.copyWith(
          status: WizardStatus.ready,
          twinId: twinId,
          twinState: newTwinState ?? state.twinState, // Sync state from backend
          hasUnsavedChanges: false,
          savedCalcResult:
              state.calcResult, // Update saved result on successful save
          savedCalcResultRaw: state.calcResultRaw, // Update saved raw result
          step3Invalidated: false, // Clear invalidation after save
          successMessage: stateRegressed
              ? 'Saved. Configuration reverted to draft.'
              : 'Draft saved!',
        ),
      );
    } catch (e) {
      debugPrint(
        '[WizardBloc] Save failed: ${ApiErrorHandler.extractMessage(e)}',
      );
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

      await _api.updateTwinConfigRequest(
        twinId!,
        WizardConfigRequestBuilder.buildTwinConfigRequest(state),
      );

      // Save deployer config (Step 3 data) - mirrors _onSaveDraft logic
      await _api.updateDeployerConfigRequest(
        twinId,
        WizardConfigRequestBuilder.buildDeployerConfigRequest(state),
      );

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
      debugPrint(
        '[WizardBloc] Finish failed: ${ApiErrorHandler.extractMessage(e)}',
      );
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

  Future<void> _onArtifactValidationRequested(
    WizardArtifactValidationRequested event,
    Emitter<WizardState> emit,
  ) async {
    final request = event.request;
    final artifactId = request.artifactId;
    if (state.isArtifactValidating(artifactId)) return;

    final requestError = request.validationError;
    if (requestError != null) {
      emit(
        _applyArtifactValidation(
          _withArtifactFeedback(
            state,
            artifactId,
            DeployerArtifactValidationFeedback(
              valid: false,
              message: requestError,
            ),
          ),
          request,
          false,
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        validatingArtifactIds: {...state.validatingArtifactIds, artifactId},
        artifactValidationFeedback: state.feedbackWithout(artifactId),
      ),
    );

    try {
      final result = switch (request.boundary) {
        DeployerValidationBoundary.config =>
          await _deployerValidationService.validateConfigFile(
            twinId: state.twinId,
            configType: request.validationType,
            content: request.content,
          ),
        DeployerValidationBoundary.layer2 =>
          await _deployerValidationService.validateL2Content(
            twinId: state.twinId,
            provider: request.provider,
            type: request.validationType,
            content: request.content,
          ),
        DeployerValidationBoundary.layer4Or5 =>
          await _deployerValidationService.validateL4Content(
            twinId: state.twinId,
            provider: request.provider,
            type: request.validationType,
            content: request.content,
          ),
      };

      // Content-change handlers remove the busy marker. Ignore a result for
      // content that changed while the request was in flight.
      if (!state.isArtifactValidating(artifactId)) return;

      final feedback = DeployerArtifactValidationFeedback(
        valid: result.valid,
        message: result.message,
      );
      emit(
        _applyArtifactValidation(
          _withArtifactFeedback(state, artifactId, feedback),
          request,
          result.valid,
        ),
      );
    } catch (error) {
      if (!state.isArtifactValidating(artifactId)) return;
      emit(
        _applyArtifactValidation(
          _withArtifactFeedback(
            state,
            artifactId,
            DeployerArtifactValidationFeedback(
              valid: false,
              message: ApiErrorHandler.extractMessage(error),
            ),
          ),
          request,
          false,
        ),
      );
    }
  }

  WizardState _withArtifactFeedback(
    WizardState current,
    String artifactId,
    DeployerArtifactValidationFeedback feedback,
  ) {
    final busy = Set<String>.from(current.validatingArtifactIds)
      ..remove(artifactId);
    return current.copyWith(
      validatingArtifactIds: busy,
      artifactValidationFeedback: {
        ...current.artifactValidationFeedback,
        artifactId: feedback,
      },
    );
  }

  WizardState _applyArtifactValidation(
    WizardState current,
    DeployerArtifactValidationRequest request,
    bool valid,
  ) => switch (request.type) {
    DeployerArtifactType.config => current.copyWith(configJsonValidated: valid),
    DeployerArtifactType.events => current.copyWith(
      configEventsValidated: valid,
    ),
    DeployerArtifactType.iotDevices => current.copyWith(
      configIotDevicesValidated: valid,
    ),
    DeployerArtifactType.payloads => current.copyWith(payloadsValidated: valid),
    DeployerArtifactType.processor => current.copyWith(
      processorValidated: {
        ...current.processorValidated,
        request.entityId!: valid,
      },
    ),
    DeployerArtifactType.eventFeedback => current.copyWith(
      eventFeedbackValidated: valid,
    ),
    DeployerArtifactType.eventAction => current.copyWith(
      eventActionValidated: {
        ...current.eventActionValidated,
        request.entityId!: valid,
      },
    ),
    DeployerArtifactType.stateMachine => current.copyWith(
      stateMachineValidated: valid,
    ),
    DeployerArtifactType.hierarchy => current.copyWith(
      hierarchyValidated: valid,
    ),
    DeployerArtifactType.sceneConfig => current.copyWith(
      sceneConfigValidated: valid,
    ),
    DeployerArtifactType.userConfig => current.copyWith(
      userConfigValidated: valid,
    ),
  };

  WizardState _clearArtifactValidationState(
    WizardState current, {
    Set<String> artifactIds = const {},
    Set<String> artifactPrefixes = const {},
  }) {
    bool matches(String id) =>
        artifactIds.contains(id) ||
        artifactPrefixes.any((prefix) => id.startsWith(prefix));
    return current.copyWith(
      validatingArtifactIds: current.validatingArtifactIds
          .where((id) => !matches(id))
          .toSet(),
      artifactValidationFeedback: Map.fromEntries(
        current.artifactValidationFeedback.entries.where(
          (entry) => !matches(entry.key),
        ),
      ),
    );
  }

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
      _clearArtifactValidationState(
        state,
        artifactIds: const {'config:events'},
        artifactPrefixes: const {'event-action:'},
      ).copyWith(
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
      _clearArtifactValidationState(
        state,
        artifactIds: const {'config:iot-devices', 'event-feedback'},
        artifactPrefixes: const {'processor:'},
      ).copyWith(
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
      _clearArtifactValidationState(
        state,
        artifactIds: const {'config:core'},
      ).copyWith(
        deployerDigitalTwinName: event.name,
        configJsonValidated:
            false, // Reset validation when name changes (name is part of config.json)
        hasUnsavedChanges: true,
      ),
    );
  }

  // ============================================================
  // STEP 3 SECTION 3: L1 PAYLOADS HANDLERS
  // ============================================================

  void _onPayloadsChanged(
    WizardPayloadsChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      _clearArtifactValidationState(
        state,
        artifactIds: const {'payloads'},
      ).copyWith(
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
      _clearArtifactValidationState(
        state,
        artifactIds: {'processor:${event.deviceId}'},
      ).copyWith(
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
      _clearArtifactValidationState(
        state,
        artifactIds: const {'event-feedback'},
      ).copyWith(
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
      _clearArtifactValidationState(
        state,
        artifactIds: {'event-action:${event.functionName}'},
      ).copyWith(
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
      _clearArtifactValidationState(
        state,
        artifactIds: const {'state-machine'},
      ).copyWith(
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
      _clearArtifactValidationState(
        state,
        artifactIds: const {'hierarchy', 'scene-config'},
      ).copyWith(
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
  // STEP 3: L4 HIERARCHY HANDLERS
  // ============================================================

  void _onHierarchyContentChanged(
    WizardHierarchyContentChanged event,
    Emitter<WizardState> emit,
  ) {
    // Reset validation for dependent scene config (content preserved)
    emit(
      _clearArtifactValidationState(
        state,
        artifactIds: const {'scene-config'},
      ).copyWith(
        hierarchyContent: event.content,
        hierarchyValidated: false, // Invalidate on content change
        // CASCADE: Reset scene config validation (content preserved)
        sceneConfigValidated: false,
        hasUnsavedChanges: true,
      ),
    );
  }

  // ============================================================
  // STEP 3: L4 SCENE HANDLERS
  // ============================================================

  void _onSceneConfigContentChanged(
    WizardSceneConfigContentChanged event,
    Emitter<WizardState> emit,
  ) {
    emit(
      _clearArtifactValidationState(
        state,
        artifactIds: const {'user-config'},
      ).copyWith(
        sceneConfigContent: event.content,
        sceneConfigValidated: false, // Invalidate on content change
        hasUnsavedChanges: true,
      ),
    );
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

    await _glbCleanupService.deleteUploadedGlb(
      twinId: twinId,
      wasUploaded: wasGlbUploaded,
    );
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
  ///
  /// Delegates to WizardZipService for the heavy lifting.
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
      // Call API to upload and parse zip
      final result = await _api.uploadProjectZip(twinId, fileBytes, fileName);

      // Delegate to service for processing
      final processingResult = _zipService.processZipUpload(
        state: state,
        apiResult: result,
      );
      emit(processingResult.state);

      // Handle section collapse if all sections are valid
      if (processingResult.shouldTriggerCollapse) {
        // P3-1: Brief delay so users see validation checkmarks before collapse
        await Future.delayed(const Duration(milliseconds: 400));
        emit(processingResult.state.copyWith(forceCollapseSections: true));
        // Wait one frame so the UI widget's didUpdateWidget sees the true state
        await Future.delayed(const Duration(milliseconds: 50));
        // Reset so subsequent uploads can trigger again
        emit(processingResult.state.copyWith(forceCollapseSections: false));
      }
    } catch (e) {
      debugPrint(
        '[WizardBloc] Upload failed: ${ApiErrorHandler.extractMessage(e)}',
      );
      emit(
        state.copyWith(
          zipUploadInProgress: false,
          errorMessage: 'Upload failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }
}
