// lib/bloc/twin_overview/twin_overview_bloc.dart
// BLoC for the twin overview screen

import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../config/api_config.dart';
import '../../services/api_service.dart';
import '../../services/sse_service.dart';
import '../../utils/api_error_handler.dart';
import 'twin_overview_event.dart';
import 'twin_overview_state.dart';

/// Toggle for UI testing - uses mock deployment endpoints when true.
/// Set to false for production/real deployments.
const bool kUseTestDeploy = true;

class TwinOverviewBloc extends Bloc<TwinOverviewEvent, TwinOverviewState> {
  final ApiService _api;
  String? _currentTwinId;
  Timer? _pollingTimer;
  StreamSubscription? _sseSubscription;
  SseService? _sseService;

  TwinOverviewBloc({required ApiService api})
    : _api = api,
      super(const TwinOverviewLoading()) {
    on<TwinOverviewLoad>(_onLoad);
    on<TwinOverviewRefresh>(_onRefresh);
    on<TwinOverviewDeploy>(_onDeploy);
    on<TwinOverviewDestroy>(_onDestroy);
    on<TwinOverviewDelete>(_onDelete);
    on<TwinOverviewLogReceived>(_onLogReceived);
    on<TwinOverviewDeploymentComplete>(_onDeploymentComplete);
    on<TwinOverviewClearMessages>(_onClearMessages);
    on<TwinOverviewShowMessage>(_onShowMessage);
    on<TwinOverviewCloseTerminal>(_onCloseTerminal);
  }

