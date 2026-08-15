part of '../wizard_bloc.dart';

extension _WizardUserFunctionExtensionHandlers on WizardBloc {
  Future<void> _onExtensionCatalogLoadRequested(
    WizardExtensionCatalogLoadRequested event,
    Emitter<WizardState> emit,
  ) async {
    await _loadExtensionCatalog(emit);
  }

  Future<void> _loadExtensionCatalog(Emitter<WizardState> emit) async {
    emit(
      state.copyWith(
        extensionCatalogLoading: true,
        extensionErrors: {...state.extensionErrors}..remove('_catalog'),
      ),
    );
    try {
      final slots = await _api.listExtensionSlots();
      final artifacts = await _api.listUserFunctionArtifacts();
      final twinId = state.twinId;
      final bindings = twinId == null
          ? const <TwinExtensionBinding>[]
          : await _api.listTwinExtensionBindings(twinId);
      emit(
        state.copyWith(
          extensionCatalogLoading: false,
          extensionSlots: slots,
          extensionArtifacts: artifacts,
          extensionBindings: bindings,
          extensionPhases: {
            ...state.extensionPhases,
            for (final binding in bindings)
              binding.slotId: UserFunctionWorkflowPhase.bound,
          },
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          extensionCatalogLoading: false,
          extensionErrors: {
            ...state.extensionErrors,
            '_catalog': ApiErrorHandler.extractMessage(error),
          },
        ),
      );
    }
  }

  void _onExtensionSourceSelected(
    WizardExtensionSourceSelected event,
    Emitter<WizardState> emit,
  ) {
    if (!event.fileName.toLowerCase().endsWith('.zip') ||
        event.fileBytes.isEmpty ||
        event.fileBytes.length > 10 * 1024 * 1024) {
      emit(
        _extensionFailure(
          event.slotId,
          'Choose a non-empty source ZIP no larger than 10 MiB.',
          UserFunctionWorkflowPhase.invalid,
        ),
      );
      return;
    }
    final current = state.extensionDraft(event.slotId);
    emit(
      state.copyWith(
        extensionDrafts: {
          ...state.extensionDrafts,
          event.slotId: UserFunctionSourceDraft(
            filename: event.fileName,
            bytes: event.fileBytes,
            configuration: current?.configuration ?? const {},
          ),
        },
        extensionValidationResults: {...state.extensionValidationResults}
          ..remove(event.slotId),
        extensionPhases: {
          ...state.extensionPhases,
          event.slotId: UserFunctionWorkflowPhase.draft,
        },
        extensionErrors: {...state.extensionErrors}..remove(event.slotId),
        hasUnsavedChanges: true,
      ),
    );
  }

  void _onExtensionConfigurationChanged(
    WizardExtensionConfigurationChanged event,
    Emitter<WizardState> emit,
  ) {
    final current = state.extensionDraft(event.slotId);
    final configuration = <String, dynamic>{...?current?.configuration};
    if (event.value == null || event.value == '') {
      configuration.remove(event.field);
    } else {
      configuration[event.field] = event.value;
    }
    emit(
      state.copyWith(
        extensionDrafts: {
          ...state.extensionDrafts,
          event.slotId: UserFunctionSourceDraft(
            filename: current?.filename ?? '',
            bytes: current?.bytes ?? Uint8List(0),
            configuration: configuration,
          ),
        },
        extensionValidationResults: {...state.extensionValidationResults}
          ..remove(event.slotId),
        extensionPhases: {
          ...state.extensionPhases,
          event.slotId: UserFunctionWorkflowPhase.draft,
        },
        extensionErrors: {...state.extensionErrors}..remove(event.slotId),
        hasUnsavedChanges: true,
      ),
    );
  }

