// lib/bloc/twin_overview/twin_overview_bloc.dart
// BLoC for the twin overview screen

import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../config/api_config.dart';
import '../../services/api_service.dart';
import '../../services/sse_service.dart';
import '../../utils/api_error_handler.dart';
import 'twin_overview_event.dart';
import 'twin_overview_state.dart';

class TwinOverviewBloc extends Bloc<TwinOverviewEvent, TwinOverviewState> {
  final ApiService _api;
  String? _currentTwinId;
  Timer? _pollingTimer;
  StreamSubscription? _sseSubscription;
  SseService? _sseService;
  StreamSubscription? _logTraceSseSubscription;
  SseService? _logTraceSseService;

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

      // Fetch outputs for deployed twins (page refresh persistence)
      Map<String, dynamic>? deploymentOutputs;
      DateTime? outputsTimestamp;
      String? outputsError;
      if (twinState == 'deployed') {
        try {
          final outputsResponse = await _api.getDeploymentOutputs(event.twinId);
          deploymentOutputs =
              outputsResponse['outputs'] as Map<String, dynamic>?;
          final deployedAtStr = outputsResponse['deployed_at'] as String?;
          if (deployedAtStr != null) {
            outputsTimestamp = DateTime.tryParse(deployedAtStr);
          }
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
        try {
          final status = await _api.getDeploymentStatus(event.twinId);
          final activeSession =
              status['active_session'] as Map<String, dynamic>?;
          if (activeSession != null) {
            final sseUrl = activeSession['sse_url'] as String;

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
              sessionId: activeSession['session_id'] as String?,
              twinId: event.twinId,
              isDestroy: isDestroy,
            );
          }
        } catch (e) {
          debugPrint('[TwinOverviewBloc] SSE reconnect failed: $e');
          // Non-fatal — user sees the deploying/destroying state, just without live logs
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
    // Preserve outputs during refresh (they may be from SSE, not yet in DB)
    final preservedOutputs = currentState is TwinOverviewLoaded
        ? currentState.deploymentOutputs
        : null;
    final preservedOutputsTimestamp = currentState is TwinOverviewLoaded
        ? currentState.outputsTimestamp
        : null;

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
          // Preserve outputs - they'll be refreshed if needed on full load
          deploymentOutputs: preservedOutputs,
          outputsTimestamp: preservedOutputsTimestamp,
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
      ),
    );

    try {
      // Call backend to start deployment - now returns session_id and sse_url
      final result = await _api.deployTwin(currentState.twinId);

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
      debugPrint(
        '[TwinOverviewBloc] Deployment failed: ${ApiErrorHandler.extractMessage(e)}',
      );
      final errPerms = _permissionsForState('error');
      emit(
        currentState.copyWith(
          isDeploying: false,
          twinState: 'error',
          canDeploy: errPerms['canDeploy'],
          canDestroy: errPerms['canDestroy'],
          canEdit: errPerms['canEdit'],
          canDelete: errPerms['canDelete'],
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
      ),
    );

    try {
      // Call backend to start destruction - now returns session_id and sse_url
      final result = await _api.destroyTwin(currentState.twinId);

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
      debugPrint(
        '[TwinOverviewBloc] Destroy failed: ${ApiErrorHandler.extractMessage(e)}',
      );
      final errPerms = _permissionsForState('error');
      emit(
        currentState.copyWith(
          isDestroying: false,
          twinState: 'error',
          canDeploy: errPerms['canDeploy'],
          canDestroy: errPerms['canDestroy'],
          canEdit: errPerms['canEdit'],
          canDelete: errPerms['canDelete'],
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
    emit(
      currentState.copyWith(
        isDeploying: false,
        isDestroying: false,
        twinState: newState,
        canDeploy: perms['canDeploy'],
        canDestroy: perms['canDestroy'],
        canEdit: perms['canEdit'],
        canDelete: perms['canDelete'],
        lastError: event.success ? null : event.message,
        successMessage: event.success ? event.message : null,
        // Store outputs from SSE on successful deploy, clear on destroy
        deploymentOutputs: isDestroy ? null : event.outputs,
        outputsTimestamp: (event.outputs != null && !isDestroy)
            ? DateTime.now()
            : null,
        clearOutputsError: true,
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
      ),
    );

    try {
      // Call backend to start log trace
      final result = await _api.startLogTrace(currentState.twinId);

      final traceId = result['trace_id'] as String?;
      final providers = result['providers'] as List<dynamic>?;

      if (traceId == null) {
        throw Exception('Backend did not return trace_id');
      }

      // Add trace info to terminal
      emit(
        (state as TwinOverviewLoaded).copyWith(
          traceId: traceId,
          terminalLogs: [
            ...currentState.terminalLogs,
            '> Trace ID: $traceId',
            '> Providers: ${providers?.join(", ") ?? "unknown"}',
            '> Streaming logs for 90 seconds...',
            '',
          ],
        ),
      );

      // Subscribe to log trace SSE stream
      // For test mode, use the sse_url returned by backend; otherwise construct URL
      final sseUrl = result['sse_url'] as String?;
      _subscribeToLogTraceSseStream(
        twinId: currentState.twinId,
        traceId: traceId,
        sseUrl: sseUrl,
      );
    } catch (e) {
      debugPrint(
        '[TwinOverviewBloc] Log trace failed: ${ApiErrorHandler.extractMessage(e)}',
      );
      emit(
        currentState.copyWith(
          isTracing: false,
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

    _logTraceSseService = SseService(
      baseUrl: ApiConfig.baseUrl,
      authToken: 'dev-token', // TODO: Get from ApiService
    );

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
            // SSE connection error - update state
            debugPrint(
              '[TwinOverviewBloc] SSE connection lost: ${ApiErrorHandler.extractMessage(e)}',
            );
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
      ),
    );

    try {
      final bytes = await _api.downloadSimulator(currentState.twinId);
      emit(
        currentState.copyWith(
          isDownloadingSimulator: false,
          simulatorBytes: bytes,
          clearInfo: true,
        ),
      );
    } catch (e) {
      debugPrint(
        '[TwinOverviewBloc] Download failed: ${ApiErrorHandler.extractMessage(e)}',
      );
      emit(
        currentState.copyWith(
          isDownloadingSimulator: false,
          errorMessage: 'Download failed: ${ApiErrorHandler.extractMessage(e)}',
          clearInfo: true,
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
    emit(currentState.copyWith(clearSimulatorBytes: true));
  }
}
