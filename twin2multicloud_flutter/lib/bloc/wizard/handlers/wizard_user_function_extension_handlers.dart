part of '../wizard_bloc.dart';

extension _WizardUserFunctionExtensionHandlers on WizardBloc {
  Future<void> _onUserFunctionsLoadRequested(
    WizardUserFunctionsLoadRequested event,
    Emitter<WizardState> emit,
  ) async {
    await _loadUserFunctions(emit);
  }

  Future<void> _loadUserFunctions(Emitter<WizardState> emit) async {
    emit(
      state.copyWith(
        userFunctionsLoading: true,
        extensionErrors: {...state.extensionErrors}..remove('_sources'),
      ),
    );
    try {
      final slots = await _api.listExtensionSlots();
      final twinId = state.twinId;
      final userFunctions = twinId == null
          ? const <TwinUserFunction>[]
          : await _api.listTwinUserFunctions(twinId);
      emit(
        state.copyWith(
          userFunctionsLoading: false,
          extensionSlots: slots,
          twinUserFunctions: userFunctions,
          extensionPhases: {
            for (final slot in slots)
              slot.slotId:
                  userFunctions.any(
                    (userFunction) => userFunction.slotId == slot.slotId,
                  )
                  ? UserFunctionWorkflowPhase.saved
                  : state.extensionDraft(slot.slotId) == null
                  ? UserFunctionWorkflowPhase.draft
                  : state.extensionPhase(slot.slotId),
          },
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          userFunctionsLoading: false,
          extensionErrors: {
            ...state.extensionErrors,
            '_sources': ApiErrorHandler.extractMessage(error),
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
    final twinId = state.twinId;
    final upload = _extensionUpload(event.slotId);
    if (upload == null || twinId == null) {
      emit(
        _extensionFailure(
          event.slotId,
          twinId == null
              ? 'Save the Digital Twin before validating its function source.'
              : 'Choose a source ZIP and complete all required configuration fields.',
          UserFunctionWorkflowPhase.invalid,
        ),
      );
      return;
    }
    emit(_extensionPhase(event.slotId, UserFunctionWorkflowPhase.validating));
    try {
      final result = await _api.validateTwinUserFunction(twinId, upload);
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

  Future<void> _onExtensionSaveRequested(
    WizardExtensionSaveRequested event,
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
              ? 'Save the Digital Twin before saving its function source.'
              : 'Validate the current source archive before saving it.',
          UserFunctionWorkflowPhase.error,
        ),
      );
      return;
    }
    emit(_extensionPhase(event.slotId, UserFunctionWorkflowPhase.saving));
    try {
      final userFunction = await _api.saveTwinUserFunction(twinId, upload);
      final draftChanged = state.extensionDraft(event.slotId) != upload.draft;
      emit(
        state.copyWith(
          twinUserFunctions: [
            ...state.twinUserFunctions.where(
              (item) => item.slotId != userFunction.slotId,
            ),
            userFunction,
          ],
          extensionPhases: {
            ...state.extensionPhases,
            event.slotId: draftChanged
                ? UserFunctionWorkflowPhase.stale
                : UserFunctionWorkflowPhase.saved,
          },
          extensionErrors: draftChanged
              ? {
                  ...state.extensionErrors,
                  event.slotId:
                      'The previous draft was saved. Validate the current '
                      'source before replacing it.',
                }
              : ({...state.extensionErrors}..remove(event.slotId)),
          hasUnsavedChanges: true,
          successMessage: draftChanged ? null : 'Validated Twin function saved',
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

  Future<void> _onExtensionDeleteRequested(
    WizardExtensionDeleteRequested event,
    Emitter<WizardState> emit,
  ) async {
    final twinId = state.twinId;
    final slot = state.extensionSlot(event.slotId);
    if (twinId == null || slot == null) return;
    emit(_extensionPhase(event.slotId, UserFunctionWorkflowPhase.saving));
    try {
      await _api.deleteTwinUserFunction(twinId, slot);
      emit(
        state.copyWith(
          twinUserFunctions: state.twinUserFunctions
              .where((item) => item.slotId != event.slotId)
              .toList(growable: false),
          extensionValidationResults: {...state.extensionValidationResults}
            ..remove(event.slotId),
          extensionPhases: {
            ...state.extensionPhases,
            event.slotId: UserFunctionWorkflowPhase.draft,
          },
          extensionErrors: {...state.extensionErrors}..remove(event.slotId),
          hasUnsavedChanges: true,
          successMessage: 'Twin function removed',
        ),
      );
    } catch (error) {
      emit(
        _extensionFailure(
          event.slotId,
          ApiErrorHandler.extractMessage(error),
          UserFunctionWorkflowPhase.error,
        ),
      );
    }
  }

  UserFunctionSourceUpload? _extensionUpload(String slotId) {
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
    return UserFunctionSourceUpload(slot: slot, draft: draft);
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
