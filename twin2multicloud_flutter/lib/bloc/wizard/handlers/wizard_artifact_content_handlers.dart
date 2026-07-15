part of '../wizard_bloc.dart';

extension _WizardArtifactContentHandlers on WizardBloc {
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
}
