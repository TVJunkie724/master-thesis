part of '../wizard_bloc.dart';

extension _WizardTransferCommandHandlers on WizardBloc {
  Future<void> _onSceneGlbUploadRequested(
    WizardSceneGlbUploadRequested event,
    Emitter<WizardState> emit,
  ) async {
    if (state.sceneGlbCommand.isBusy) return;
    final twinId = state.twinId;
    if (twinId == null) {
      emit(
        state.copyWith(
          sceneGlbCommand: const SceneGlbCommandState(
            message: 'Save the draft before uploading a GLB file.',
          ),
          errorMessage: 'Save the draft before uploading a GLB file.',
        ),
      );
      return;
    }
    if (!_isSafeUploadFilename(event.filename, '.glb') || event.bytes.isEmpty) {
      emit(
        state.copyWith(
          sceneGlbCommand: const SceneGlbCommandState(
            message: 'Select a non-empty .glb file with a safe filename.',
          ),
          errorMessage: 'Select a non-empty .glb file with a safe filename.',
        ),
      );
      return;
    }
    if (event.bytes.length > _maxSceneGlbBytes) {
      emit(
        state.copyWith(
          sceneGlbCommand: const SceneGlbCommandState(
            message: 'The GLB file exceeds the 100 MB upload limit.',
          ),
          errorMessage: 'The GLB file exceeds the 100 MB upload limit.',
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        sceneGlbCommand: const SceneGlbCommandState(
          phase: SceneGlbCommandPhase.uploading,
        ),
        clearError: true,
        clearSuccess: true,
      ),
    );
    try {
      await _api.uploadSceneGlb(twinId, event.bytes, event.filename);
      emit(
        state.copyWith(
          sceneGlbUploaded: true,
          sceneGlbCommand: const SceneGlbCommandState(
            message: 'GLB uploaded successfully.',
          ),
          hasUnsavedChanges: true,
          successMessage: 'GLB uploaded successfully.',
        ),
      );
    } catch (error) {
      final message =
          'GLB upload failed: ${ApiErrorHandler.extractMessage(error)}';
      emit(
        state.copyWith(
          sceneGlbCommand: SceneGlbCommandState(message: message),
          errorMessage: message,
        ),
      );
    }
  }

  Future<void> _onSceneGlbDeleteRequested(
    WizardSceneGlbDeleteRequested event,
    Emitter<WizardState> emit,
  ) async {
    if (state.sceneGlbCommand.isBusy) return;
    final twinId = state.twinId;
    if (twinId == null) {
      emit(
        state.copyWith(
          sceneGlbCommand: const SceneGlbCommandState(
            message: 'Save the draft before deleting a GLB file.',
          ),
          errorMessage: 'Save the draft before deleting a GLB file.',
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        sceneGlbCommand: const SceneGlbCommandState(
          phase: SceneGlbCommandPhase.deleting,
        ),
        clearError: true,
        clearSuccess: true,
      ),
    );
    try {
      await _api.deleteSceneGlb(twinId);
      emit(
        state.copyWith(
          sceneGlbUploaded: false,
          sceneGlbCommand: const SceneGlbCommandState(
            message: 'GLB deleted successfully.',
          ),
          hasUnsavedChanges: true,
          successMessage: 'GLB deleted successfully.',
        ),
      );
    } catch (error) {
      final message =
          'GLB deletion failed: ${ApiErrorHandler.extractMessage(error)}';
      emit(
        state.copyWith(
          sceneGlbCommand: SceneGlbCommandState(message: message),
          errorMessage: message,
        ),
      );
    }
  }

  bool _isSafeUploadFilename(String filename, String extension) {
    final normalized = filename.trim();
    return normalized.isNotEmpty &&
        normalized.toLowerCase().endsWith(extension) &&
        !normalized.contains('/') &&
        !normalized.contains('\\') &&
        !normalized.codeUnits.any((unit) => unit < 32 || unit == 127);
  }
}