  Future<void> _onLoad(
    TwinOverviewLoad event,
    Emitter<TwinOverviewState> emit,
  ) async {
    _currentTwinId = event.twinId;
    emit(const TwinOverviewLoading());

    try {
      // Load twin basic data
      final twin = await _api.getTwin(event.twinId);

      // Load optimizer config (includes pricing snapshots)
      Map<String, dynamic>? optimizerConfig;
      try {
        optimizerConfig = await _api.getOptimizerConfig(event.twinId);
      } catch (e) {
        // Optimizer config may not exist yet
      }

      // Load deployer config
      Map<String, dynamic>? deployerConfig;
      try {
        deployerConfig = await _api.getDeployerConfig(event.twinId);
      } catch (e) {
        // Deployer config may not exist yet
      }

      final twinState = twin['state'] as String? ?? 'draft';

      emit(
        _buildLoadedState(
          twinId: event.twinId,
          twin: twin,
          twinState: twinState,
          optimizerConfig: optimizerConfig,
          deployerConfig: deployerConfig,
        ),
      );
    } catch (e) {
      emit(
        TwinOverviewError(
          'Failed to load twin: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onRefresh(
    TwinOverviewRefresh event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    // Preserve terminal state during refresh
    final preservedLogs = currentState is TwinOverviewLoaded
        ? currentState.terminalLogs
        : <String>[];
    final preservedShowTerminal = currentState is TwinOverviewLoaded
        ? currentState.showTerminal
        : false;

    if (_currentTwinId != null) {
      try {
        // Load fresh data from API
        final twin = await _api.getTwin(_currentTwinId!);
        Map<String, dynamic>? optimizerConfig;
        try {
          optimizerConfig = await _api.getOptimizerConfig(_currentTwinId!);
        } catch (e) {
          // Optimizer config may not exist yet
        }
        Map<String, dynamic>? deployerConfig;
        try {
          deployerConfig = await _api.getDeployerConfig(_currentTwinId!);
        } catch (e) {
          // Deployer config may not exist yet
        }

        final twinState = twin['state'] as String? ?? 'draft';
        final freshState = _buildLoadedState(
          twinId: _currentTwinId!,
          twin: twin,
          twinState: twinState,
          optimizerConfig: optimizerConfig,
          deployerConfig: deployerConfig,
        );

        // Emit fresh state but preserve terminal state
        emit(
          freshState.copyWith(
            terminalLogs: preservedLogs,
            showTerminal: preservedShowTerminal,
          ),
        );
      } catch (e) {
        // On error, just keep the current state
      }
    }
  }

  Future<void> _onDeploy(
    TwinOverviewDeploy event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    emit(
      currentState.copyWith(
        isDeploying: true,
        twinState: 'deploying',
        showTerminal: true,
        terminalLogs: ['> Starting deployment...'],
      ),
    );

    try {
      // Call backend to start deployment - now returns session_id and sse_url
      final result = kUseTestDeploy
          ? await _api.testDeployTwin(currentState.twinId, duration: 30)
          : await _api.deployTwin(currentState.twinId);

      final sseUrl = result['sse_url'] as String?;
      final sessionId = result['session_id'] as String?;

      if (sseUrl == null) {
        throw Exception(
          'Backend did not return SSE URL - SSE streaming is required',
        );
      }

      // SSE streaming mode - subscribe to log stream
      _subscribeToSseStream(
        sseUrl: sseUrl,
        sessionId: sessionId,
        twinId: currentState.twinId,
        isDestroy: false,
      );
    } catch (e) {
      emit(
        currentState.copyWith(
          isDeploying: false,
          twinState: 'error',
          errorMessage:
              'Deployment failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onDestroy(
    TwinOverviewDestroy event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    emit(
      currentState.copyWith(
        isDestroying: true,
        twinState: 'destroying',
        showTerminal: true,
        terminalLogs: ['> Starting resource destruction...'],
      ),
    );

    try {
      // Call backend to start destruction - now returns session_id and sse_url
      final result = kUseTestDeploy
          ? await _api.testDestroyTwin(currentState.twinId, duration: 20)
          : await _api.destroyTwin(currentState.twinId);

      final sseUrl = result['sse_url'] as String?;
      final sessionId = result['session_id'] as String?;

      if (sseUrl == null) {
        throw Exception(
          'Backend did not return SSE URL - SSE streaming is required',
        );
      }

      // SSE streaming mode - subscribe to log stream
      _subscribeToSseStream(
        sseUrl: sseUrl,
        sessionId: sessionId,
        twinId: currentState.twinId,
        isDestroy: true,
      );
    } catch (e) {
      emit(
        currentState.copyWith(
          isDestroying: false,
          twinState: 'error',
          errorMessage: 'Destroy failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onDelete(
    TwinOverviewDelete event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    try {
      await _api.deleteTwin(currentState.twinId);
      // Navigation will be handled by the screen listener
      emit(currentState.copyWith(successMessage: 'deleted'));
    } catch (e) {
      emit(
        currentState.copyWith(
          errorMessage:
              'Failed to delete: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  void _onLogReceived(
    TwinOverviewLogReceived event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    final newLogs = [...currentState.terminalLogs, event.log];
    emit(currentState.copyWith(terminalLogs: newLogs));
  }

  void _onDeploymentComplete(
    TwinOverviewDeploymentComplete event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    // First emit state update that PRESERVES terminal logs so they stay visible
    emit(
      currentState.copyWith(
        isDeploying: false,
        isDestroying: false,
        twinState: event.newState ?? (event.success ? 'deployed' : 'error'),
        lastError: event.success ? null : event.message,
        successMessage: event.success ? event.message : null,
        // terminalLogs are preserved by copyWith's default behavior
      ),
    );

    // Then schedule a background refresh to get updated server state
    // (but don't clear logs - the user can close the terminal manually)
    if (event.success) {
      Future.delayed(const Duration(milliseconds: 500), () {
        add(TwinOverviewRefresh());
      });
    }
  }

  void _onClearMessages(
    TwinOverviewClearMessages event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    emit(
      currentState.copyWith(
        clearSuccess: true,
        clearError: true,
        clearInfo: true,
      ),
    );
  }

  void _onShowMessage(
    TwinOverviewShowMessage event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    switch (event.type) {
      case MessageType.success:
        emit(
          currentState.copyWith(
            successMessage: event.message,
            clearError: true,
            clearInfo: true,
          ),
        );
        break;
      case MessageType.error:
        emit(
          currentState.copyWith(
            errorMessage: event.message,
            clearSuccess: true,
            clearInfo: true,
          ),
        );
        break;
      case MessageType.info:
        emit(
          currentState.copyWith(
            infoMessage: event.message,
            clearSuccess: true,
            clearError: true,
          ),
        );
        break;
    }
  }

  /// Handle close terminal event - hide terminal and clear logs
  void _onCloseTerminal(
    TwinOverviewCloseTerminal event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    emit(currentState.copyWith(showTerminal: false, terminalLogs: const []));
  }

  // ==========================================================================
  // SSE Streaming
  // ==========================================================================

  /// Subscribe to SSE stream for real-time deployment/destroy logs
  void _subscribeToSseStream({
    required String sseUrl,
    String? sessionId,
    required String twinId,
    required bool isDestroy,
  }) {
    _cancelSseSubscription();

    // Create SSE service with auth token
    _sseService = SseService(
      baseUrl: ApiConfig.baseUrl,
      authToken: 'dev-token', // TODO: Get from ApiService
    );

    _sseSubscription = _sseService!
        .streamDeploymentLogs(sseUrl)
        .listen(
          (event) {
            if (event.isHeartbeat) return; // Ignore heartbeats

            if (event.isLog) {
              // Emit log event
              add(TwinOverviewLogReceived(event.message));
            } else if (event.isComplete) {
              // Success completion
              _cancelSseSubscription();
              add(
                TwinOverviewDeploymentComplete(
                  success: true,
                  newState: isDestroy ? 'destroyed' : 'deployed',
                  message: event.message,
                ),
              );
            } else if (event.isError) {
              // Error completion
              _cancelSseSubscription();
              add(
                TwinOverviewDeploymentComplete(
                  success: false,
                  newState: 'error',
                  message: event.message,
                ),
              );
            }
          },
          onError: (e) {
            // SSE connection error - update state
            _cancelSseSubscription();
            add(
              TwinOverviewDeploymentComplete(
                success: false,
                newState: 'error',
                message:
                    'Connection lost: ${ApiErrorHandler.extractMessage(e)}',
              ),
            );
          },
        );
  }

  /// Cancel current SSE subscription
  void _cancelSseSubscription() {
    _sseSubscription?.cancel();
    _sseSubscription = null;
    _sseService?.cancel();
    _sseService = null;
  }

  void _stopPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = null;
  }

  @override
  Future<void> close() {
    _stopPolling();
    _cancelSseSubscription();
    return super.close();
  }

  /// Build loaded state with calculated permissions based on twin state
  TwinOverviewLoaded _buildLoadedState({
    required String twinId,
    required Map<String, dynamic> twin,
    required String twinState,
    Map<String, dynamic>? optimizerConfig,
    Map<String, dynamic>? deployerConfig,
  }) {
    // State-based permission matrix (from implementation plan)
    final canDeploy = ['configured', 'destroyed', 'error'].contains(twinState);
    final canDestroy = ['deployed', 'error'].contains(twinState);
    final canEdit = ![
      'deploying',
      'destroying',
      'deployed',
    ].contains(twinState);
    final canDelete = ![
      'deploying',
      'destroying',
      'deployed',
    ].contains(twinState);

    return TwinOverviewLoaded(
      twinId: twinId,
      projectName: twin['name'] as String? ?? 'Unnamed Twin',
      cloudResourceName:
          deployerConfig?['deployer_digital_twin_name'] as String?,
      twinState: twinState,
      canDeploy: canDeploy,
      canDestroy: canDestroy,
      canEdit: canEdit,
      canDelete: canDelete,
      lastError: twin['last_error'] as String?,
      lastDeploymentLogs: twin['last_deployment_logs'] as String?,
      // Optimizer result and params
      optimizerResult: optimizerConfig?['result'] as Map<String, dynamic>?,
      optimizerParams: optimizerConfig?['params'] as Map<String, dynamic>?,
      cheapestPath: optimizerConfig?['cheapest_path'] as Map<String, dynamic>?,
      calculatedAt: optimizerConfig?['calculated_at'] as String?,
      // Pricing snapshots - match API field names
      pricingAws:
          optimizerConfig?['pricing_aws_snapshot'] as Map<String, dynamic>?,
      pricingAwsUpdatedAt:
          optimizerConfig?['pricing_aws_updated_at'] as String?,
      pricingAzure:
          optimizerConfig?['pricing_azure_snapshot'] as Map<String, dynamic>?,
      pricingAzureUpdatedAt:
          optimizerConfig?['pricing_azure_updated_at'] as String?,
      pricingGcp:
          optimizerConfig?['pricing_gcp_snapshot'] as Map<String, dynamic>?,
      pricingGcpUpdatedAt:
          optimizerConfig?['pricing_gcp_updated_at'] as String?,
      deployerConfig: deployerConfig,
    );
  }
}
