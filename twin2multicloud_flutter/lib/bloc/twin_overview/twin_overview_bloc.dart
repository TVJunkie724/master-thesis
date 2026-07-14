// lib/bloc/twin_overview/twin_overview_bloc.dart
// BLoC for the twin overview screen

import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../models/deployment_operations.dart';
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
  Timer? _deploymentReconnectTimer;
  Timer? _postOperationRefreshTimer;
  int _deploymentStreamGeneration = 0;
  StreamSubscription? _logTraceSseSubscription;
  LogStreamClient? _logTraceSseService;
  final Duration _reconnectDelay;
  final DateTime Function() _clock;

  static const _maxReconnectAttempts = 3;

  TwinOverviewBloc({
    required ManagementApi api,
    required LogStreamClientFactory logStreamClientFactory,
    Duration reconnectDelay = const Duration(seconds: 2),
    DateTime Function()? clock,
  }) : _api = api,
       _logStreamClientFactory = logStreamClientFactory,
       _reconnectDelay = reconnectDelay,
       _clock = clock ?? DateTime.now,
       super(const TwinOverviewLoading()) {
    on<TwinOverviewLoad>(_onLoad);
    on<TwinOverviewRefresh>(_onRefresh);
    on<TwinOverviewRunDeploymentPreflight>(_onRunDeploymentPreflight);
    on<TwinOverviewDeploy>(_onDeploy);
    on<TwinOverviewDestroy>(_onDestroy);
    on<TwinOverviewDelete>(_onDelete);
    on<TwinOverviewDeploymentComplete>(_onDeploymentComplete);
    on<_DeploymentStreamData>(_onDeploymentStreamData);
    on<_DeploymentStreamDisconnected>(_onDeploymentStreamDisconnected);
    on<_DeploymentReconnectDue>(_onDeploymentReconnectDue);
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
      final deploymentReadiness = await _loadCachedReadiness(event.twinId);

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

      var loadedState = _buildLoadedState(
        twinId: event.twinId,
        twin: twin,
        twinState: twinState,
        lastError: deploymentStatus.lastError,
        optimizerConfig: optimizerConfig,
        deployerConfig: deployerConfig,
        deploymentOutputs: deploymentOutputs,
        outputsTimestamp: outputsTimestamp,
        outputsError: outputsError,
        deploymentReadiness: deploymentReadiness,
      );
      final activeSession = deploymentStatus.activeSession;
      if (activeSession != null &&
          ['deploying', 'destroying'].contains(twinState)) {
        loadedState = loadedState.copyWith(
          deploymentOperation: DeploymentOperationViewState(
            phase: DeploymentOperationViewPhase.reconnecting,
            operationType: activeSession.operationType,
            session: activeSession,
            reconnectAttempt: 0,
            showLogs: true,
            message: 'Restoring the active deployment log stream.',
          ),
        );
      }
      emit(loadedState);

      if (activeSession != null &&
          ['deploying', 'destroying'].contains(twinState)) {
        await _catchUpAndSubscribe(emit, reconnecting: true);
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
        final deploymentReadiness = await _loadCachedReadiness(
          _currentTwinId!,
          previous: currentState is TwinOverviewLoaded
              ? currentState.deploymentReadiness
              : null,
        );
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
        var deploymentOperation = currentState is TwinOverviewLoaded
            ? currentState.deploymentOperation
            : const DeploymentOperationViewState();
        if (deploymentOperation.isActive &&
            !{'deploying', 'destroying'}.contains(twinState)) {
          deploymentOperation = deploymentOperation.copyWith(
            phase: twinState == 'error'
                ? DeploymentOperationViewPhase.failed
                : DeploymentOperationViewPhase.completed,
            message:
                deploymentStatus.lastError ??
                (twinState == 'destroyed'
                    ? 'Resource destruction completed.'
                    : 'Deployment completed.'),
            showLogs: true,
          );
          _cancelSseSubscription();
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
          deploymentReadiness: deploymentReadiness,
          deploymentOperation: deploymentOperation,
        );

        emit(
          freshState.copyWith(
            showTraceTerminal: currentState is TwinOverviewLoaded
                ? currentState.showTraceTerminal
                : false,
            traceTerminalLogs: currentState is TwinOverviewLoaded
                ? currentState.traceTerminalLogs
                : const [],
          ),
        );

        final activeSession = deploymentStatus.activeSession;
        if (activeSession != null && !deploymentOperation.isActive) {
          final activeState = state;
          if (activeState is TwinOverviewLoaded) {
            emit(
              activeState.copyWith(
                deploymentOperation: DeploymentOperationViewState(
                  phase: DeploymentOperationViewPhase.reconnecting,
                  operationType: activeSession.operationType,
                  session: activeSession,
                  showLogs: true,
                  message: 'Restoring the active deployment log stream.',
                ),
              ),
            );
            await _catchUpAndSubscribe(emit, reconnecting: true);
          }
        }
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
    if (!currentState.deploymentReadiness.isDeployable) {
      emit(
        currentState.copyWith(
          errorMessage:
              'Deployment is blocked until the current provider preflight passes.',
        ),
      );
      return;
    }

    final perms = _permissionsForState('deploying');
    emit(
      currentState.copyWith(
        deploymentOperation: DeploymentOperationViewState.starting(
          DeploymentOperationType.deploy,
        ),
        twinState: 'deploying',
        canDeploy: perms['canDeploy'],
        canDestroy: perms['canDestroy'],
        canEdit: perms['canEdit'],
        canDelete: perms['canDelete'],
        showTraceTerminal: false,
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
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          deploymentOperation: activeState.deploymentOperation.copyWith(
            phase: DeploymentOperationViewPhase.connecting,
            session: result,
            clearMessage: true,
          ),
        ),
      );
      await _catchUpAndSubscribe(emit);
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
          deploymentOperation: activeState.deploymentOperation.copyWith(
            phase: DeploymentOperationViewPhase.failed,
            message: 'Deployment failed: ${ApiErrorHandler.extractMessage(e)}',
            showLogs: true,
          ),
          errorMessage:
              'Deployment failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
      // Refresh from backend to get the correct rolled-back state
      add(TwinOverviewRefresh());
    }
  }

  Future<void> _onRunDeploymentPreflight(
    TwinOverviewRunDeploymentPreflight event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded ||
        currentState.deploymentReadiness.phase ==
            DeploymentReadinessViewPhase.loading) {
      return;
    }

    final previous = currentState.deploymentReadiness.snapshot;
    emit(
      currentState.copyWith(
        deploymentReadiness: DeploymentReadinessViewState.loading(
          previous: previous,
        ),
        clearError: true,
      ),
    );
    try {
      final snapshot = await _api.runDeploymentPreflight(currentState.twinId);
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          deploymentReadiness: DeploymentReadinessViewState.fromSnapshot(
            snapshot,
          ),
        ),
      );
    } catch (error) {
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          deploymentReadiness: DeploymentReadinessViewState.failed(
            'Preflight failed: ${ApiErrorHandler.extractMessage(error)}',
            previous: previous,
          ),
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

    final perms = _permissionsForState('destroying');
    emit(
      currentState.copyWith(
        deploymentOperation: DeploymentOperationViewState.starting(
          DeploymentOperationType.destroy,
        ),
        twinState: 'destroying',
        canDeploy: perms['canDeploy'],
        canDestroy: perms['canDestroy'],
        canEdit: perms['canEdit'],
        canDelete: perms['canDelete'],
        showTraceTerminal: false,
        clearSuccess: true,
        clearError: true,
        clearInfo: true,
      ),
    );

    try {
      // Call backend to start destruction - now returns session_id and sse_url
      final result = await _api.destroyTwin(currentState.twinId);
      final activeState = state;
      if (activeState is! TwinOverviewLoaded ||
          activeState.twinId != currentState.twinId) {
        return;
      }
      emit(
        activeState.copyWith(
          deploymentOperation: activeState.deploymentOperation.copyWith(
            phase: DeploymentOperationViewPhase.connecting,
            session: result,
            clearMessage: true,
          ),
        ),
      );
      await _catchUpAndSubscribe(emit);
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
          deploymentOperation: activeState.deploymentOperation.copyWith(
            phase: DeploymentOperationViewPhase.failed,
            message: 'Destroy failed: ${ApiErrorHandler.extractMessage(e)}',
            showLogs: true,
          ),
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

  void _onDeploymentComplete(
    TwinOverviewDeploymentComplete event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    _applyDeploymentComplete(currentState, event, emit);
  }

  void _applyDeploymentComplete(
    TwinOverviewLoaded currentState,
    TwinOverviewDeploymentComplete event,
    Emitter<TwinOverviewState> emit,
  ) {
    _cancelSseSubscription();

    // Clear outputs on destroy, store on deploy
    final isDestroy = event.newState == 'destroyed';

    // First emit state update that PRESERVES terminal logs so they stay visible
    final newState = event.newState ?? (event.success ? 'deployed' : 'error');
    final perms = _permissionsForState(newState);
    final failureMessage = event.success
        ? null
        : (event.message ?? 'Deployment operation failed.');
    final hasCurrentOutputs = !isDestroy && event.outputs != null;
    final currentOperation = currentState.deploymentOperation;
    final operationType =
        currentOperation.operationType ??
        (isDestroy
            ? DeploymentOperationType.destroy
            : DeploymentOperationType.deploy);
    final completedOperation = currentOperation.copyWith(
      phase: event.success
          ? DeploymentOperationViewPhase.completed
          : DeploymentOperationViewPhase.failed,
      operationType: operationType,
      lastEventId: event.eventId == null
          ? currentOperation.lastEventId
          : event.eventId! > currentOperation.lastEventId
          ? event.eventId
          : currentOperation.lastEventId,
      reconnectAttempt: 0,
      showLogs: true,
      message:
          event.message ??
          (event.success
              ? (isDestroy
                    ? 'Resource destruction completed.'
                    : 'Deployment completed.')
              : 'Deployment operation failed.'),
    );
    emit(
      currentState.copyWith(
        deploymentOperation: completedOperation,
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
        outputsTimestamp: hasCurrentOutputs ? _clock() : null,
        clearOutputsTimestamp: !hasCurrentOutputs,
        clearOutputsError: true,
      ),
    );

    _postOperationRefreshTimer?.cancel();
    _postOperationRefreshTimer = Timer(const Duration(milliseconds: 500), () {
      if (!isClosed) add(const TwinOverviewRefresh());
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

    if (currentState.showTraceTerminal) {
      emit(
        currentState.copyWith(
          showTraceTerminal: false,
          traceTerminalLogs: const [],
        ),
      );
      return;
    }
    emit(
      currentState.copyWith(
        deploymentOperation: currentState.deploymentOperation.copyWith(
          showLogs: false,
        ),
      ),
    );
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
        deploymentOperation: currentState.deploymentOperation.copyWith(
          showLogs: false,
        ),
        showTraceTerminal: true,
        traceTerminalLogs: ['> Starting log trace test...'],
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
          traceTerminalLogs: [
            ...activeState.traceTerminalLogs,
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

    final newLogs = [...currentState.traceTerminalLogs, event.logLine];
    emit(currentState.copyWith(traceTerminalLogs: newLogs));
  }

  void _onLogTraceComplete(
    TwinOverviewLogTraceComplete event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    _cancelLogTraceSseSubscription();

    final newLogs = [
      ...currentState.traceTerminalLogs,
      '',
      '> Trace complete. Total logs: ${event.totalLogs ?? 0}',
    ];

    emit(currentState.copyWith(isTracing: false, traceTerminalLogs: newLogs));
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

  Future<void> _catchUpAndSubscribe(
    Emitter<TwinOverviewState> emit, {
    bool reconnecting = false,
  }) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    final operation = currentState.deploymentOperation;
    final session = operation.session;
    final operationType = operation.operationType;
    if (session == null || operationType == null || !operation.isActive) return;

    _cancelSseSubscription();
    final generation = _deploymentStreamGeneration;
    var recovered = operation.copyWith(
      phase: reconnecting
          ? DeploymentOperationViewPhase.reconnecting
          : DeploymentOperationViewPhase.connecting,
      showLogs: true,
      message: reconnecting
          ? 'Recovering persisted deployment logs.'
          : 'Connecting to the deployment log stream.',
    );
    emit(currentState.copyWith(deploymentOperation: recovered));

    try {
      var hasMore = true;
      while (hasMore) {
        final page = await _api.getDeploymentLogs(
          currentState.twinId,
          sessionId: session.sessionId,
          afterEventId: recovered.lastEventId,
          limit: DeploymentOperationViewState.maxLogEntries,
        );
        _validateLogPage(
          page,
          twinId: currentState.twinId,
          sessionId: session.sessionId,
          expectedCursor: recovered.lastEventId,
          operationType: operationType,
        );
        for (final entry in page.logs) {
          recovered = recovered.append(entry);
        }
        hasMore = page.hasMore;
        if (hasMore && page.logs.isEmpty) {
          throw const _DeploymentStreamContractException(
            'Deployment log pagination did not advance the cursor.',
          );
        }
      }

      final activeState = state;
      if (!_isCurrentOperation(activeState, session.sessionId, generation)) {
        return;
      }
      recovered = recovered.copyWith(
        phase: DeploymentOperationViewPhase.streaming,
        reconnectAttempt: reconnecting ? recovered.reconnectAttempt : 0,
        clearMessage: true,
      );
      emit(
        (activeState as TwinOverviewLoaded).copyWith(
          deploymentOperation: recovered,
        ),
      );
      _subscribeToDeploymentStream(
        session: session,
        lastEventId: recovered.lastEventId,
        generation: generation,
      );
    } catch (error) {
      final activeState = state;
      if (!_isCurrentOperation(activeState, session.sessionId, generation)) {
        return;
      }
      await _handleDeploymentConnectionFailure(
        activeState as TwinOverviewLoaded,
        emit,
        'Log recovery failed: ${ApiErrorHandler.extractMessage(error)}',
      );
    }
  }

  void _validateLogPage(
    DeploymentLogPage page, {
    required String twinId,
    required String sessionId,
    required int expectedCursor,
    required DeploymentOperationType operationType,
  }) {
    if (page.twinId != twinId || page.sessionId != sessionId) {
      throw const _DeploymentStreamContractException(
        'Deployment log page belongs to another twin or session.',
      );
    }
    if (page.afterEventId != expectedCursor) {
      throw const _DeploymentStreamContractException(
        'Deployment log page returned an unexpected cursor.',
      );
    }
    var cursor = expectedCursor;
    for (final entry in page.logs) {
      if (entry.sessionId != sessionId ||
          entry.operationType != operationType.apiValue) {
        throw const _DeploymentStreamContractException(
          'Deployment log entry belongs to another operation.',
        );
      }
      if (entry.eventId != cursor + 1) {
        throw const _DeploymentStreamContractException(
          'Deployment log history contains an event gap.',
        );
      }
      cursor = entry.eventId;
    }
    if (page.nextAfterEventId != null && page.nextAfterEventId != cursor) {
      throw const _DeploymentStreamContractException(
        'Deployment log page returned an inconsistent next cursor.',
      );
    }
  }

  void _subscribeToDeploymentStream({
    required OperationSession session,
    required int lastEventId,
    required int generation,
  }) {
    _sseService = _logStreamClientFactory();
    var terminalReceived = false;
    var streamCursor = lastEventId;
    _sseSubscription = _sseService!
        .streamDeploymentLogs(session.sseUrl, lastEventId: lastEventId)
        .listen(
          (event) {
            final advancesCursor = event.id == streamCursor + 1;
            if (advancesCursor) streamCursor = event.id;
            terminalReceived =
                terminalReceived ||
                ((event.isComplete || event.isError) && advancesCursor);
            if (!isClosed) {
              add(
                _DeploymentStreamData(
                  event: event,
                  generation: generation,
                  sessionId: session.sessionId,
                ),
              );
            }
          },
          onError: (Object error, StackTrace stackTrace) {
            if (!isClosed) {
              add(
                _DeploymentStreamDisconnected(
                  error: error,
                  generation: generation,
                  sessionId: session.sessionId,
                ),
              );
            }
          },
          onDone: () {
            if (!terminalReceived && !isClosed) {
              add(
                _DeploymentStreamDisconnected(
                  generation: generation,
                  sessionId: session.sessionId,
                ),
              );
            }
          },
          cancelOnError: true,
        );
  }

  Future<void> _onDeploymentStreamData(
    _DeploymentStreamData event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (!_isCurrentOperation(currentState, event.sessionId, event.generation)) {
      return;
    }
    if (event.event.isHeartbeat) return;

    final loaded = currentState as TwinOverviewLoaded;
    final operation = loaded.deploymentOperation;
    if (event.event.type == 'catchup_required') {
      await _handleDeploymentConnectionFailure(
        loaded,
        emit,
        'The live stream requires persisted log catch-up.',
      );
      return;
    }
    if (event.event.id <= operation.lastEventId) return;
    if (event.event.id != operation.lastEventId + 1) {
      await _handleDeploymentConnectionFailure(
        loaded,
        emit,
        'A deployment log event gap was detected.',
      );
      return;
    }

    if (event.event.isLog) {
      final entry = DeploymentLogEntry(
        eventId: event.event.id,
        sessionId: event.sessionId,
        timestamp: event.event.timestamp ?? _clock(),
        level: event.event.level ?? 'info',
        message: event.event.message,
        operationType: operation.operationType!.apiValue,
      );
      emit(
        loaded.copyWith(
          deploymentOperation: operation
              .append(entry)
              .copyWith(
                phase: DeploymentOperationViewPhase.streaming,
                reconnectAttempt: 0,
                clearMessage: true,
              ),
        ),
      );
      return;
    }

    if (event.event.isComplete || event.event.isError) {
      _applyDeploymentComplete(
        loaded,
        TwinOverviewDeploymentComplete(
          success: event.event.isComplete,
          newState: event.event.isComplete
              ? (operation.operationType == DeploymentOperationType.destroy
                    ? 'destroyed'
                    : 'deployed')
              : 'error',
          message: event.event.message,
          outputs: event.event.outputs,
          eventId: event.event.id,
        ),
        emit,
      );
      return;
    }

    await _handleDeploymentConnectionFailure(
      loaded,
      emit,
      'The deployment stream returned an unsupported event type.',
    );
  }

  Future<void> _onDeploymentStreamDisconnected(
    _DeploymentStreamDisconnected event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (!_isCurrentOperation(currentState, event.sessionId, event.generation)) {
      return;
    }
    final detail = event.error == null
        ? 'The deployment log stream closed before a terminal event.'
        : 'Deployment log connection lost: '
              '${ApiErrorHandler.extractMessage(event.error!)}';
    await _handleDeploymentConnectionFailure(
      currentState as TwinOverviewLoaded,
      emit,
      detail,
    );
  }

  Future<void> _handleDeploymentConnectionFailure(
    TwinOverviewLoaded currentState,
    Emitter<TwinOverviewState> emit,
    String message,
  ) async {
    _cancelSseSubscription();
    final operation = currentState.deploymentOperation;
    final session = operation.session;
    if (session == null || !operation.isActive) return;

    final nextAttempt = operation.reconnectAttempt + 1;
    if (nextAttempt > _maxReconnectAttempts) {
      await _resolveDeploymentAfterReconnectExhausted(
        currentState,
        emit,
        message,
      );
      return;
    }

    final reconnecting = operation.copyWith(
      phase: DeploymentOperationViewPhase.reconnecting,
      reconnectAttempt: nextAttempt,
      showLogs: true,
      message: '$message Reconnecting ($nextAttempt/$_maxReconnectAttempts).',
    );
    emit(currentState.copyWith(deploymentOperation: reconnecting));
    final generation = _deploymentStreamGeneration;
    _deploymentReconnectTimer = Timer(_reconnectDelay, () {
      if (!isClosed) {
        add(
          _DeploymentReconnectDue(
            generation: generation,
            sessionId: session.sessionId,
          ),
        );
      }
    });
  }

  Future<void> _resolveDeploymentAfterReconnectExhausted(
    TwinOverviewLoaded currentState,
    Emitter<TwinOverviewState> emit,
    String connectionMessage,
  ) async {
    try {
      final status = await _api.getDeploymentStatus(currentState.twinId);
      final stateValue = status.state.apiValue;
      if ({'deployed', 'destroyed', 'error'}.contains(stateValue)) {
        _applyDeploymentComplete(
          currentState,
          TwinOverviewDeploymentComplete(
            success: stateValue != 'error',
            newState: stateValue,
            message:
                status.lastError ??
                (stateValue == 'destroyed'
                    ? 'Resource destruction completed.'
                    : 'Deployment completed.'),
          ),
          emit,
        );
        return;
      }
    } catch (error) {
      connectionMessage =
          '$connectionMessage Status check failed: '
          '${ApiErrorHandler.extractMessage(error)}';
    }

    emit(
      currentState.copyWith(
        deploymentOperation: currentState.deploymentOperation.copyWith(
          phase: DeploymentOperationViewPhase.failed,
          reconnectAttempt: _maxReconnectAttempts,
          showLogs: true,
          message:
              '$connectionMessage Live logs are unavailable; refresh to retry.',
        ),
        errorMessage:
            'Live deployment logs are unavailable. The cloud operation status was not changed.',
      ),
    );
  }

  Future<void> _onDeploymentReconnectDue(
    _DeploymentReconnectDue event,
    Emitter<TwinOverviewState> emit,
  ) async {
    _deploymentReconnectTimer = null;
    final currentState = state;
    if (!_isCurrentOperation(currentState, event.sessionId, event.generation)) {
      return;
    }
    await _catchUpAndSubscribe(emit, reconnecting: true);
  }

  bool _isCurrentOperation(
    TwinOverviewState candidate,
    String sessionId,
    int generation,
  ) {
    return !isClosed &&
        candidate is TwinOverviewLoaded &&
        candidate.deploymentOperation.isActive &&
        candidate.deploymentOperation.session?.sessionId == sessionId &&
        generation == _deploymentStreamGeneration;
  }

  /// Cancel current SSE subscription and invalidate delayed stream events.
  void _cancelSseSubscription() {
    _deploymentReconnectTimer?.cancel();
    _deploymentReconnectTimer = null;
    _sseSubscription?.cancel();
    _sseSubscription = null;
    _sseService?.cancel();
    _sseService = null;
    _deploymentStreamGeneration += 1;
  }

  void _stopPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = null;
  }

  @override
  Future<void> close() {
    _stopPolling();
    _cancelSseSubscription();
    _postOperationRefreshTimer?.cancel();
    _postOperationRefreshTimer = null;
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
    required DeploymentReadinessViewState deploymentReadiness,
    DeploymentOperationViewState deploymentOperation =
        const DeploymentOperationViewState(),
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
      deploymentReadiness: deploymentReadiness,
      deploymentOperation: deploymentOperation,
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

  Future<DeploymentReadinessViewState> _loadCachedReadiness(
    String twinId, {
    DeploymentReadinessViewState? previous,
  }) async {
    try {
      final snapshot = await _api.getDeploymentReadiness(twinId);
      return DeploymentReadinessViewState.fromSnapshot(snapshot);
    } catch (error) {
      return DeploymentReadinessViewState.failed(
        'Readiness unavailable: ${ApiErrorHandler.extractMessage(error)}',
        previous: previous?.snapshot,
      );
    }
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

class _DeploymentStreamData extends TwinOverviewEvent {
  final SseLogEvent event;
  final int generation;
  final String sessionId;

  const _DeploymentStreamData({
    required this.event,
    required this.generation,
    required this.sessionId,
  });

  @override
  List<Object?> get props => [event, generation, sessionId];
}

class _DeploymentStreamDisconnected extends TwinOverviewEvent {
  final Object? error;
  final int generation;
  final String sessionId;

  const _DeploymentStreamDisconnected({
    this.error,
    required this.generation,
    required this.sessionId,
  });

  @override
  List<Object?> get props => [error, generation, sessionId];
}

class _DeploymentReconnectDue extends TwinOverviewEvent {
  final int generation;
  final String sessionId;

  const _DeploymentReconnectDue({
    required this.generation,
    required this.sessionId,
  });

  @override
  List<Object?> get props => [generation, sessionId];
}

class _DeploymentStreamContractException implements Exception {
  final String message;

  const _DeploymentStreamContractException(this.message);

  @override
  String toString() => message;
}
