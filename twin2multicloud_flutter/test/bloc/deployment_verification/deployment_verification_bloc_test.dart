import 'dart:async';
import 'dart:convert';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/deployment_verification/deployment_verification.dart';
import 'package:twin2multicloud_flutter/models/deployment_verification.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/services/sse_service.dart';

class MockApiService extends Mock implements ApiService {}

class MockSseService extends Mock implements SseService {}

void main() {
  late MockApiService api;
  late MockSseService sse;

  setUpAll(() {
    registerFallbackValue(<String, dynamic>{});
  });

  setUp(() {
    api = MockApiService();
    sse = MockSseService();
  });

  DeploymentVerificationBloc buildBloc({bool loadHistory = false}) {
    return DeploymentVerificationBloc(
      twinId: 'twin-1',
      api: api,
      logStreamClientFactory: () => sse,
      loadHistory: loadHistory,
    );
  }

  group('DeploymentVerificationBloc', () {
    blocTest<DeploymentVerificationBloc, DeploymentVerificationState>(
      'loads persisted history on creation',
      setUp: () {
        when(() => api.listDataFlowVerifications('twin-1')).thenAnswer(
          (_) async => TelemetryVerificationHistory.fromJson({
            'schema_version': 'telemetry-verification-history.v1',
            'verifications': [_recordJson()],
          }),
        );
      },
      build: () => buildBloc(loadHistory: true),
      expect: () => [
        isA<DeploymentVerificationState>().having(
          (state) => state.isLoadingHistory,
          'loading history',
          true,
        ),
        isA<DeploymentVerificationState>()
            .having((state) => state.isLoadingHistory, 'loading history', false)
            .having(
              (state) => state.latestDataFlowRecord?.traceId,
              'persisted trace',
              'VERIFY-A1B2C3D4',
            ),
      ],
      verify: (_) {
        verify(() => api.listDataFlowVerifications('twin-1')).called(1);
      },
    );

    blocTest<DeploymentVerificationBloc, DeploymentVerificationState>(
      'loads infrastructure verification result',
      build: () {
        when(() => api.verifyInfrastructure('twin-1')).thenAnswer(
          (_) async => {
            'checks': [
              {
                'layer': 'L1',
                'name': 'IoT endpoint',
                'provider': 'aws',
                'status': 'pass',
                'detail': 'ok',
              },
            ],
            'summary': {
              'pass_count': 1,
              'fail_count': 0,
              'skip_count': 0,
              'total': 1,
              'healthy': true,
            },
          },
        );
        return buildBloc();
      },
      act: (bloc) =>
          bloc.add(const DeploymentVerificationInfrastructureRequested()),
      expect: () => [
        isA<DeploymentVerificationState>().having(
          (state) => state.isCheckingInfrastructure,
          'checking',
          true,
        ),
        isA<DeploymentVerificationState>()
            .having(
              (state) => state.isCheckingInfrastructure,
              'checking',
              false,
            )
            .having(
              (state) => state.infrastructureResult?.summary.healthy,
              'healthy',
              true,
            ),
      ],
    );

    blocTest<DeploymentVerificationBloc, DeploymentVerificationState>(
      'rejects invalid JSON payload before API call',
      build: buildBloc,
      act: (bloc) =>
          bloc.add(const DeploymentVerificationDataFlowRequested('not-json')),
      expect: () => [
        isA<DeploymentVerificationState>().having(
          (state) => state.dataFlowError,
          'error',
          'Invalid JSON payload',
        ),
      ],
      verify: (_) {
        verifyNever(() => api.verifyDataFlow(any(), any()));
      },
    );

    blocTest<DeploymentVerificationBloc, DeploymentVerificationState>(
      'streams logs, validates terminal evidence, and reloads its record',
      build: () {
        when(
          () => api.verifyDataFlow('twin-1', any()),
        ).thenAnswer((_) async => _start());
        when(
          () => api.getDataFlowVerification('twin-1', 'verification-1'),
        ).thenAnswer(
          (_) async => TelemetryVerificationRecord.fromJson(_recordJson()),
        );
        when(() => sse.streamDeploymentLogs('/stream/session-1')).thenAnswer(
          (_) => Stream.fromIterable([
            SseLogEvent(
              message: jsonEncode({
                'timestamp': '10:00:00',
                'message': 'Processor received payload',
                'status': 'pass',
              }),
              type: 'log',
            ),
            SseLogEvent(message: jsonEncode(_evidenceJson()), type: 'done'),
          ]),
        );
        when(() => sse.cancel()).thenReturn(null);
        return buildBloc();
      },
      act: (bloc) => bloc.add(
        const DeploymentVerificationDataFlowRequested(
          '{"iotDeviceId":"device-1"}',
        ),
      ),
      wait: const Duration(milliseconds: 20),
      expect: () => [
        isA<DeploymentVerificationState>().having(
          (state) => state.isRunningDataFlow,
          'running',
          true,
        ),
        isA<DeploymentVerificationState>().having(
          (state) => state.activeVerificationId,
          'active ID',
          'verification-1',
        ),
        isA<DeploymentVerificationState>().having(
          (state) => state.dataFlowLogs.length,
          'log count',
          1,
        ),
        isA<DeploymentVerificationState>()
            .having(
              (state) => state.terminalEvidence?.traceId,
              'terminal trace',
              'VERIFY-A1B2C3D4',
            )
            .having((state) => state.isRunningDataFlow, 'running', false),
        isA<DeploymentVerificationState>()
            .having(
              (state) => state.latestDataFlowRecord?.id,
              'record ID',
              'verification-1',
            )
            .having(
              (state) => state.dataFlowSummary?.passCount,
              'pass count',
              3,
            ),
      ],
      verify: (_) {
        verify(() => api.verifyDataFlow('twin-1', any())).called(1);
        verify(
          () => api.getDataFlowVerification('twin-1', 'verification-1'),
        ).called(1);
      },
    );

    blocTest<DeploymentVerificationBloc, DeploymentVerificationState>(
      'recovers a dropped stream by GET without sending a second message',
      build: () {
        when(
          () => api.verifyDataFlow('twin-1', any()),
        ).thenAnswer((_) async => _start());
        when(() => sse.streamDeploymentLogs('/stream/session-1')).thenAnswer(
          (_) => Stream.error(StateError('transport secret must not surface')),
        );
        when(() => sse.cancel()).thenReturn(null);
        when(
          () => api.getDataFlowVerification('twin-1', 'verification-1'),
        ).thenAnswer(
          (_) async => TelemetryVerificationRecord.fromJson(_recordJson()),
        );
        return buildBloc();
      },
      act: (bloc) => bloc.add(
        const DeploymentVerificationDataFlowRequested(
          '{"iotDeviceId":"device-1"}',
        ),
      ),
      wait: const Duration(milliseconds: 20),
      verify: (_) {
        verify(() => api.verifyDataFlow('twin-1', any())).called(1);
        verify(
          () => api.getDataFlowVerification('twin-1', 'verification-1'),
        ).called(1);
      },
    );
  });
}

