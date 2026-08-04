part of '../wizard_bloc.dart';

extension _WizardArchitectureProfileHandlers on WizardBloc {
  Future<void> _onArchitectureProfilesLoadRequested(
    WizardArchitectureProfilesLoadRequested event,
    Emitter<WizardState> emit,
  ) async {
    final generation = ++_architectureCatalogGeneration;
    emit(
      state.copyWith(
        architectureCatalogPhase: ArchitectureCatalogPhase.loading,
        clearArchitectureCatalogError: true,
      ),
    );

    try {
      final profiles = await _api.listArchitectureProfiles();
      if (generation != _architectureCatalogGeneration) return;

      TwinArchitectureSelection? selection = state.architectureSelection;
      final twinId = state.twinId;
      if (twinId != null) {
        selection = await _api.getTwinArchitectureSelection(twinId);
        if (generation != _architectureCatalogGeneration) return;
      }

      final selectedProfile = _profileForRef(profiles, selection?.profileRef);
      emit(
        state.copyWith(
          architectureCatalogPhase: profiles.isEmpty
              ? ArchitectureCatalogPhase.empty
              : ArchitectureCatalogPhase.ready,
          architectureProfiles: List.unmodifiable(profiles),
          architectureSelection: selection,
          clearArchitectureSelection: selection == null,
          architectureDetailPhase: selectedProfile == null
              ? ArchitectureDetailPhase.idle
              : ArchitectureDetailPhase.loading,
          architectureDetailAcknowledged:
              selectedProfile != null &&
                  state.architectureProfileDetail != null &&
                  _architectureRefsMatch(
                    state.architectureProfileDetail!.summary.ref,
                    selectedProfile.ref,
                  )
              ? state.architectureDetailAcknowledged
              : false,
          clearArchitectureProfileDetail: selectedProfile == null,
          clearArchitectureDetailError: true,
          clearArchitectureCatalogError: true,
        ),
      );

      if (selectedProfile != null) {
        add(WizardArchitectureProfileDetailLoadRequested(selectedProfile.ref));
      }
      final selectedRun = state.deploymentReview.ready
          ? state.deploymentRun
          : null;
      if (selectedRun != null &&
          state.resolvedArchitecture?.calculationRunId != selectedRun.id) {
        add(WizardResolvedArchitectureLoadRequested(runId: selectedRun.id));
      }
    } catch (error) {
      if (generation != _architectureCatalogGeneration) return;
      emit(
        state.copyWith(
          architectureCatalogPhase: ArchitectureCatalogPhase.error,
          architectureCatalogError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onArchitectureProfileDetailLoadRequested(
    WizardArchitectureProfileDetailLoadRequested event,
    Emitter<WizardState> emit,
  ) async {
    if (_profileForRef(state.architectureProfiles, event.profileRef) == null) {
      emit(
        state.copyWith(
          architectureDetailPhase: ArchitectureDetailPhase.error,
          architectureDetailError:
              'This architecture profile is not active and cannot be opened.',
          clearArchitectureProfileDetail: true,
        ),
      );
      return;
    }

    final generation = ++_architectureDetailGeneration;
    final retainsAcknowledgement =
        state.architectureProfileDetail != null &&
        _architectureRefsMatch(
          state.architectureProfileDetail!.summary.ref,
          event.profileRef,
        );
    emit(
      state.copyWith(
        architectureDetailPhase: ArchitectureDetailPhase.loading,
        architectureDetailAcknowledged: retainsAcknowledgement
            ? state.architectureDetailAcknowledged
            : false,
        clearArchitectureProfileDetail: !retainsAcknowledgement,
        clearArchitectureDetailError: true,
      ),
    );

    try {
      final detail = await _api.getArchitectureProfile(
        event.profileRef.id,
        event.profileRef.version,
      );
      if (generation != _architectureDetailGeneration) return;
      if (!_architectureRefsMatch(detail.summary.ref, event.profileRef)) {
        throw const FormatException(
          'Invalid API contract: architecture profile detail reference differs.',
        );
      }
      emit(
        state.copyWith(
          architectureDetailPhase: ArchitectureDetailPhase.ready,
          architectureProfileDetail: detail,
          clearArchitectureDetailError: true,
        ),
      );
    } catch (error) {
      if (generation != _architectureDetailGeneration) return;
      emit(
        state.copyWith(
          architectureDetailPhase: ArchitectureDetailPhase.error,
          architectureDetailError: ApiErrorHandler.extractMessage(error),
          clearArchitectureProfileDetail: true,
        ),
      );
    }
  }

  void _onArchitectureUnderstandingAcknowledged(
    WizardArchitectureUnderstandingAcknowledged event,
    Emitter<WizardState> emit,
  ) {
    final selected = state.architectureSelection?.profileRef;
    final detail = state.architectureProfileDetail?.summary.ref;
    if (state.architectureDetailPhase != ArchitectureDetailPhase.ready ||
        selected == null ||
        detail == null ||
        !_architectureRefsMatch(selected, detail) ||
        state.architectureDetailAcknowledged) {
      return;
    }
    emit(state.copyWith(architectureDetailAcknowledged: true));
  }

  Future<void> _onArchitectureProfileSelected(
    WizardArchitectureProfileSelected event,
    Emitter<WizardState> emit,
  ) async {
    final target = _profileForRef(state.architectureProfiles, event.profileRef);
    final current = state.architectureSelection;
    final twinId = state.twinId;
    if (target == null) {
      emit(
        state.copyWith(
          architectureChangePhase: ArchitectureChangePhase.error,
          architectureChangeError:
              'This architecture profile is not active and cannot be selected.',
          clearArchitectureChangePreview: true,
        ),
      );
      return;
    }
    if (current != null &&
        _architectureRefsMatch(current.profileRef, event.profileRef)) {
      return;
    }
    if ({
      ArchitectureChangePhase.previewing,
      ArchitectureChangePhase.awaitingConfirmation,
      ArchitectureChangePhase.submitting,
    }.contains(state.architectureChangePhase)) {
      return;
    }
    if (twinId == null || current == null) {
      emit(
        state.copyWith(
          architectureChangePhase: ArchitectureChangePhase.error,
          architectureChangeError:
              'Save the Twin draft before selecting an architecture profile.',
          clearArchitectureChangePreview: true,
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        architectureChangePhase: ArchitectureChangePhase.previewing,
        clearArchitectureChangePreview: true,
        clearArchitectureChangeError: true,
      ),
    );
    try {
      final preview = await _api.previewTwinArchitectureProfileChange(
        twinId,
        ArchitectureProfileChangePreviewRequest(
          profileId: target.profileId,
          profileVersion: target.profileVersion,
          expectedRevision: current.revision,
        ),
      );
      if (!_architectureRefsMatch(preview.current, current.profileRef) ||
          !_architectureRefsMatch(preview.target, target.ref) ||
          preview.expectedRevision != current.revision) {
        throw const FormatException(
          'Invalid API contract: architecture profile preview differs.',
        );
      }
      emit(
        state.copyWith(
          architectureChangePhase: ArchitectureChangePhase.awaitingConfirmation,
          architectureChangePreview: preview,
          clearArchitectureChangeError: true,
        ),
      );
    } catch (error) {
      if (_isArchitectureConflict(error)) {
        await _reloadArchitectureSelectionAfterConflict(emit);
        return;
      }
      emit(
        state.copyWith(
          architectureChangePhase: ArchitectureChangePhase.error,
          architectureChangeError: ApiErrorHandler.extractMessage(error),
          clearArchitectureChangePreview: true,
        ),
      );
    }
  }

  Future<void> _onArchitectureProfileChangeConfirmed(
    WizardArchitectureProfileChangeConfirmed event,
    Emitter<WizardState> emit,
  ) async {
    final preview = state.architectureChangePreview;
    final twinId = state.twinId;
    if (preview == null ||
        twinId == null ||
        state.architectureChangePhase !=
            ArchitectureChangePhase.awaitingConfirmation) {
      return;
    }

    emit(
      state.copyWith(
        architectureChangePhase: ArchitectureChangePhase.submitting,
        clearArchitectureChangeError: true,
      ),
    );
    try {
      final result = await _api.selectTwinArchitectureProfile(
        twinId,
        ArchitectureProfileSelectRequest.fromPreview(preview),
      );
      if (!_architectureRefsMatch(
        result.selection.profileRef,
        preview.target,
      )) {
        throw const FormatException(
          'Invalid API contract: selected architecture profile differs.',
        );
      }

      final unbound = result.unboundExtensionSlotIds.toSet();
      final invalidatedRunIsSelected =
          result.invalidatedCalculationRunId != null &&
          result.invalidatedCalculationRunId == state.deploymentRun?.id;
      _resolvedArchitectureGeneration++;
      emit(
        state.copyWith(
          architectureSelection: result.selection,
          architectureDetailPhase: ArchitectureDetailPhase.loading,
          architectureDetailAcknowledged: false,
          architectureChangePhase: ArchitectureChangePhase.idle,
          architectureInvalidatedWorkloadFieldIds: Set.unmodifiable(
            result.clearedWorkloadFieldIds,
          ),
          extensionBindings: state.extensionBindings
              .where((binding) => !unbound.contains(binding.slotId))
              .toList(growable: false),
          extensionPhases: {
            ...state.extensionPhases,
            for (final slotId in unbound)
              slotId: UserFunctionWorkflowPhase.draft,
          },
          clearArchitectureChangePreview: true,
          clearArchitectureChangeError: true,
          clearArchitectureProfileDetail: true,
          clearArchitectureDetailError: true,
          clearCalcResult: invalidatedRunIsSelected,
          clearOptimizationResultData: invalidatedRunIsSelected,
          clearDeploymentRun: invalidatedRunIsSelected,
          clearDeploymentRunSelectionError: invalidatedRunIsSelected,
          resolvedArchitecturePhase: ResolvedArchitecturePhase.idle,
          clearResolvedArchitecture: true,
          clearResolvedArchitectureError: true,
          step3Invalidated:
              result.deploymentReadinessState == 'invalidated' ||
              state.step3Invalidated,
          hasUnsavedChanges: true,
          warningMessage: _profileChangeWarning(result),
        ),
      );
      add(
        WizardArchitectureProfileDetailLoadRequested(
          result.selection.profileRef,
        ),
      );
    } catch (error) {
      if (_isArchitectureConflict(error)) {
        await _reloadArchitectureSelectionAfterConflict(emit);
        return;
      }
      emit(
        state.copyWith(
          architectureChangePhase: ArchitectureChangePhase.error,
          architectureChangeError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  void _onArchitectureProfileChangeCancelled(
    WizardArchitectureProfileChangeCancelled event,
    Emitter<WizardState> emit,
  ) {
    emit(
      state.copyWith(
        architectureChangePhase: ArchitectureChangePhase.idle,
        clearArchitectureChangePreview: true,
        clearArchitectureChangeError: true,
      ),
    );
  }

  Future<void> _reloadArchitectureSelectionAfterConflict(
    Emitter<WizardState> emit,
  ) async {
    final twinId = state.twinId;
    emit(
      state.copyWith(
        architectureChangePhase: ArchitectureChangePhase.conflict,
        architectureChangeError:
            'The architecture selection changed. Review a fresh preview before confirming again.',
        clearArchitectureChangePreview: true,
      ),
    );
    if (twinId == null) return;
    try {
      final selection = await _api.getTwinArchitectureSelection(twinId);
      emit(state.copyWith(architectureSelection: selection));
      final active = _profileForRef(
        state.architectureProfiles,
        selection.profileRef,
      );
      if (active != null) {
        add(WizardArchitectureProfileDetailLoadRequested(active.ref));
      }
    } catch (_) {
      // Preserve the conflict. A catalog retry remains the recovery action.
    }
  }

  Future<void> _onResolvedArchitectureLoadRequested(
    WizardResolvedArchitectureLoadRequested event,
    Emitter<WizardState> emit,
  ) => _loadResolvedArchitecture(event.runId, emit);

  Future<void> _onResolvedArchitectureRetried(
    WizardResolvedArchitectureRetried event,
    Emitter<WizardState> emit,
  ) => _loadResolvedArchitecture(event.runId, emit);

  Future<void> _loadResolvedArchitecture(
    String? runId,
    Emitter<WizardState> emit,
  ) async {
    final twinId = state.twinId;
    if (runId == null && twinId == null) return;
    final generation = ++_resolvedArchitectureGeneration;
    emit(
      state.copyWith(
        resolvedArchitecturePhase: ResolvedArchitecturePhase.loading,
        clearResolvedArchitectureError: true,
      ),
    );
    try {
      final resolved = runId == null
          ? await _api.getSelectedResolvedArchitecture(twinId!)
          : await _api.getRunResolvedArchitecture(runId);
      if (generation != _resolvedArchitectureGeneration) return;
      final selected = state.architectureSelection?.profileRef;
      final matchesSelection =
          selected != null &&
          _architectureRefsMatch(selected, resolved.architecture.profileRef);
      final matchesRun = runId == null || resolved.calculationRunId == runId;
      final matchesTwin = twinId == null || resolved.twinId == twinId;
      if (!matchesSelection || !matchesRun || !matchesTwin) {
        emit(
          state.copyWith(
            resolvedArchitecturePhase: ResolvedArchitecturePhase.incompatible,
            resolvedArchitectureError:
                'The resolved architecture does not match the selected profile or run.',
            clearResolvedArchitecture: true,
          ),
        );
        return;
      }
      final missingProviders = _unconfiguredResolvedProviders(resolved);
      emit(
        state.copyWith(
          resolvedArchitecturePhase: ResolvedArchitecturePhase.ready,
          resolvedArchitecture: resolved,
          clearResolvedArchitectureError: true,
          warningMessage: missingProviders.isEmpty
              ? null
              : 'Deployment access is missing for: '
                    '${missingProviders.join(', ')}. '
                    'Open Cloud access to continue.',
          clearWarning:
              missingProviders.isEmpty &&
              state.warningMessage?.startsWith(
                    'Deployment access is missing for:',
                  ) ==
                  true,
        ),
      );
    } catch (error) {
      if (generation != _resolvedArchitectureGeneration) return;
      final code = _architectureErrorCode(error);
      final incompatible = {
        'ARCH_LEGACY_NOT_RESOLVABLE',
        'ARCH_LEGACY_PROJECTION_UNSUPPORTED',
      }.contains(code);
      emit(
        state.copyWith(
          resolvedArchitecturePhase: incompatible
              ? ResolvedArchitecturePhase.incompatible
              : ResolvedArchitecturePhase.error,
          resolvedArchitectureError: ApiErrorHandler.extractMessage(error),
          clearResolvedArchitecture: true,
        ),
      );
    }
  }

  ArchitectureProfileSummary? _profileForRef(
    List<ArchitectureProfileSummary> profiles,
    PinnedArchitectureReference? ref,
  ) {
    if (ref == null) return null;
    for (final profile in profiles) {
      if (_architectureRefsMatch(profile.ref, ref)) return profile;
    }
    return null;
  }

  bool _isArchitectureConflict(Object error) => {
    'ARCH_SELECTION_REVISION_CONFLICT',
    'ARCH_SELECTION_INVALIDATION_STALE',
  }.contains(_architectureErrorCode(error));

  String? _architectureErrorCode(Object error) {
    if (error is CodedUserFacingException) return error.code;
    if (error is AppException) return error.code;
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map) {
        final direct = data['error_code'];
        if (direct is String) return direct;
        final detail = data['detail'];
        if (detail is Map && detail['error_code'] is String) {
          return detail['error_code'] as String;
        }
      }
    }
    return null;
  }

  String _profileChangeWarning(ArchitectureProfileSelectionResult result) {
    final categories = <String>[
      if (result.clearedWorkloadFieldIds.isNotEmpty) 'workload fields',
      if (result.unboundExtensionSlotIds.isNotEmpty) 'user-function bindings',
      if (result.invalidatedCalculationRunId != null) 'the selected run',
      if (result.deploymentReadinessState == 'invalidated')
        'deployment readiness',
    ];
    return categories.isEmpty
        ? 'Architecture profile changed.'
        : 'Architecture profile changed and invalidated ${categories.join(', ')}.';
  }

  List<String> _unconfiguredResolvedProviders(
    ResolvedTwinArchitectureRead resolved,
  ) {
    final required = resolved.architecture.providers
        .map((provider) => provider.name.toUpperCase())
        .toSet();
    final missing = required.difference(state.configuredProviders).toList()
      ..sort();
    return missing;
  }
}

bool _architectureRefsMatch(
  PinnedArchitectureReference left,
  PinnedArchitectureReference right,
) =>
    left.id == right.id &&
    left.version == right.version &&
    left.digest == right.digest;
