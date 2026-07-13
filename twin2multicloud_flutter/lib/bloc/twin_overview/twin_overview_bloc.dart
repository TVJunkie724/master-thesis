// lib/bloc/twin_overview/twin_overview_bloc.dart
// BLoC for the twin overview screen

import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../services/log_stream_client.dart';
import '../../services/management_api.dart';
import '../../utils/api_error_handler.dart';
import 'twin_overview_event.dart';
import 'twin_overview_state.dart';

class TwinOverviewBloc extends Bloc<TwinOverviewEvent, TwinOverviewState> {
  final ManagementApi _api;
  final LogStreamClientFactory _logStreamClientFactory;
  String? _currentTwinId;
  Timer? _pollingTimer;
  StreamSubscription? _sseSubscription;
  LogStreamClient? _sseService;
  StreamSubscription? _logTraceSseSubscription;
  LogStreamClient? _logTraceSseService;

  TwinOverviewBloc({
    required ManagementApi api,
    required LogStreamClientFactory logStreamClientFactory,
  }) : _api = api,
       _logStreamClientFactory = logStreamClientFactory,
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
    on<TwinOverviewStartLogTrace>(_onStartLogTrace);
    on<TwinOverviewLogTraceUpdate>(_onLogTraceUpdate);
    on<TwinOverviewLogTraceComplete>(_onLogTraceComplete);
    on<TwinOverviewLogTraceError>(_onLogTraceError);
    on<TwinOverviewDownloadSimulator>(_onDownloadSimulator);
    on<TwinOverviewClearSimulatorBytes>(_onClearSimulatorBytes);
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
      final deploymentStatus = await _api.getDeploymentStatus(event.twinId);

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

      final twinState = deploymentStatus.state.apiValue;

      // Fetch outputs for deployed twins (page refresh persistence)
      Map<String, dynamic>? deploymentOutputs;
      DateTime? outputsTimestamp;
      String? outputsError;
      if (twinState == 'deployed') {
        try {
          final outputsResponse = await _api.getDeploymentOutputs(event.twinId);
          deploymentOutputs = outputsResponse.outputs;
          outputsTimestamp = outputsResponse.deployedAt;
        } catch (e) {
          // Not silent - surface error to user
          outputsError =
              'Failed to load outputs: ${ApiErrorHandler.extractMessage(e)}';
        }
      }

      emit(
        _buildLoadedState(
          twinId: event.twinId,
          twin: twin,
          twinState: twinState,
          lastError: deploymentStatus.lastError,
          optimizerConfig: optimizerConfig,
          deployerConfig: deployerConfig,
          deploymentOutputs: deploymentOutputs,
          outputsTimestamp: outputsTimestamp,
          outputsError: outputsError,
        ),
      );