TelemetryVerificationStart _start() => TelemetryVerificationStart.fromJson({
  'schema_version': 'telemetry-verification-session.v1',
  'verification_id': 'verification-1',
  'session_id': 'session-1',
  'sse_url': '/stream/session-1',
  'status_url': '/twins/twin-1/verify/dataflow/verification-1',
  'status': 'running',
});

Map<String, dynamic> _evidenceJson() => {
  'schema_version': 'telemetry-verification.v1',
  'trace_id': 'VERIFY-A1B2C3D4',
  'status': 'pass',
  'pass_count': 3,
  'fail_count': 0,
  'skip_count': 0,
  'total_time': 4.2,
  'evidence': [
    {'phase': 1, 'kind': 'message_accepted', 'provider': 'aws'},
    {
      'phase': 2,
      'kind': 'trace_correlated_hot_record',
      'provider': 'gcp',
      'record_count': 1,
    },
    {
      'phase': 3,
      'kind': 'azure_twin_projection',
      'provider': 'azure',
      'correlation': 'source_sequence',
    },
  ],
};

Map<String, dynamic> _recordJson() => {
  'id': 'verification-1',
  'twin_id': 'twin-1',
  'deployment_id': 'deployment-1',
  'session_id': 'session-1',
  'device_id': 'device-1',
  'status': 'pass',
  'trace_id': 'VERIFY-A1B2C3D4',
  'result': {..._evidenceJson(), 'failed_phase': null},
  'error_code': null,
  'error_message': null,
  'requested_at': '2026-08-27T10:00:00Z',
  'completed_at': '2026-08-27T10:00:05Z',
};
