part of '../wizard_bloc.dart';

extension _WizardArchitectureProfileHandlers on WizardBloc {
  static const _canonicalProfileId = 'six-layer-eventing';
  static const _canonicalProfileVersion = '1';

  Future<void> _onCanonicalArchitectureLoadRequested(
    WizardCanonicalArchitectureLoadRequested event,
    Emitter<WizardState> emit,
  ) async {
    final generation = ++_architectureDetailGeneration;
    emit(
      state.copyWith(
        architectureDetailPhase: ArchitectureDetailPhase.loading,
        clearArchitectureProfileDetail: true,
        clearArchitectureDetailError: true,
      ),
    );

    try {
      final detail = await _api.getArchitectureProfile(
        _canonicalProfileId,
        _canonicalProfileVersion,
      );
      if (generation != _architectureDetailGeneration) return;
      final canonicalRef = detail.summary.ref;
      if (canonicalRef.id != _canonicalProfileId ||
          canonicalRef.version != _canonicalProfileVersion) {
        throw const AppException(
          'Invalid API contract: the canonical architecture detail reference differs.',
          code: 'ARCH_CANONICAL_CONTRACT_MISMATCH',
        );
      }

      TwinArchitectureSelection? selection;
      final twinId = state.twinId;
      if (twinId != null) {
        selection = await _api.getTwinArchitectureSelection(twinId);
        if (generation != _architectureDetailGeneration) return;
        if (!_architectureRefsMatch(selection.profileRef, canonicalRef)) {
          throw const AppException(
            'This Twin does not use the canonical six-layer-eventing@1 architecture contract.',
            code: 'ARCH_CANONICAL_SELECTION_MISMATCH',
          );
        }
      }

      emit(
        state.copyWith(
          architectureDetailPhase: ArchitectureDetailPhase.ready,
          architectureProfileDetail: detail,
          architectureSelection: selection,
          clearArchitectureSelection: selection == null,
          clearArchitectureDetailError: true,
          clearError: true,
        ),
      );

      final selectedRun = state.deploymentReview.ready
          ? state.deploymentRun
          : null;
      if (selectedRun != null &&
          state.resolvedArchitecture?.calculationRunId != selectedRun.id) {
        add(WizardResolvedArchitectureLoadRequested(runId: selectedRun.id));
      }
    } catch (error) {
      if (generation != _architectureDetailGeneration) return;
      final message = ApiErrorHandler.extractMessage(error);
      emit(
        state.copyWith(
          architectureDetailPhase: ArchitectureDetailPhase.error,
          architectureDetailError: message,
          errorMessage: 'Canonical architecture unavailable: $message',
          clearArchitectureProfileDetail: true,
          clearArchitectureSelection: true,
        ),
      );
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
      final evaluationOnly =
          state.deploymentReview.state ==
          ResolvedDeploymentReviewState.evaluationOnly;
      emit(
        state.copyWith(
          resolvedArchitecturePhase: ResolvedArchitecturePhase.ready,
          resolvedArchitecture: resolved,
          clearResolvedArchitectureError: true,
          warningMessage: evaluationOnly
              ? state.warningMessage
              : missingProviders.isEmpty
              ? null
              : 'Deployment access is missing for: '
                    '${missingProviders.join(', ')}. '
                    'Open Cloud access to continue.',
          clearWarning:
              !evaluationOnly &&
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