      // If the twin is deploying/destroying, try to reconnect to the active SSE session
      // (handles the case where user navigated away and came back)
      if (['deploying', 'destroying'].contains(twinState)) {
        final isDestroy = twinState == 'destroying';
        final activeSession = deploymentStatus.activeSession;
        if (activeSession != null) {
          try {
            final sseUrl = activeSession.sseUrl;

            // Update UI to show terminal with reconnection indicator
            final currentState = state;
            if (currentState is TwinOverviewLoaded) {
              emit(
                currentState.copyWith(
                  isDeploying: !isDestroy,
                  isDestroying: isDestroy,
                  showTerminal: true,
                  terminalLogs: ['> Reconnected to active session...'],
                ),
              );
            }

            // Reuse existing SSE subscription method
            _subscribeToSseStream(
              sseUrl: sseUrl,
              sessionId: activeSession.sessionId,
              twinId: event.twinId,
              isDestroy: isDestroy,
            );
          } catch (e) {
            debugPrint('[TwinOverviewBloc] SSE reconnect failed: $e');
            // Non-fatal — the persisted operation state remains visible.
          }
        }
      }
    } catch (e) {
      debugPrint(
        '[TwinOverviewBloc] Failed to load twin: ${ApiErrorHandler.extractMessage(e)}',
      );
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
        final deploymentStatus = await _api.getDeploymentStatus(
          _currentTwinId!,
        );
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

        final twinState = deploymentStatus.state.apiValue;
        Map<String, dynamic>? deploymentOutputs;
        DateTime? outputsTimestamp;
        String? outputsError;
        if (twinState == 'deployed') {
          try {
            final outputs = await _api.getDeploymentOutputs(_currentTwinId!);
            deploymentOutputs = outputs.outputs;
            outputsTimestamp = outputs.deployedAt;
          } catch (error) {
            deploymentOutputs = currentState is TwinOverviewLoaded
                ? currentState.deploymentOutputs
                : null;
            outputsTimestamp = currentState is TwinOverviewLoaded
                ? currentState.outputsTimestamp
                : null;
            outputsError =
                'Failed to refresh outputs: ${ApiErrorHandler.extractMessage(error)}';
          }
        } else if (twinState == 'deploying') {
          deploymentOutputs = currentState is TwinOverviewLoaded
              ? currentState.deploymentOutputs
              : null;
          outputsTimestamp = currentState is TwinOverviewLoaded
              ? currentState.outputsTimestamp
              : null;
        }
        final freshState = _buildLoadedState(
          twinId: _currentTwinId!,
          twin: twin,
          twinState: twinState,
          lastError: deploymentStatus.lastError,
          optimizerConfig: optimizerConfig,
          deployerConfig: deployerConfig,
          deploymentOutputs: deploymentOutputs,
          outputsTimestamp: outputsTimestamp,
          outputsError: outputsError,
        );

        // Emit fresh state but preserve terminal state
        emit(
          freshState.copyWith(
            terminalLogs: preservedLogs,
            showTerminal: preservedShowTerminal,
          ),
        );
      } catch (e) {
        if (currentState is TwinOverviewLoaded) {
          emit(
            currentState.copyWith(
              errorMessage:
                  'Refresh failed: ${ApiErrorHandler.extractMessage(e)}',
            ),
          );
        }
      }
    }
  }

  Future<void> _onDeploy(
    TwinOverviewDeploy event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    final perms = _permissionsForState('deploying');
    emit(
      currentState.copyWith(
        isDeploying: true,
        twinState: 'deploying',
        canDeploy: perms['canDeploy'],
        canDestroy: perms['canDestroy'],
        canEdit: perms['canEdit'],
        canDelete: perms['canDelete'],
        showTerminal: true,
        terminalLogs: ['> Starting deployment...'],
        clearDeploymentOutputs: true,
        clearOutputsTimestamp: true,
        clearOutputsError: true,
        clearLastError: true,
        clearSuccess: true,
        clearError: true,
        clearInfo: true,
      ),
    );

    try {
      // Call backend to start deployment - now returns session_id and sse_url
      final result = await _api.deployTwin(currentState.twinId);

      // SSE streaming mode - subscribe to log stream
      _subscribeToSseStream(
        sseUrl: result.sseUrl,
        sessionId: result.sessionId,
        twinId: currentState.twinId,
        isDestroy: false,
      );
    } catch (e) {
      debugPrint(
        '[TwinOverviewBloc] Deployment failed: ${ApiErrorHandler.extractMessage(e)}',
      );
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          isDeploying: false,
          errorMessage:
              'Deployment failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
      // Refresh from backend to get the correct rolled-back state
      add(TwinOverviewRefresh());
    }
  }

  Future<void> _onDestroy(
    TwinOverviewDestroy event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    final perms = _permissionsForState('destroying');
    emit(
      currentState.copyWith(
        isDestroying: true,
        twinState: 'destroying',
        canDeploy: perms['canDeploy'],
        canDestroy: perms['canDestroy'],
        canEdit: perms['canEdit'],
        canDelete: perms['canDelete'],
        showTerminal: true,
        terminalLogs: ['> Starting resource destruction...'],
        clearSuccess: true,
        clearError: true,
        clearInfo: true,
      ),
    );

    try {
      // Call backend to start destruction - now returns session_id and sse_url
      final result = await _api.destroyTwin(currentState.twinId);

      // SSE streaming mode - subscribe to log stream
      _subscribeToSseStream(
        sseUrl: result.sseUrl,
        sessionId: result.sessionId,
        twinId: currentState.twinId,
        isDestroy: true,
      );
    } catch (e) {
      debugPrint(
        '[TwinOverviewBloc] Destroy failed: ${ApiErrorHandler.extractMessage(e)}',
      );
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          isDestroying: false,
          errorMessage: 'Destroy failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
      // Refresh from backend to get the correct rolled-back state
      add(TwinOverviewRefresh());
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
      debugPrint(
        '[TwinOverviewBloc] Delete failed: ${ApiErrorHandler.extractMessage(e)}',
      );
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

    // Clear outputs on destroy, store on deploy
    final isDestroy = event.newState == 'destroyed';

    // First emit state update that PRESERVES terminal logs so they stay visible
    final newState = event.newState ?? (event.success ? 'deployed' : 'error');
    final perms = _permissionsForState(newState);
    final failureMessage = event.success
        ? null
        : (event.message ?? 'Deployment operation failed.');
    final hasCurrentOutputs = !isDestroy && event.outputs != null;
    emit(
      currentState.copyWith(
        isDeploying: false,
        isDestroying: false,
        twinState: newState,
        canDeploy: perms['canDeploy'],
        canDestroy: perms['canDestroy'],
        canEdit: perms['canEdit'],
        canDelete: perms['canDelete'],
        lastError: failureMessage,
        clearLastError: event.success,
        successMessage: event.success ? event.message : null,
        errorMessage: failureMessage,
        clearError: event.success,
        // Store outputs from SSE on successful deploy, clear on destroy
        deploymentOutputs: isDestroy ? null : event.outputs,
        clearDeploymentOutputs: !hasCurrentOutputs,
        outputsTimestamp: hasCurrentOutputs ? DateTime.now() : null,
        clearOutputsTimestamp: !hasCurrentOutputs,
        clearOutputsError: true,
        // terminalLogs are preserved by copyWith's default behavior
      ),
    );

    // Always refresh from backend to ensure state is synchronized
    Future.delayed(const Duration(milliseconds: 500), () {
      if (!isClosed) add(TwinOverviewRefresh());
    });
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
  // Log Trace
  // ==========================================================================

  Future<void> _onStartLogTrace(
    TwinOverviewStartLogTrace event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    // Must be deployed to trace logs
    if (currentState.twinState != 'deployed') {
      emit(
        currentState.copyWith(
          errorMessage: 'Twin must be deployed to trace logs',
        ),
      );
      return;
    }

    emit(
      currentState.copyWith(
        isTracing: true,
        showTerminal: true,
        terminalLogs: ['> Starting log trace test...'],
        clearTraceId: true,
        clearSuccess: true,
        clearError: true,
        clearInfo: true,
      ),
    );

    try {
      // Call backend to start log trace
      final result = await _api.startLogTrace(currentState.twinId);

      // Add trace info to terminal
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          traceId: result.traceId,
          terminalLogs: [
            ...activeState.terminalLogs,
            '> Trace ID: ${result.traceId}',
            '> Providers: ${result.providers.join(", ")}',
            '> Streaming logs for 90 seconds...',
            '',
          ],
        ),
      );

      // Subscribe to log trace SSE stream
      // For test mode, use the sse_url returned by backend; otherwise construct URL
      _subscribeToLogTraceSseStream(
        twinId: currentState.twinId,
        traceId: result.traceId,
        sseUrl: result.sseUrl,
      );
    } catch (e) {
      debugPrint(
        '[TwinOverviewBloc] Log trace failed: ${ApiErrorHandler.extractMessage(e)}',
      );
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          isTracing: false,
          clearTraceId: true,
          errorMessage:
              'Log trace failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  void _onLogTraceUpdate(
    TwinOverviewLogTraceUpdate event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    final newLogs = [...currentState.terminalLogs, event.logLine];
    emit(currentState.copyWith(terminalLogs: newLogs));
  }

  void _onLogTraceComplete(
    TwinOverviewLogTraceComplete event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    _cancelLogTraceSseSubscription();

    final newLogs = [
      ...currentState.terminalLogs,
      '',
      '> Trace complete. Total logs: ${event.totalLogs ?? 0}',
    ];

    emit(currentState.copyWith(isTracing: false, terminalLogs: newLogs));
  }

  void _onLogTraceError(
    TwinOverviewLogTraceError event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    _cancelLogTraceSseSubscription();

    emit(currentState.copyWith(isTracing: false, errorMessage: event.message));
  }

  void _subscribeToLogTraceSseStream({
    required String twinId,
    required String traceId,
    String? sseUrl,
  }) {
    _cancelLogTraceSseSubscription();

    _logTraceSseService = _logStreamClientFactory();

    // Use provided sseUrl (from test endpoint) or construct default URL
    final streamUrl = sseUrl ?? '/twins/$twinId/log-trace/stream/$traceId';

    _logTraceSseSubscription = _logTraceSseService!
        .streamDeploymentLogs(streamUrl)
        .listen(
          (event) {
            // Handle events by SSE type (now consistent between mock and real)
            if (event.isHeartbeat) {
              add(TwinOverviewLogTraceUpdate('...'));
              return;
            }

            if (event.type == 'done') {
              final data = event.data?['data'];
              final logCount = data is Map ? data['log_count'] as int? : null;
              add(TwinOverviewLogTraceComplete(totalLogs: logCount));
              return;
            }

            if (event.isError) {
              add(TwinOverviewLogTraceError(event.message));
              return;
            }

            // Regular log event - format with aligned columns
            if (event.type == 'log') {
              add(TwinOverviewLogTraceUpdate(_formatLogEvent(event)));
            }
          },
          onError: (e) {
            _cancelLogTraceSseSubscription();
            add(
              TwinOverviewLogTraceError(
                'Connection lost: ${ApiErrorHandler.extractMessage(e)}',
              ),
            );
          },
        );
  }

  void _cancelLogTraceSseSubscription() {
    _logTraceSseSubscription?.cancel();
    _logTraceSseSubscription = null;
    _logTraceSseService?.cancel();
    _logTraceSseService = null;
  }

  /// Parse log data from SSE event.
  /// Returns null if parsing fails.
  Map<String, dynamic>? _parseLogData(SseLogEvent event) {
    final outerData = event.data;
    if (outerData == null) return null;

    final innerDataRaw = outerData['data'];
    if (innerDataRaw is String) {
      try {
        return json.decode(innerDataRaw) as Map<String, dynamic>?;
      } catch (_) {
        return null;
      }
    } else if (innerDataRaw is Map<String, dynamic>) {
      return innerDataRaw;
    }
    return null;
  }

  /// Format log trace event with aligned columns
  /// Output: [HH:MM:SS] L1 AWS   │ function         │ message
  String _formatLogEvent(SseLogEvent event) {
    final logData = _parseLogData(event);
    if (logData == null) return event.message;

    final timestamp = logData['timestamp'] as String?;
    final layer = logData['layer'] as String? ?? '';
    final provider = (logData['provider'] as String?)?.toUpperCase() ?? '';
    final function = logData['function'] as String? ?? '';
    final message = logData['message'] as String? ?? event.message;

    final time = timestamp != null
        ? DateTime.tryParse(timestamp)?.toLocal()
        : DateTime.now();
    final timeStr = time != null
        ? '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}:${time.second.toString().padLeft(2, '0')}'
        : '';

    return '[$timeStr] $layer ${provider.padRight(5)} │ ${function.padRight(16)} │ $message';
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
    _sseService = _logStreamClientFactory();

    _sseSubscription = _sseService!
        .streamDeploymentLogs(sseUrl)
        .listen(
          (event) {
            if (event.isHeartbeat) return; // Ignore heartbeats

            if (event.isLog) {
              // Emit log event
              add(TwinOverviewLogReceived(event.message));
            } else if (event.isComplete) {
              // Success completion - pass outputs from SSE
              _cancelSseSubscription();
              add(
                TwinOverviewDeploymentComplete(
                  success: true,
                  newState: isDestroy ? 'destroyed' : 'deployed',
                  message: event.message,
                  outputs: event.outputs, // Pass outputs from SSE event
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
            // SSE connection error — don't decide state, poll backend instead
            debugPrint(
              '[TwinOverviewBloc] SSE connection lost: ${ApiErrorHandler.extractMessage(e)}',
            );
            _cancelSseSubscription();
            // Wait briefly for the backend to finish its DB commit
            Future.delayed(const Duration(seconds: 3), () {
              if (!isClosed) add(TwinOverviewRefresh());
            });
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
    _cancelLogTraceSseSubscription();
    return super.close();
  }

  /// Recalculate permissions for a given twinState.
  /// Single source of truth — used by _buildLoadedState and all copyWith transitions.
  static Map<String, bool> _permissionsForState(String twinState) {
    return {
      'canDeploy': ['configured', 'destroyed', 'error'].contains(twinState),
      'canDestroy': ['deployed', 'error'].contains(twinState),
      'canEdit': !['deploying', 'destroying', 'deployed'].contains(twinState),
      'canDelete': !['deploying', 'destroying', 'deployed'].contains(twinState),
    };
  }

  /// Build loaded state with calculated permissions based on twin state
  TwinOverviewLoaded _buildLoadedState({
    required String twinId,
    required Map<String, dynamic> twin,
    required String twinState,
    String? lastError,
    Map<String, dynamic>? optimizerConfig,
    Map<String, dynamic>? deployerConfig,
    Map<String, dynamic>? deploymentOutputs,
    DateTime? outputsTimestamp,
    String? outputsError,
  }) {
    final perms = _permissionsForState(twinState);

    return TwinOverviewLoaded(
      twinId: twinId,
      projectName: twin['name'] as String? ?? 'Unnamed Twin',
      cloudResourceName:
          deployerConfig?['deployer_digital_twin_name'] as String?,
      twinState: twinState,
      canDeploy: perms['canDeploy']!,
      canDestroy: perms['canDestroy']!,
      canEdit: perms['canEdit']!,
      canDelete: perms['canDelete']!,
      lastError: lastError,
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
      // Terraform outputs
      deploymentOutputs: deploymentOutputs,
      outputsTimestamp: outputsTimestamp,
      outputsError: outputsError,
    );
  }

  /// Handle simulator download request
  Future<void> _onDownloadSimulator(
    TwinOverviewDownloadSimulator event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;
    if (currentState.twinState != 'deployed') return;

    emit(
      currentState.copyWith(
        isDownloadingSimulator: true,
        infoMessage: 'Downloading simulator...',
        clearSuccess: true,
        clearError: true,
        clearSimulatorBytes: true,
        clearSimulatorFilename: true,
      ),
    );

    try {
      final download = await _api.downloadSimulator(currentState.twinId);
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          isDownloadingSimulator: false,
          simulatorBytes: download.bytes,
          simulatorFilename: download.filename,
          clearInfo: true,
        ),
      );
    } catch (e) {
      debugPrint(
        '[TwinOverviewBloc] Download failed: ${ApiErrorHandler.extractMessage(e)}',
      );
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          isDownloadingSimulator: false,
          errorMessage: 'Download failed: ${ApiErrorHandler.extractMessage(e)}',
          clearInfo: true,
          clearSimulatorBytes: true,
          clearSimulatorFilename: true,
        ),
      );
    }
  }

  /// Handle clearing simulator bytes from state
  void _onClearSimulatorBytes(
    TwinOverviewClearSimulatorBytes event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;
    emit(
      currentState.copyWith(
        clearSimulatorBytes: true,
        clearSimulatorFilename: true,
      ),
    );
  }
}
