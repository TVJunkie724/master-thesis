part of '../wizard_bloc.dart';

extension _WizardOptimizationPersistenceHandlers on WizardBloc {
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
              errorMessage: 'Enter a twin name before continuing',
            ),
          );
          return;
        }
        break;
      case 1:
        if (!state.canProceedToStep3) {
          emit(
            newState.copyWith(
              errorMessage:
                  'Calculate and verify the deployment selection before proceeding',
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
    CalcParams? snapshotCalcParams;
    OptimizationResultData? snapshotOptimizationResultData;
    OptimizerDeploymentRunData? snapshotDeploymentRun;
    if (state.currentStep == 1 &&
        nextStep == 2 &&
        state.savedCalcResult == null) {
      snapshotCalcResult = state.calcResult;
      snapshotCalcParams = state.calcParams;
      snapshotOptimizationResultData = state.optimizationResultData;
      snapshotDeploymentRun = state.deploymentRun;
    }

    emit(
      newState.copyWith(
        currentStep: nextStep,
        highestStepReached: nextStep > state.highestStepReached
            ? nextStep
            : state.highestStepReached,
        savedCalcResult: snapshotCalcResult,
        savedCalcParams: snapshotCalcParams,
        savedOptimizationResultData: snapshotOptimizationResultData,
        savedDeploymentRun: snapshotDeploymentRun,
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
    final reachable = switch (event.step) {
      0 => true,
      1 => state.twinName?.trim().isNotEmpty == true,
      2 => state.canProceedToStep3,
      _ => false,
    };
    if (!reachable) return;

    final enteringDeployment =
        event.step == 2 &&
        state.currentStep != 2 &&
        state.savedCalcResult == null;
    emit(
      state.clearNotifications().copyWith(
        currentStep: event.step,
        highestStepReached: event.step > state.highestStepReached
            ? event.step
            : state.highestStepReached,
        savedCalcParams: enteringDeployment ? state.calcParams : null,
        savedCalcResult: enteringDeployment ? state.calcResult : null,
        savedOptimizationResultData: enteringDeployment
            ? state.optimizationResultData
            : null,
        savedDeploymentRun: enteringDeployment ? state.deploymentRun : null,
      ),
    );
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
    final inputsChanged =
        state.calcParams?.hasSameCalculationInputs(event.params) != true;
    emit(
      state.copyWith(
        calcParams: event.params,
        hasUnsavedChanges: true,
        step3Invalidated: inputsChanged && state.hasSection3Data
            ? true
            : state.step3Invalidated,
        clearCalcResult: inputsChanged,
        clearOptimizationResultData: inputsChanged,
        clearDeploymentRun: inputsChanged,
        clearDeploymentRunSelectionError: inputsChanged,
        isSelectingDeploymentRun: inputsChanged
            ? false
            : state.isSelectingDeploymentRun,
        clearError: inputsChanged,
        clearSuccess: inputsChanged,
      ),
    );
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
    if (state.status == WizardStatus.saving ||
        state.isCalculating ||
        state.isSelectingDeploymentRun) {
      return;
    }
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

    final requestedParams = state.calcParams!;
    emit(
      state.copyWith(
        isCalculating: true,
        clearError: true,
        clearDeploymentRunSelectionError: true,
      ),
    );

    try {
      String? twinId = state.twinId;
      if (twinId == null) {
        final name = state.twinName?.trim() ?? '';
        if (name.isEmpty) {
          emit(
            state.copyWith(
              isCalculating: false,
              errorMessage: 'Twin name is required',
            ),
          );
          return;
        }
        final twin = await _api.createTwin(name);
        twinId = twin.id;
        emit(state.copyWith(twinId: twinId));
      }

      final run = await _api.createOptimizerRun(twinId, requestedParams);
      if (state.calcParams?.hasSameCalculationInputs(requestedParams) != true) {
        emit(
          state.copyWith(
            isCalculating: false,
            isSelectingDeploymentRun: false,
            errorMessage:
                'Calculation inputs changed while the optimizer was running. Calculate again to verify the current workload.',
            clearDeploymentRun: true,
            clearDeploymentRunSelectionError: true,
          ),
        );
        return;
      }
      final response = run.optimization;
      final result = response.result;

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
            'The architecture changed. Deployment preparation requires review before continuing.';
      } else if (unconfigured.isNotEmpty) {
        warning =
            'Deployment access is missing for: ${unconfigured.join(", ")}. Open Cloud access to continue.';
      }

      emit(
        state.copyWith(
          isCalculating: false,
          isSelectingDeploymentRun: true,
          calcResult: result,
          optimizationResultData: response,
          deploymentRun: run.deploymentRun,
          hasUnsavedChanges: true,
          step3Invalidated: invalidatesStep3,
          warningMessage: warning,
          clearSuccess:
              invalidatesStep3, // Clear success message when warning appears
          clearDeploymentRunSelectionError: true,
        ),
      );
      await _selectDeploymentRun(
        run.deploymentRun,
        emit,
        warningMessage: warning,
        replaceWarning: true,
      );
    } catch (e) {
      _logger.warning(AppLogEvent.costCalculationFailed);
      emit(
        state.copyWith(
          isCalculating: false,
          isSelectingDeploymentRun: false,
          errorMessage:
              'Calculation failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onDeploymentRunSelectionRequested(
    WizardDeploymentRunSelectionRequested event,
    Emitter<WizardState> emit,
  ) async {
    final run = state.deploymentRun;
    final reviewState = state.deploymentReview.state;
    if (run == null ||
        !{
          ResolvedDeploymentReviewState.selectionRequired,
          ResolvedDeploymentReviewState.failed,
        }.contains(reviewState) ||
        state.isCalculating ||
        state.status == WizardStatus.saving ||
        state.isSelectingDeploymentRun) {
      return;
    }
    emit(
      state.copyWith(
        isSelectingDeploymentRun: true,
        clearError: true,
        clearDeploymentRunSelectionError: true,
      ),
    );
    await _selectDeploymentRun(run, emit);
  }

  Future<void> _selectDeploymentRun(
    OptimizerDeploymentRunData run,
    Emitter<WizardState> emit, {
    String? warningMessage,
    bool replaceWarning = false,
  }) async {
    try {
      final selection = await _api.selectOptimizerRunForDeployment(
        run.twinId,
        run.id,
      );
      if (state.deploymentRun != run || !state.isSelectingDeploymentRun) {
        return;
      }
      final selectedRun = run.applySelection(selection);
      emit(
        state.copyWith(
          deploymentRun: selectedRun,
          isSelectingDeploymentRun: false,
          warningMessage: warningMessage,
          clearWarning: replaceWarning && warningMessage == null,
          clearDeploymentRunSelectionError: true,
          clearError: true,
        ),
      );
    } catch (error) {
      if (state.deploymentRun != run || !state.isSelectingDeploymentRun) {
        return;
      }
      _logger.warning(AppLogEvent.deploymentRunSelectionFailed);
      final message = ApiErrorHandler.extractMessage(error);
      emit(
        state.copyWith(
          isSelectingDeploymentRun: false,
          deploymentRunSelectionError: message,
          errorMessage:
              'Deployment selection failed: $message. The calculation remains available for review.',
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
    if (state.status == WizardStatus.saving ||
        state.isCalculating ||
        state.isSelectingDeploymentRun) {
      return;
    }
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
        twinId = result.id;
      }

      // Save config and capture response for state sync
      final configResponse = await _api.updateTwinConfigRequest(
        twinId!,
        WizardConfigRequestBuilder.buildTwinConfigRequest(state),
      );

      // Track if state was regressed by backend
      final newTwinState = configResponse.twinState;
      final bool stateRegressed =
          newTwinState != null &&
          newTwinState != state.twinState &&
          newTwinState == 'draft';

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
          savedCalcParams: state.calcParams,
          savedOptimizationResultData: state.optimizationResultData,
          savedDeploymentRun: state.deploymentRun,
          step3Invalidated: false, // Clear invalidation after save
          successMessage: stateRegressed
              ? 'Saved. Configuration reverted to draft.'
              : 'Draft saved!',
        ),
      );
    } catch (e) {
      _logger.warning(AppLogEvent.wizardSaveFailed);
      emit(
        state.copyWith(
          status: WizardStatus.ready,
          errorMessage: 'Save failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onFinish(WizardFinish event, Emitter<WizardState> emit) async {
    if (state.status == WizardStatus.saving ||
        state.isCalculating ||
        state.isSelectingDeploymentRun) {
      return;
    }
    if (!state.isConfigurationReadyForFinish) {
      emit(
        state.copyWith(
          status: WizardStatus.ready,
          errorMessage:
              'Resolve all configuration readiness findings before finishing',
        ),
      );
      return;
    }
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
        twinId = result.id;
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
      _logger.warning(AppLogEvent.wizardFinishFailed);
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
        calcParams: state.savedCalcParams,
        calcResult: state.savedCalcResult, // Visually revert to saved result
        optimizationResultData: state.savedOptimizationResultData,
        deploymentRun: state.savedDeploymentRun,
        clearDeploymentRun: state.savedDeploymentRun == null,
        clearDeploymentRunSelectionError: true,
        isSelectingDeploymentRun: false,
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
    if (state.status == WizardStatus.saving || state.isCalculating) return;
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
}
