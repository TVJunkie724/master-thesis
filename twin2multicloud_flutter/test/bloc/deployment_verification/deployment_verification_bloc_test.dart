import 'dart:async';
import 'dart:convert';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/deployment_verification/deployment_verification.dart';
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

  DeploymentVerificationBloc buildBloc() {
    return DeploymentVerificationBloc(
      twinId: 'twin-1',
      api: api,
      logStreamClientFactory: () => sse,
    );
  }

  group('DeploymentVerificationBloc', () {
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
      'streams data flow logs and summary',
      build: () {
        when(
          () => api.verifyDataFlow('twin-1', any()),
        ).thenAnswer((_) async => {'sse_url': '/stream/session-1'});
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
            SseLogEvent(
              message: jsonEncode({
                'pass_count': 3,
                'fail_count': 0,
                'skip_count': 0,
                'total_time': 4.2,
              }),
              type: 'done',
            ),
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
          (state) => state.dataFlowLogs.length,
          'log count',
          1,
        ),
        isA<DeploymentVerificationState>()
            .having((state) => state.isRunningDataFlow, 'running', false)
            .having(
              (state) => state.dataFlowSummary?.passCount,
              'pass count',
              3,
            ),
      ],
    );
  });
}
