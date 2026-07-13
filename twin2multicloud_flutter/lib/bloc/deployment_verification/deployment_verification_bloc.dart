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

  DeploymentVerificationBloc({
    required this.twinId,
    required VerificationApi api,
    required LogStreamClientFactory logStreamClientFactory,
  }) : _api = api,
       _logStreamClientFactory = logStreamClientFactory,
       super(const DeploymentVerificationState()) {
    on<DeploymentVerificationInfrastructureRequested>(_onInfrastructure);
    on<DeploymentVerificationDataFlowRequested>(_onDataFlow);
    on<DeploymentVerificationSseReceived>(_onSseReceived);
    on<DeploymentVerificationSseFailed>(_onSseFailed);
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
    emit(
      state.copyWith(
        isRunningDataFlow: true,
        clearDataFlowError: true,
        dataFlowLogs: const [],
        clearDataFlowSummary: true,
      ),
    );

    try {
      final result = await _api.verifyDataFlow(twinId, payload);
      final sseUrl = result['sse_url']?.toString();
      if (sseUrl == null || sseUrl.isEmpty) {
        throw StateError('Backend did not return SSE URL');
      }

      _logStreamClient = _logStreamClientFactory();
      _sseSubscription = _logStreamClient!
          .streamDeploymentLogs(sseUrl)
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
      if (sse.isComplete || sse.isError) await _cancelSse();
      return;
    }

    final summary = _summaryFromPayload(parsed);
    if (summary != null) {
      await _cancelSse();
      emit(state.copyWith(isRunningDataFlow: false, dataFlowSummary: summary));
      return;
    }

    final log = _logFromPayload(parsed);
    if (log != null) {
      emit(state.copyWith(dataFlowLogs: [...state.dataFlowLogs, log]));
    }

    if (sse.isComplete || sse.isError) {
      await _cancelSse();
      emit(state.copyWith(isRunningDataFlow: false));
    }
  }

  Future<void> _onSseFailed(
    DeploymentVerificationSseFailed event,
    Emitter<DeploymentVerificationState> emit,
  ) async {
    await _cancelSse();
    emit(
      state.copyWith(
        isRunningDataFlow: false,
        dataFlowError: 'SSE connection lost: ${event.error}',
      ),
    );
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

  DataFlowVerificationSummary? _summaryFromPayload(Map<String, dynamic> data) {
    if (!data.containsKey('pass_count')) return null;
    return DataFlowVerificationSummary.fromJson(data);
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
