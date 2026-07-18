part of '../wizard_bloc.dart';

extension _WizardInitializationCloudAccessHandlers on WizardBloc {
  // ============================================================
  // INITIALIZATION HANDLERS - Delegated to WizardInitService
  // ============================================================

  Future<void> _onInitCreate(
    WizardInitCreate event,
    Emitter<WizardState> emit,
  ) async {
    emit(_initService.initializeCreateMode());
    await _loadProviderCapabilities(emit);
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

      // The adapter maps an expected 404 to null. Other failures remain visible.
      final deployerConfig = await _api.getDeployerConfig(event.twinId);
      final deploymentRun = await _api.getLatestOptimizerRun(event.twinId);

      // Pass to stateless service for state construction
      final result = _initService.initializeEditMode(
        twinId: event.twinId,
        data: TwinEditData(
          twin: twin,
          config: config,
          deployerConfig: deployerConfig,
          deploymentRun: deploymentRun,
        ),
      );
      emit(result.state);
      await _loadProviderCapabilities(emit);
      await _loadCloudConnections(emit);
    } catch (e) {
      _logger.warning(AppLogEvent.wizardInitializationFailed);
      emit(
        state.copyWith(
          status: WizardStatus.error,
          errorMessage:
              'Failed to load twin: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onProviderCapabilitiesLoadRequested(
    WizardProviderCapabilitiesLoadRequested event,
    Emitter<WizardState> emit,
  ) async {
    await _loadProviderCapabilities(emit);
  }

  Future<void> _loadProviderCapabilities(Emitter<WizardState> emit) async {
    emit(
      state.copyWith(
        providerCapabilitiesLoading: true,
        clearProviderCapabilitiesError: true,
      ),
    );
    try {
      final capabilities = await _api.getProviderCapabilities();
      emit(
        state.copyWith(
          providerCapabilities: capabilities,
          providerCapabilitiesLoading: false,
          clearProviderCapabilitiesError: true,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          providerCapabilitiesLoading: false,
          providerCapabilitiesError: ApiErrorHandler.extractMessage(error),
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
              .where(
                (connection) =>
                    connection.provider == provider &&
                    connection.purpose == CloudConnectionPurpose.deployment,
              )
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
}