  Future<void> _onExtensionValidationRequested(
    WizardExtensionValidationRequested event,
    Emitter<WizardState> emit,
  ) async {
    final upload = _extensionUpload(event.slotId);
    if (upload == null) {
      emit(
        _extensionFailure(
          event.slotId,
          'Choose a source ZIP and complete all required configuration fields.',
          UserFunctionWorkflowPhase.invalid,
        ),
      );
      return;
    }
    emit(_extensionPhase(event.slotId, UserFunctionWorkflowPhase.validating));
    try {
      final result = await _api.validateUserFunctionArtifact(upload);
      if (state.extensionDraft(event.slotId) != upload.draft) return;
      emit(
        state.copyWith(
          extensionValidationResults: {
            ...state.extensionValidationResults,
            event.slotId: result,
          },
          extensionPhases: {
            ...state.extensionPhases,
            event.slotId: UserFunctionWorkflowPhase.valid,
          },
          extensionErrors: {...state.extensionErrors}..remove(event.slotId),
        ),
      );
    } catch (error) {
      if (state.extensionDraft(event.slotId) != upload.draft) return;
      emit(
        _extensionFailure(
          event.slotId,
          ApiErrorHandler.extractMessage(error),
          UserFunctionWorkflowPhase.invalid,
        ),
      );
    }
  }

  Future<void> _onExtensionBindRequested(
    WizardExtensionBindRequested event,
    Emitter<WizardState> emit,
  ) async {
    final upload = _extensionUpload(event.slotId);
    final twinId = state.twinId;
    if (upload == null ||
        state.extensionValidation(event.slotId) == null ||
        twinId == null) {
      emit(
        _extensionFailure(
          event.slotId,
          twinId == null
              ? 'Save the Digital Twin before binding an extension artifact.'
              : 'Validate the current source archive before binding it.',
          UserFunctionWorkflowPhase.error,
        ),
      );
      return;
    }
    emit(_extensionPhase(event.slotId, UserFunctionWorkflowPhase.binding));
    try {
      final artifact = await _api.createUserFunctionArtifact(upload);
      final current = state.extensionBinding(event.slotId);
      final binding = await _api.bindTwinExtensionArtifact(
        twinId,
        upload.slot,
        artifact.artifactId,
        expectedRevision: current?.revision,
      );
      final draftChanged = state.extensionDraft(event.slotId) != upload.draft;
      emit(
        state.copyWith(
          extensionArtifacts: [
            ...state.extensionArtifacts.where(
              (item) => item.artifactId != artifact.artifactId,
            ),
            artifact,
          ],
          extensionBindings: [
            ...state.extensionBindings.where(
              (item) =>
                  item.slotId != binding.slotId ||
                  item.slotVersion != binding.slotVersion,
            ),
            binding,
          ],
          extensionPhases: {
            ...state.extensionPhases,
            event.slotId: draftChanged
                ? UserFunctionWorkflowPhase.stale
                : UserFunctionWorkflowPhase.bound,
          },
          extensionErrors: draftChanged
              ? {
                  ...state.extensionErrors,
                  event.slotId:
                      'The previous draft was bound. Validate the current '
                      'source before replacing it.',
                }
              : ({...state.extensionErrors}..remove(event.slotId)),
          hasUnsavedChanges: true,
          successMessage: draftChanged
              ? null
              : 'Validated extension artifact bound',
          clearSuccess: draftChanged,
        ),
      );
    } catch (error) {
      if (state.extensionDraft(event.slotId) != upload.draft) return;
      final message = ApiErrorHandler.extractMessage(error);
      emit(
        _extensionFailure(
          event.slotId,
          message,
          message.toLowerCase().contains('stale')
              ? UserFunctionWorkflowPhase.stale
              : UserFunctionWorkflowPhase.error,
        ),
      );
    }
  }

  UserFunctionArtifactUpload? _extensionUpload(String slotId) {
    final slot = state.extensionSlot(slotId);
    final draft = state.extensionDraft(slotId);
    if (slot == null ||
        draft == null ||
        draft.filename.isEmpty ||
        draft.bytes.isEmpty ||
        slot.configurationFields.any(
          (field) =>
              field.required && !draft.configuration.containsKey(field.name),
        )) {
      return null;
    }
    return UserFunctionArtifactUpload(slot: slot, draft: draft);
  }

  WizardState _extensionPhase(String slotId, UserFunctionWorkflowPhase phase) {
    return state.copyWith(
      extensionPhases: {...state.extensionPhases, slotId: phase},
      extensionErrors: {...state.extensionErrors}..remove(slotId),
    );
  }

  WizardState _extensionFailure(
    String slotId,
    String message,
    UserFunctionWorkflowPhase phase,
  ) {
    return state.copyWith(
      extensionPhases: {...state.extensionPhases, slotId: phase},
      extensionErrors: {...state.extensionErrors, slotId: message},
    );
  }
}
