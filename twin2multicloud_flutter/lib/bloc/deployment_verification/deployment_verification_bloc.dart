import 'dart:async';
import 'dart:convert';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../models/deployment_verification.dart';
import '../../services/log_stream_client.dart';
import '../../services/management_api.dart';
import '../../utils/api_error_handler.dart';
import 'deployment_verification_event.dart';
import 'deployment_verification_state.dart';

class DeploymentVerificationBloc
    extends Bloc<DeploymentVerificationEvent, DeploymentVerificationState> {
  final String twinId;
  final VerificationApi _api;
  final LogStreamClientFactory _logStreamClientFactory;
  LogStreamClient? _logStreamClient;
  StreamSubscription<SseLogEvent>? _sseSubscription;
  int _historyGeneration = 0;

  DeploymentVerificationBloc({
    required this.twinId,
    required VerificationApi api,
    required LogStreamClientFactory logStreamClientFactory,
    bool loadHistory = true,
  }) : _api = api,
       _logStreamClientFactory = logStreamClientFactory,
       super(const DeploymentVerificationState()) {
    on<DeploymentVerificationHistoryRequested>(_onHistory);
    on<DeploymentVerificationInfrastructureRequested>(_onInfrastructure);
    on<DeploymentVerificationDataFlowRequested>(_onDataFlow);
    on<DeploymentVerificationSseReceived>(_onSseReceived);
    on<DeploymentVerificationSseFailed>(_onSseFailed);
    if (loadHistory) add(const DeploymentVerificationHistoryRequested());
  }

  Future<void> _onHistory(
    DeploymentVerificationHistoryRequested event,
    Emitter<DeploymentVerificationState> emit,
  ) async {
    final generation = ++_historyGeneration;
    emit(state.copyWith(isLoadingHistory: true, clearHistoryError: true));
    try {
      final history = await _api.listDataFlowVerifications(twinId);
      if (generation != _historyGeneration) return;
      emit(
        state.copyWith(
          isLoadingHistory: false,
          verificationHistory: history.verifications,
          latestDataFlowRecord: history.verifications.firstOrNull,
          clearLatestDataFlowRecord: history.verifications.isEmpty,
        ),
      );
    } catch (error) {
      if (generation != _historyGeneration) return;
      emit(
        state.copyWith(
          isLoadingHistory: false,
          historyError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onInfrastructure(
    DeploymentVerificationInfrastructureRequested event,
    Emitter<DeploymentVerificationState> emit,
  ) async {
    emit(
      state.copyWith(
        isCheckingInfrastructure: true,
        clearInfrastructureError: true,
        clearInfrastructureResult: true,
      ),
    );

    try {
      final result = await _api.verifyInfrastructure(twinId);
      emit(
        state.copyWith(
          isCheckingInfrastructure: false,
          infrastructureResult: InfrastructureVerificationResult.fromJson(
            result,
          ),
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          isCheckingInfrastructure: false,
          infrastructureError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onDataFlow(
    DeploymentVerificationDataFlowRequested event,
    Emitter<DeploymentVerificationState> emit,
  ) async {
    if (state.isRunningDataFlow) return;
    final payload = _parsePayload(event.payloadText);
    if (payload == null) {
      emit(
        state.copyWith(
          dataFlowError: 'Invalid JSON payload',
          isRunningDataFlow: false,
        ),
      );
      return;
    }

    if (!payload.containsKey('iotDeviceId')) {
      emit(
        state.copyWith(
          dataFlowError: 'Payload must contain "iotDeviceId" field',
          isRunningDataFlow: false,
        ),
      );
      return;
    }

    await _cancelSse();
    _historyGeneration += 1;
    emit(
      state.copyWith(
        isRunningDataFlow: true,
        isLoadingHistory: false,
        clearDataFlowError: true,
        dataFlowLogs: const [],
        clearTerminalEvidence: true,
        clearActiveVerificationId: true,
      ),
    );

    try {
      final session = await _api.verifyDataFlow(twinId, payload);
      emit(state.copyWith(activeVerificationId: session.verificationId));
      if (session.status != TelemetryVerificationStatus.running) {
        await _refreshRecord(
          session.verificationId,
          emit,
          streamError: session.status == TelemetryVerificationStatus.notRun
              ? 'Live telemetry verification was not run.'
              : null,
        );
        return;
      }

      _logStreamClient = _logStreamClientFactory();
      _sseSubscription = _logStreamClient!
          .streamDeploymentLogs(session.sseUrl)
          .listen(
            (event) => add(DeploymentVerificationSseReceived(event)),
            onError: (error) => add(DeploymentVerificationSseFailed(error)),
          );
    } catch (error) {
      await _cancelSse();
      emit(
        state.copyWith(
          isRunningDataFlow: false,
          dataFlowError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onSseReceived(
    DeploymentVerificationSseReceived event,
    Emitter<DeploymentVerificationState> emit,
  ) async {
    final sse = event.event;
    if (sse.isHeartbeat) return;

    final parsed = _parseSsePayload(sse.message);
    if (parsed == null) {
      final logs = [
        ...state.dataFlowLogs,
        DataFlowLogEntry(timestamp: '', message: sse.message),
      ];
      emit(
        state.copyWith(
          dataFlowLogs: logs,
          isRunningDataFlow: !(sse.isComplete || sse.isError),
        ),
      );
      if (sse.isComplete || sse.isError) {
        await _cancelSse();
        await _refreshActiveRecord(
          emit,
          streamError: sse.isError ? 'Telemetry verification failed.' : null,
        );
      }
      return;
    }

    if (sse.isComplete) {
      TelemetryVerificationEvidence? terminalEvidence;
      String? contractError;
      try {
        terminalEvidence = TelemetryVerificationEvidence.fromJson(parsed);
      } catch (error) {
        contractError = ApiErrorHandler.extractMessage(error);
      }
      await _cancelSse();
      emit(
        state.copyWith(
          isRunningDataFlow: false,
          terminalEvidence: terminalEvidence,
          dataFlowError: contractError,
          clearDataFlowError: contractError == null,
        ),
      );
      await _refreshActiveRecord(emit, streamError: contractError);
      return;
    }

    final log = _logFromPayload(parsed);
    if (log != null) {
      emit(state.copyWith(dataFlowLogs: [...state.dataFlowLogs, log]));
    }

    if (sse.isComplete || sse.isError) {
      await _cancelSse();
      await _refreshActiveRecord(
        emit,
        streamError: sse.isError ? 'Telemetry verification failed.' : null,
      );
    }
  }

  Future<void> _onSseFailed(
    DeploymentVerificationSseFailed event,
    Emitter<DeploymentVerificationState> emit,
  ) async {
    await _cancelSse();
    await _refreshActiveRecord(
      emit,
      streamError:
          'Telemetry verification stream was interrupted. Persisted evidence was reloaded.',
    );
  }

  Future<void> _refreshActiveRecord(
    Emitter<DeploymentVerificationState> emit, {
    String? streamError,
  }) async {
    final verificationId = state.activeVerificationId;
    if (verificationId == null) {
      emit(
        state.copyWith(
          isRunningDataFlow: false,
          dataFlowError: streamError ?? 'Telemetry verification ID is missing.',
        ),
      );
      return;
    }
    await _refreshRecord(verificationId, emit, streamError: streamError);
  }

  Future<void> _refreshRecord(
    String verificationId,
    Emitter<DeploymentVerificationState> emit, {
    String? streamError,
  }) async {
    try {
      final record = await _api.getDataFlowVerification(twinId, verificationId);
      final history = [
        record,
        ...state.verificationHistory.where((item) => item.id != record.id),
      ];
      emit(
        state.copyWith(
          isRunningDataFlow: false,
          latestDataFlowRecord: record,
          verificationHistory: List.unmodifiable(history.take(25)),
          clearActiveVerificationId: true,
          dataFlowError: _recordError(record) ?? streamError,
          clearDataFlowError:
              _recordError(record) == null && streamError == null,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          isRunningDataFlow: false,
          clearActiveVerificationId: true,
          dataFlowError: streamError ?? ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  String? _recordError(TelemetryVerificationRecord record) {
    return switch (record.status) {
      TelemetryVerificationStatus.pass => null,
      TelemetryVerificationStatus.running =>
        'Telemetry verification is still running; reload persisted evidence later.',
      TelemetryVerificationStatus.fail || TelemetryVerificationStatus.notRun =>
        record.errorMessage ?? 'Telemetry verification did not pass.',
    };
  }

  Map<String, dynamic>? _parsePayload(String payloadText) {
    try {
      final decoded = json.decode(payloadText);
      if (decoded is Map<String, dynamic>) return decoded;
      if (decoded is Map) return Map<String, dynamic>.from(decoded);
    } catch (_) {
      return null;
    }
    return null;
  }

  Map<String, dynamic>? _parseSsePayload(String message) {
    try {
      final decoded = json.decode(message);
      if (decoded is Map<String, dynamic>) return decoded;
      if (decoded is Map) return Map<String, dynamic>.from(decoded);
    } catch (_) {
      return null;
    }
    return null;
  }

  DataFlowLogEntry? _logFromPayload(Map<String, dynamic> data) {
    final timestamp = data['timestamp']?.toString() ?? '';
    final message = data['message']?.toString() ?? '';
    final status = data['status']?.toString();
    final detail = data['detail']?.toString();
    final phase = data['phase'];
    final name = data['name']?.toString();

    if (phase != null && name != null && status != null) {
      return DataFlowLogEntry(
        timestamp: timestamp,
        message: _phaseMessage(data, phase, name, status),
        status: status == 'running' ? null : status,
      );
    }

    if (message.isEmpty) return null;
    return DataFlowLogEntry(
      timestamp: timestamp,
      message: message,
      status: status,
      detail: detail,
    );
  }

  String _phaseMessage(
    Map<String, dynamic> data,
    Object phase,
    String name,
    String status,
  ) {
    return switch (status) {
      'running' =>
        'Phase $phase: $name'
            '${data['timeout'] != null ? ' (timeout: ${data['timeout']}s)' : ''}',
      'pass' =>
        'Phase $phase passed'
            '${data['elapsed'] != null ? ' (${data['elapsed']}s)' : ''}',
      'fail' =>
        'Phase $phase failed'
            '${data['reason'] != null ? ': ${data['reason']}' : ''}',
      'skip' => 'Phase $phase skipped',
      _ => 'Phase $phase: $name ($status)',
    };
  }

  Future<void> _cancelSse() async {
    await _sseSubscription?.cancel();
    _sseSubscription = null;
    _logStreamClient?.cancel();
    _logStreamClient = null;
  }

  @override
  Future<void> close() async {
    await _cancelSse();
    return super.close();
  }
}
