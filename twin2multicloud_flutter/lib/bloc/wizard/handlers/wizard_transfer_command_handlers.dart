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

  // ============================================================
  // STEP 3: ZIP UPLOAD HANDLERS
  // ============================================================

  /// Process a presentation-confirmed, transient ZIP upload.
  Future<void> _onZipUploadRequested(
    WizardZipUploadRequested event,
    Emitter<WizardState> emit,
  ) async {
    if (state.zipUploadInProgress) return;
    if (!_isSafeUploadFilename(event.fileName, '.zip') ||
        event.fileBytes.isEmpty) {
      emit(
        state.copyWith(
          errorMessage: 'Select a non-empty .zip file with a safe filename.',
        ),
      );
      return;
    }
    if (event.fileBytes.length > _maxProjectZipBytes) {
      emit(
        state.copyWith(
          errorMessage: 'The project ZIP exceeds the 100 MB upload limit.',
        ),
      );
      return;
    }
    await _processZipUpload(event.fileBytes, event.fileName, emit);
  }

  /// Process the actual zip upload and populate fields
  ///
  /// Delegates to WizardZipService for the heavy lifting.
  Future<void> _processZipUpload(
    Uint8List fileBytes,
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
      _logger.warning(AppLogEvent.projectZipUploadFailed);
      emit(
        state.copyWith(
          zipUploadInProgress: false,
          errorMessage: 'Upload failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }
}
