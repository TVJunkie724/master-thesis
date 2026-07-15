import 'dart:async';
import 'dart:typed_data';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_bloc.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_event.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_operations.dart';
import 'package:twin2multicloud_flutter/models/deployment_readiness.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/services/log_stream_client.dart';

import '../../fixtures/typed_api_fixtures.dart';

class MockApiService extends Mock implements ApiService {}

class ControlledLogStreamClient implements LogStreamClient {
  final StreamController<SseLogEvent> controller =
      StreamController<SseLogEvent>();
  String? requestedUrl;
  int? requestedLastEventId;
  bool cancelled = false;

  @override
  Stream<SseLogEvent> streamDeploymentLogs(String sseUrl, {int? lastEventId}) {
    requestedUrl = sseUrl;
    requestedLastEventId = lastEventId;
    return controller.stream;
  }

  @override
  void cancel() => cancelled = true;

  Future<void> dispose() async {
    if (!controller.isClosed) await controller.close();
  }
}

class ControlledLogStreamFactory {
  final List<ControlledLogStreamClient> clients = [];

  LogStreamClient create() {
    final client = ControlledLogStreamClient();
    clients.add(client);
    return client;
  }

  Future<void> dispose() async {
    for (final client in clients) {
      await client.dispose();
    }
  }
}

void main() {
  group('DeploymentOperationViewState', () {
    test('derives terminal visibility and formatted typed logs', () {
      final state = _loaded(
        operation: _operation(
          logs: [_log(1, message: 'Validated manifest.')],
          lastEventId: 1,
        ),
      );

      expect(state.showTerminal, isTrue);
      expect(state.isDeploying, isTrue);
      expect(state.terminalLogs.single, contains('Validated manifest.'));
      expect(state.terminalLogs.single, contains('[INFO]'));
    });

    test(
      'copyWith preserves operation state and clears nullable artifacts',
      () {
        final state = _loaded(
          twinState: 'error',
          operation: _operation(logs: [_log(1)], lastEventId: 1),
          trace: const TraceViewState(traceId: 'TRACE-1'),
          lastError: 'Old deployment error',
          deploymentOutputs: _outputs(const {
            'endpoint': 'old',
          }, deployedAt: DateTime.utc(2026, 7, 14)),
          simulator: SimulatorDownloadViewState(
            phase: SimulatorDownloadViewPhase.readyToSave,
            filename: 'simulator_test.zip',
            requestToken: 1,
            pendingDownload: BinaryDownload(
              bytes: Uint8List.fromList([1, 2, 3]),
              filename: 'simulator_test.zip',
              mediaType: 'application/zip',
            ),
          ),
        );

        final cleared = state.copyWith(
          trace: state.trace.copyWith(clearTraceId: true),
          clearLastError: true,
          clearDeploymentOutputs: true,
          simulatorDownload: state.simulatorDownload.copyWith(
            clearPendingDownload: true,
            clearFilename: true,
          ),
        );

        expect(cleared.deploymentOperation, state.deploymentOperation);
        expect(cleared.trace.traceId, isNull);
        expect(cleared.lastError, isNull);
        expect(cleared.deploymentOutputs, isNull);
        expect(cleared.simulatorDownload.pendingDownload, isNull);
        expect(cleared.simulatorDownload.filename, isNull);
      },
    );

    test(
      'ignores duplicates, rejects gaps, and retains the newest 500 logs',
      () {
        var operation = _operation();
        for (var eventId = 1; eventId <= 501; eventId += 1) {
          operation = operation.append(_log(eventId));
        }

        expect(operation.logs, hasLength(500));
        expect(operation.logs.first.eventId, 2);
        expect(operation.logs.last.eventId, 501);
        expect(operation.append(_log(501)), same(operation));
        expect(() => operation.append(_log(503)), throwsStateError);
        expect(
          () => operation.append(_log(502, sessionId: 'another-session')),
          throwsStateError,
        );
      },
    );
  });

  group('Testing utility view states', () {
    test('trace diagnostics retain only the newest bounded entries', () {
      var trace = const TraceViewState(phase: TraceViewPhase.streaming);
      for (
        var index = 0;
        index <= TraceViewState.maxDiagnosticEntries;
        index++
      ) {
        trace = trace.appendDiagnostic('entry-$index');
      }

      expect(trace.diagnostics, hasLength(TraceViewState.maxDiagnosticEntries));
      expect(trace.diagnostics.first, 'entry-1');
      expect(trace.diagnostics.last, 'entry-500');
    });

    test('simulator binary bytes never participate in Equatable equality', () {
      SimulatorDownloadViewState stateWith(List<int> bytes) =>
          SimulatorDownloadViewState(
            phase: SimulatorDownloadViewPhase.readyToSave,
            filename: 'simulator.zip',
            requestToken: 2,
            pendingDownload: BinaryDownload(
              bytes: Uint8List.fromList(bytes),
              filename: 'simulator.zip',
              mediaType: 'application/zip',
            ),
          );

      expect(stateWith([1]), stateWith([9, 8, 7]));
      expect(stateWith([1]).props, isNot(contains(isA<BinaryDownload>())));
    });
  });

  group('TwinOverviewBloc messages and permissions', () {
    late MockApiService api;

    setUp(() => api = MockApiService());

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'closes deployment logs without discarding typed history',
      seed: () =>
          _loaded(operation: _operation(logs: [_log(1)], lastEventId: 1)),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewCloseTerminal()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((state) => state.showTerminal, 'showTerminal', isFalse)
            .having(
              (state) => state.deploymentOperation.logs,
              'typed history',
              hasLength(1),
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'closes deployment logs without mutating independent trace diagnostics',
      seed: () => _loaded(
        operation: _operation(logs: [_log(1)], lastEventId: 1),
        trace: const TraceViewState(
          phase: TraceViewPhase.completed,
          diagnostics: ['Trace event'],
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewCloseTerminal()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((state) => state.trace.diagnostics, 'trace retained', [
              'Trace event',
            ])
            .having((state) => state.showTerminal, 'terminal hidden', isFalse)
            .having(
              (state) => state.deploymentOperation.logs,
              'deployment history',
              hasLength(1),
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'successful destroy clears outputs and recalculates permissions',
      seed: () => _loaded(
        twinState: 'destroying',
        operation: _operation(operationType: DeploymentOperationType.destroy),
        lastError: 'Previous failure',
        deploymentOutputs: _outputs(const {
          'endpoint': 'old',
        }, deployedAt: DateTime.utc(2026, 7, 14)),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(
        const TwinOverviewDeploymentComplete(
          success: true,
          newState: 'destroyed',
          message: 'Resources destroyed',
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((state) => state.twinState, 'state', 'destroyed')
            .having((state) => state.lastError, 'lastError', isNull)
            .having((state) => state.deploymentOutputs, 'outputs', isNull)
            .having((state) => state.canDeploy, 'canDeploy', isTrue)
            .having((state) => state.canDestroy, 'canDestroy', isFalse),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'failed deployment keeps logs and enables cleanup',
      seed: () => _loaded(
        operation: _operation(
          logs: [_log(1, message: 'Terraform failed')],
          lastEventId: 1,
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(
        const TwinOverviewDeploymentComplete(
          success: false,
          newState: 'error',
          message: 'Deployment failed',
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((state) => state.twinState, 'state', 'error')
            .having((state) => state.canDeploy, 'canDeploy', isTrue)
            .having((state) => state.canDestroy, 'canDestroy', isTrue)
            .having(
              (state) => state.deploymentOperation.logs,
              'logs',
              hasLength(1),
            )
            .having(
              (state) => state.deploymentOperation.phase,
              'phase',
              DeploymentOperationViewPhase.failed,
            ),
      ],
    );
  });

  group('TwinOverviewBloc deployment readiness', () {
    late MockApiService api;

    setUp(() => api = MockApiService());

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'loads cached readiness without contacting preflight',
      setUp: () => _stubLoad(
        api,
        status: const DeploymentStatusSnapshot(
          schemaVersion: DeploymentStatusSnapshot.supportedSchemaVersion,
          state: DeploymentTwinState.configured,
        ),
        readiness: _readiness(ready: false),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewLoad('test-id')),
      expect: () => [
        isA<TwinOverviewLoading>(),
        isA<TwinOverviewLoaded>().having(
          (state) => state.deploymentReadiness.phase,
          'phase',
          DeploymentReadinessViewPhase.reviewRequired,
        ),
      ],
      verify: (_) {
        verify(() => api.getDeploymentReadiness('test-id')).called(1);
        verifyNever(() => api.runDeploymentPreflight(any()));
      },
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'runs explicit preflight and preserves prior evidence on failure',
      seed: () => _loaded(readinessReady: false),
      setUp: () => when(
        () => api.runDeploymentPreflight('test-id'),
      ).thenThrow(Exception('service unavailable')),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewRunDeploymentPreflight()),
      expect: () => [
        isA<TwinOverviewLoaded>().having(
          (state) => state.deploymentReadiness.phase,
          'loading',
          DeploymentReadinessViewPhase.loading,
        ),
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.deploymentReadiness.phase,
              'failed',
              DeploymentReadinessViewPhase.failed,
            )
            .having(
              (state) => state.deploymentReadiness.snapshot,
              'prior snapshot',
              isNotNull,
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'blocks deploy before API I/O when readiness is not ready',
      seed: () => _loaded(readinessReady: false),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewDeploy()),
      expect: () => [
        isA<TwinOverviewLoaded>().having(
          (state) => state.errorMessage,
          'errorMessage',
          contains('blocked'),
        ),
      ],
      verify: (_) => verifyNever(() => api.deployTwin(any())),
    );
  });

  group('TwinOverviewBloc resilient deployment stream', () {
    late MockApiService api;
    late ControlledLogStreamFactory streams;

    setUp(() {
      api = MockApiService();
      streams = ControlledLogStreamFactory();
    });

    tearDown(() async => streams.dispose());

    test(
      'catches up persisted logs before SSE and resumes after cursor',
      () async {
        _stubConfiguredLoad(api);
        _stubOperationStart(api);
        when(
          () => api.getDeploymentLogs(
            'test-id',
            sessionId: 'session-1',
            afterEventId: 0,
            limit: 500,
          ),
        ).thenAnswer(
          (_) async => _page(
            logs: [_log(1), _log(2)],
            nextAfterEventId: 2,
            latestEventId: 2,
          ),
        );
        final bloc = _buildBloc(api, streams: streams);

        await _loadConfigured(bloc);
        bloc.add(const TwinOverviewDeploy());
        await pumpEventQueue(times: 20);

        final loaded = bloc.state as TwinOverviewLoaded;
        expect(
          loaded.deploymentOperation.phase,
          DeploymentOperationViewPhase.streaming,
        );
        expect(loaded.deploymentOperation.lastEventId, 2);
        expect(loaded.deploymentOperation.logs, hasLength(2));
        expect(streams.clients, hasLength(1));
        expect(streams.clients.single.requestedUrl, '/sse/deploy/session-1');
        expect(streams.clients.single.requestedLastEventId, 2);
        verifyInOrder([
          () => api.deployTwin('test-id'),
          () => api.getDeploymentLogs(
            'test-id',
            sessionId: 'session-1',
            afterEventId: 0,
            limit: 500,
          ),
        ]);

        await bloc.close();
        expect(streams.clients.single.cancelled, isTrue);
      },
    );

    test('paginates persisted catch-up until the latest cursor', () async {
      _stubConfiguredLoad(api);
      _stubOperationStart(api);
      when(
        () => api.getDeploymentLogs(
          'test-id',
          sessionId: 'session-1',
          afterEventId: 0,
          limit: 500,
        ),
      ).thenAnswer(
        (_) async => _page(
          logs: [_log(1)],
          hasMore: true,
          nextAfterEventId: 1,
          latestEventId: 2,
        ),
      );
      when(
        () => api.getDeploymentLogs(
          'test-id',
          sessionId: 'session-1',
          afterEventId: 1,
          limit: 500,
        ),
      ).thenAnswer(
        (_) async => _page(
          afterEventId: 1,
          logs: [_log(2)],
          nextAfterEventId: 2,
          latestEventId: 2,
        ),
      );
      final bloc = _buildBloc(api, streams: streams);

      await _loadConfigured(bloc);
      bloc.add(const TwinOverviewDeploy());
      await pumpEventQueue(times: 30);

      final operation = (bloc.state as TwinOverviewLoaded).deploymentOperation;
      expect(operation.logs.map((entry) => entry.eventId), [1, 2]);
      expect(streams.clients.single.requestedLastEventId, 2);
      verify(
        () => api.getDeploymentLogs(
          'test-id',
          sessionId: 'session-1',
          afterEventId: 1,
          limit: 500,
        ),
      ).called(1);
      await bloc.close();
    });

    test(
      'applies a terminal SSE event with outputs and final cursor',
      () async {
        _stubConfiguredLoad(api);
        _stubOperationStart(api);
        _stubEmptyLogPage(api);
        final bloc = _buildBloc(api, streams: streams);

        await _loadConfigured(bloc);
        bloc.add(const TwinOverviewDeploy());
        await pumpEventQueue(times: 20);
        streams.clients.single.controller.add(
          const SseLogEvent(
            id: 1,
            type: 'complete',
            message: 'Deployment completed.',
            outputs: {'endpoint': 'https://example.test'},
          ),
        );
        await pumpEventQueue(times: 20);

        final loaded = bloc.state as TwinOverviewLoaded;
        expect(loaded.twinState, 'deployed');
        expect(
          loaded.deploymentOperation.phase,
          DeploymentOperationViewPhase.completed,
        );
        expect(loaded.deploymentOperation.lastEventId, 1);
        expect(loaded.deploymentOutputs?.outputs, {
          'endpoint': 'https://example.test',
        });
        expect(
          loaded.deploymentOutputs?.deployedAt,
          DateTime.utc(2026, 7, 14, 12),
        );
        expect(loaded.deploymentOutputs?.redacted, isTrue);
        expect(streams.clients.single.cancelled, isTrue);
        await bloc.close();
      },
    );

    test(
      'ignores duplicate SSE events and accepts the next event once',
      () async {
        _stubConfiguredLoad(api);
        _stubOperationStart(api);
        _stubEmptyLogPage(api);
        final bloc = _buildBloc(api, streams: streams);
        await _loadConfigured(bloc);
        bloc.add(const TwinOverviewDeploy());
        await pumpEventQueue(times: 20);

        streams.clients.single.controller.add(
          const SseLogEvent(id: 1, type: 'log', message: 'First'),
        );
        await pumpEventQueue();
        streams.clients.single.controller.add(
          const SseLogEvent(id: 1, type: 'log', message: 'Duplicate'),
        );
        streams.clients.single.controller.add(
          const SseLogEvent(id: 2, type: 'log', message: 'Second'),
        );
        await pumpEventQueue(times: 10);

        final operation =
            (bloc.state as TwinOverviewLoaded).deploymentOperation;
        expect(operation.lastEventId, 2);
        expect(operation.logs.map((entry) => entry.message), [
          'First',
          'Second',
        ]);
        await bloc.close();
      },
    );

    test('detects a live event gap and schedules bounded recovery', () async {
      _stubConfiguredLoad(api);
      _stubOperationStart(api);
      _stubEmptyLogPage(api);
      final bloc = _buildBloc(
        api,
        streams: streams,
        reconnectDelay: const Duration(days: 1),
      );
      await _loadConfigured(bloc);
      bloc.add(const TwinOverviewDeploy());
      await pumpEventQueue(times: 20);

      final firstClient = streams.clients.single;
      firstClient.controller.add(
        const SseLogEvent(id: 2, type: 'log', message: 'Gap'),
      );
      await pumpEventQueue(times: 10);

      final operation = (bloc.state as TwinOverviewLoaded).deploymentOperation;
      expect(operation.phase, DeploymentOperationViewPhase.reconnecting);
      expect(operation.reconnectAttempt, 1);
      expect(operation.lastEventId, 0);
      expect(operation.logs, isEmpty);
      expect(firstClient.cancelled, isTrue);

      await bloc.close();
    });

    test(
      'reconnects after transport loss using persisted catch-up cursor',
      () async {
        _stubConfiguredLoad(api);
        _stubOperationStart(api);
        when(
          () => api.getDeploymentLogs(
            'test-id',
            sessionId: 'session-1',
            afterEventId: any(named: 'afterEventId'),
            limit: 500,
          ),
        ).thenAnswer((invocation) async {
          final cursor = invocation.namedArguments[#afterEventId] as int;
          return _page(afterEventId: cursor, nextAfterEventId: cursor);
        });
        final bloc = _buildBloc(
          api,
          streams: streams,
          reconnectDelay: Duration.zero,
        );
        await _loadConfigured(bloc);
        bloc.add(const TwinOverviewDeploy());
        await pumpEventQueue(times: 20);
        streams.clients.single.controller.add(
          const SseLogEvent(id: 1, type: 'log', message: 'Before loss'),
        );
        await pumpEventQueue();
        streams.clients.single.controller.addError(
          Exception('connection reset'),
        );
        await pumpEventQueue(times: 40);

        expect(streams.clients, hasLength(2));
        expect(streams.clients.last.requestedLastEventId, 1);
        final operation =
            (bloc.state as TwinOverviewLoaded).deploymentOperation;
        expect(operation.phase, DeploymentOperationViewPhase.streaming);
        expect(operation.logs.single.message, 'Before loss');
        await bloc.close();
      },
    );

    test(
      'fails visibly after bounded catch-up retries and status check',
      () async {
        _stubConfiguredLoad(api);
        _stubOperationStart(api);
        when(
          () => api.getDeploymentLogs(
            'test-id',
            sessionId: 'session-1',
            afterEventId: any(named: 'afterEventId'),
            limit: 500,
          ),
        ).thenThrow(Exception('database unavailable'));
        final bloc = _buildBloc(
          api,
          streams: streams,
          reconnectDelay: Duration.zero,
        );

        await _loadConfigured(bloc);
        clearInteractions(api);
        when(() => api.getDeploymentStatus('test-id')).thenAnswer(
          (_) async => const DeploymentStatusSnapshot(
            schemaVersion: DeploymentStatusSnapshot.supportedSchemaVersion,
            state: DeploymentTwinState.deploying,
            activeSession: ActiveDeploymentSession(
              sessionId: 'session-1',
              sseUrl: '/sse/deploy/session-1',
              operationType: DeploymentOperationType.deploy,
            ),
          ),
        );
        bloc.add(const TwinOverviewDeploy());
        await pumpEventQueue(times: 80);

        final loaded = bloc.state as TwinOverviewLoaded;
        expect(
          loaded.deploymentOperation.phase,
          DeploymentOperationViewPhase.failed,
        );
        expect(loaded.deploymentOperation.reconnectAttempt, 3);
        expect(
          loaded.deploymentOperation.message,
          contains('refresh to retry'),
        );
        expect(loaded.errorMessage, contains('status was not changed'));
        verify(() => api.getDeploymentStatus('test-id')).called(1);
        await bloc.close();
      },
    );

    test(
      'bounds repeated live transport failures across successful catch-up',
      () async {
        _stubConfiguredLoad(api);
        _stubOperationStart(api);
        when(
          () => api.getDeploymentLogs(
            'test-id',
            sessionId: 'session-1',
            afterEventId: any(named: 'afterEventId'),
            limit: 500,
          ),
        ).thenAnswer((invocation) async {
          final cursor = invocation.namedArguments[#afterEventId] as int;
          return _page(afterEventId: cursor, nextAfterEventId: cursor);
        });
        final bloc = _buildBloc(
          api,
          streams: streams,
          reconnectDelay: Duration.zero,
        );

        await _loadConfigured(bloc);
        clearInteractions(api);
        when(() => api.getDeploymentStatus('test-id')).thenAnswer(
          (_) async => const DeploymentStatusSnapshot(
            schemaVersion: DeploymentStatusSnapshot.supportedSchemaVersion,
            state: DeploymentTwinState.deploying,
            activeSession: ActiveDeploymentSession(
              sessionId: 'session-1',
              sseUrl: '/sse/deploy/session-1',
              operationType: DeploymentOperationType.deploy,
            ),
          ),
        );
        bloc.add(const TwinOverviewDeploy());
        await pumpEventQueue(times: 20);

        for (var attempt = 0; attempt < 4; attempt += 1) {
          expect(streams.clients, hasLength(attempt + 1));
          streams.clients[attempt].controller.addError(
            Exception('connection reset ${attempt + 1}'),
          );
          await pumpEventQueue(times: 30);
        }

        final loaded = bloc.state as TwinOverviewLoaded;
        expect(streams.clients, hasLength(4));
        expect(
          loaded.deploymentOperation.phase,
          DeploymentOperationViewPhase.failed,
        );
        expect(loaded.deploymentOperation.reconnectAttempt, 3);
        verify(() => api.getDeploymentStatus('test-id')).called(1);
        await bloc.close();
      },
    );

    test('restores an active persisted session during overview load', () async {
      const activeSession = ActiveDeploymentSession(
        sessionId: 'session-1',
        sseUrl: '/sse/deploy/session-1',
        operationType: DeploymentOperationType.deploy,
      );
      _stubLoad(
        api,
        status: const DeploymentStatusSnapshot(
          schemaVersion: DeploymentStatusSnapshot.supportedSchemaVersion,
          state: DeploymentTwinState.deploying,
          activeSession: activeSession,
        ),
        readiness: _readiness(ready: true),
      );
      when(
        () => api.getDeploymentLogs(
          'test-id',
          sessionId: 'session-1',
          afterEventId: 0,
          limit: 500,
        ),
      ).thenAnswer(
        (_) async => _page(
          logs: [_log(1, message: 'Recovered')],
          nextAfterEventId: 1,
          latestEventId: 1,
        ),
      );
      final bloc = _buildBloc(api, streams: streams);

      bloc.add(const TwinOverviewLoad('test-id'));
      await pumpEventQueue(times: 30);

      final operation = (bloc.state as TwinOverviewLoaded).deploymentOperation;
      expect(operation.phase, DeploymentOperationViewPhase.streaming);
      expect(operation.logs.single.message, 'Recovered');
      expect(streams.clients.single.requestedLastEventId, 1);
      await bloc.close();
    });
  });

  group('TwinOverviewBloc log trace', () {
    late MockApiService api;
    late ControlledLogStreamFactory streams;

    setUp(() {
      api = MockApiService();
      streams = ControlledLogStreamFactory();
    });

    tearDown(() => streams.dispose());

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'starts trace with typed metadata and subscribes to returned SSE route',
      seed: () => _loaded(twinState: 'deployed'),
      setUp: () => when(() => api.startLogTrace('test-id')).thenAnswer(
        (_) async => LogTraceStartResult(
          traceId: 'TRACE-1',
          sentAt: DateTime.utc(2026, 7, 14, 12),
          l1Provider: 'aws',
          providers: const ['aws', 'azure'],
          message: 'Trace started.',
          sessionId: 'trace-session',
          sseUrl: '/twins/test-id/log-trace/stream/TRACE-1',
        ),
      ),
      build: () => _buildBloc(api, streams: streams),
      act: (bloc) => bloc.add(const TwinOverviewStartLogTrace()),
      expect: () => [
        isA<TwinOverviewLoaded>().having(
          (state) => state.trace.phase,
          'phase',
          TraceViewPhase.starting,
        ),
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.trace.phase,
              'phase',
              TraceViewPhase.streaming,
            )
            .having((state) => state.trace.traceId, 'trace ID', 'TRACE-1')
            .having((state) => state.trace.providers, 'providers', [
              'aws',
              'azure',
            ]),
      ],
      verify: (_) {
        expect(streams.clients.single.requestedUrl, contains('TRACE-1'));
      },
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'reports a rate-limited trace start without retaining stale metadata',
      seed: () => _loaded(
        twinState: 'deployed',
        trace: const TraceViewState(
          phase: TraceViewPhase.completed,
          traceId: 'TRACE-OLD',
          diagnostics: ['Old diagnostic'],
        ),
      ),
      setUp: () => when(
        () => api.startLogTrace('test-id'),
      ).thenThrow(Exception('Too many requests')),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewStartLogTrace()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.trace.phase,
              'phase',
              TraceViewPhase.starting,
            )
            .having((state) => state.trace.traceId, 'stale trace ID', isNull),
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.trace.phase,
              'phase',
              TraceViewPhase.failed,
            )
            .having((state) => state.trace.traceId, 'trace ID', isNull)
            .having(
              (state) => state.errorMessage,
              'public error',
              contains('Too many requests'),
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'completes trace while retaining diagnostics and total log count',
      seed: () => _loaded(
        twinState: 'deployed',
        trace: const TraceViewState(
          phase: TraceViewPhase.streaming,
          traceId: 'TRACE-1',
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) {
        bloc.add(const TwinOverviewLogTraceUpdate('Telemetry accepted.'));
        bloc.add(const TwinOverviewLogTraceComplete(totalLogs: 1));
      },
      expect: () => [
        isA<TwinOverviewLoaded>().having(
          (state) => state.trace.diagnostics,
          'diagnostics',
          ['Telemetry accepted.'],
        ),
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.trace.phase,
              'phase',
              TraceViewPhase.completed,
            )
            .having((state) => state.trace.totalLogs, 'total logs', 1),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'cancels trace without changing deployment operation state',
      seed: () => _loaded(
        twinState: 'deployed',
        operation: _operation(showLogs: false),
        trace: const TraceViewState(
          phase: TraceViewPhase.streaming,
          traceId: 'TRACE-1',
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewCancelLogTrace()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.trace.phase,
              'phase',
              TraceViewPhase.cancelled,
            )
            .having(
              (state) => state.deploymentOperation.phase,
              'deployment phase',
              DeploymentOperationViewPhase.streaming,
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'ignores diagnostics and terminal events from a stale trace stream',
      seed: () => _loaded(
        twinState: 'deployed',
        trace: const TraceViewState(
          phase: TraceViewPhase.streaming,
          traceId: 'TRACE-CURRENT',
          diagnostics: ['Current trace'],
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) {
        bloc.add(
          const TwinOverviewLogTraceUpdate(
            'Stale diagnostic',
            traceId: 'TRACE-STALE',
          ),
        );
        bloc.add(
          const TwinOverviewLogTraceComplete(
            totalLogs: 99,
            traceId: 'TRACE-STALE',
          ),
        );
        bloc.add(
          const TwinOverviewLogTraceError(
            'Stale failure',
            traceId: 'TRACE-STALE',
          ),
        );
      },
      expect: () => <TwinOverviewState>[],
    );

    final delayedTraceStart = Completer<LogTraceStartResult>();
    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'does not resurrect a trace after cancellation during start',
      seed: () => _loaded(twinState: 'deployed'),
      setUp: () => when(
        () => api.startLogTrace('test-id'),
      ).thenAnswer((_) => delayedTraceStart.future),
      build: () => _buildBloc(api),
      act: (bloc) async {
        bloc.add(const TwinOverviewStartLogTrace());
        await pumpEventQueue();
        bloc.add(const TwinOverviewCancelLogTrace());
        await pumpEventQueue();
        delayedTraceStart.complete(
          LogTraceStartResult(
            traceId: 'TRACE-LATE',
            sentAt: DateTime.utc(2026, 7, 14, 12),
            l1Provider: 'aws',
            providers: const ['aws'],
            message: 'Late trace response.',
            sessionId: 'trace-session',
            sseUrl: '/twins/test-id/log-trace/stream/TRACE-LATE',
          ),
        );
      },
      expect: () => [
        isA<TwinOverviewLoaded>().having(
          (state) => state.trace.phase,
          'phase',
          TraceViewPhase.starting,
        ),
        isA<TwinOverviewLoaded>().having(
          (state) => state.trace.phase,
          'phase',
          TraceViewPhase.cancelled,
        ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'deployment lifecycle cancels trace and clears transient simulator bytes',
      seed: () => _loaded(
        twinState: 'configured',
        trace: const TraceViewState(
          phase: TraceViewPhase.streaming,
          traceId: 'TRACE-1',
        ),
        simulator: SimulatorDownloadViewState(
          phase: SimulatorDownloadViewPhase.readyToSave,
          filename: 'simulator.zip',
          pendingDownload: BinaryDownload(
            bytes: Uint8List.fromList([1, 2, 3]),
            filename: 'simulator.zip',
            mediaType: 'application/zip',
          ),
        ),
      ),
      setUp: () {
        _stubOperationStart(api);
        _stubEmptyLogPage(api);
      },
      build: () => _buildBloc(api, streams: streams),
      act: (bloc) => bloc.add(const TwinOverviewDeploy()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((state) => state.twinState, 'state', 'deploying')
            .having(
              (state) => state.trace.phase,
              'trace phase',
              TraceViewPhase.cancelled,
            )
            .having(
              (state) => state.simulatorDownload.phase,
              'simulator phase',
              SimulatorDownloadViewPhase.idle,
            )
            .having(
              (state) => state.simulatorDownload.pendingDownload,
              'pending bytes',
              isNull,
            ),
        isA<TwinOverviewLoaded>().having(
          (state) => state.deploymentOperation.phase,
          'deployment phase',
          DeploymentOperationViewPhase.connecting,
        ),
        isA<TwinOverviewLoaded>().having(
          (state) => state.deploymentOperation.phase,
          'deployment phase',
          DeploymentOperationViewPhase.connecting,
        ),
        isA<TwinOverviewLoaded>().having(
          (state) => state.deploymentOperation.phase,
          'deployment phase',
          DeploymentOperationViewPhase.streaming,
        ),
      ],
    );
  });

  group('TwinOverviewBloc simulator download', () {
    late MockApiService api;

    setUp(() => api = MockApiService());

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'keeps server filename with transient bytes outside equality props',
      seed: () => _loaded(
        twinState: 'deployed',
        simulator: SimulatorDownloadViewState(
          phase: SimulatorDownloadViewPhase.saved,
          filename: 'simulator_old.zip',
          requestToken: 1,
          pendingDownload: BinaryDownload(
            bytes: Uint8List.fromList([9]),
            filename: 'simulator_old.zip',
            mediaType: 'application/zip',
          ),
        ),
      ).copyWith(errorMessage: 'Previous download failed'),
      setUp: () => when(() => api.downloadSimulator('test-id')).thenAnswer(
        (_) async => BinaryDownload(
          bytes: Uint8List.fromList([1, 2, 3]),
          filename: 'simulator_server_name.zip',
          mediaType: 'application/zip',
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(
        const TwinOverviewDownloadSimulator(
          acknowledgedSensitiveCredentials: true,
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.simulatorDownload.phase,
              'phase',
              SimulatorDownloadViewPhase.requesting,
            )
            .having((state) => state.errorMessage, 'error', isNull)
            .having(
              (state) => state.simulatorDownload.pendingDownload,
              'old bytes',
              isNull,
            ),
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.simulatorDownload.phase,
              'phase',
              SimulatorDownloadViewPhase.readyToSave,
            )
            .having(
              (state) => state.simulatorDownload.filename,
              'filename',
              'simulator_server_name.zip',
            )
            .having(
              (state) => state.simulatorDownload.pendingDownload?.bytes,
              'bytes',
              [1, 2, 3],
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'rejects simulator download without explicit credential acknowledgement',
      seed: () => _loaded(twinState: 'deployed'),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(
        const TwinOverviewDownloadSimulator(
          acknowledgedSensitiveCredentials: false,
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.simulatorDownload.phase,
              'phase',
              SimulatorDownloadViewPhase.failed,
            )
            .having(
              (state) => state.errorMessage,
              'error',
              contains('Confirm'),
            ),
      ],
      verify: (_) => verifyNever(() => api.downloadSimulator(any())),
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'reports simulator transport failure and retains no binary payload',
      seed: () => _loaded(twinState: 'deployed'),
      setUp: () => when(
        () => api.downloadSimulator('test-id'),
      ).thenThrow(Exception('Request timed out')),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(
        const TwinOverviewDownloadSimulator(
          acknowledgedSensitiveCredentials: true,
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>().having(
          (state) => state.simulatorDownload.phase,
          'phase',
          SimulatorDownloadViewPhase.requesting,
        ),
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.simulatorDownload.phase,
              'phase',
              SimulatorDownloadViewPhase.failed,
            )
            .having(
              (state) => state.simulatorDownload.pendingDownload,
              'pending bytes',
              isNull,
            )
            .having(
              (state) => state.errorMessage,
              'public error',
              contains('Request timed out'),
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'clears transient binary immediately after save completes',
      seed: () => _loaded(
        twinState: 'deployed',
        simulator: SimulatorDownloadViewState(
          phase: SimulatorDownloadViewPhase.saving,
          filename: 'simulator.zip',
          requestToken: 3,
          pendingDownload: BinaryDownload(
            bytes: Uint8List.fromList([1, 2, 3]),
            filename: 'simulator.zip',
            mediaType: 'application/zip',
          ),
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(
        const TwinOverviewSimulatorSaveCompleted('Simulator package saved.'),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.simulatorDownload.phase,
              'phase',
              SimulatorDownloadViewPhase.saved,
            )
            .having(
              (state) => state.simulatorDownload.pendingDownload,
              'pending bytes',
              isNull,
            )
            .having(
              (state) => state.successMessage,
              'message',
              'Simulator package saved.',
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'clears transient binary immediately when saving is cancelled',
      seed: () => _loaded(
        twinState: 'deployed',
        simulator: SimulatorDownloadViewState(
          phase: SimulatorDownloadViewPhase.saving,
          filename: 'simulator.zip',
          pendingDownload: BinaryDownload(
            bytes: Uint8List.fromList([1, 2, 3]),
            filename: 'simulator.zip',
            mediaType: 'application/zip',
          ),
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewSimulatorSaveCancelled()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.simulatorDownload.phase,
              'phase',
              SimulatorDownloadViewPhase.idle,
            )
            .having(
              (state) => state.simulatorDownload.pendingDownload,
              'pending bytes',
              isNull,
            )
            .having((state) => state.errorMessage, 'error', isNull),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'clears transient binary immediately when saving fails',
      seed: () => _loaded(
        twinState: 'deployed',
        simulator: SimulatorDownloadViewState(
          phase: SimulatorDownloadViewPhase.saving,
          filename: 'simulator.zip',
          pendingDownload: BinaryDownload(
            bytes: Uint8List.fromList([1, 2, 3]),
            filename: 'simulator.zip',
            mediaType: 'application/zip',
          ),
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(
        const TwinOverviewSimulatorSaveFailed('Could not save package.'),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.simulatorDownload.phase,
              'phase',
              SimulatorDownloadViewPhase.failed,
            )
            .having(
              (state) => state.simulatorDownload.pendingDownload,
              'pending bytes',
              isNull,
            )
            .having(
              (state) => state.errorMessage,
              'error',
              'Could not save package.',
            ),
      ],
    );

    final delayedDownload = Completer<BinaryDownload>();
    final raceStreams = ControlledLogStreamFactory();
    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'drops a simulator response after the destroy lifecycle starts',
      seed: () => _loaded(twinState: 'deployed'),
      setUp: () {
        when(
          () => api.downloadSimulator('test-id'),
        ).thenAnswer((_) => delayedDownload.future);
        when(() => api.destroyTwin('test-id')).thenAnswer(
          (_) async => const OperationSession(
            sessionId: 'session-1',
            sseUrl: '/sse/deploy/session-1',
          ),
        );
        _stubEmptyLogPage(api);
      },
      build: () => _buildBloc(api, streams: raceStreams),
      act: (bloc) async {
        bloc.add(
          const TwinOverviewDownloadSimulator(
            acknowledgedSensitiveCredentials: true,
          ),
        );
        await pumpEventQueue();
        bloc.add(const TwinOverviewDestroy());
        await pumpEventQueue(times: 10);
        delayedDownload.complete(
          BinaryDownload(
            bytes: Uint8List.fromList([1, 2, 3]),
            filename: 'simulator_late.zip',
            mediaType: 'application/zip',
          ),
        );
      },
      expect: () => [
        isA<TwinOverviewLoaded>().having(
          (state) => state.simulatorDownload.phase,
          'simulator phase',
          SimulatorDownloadViewPhase.requesting,
        ),
        isA<TwinOverviewLoaded>()
            .having((state) => state.twinState, 'state', 'destroying')
            .having(
              (state) => state.simulatorDownload.phase,
              'simulator phase',
              SimulatorDownloadViewPhase.idle,
            ),
        isA<TwinOverviewLoaded>().having(
          (state) => state.deploymentOperation.phase,
          'deployment phase',
          DeploymentOperationViewPhase.connecting,
        ),
        isA<TwinOverviewLoaded>().having(
          (state) => state.deploymentOperation.phase,
          'deployment phase',
          DeploymentOperationViewPhase.connecting,
        ),
        isA<TwinOverviewLoaded>().having(
          (state) => state.deploymentOperation.phase,
          'deployment phase',
          DeploymentOperationViewPhase.streaming,
        ),
      ],
      tearDown: raceStreams.dispose,
    );
  });
}

TwinOverviewBloc _buildBloc(
  MockApiService api, {
  ControlledLogStreamFactory? streams,
  Duration reconnectDelay = const Duration(seconds: 2),
}) {
  return TwinOverviewBloc(
    api: api,
    logStreamClientFactory: streams?.create ?? ControlledLogStreamClient.new,
    reconnectDelay: reconnectDelay,
    clock: () => DateTime.utc(2026, 7, 14, 12),
  );
}

TwinOverviewLoaded _loaded({
  String twinState = 'deploying',
  bool readinessReady = true,
  DeploymentOperationViewState operation = const DeploymentOperationViewState(),
  TraceViewState trace = const TraceViewState(),
  String? lastError,
  DeploymentOutputsSnapshot? deploymentOutputs,
  SimulatorDownloadViewState simulator = const SimulatorDownloadViewState(),
}) {
  final canDeploy = {'configured', 'destroyed', 'error'}.contains(twinState);
  final canDestroy = {'deployed', 'error'}.contains(twinState);
  final canEdit = !{'deploying', 'destroying', 'deployed'}.contains(twinState);
  return TwinOverviewLoaded(
    twinId: 'test-id',
    projectName: 'Test Project',
    twinState: twinState,
    canDeploy: canDeploy,
    canDestroy: canDestroy,
    canEdit: canEdit,
    canDelete: canEdit,
    deploymentReadiness: DeploymentReadinessViewState.fromSnapshot(
      _readiness(ready: readinessReady),
    ),
    deploymentOperation: operation,
    trace: trace,
    lastError: lastError,
    deploymentOutputs: deploymentOutputs,
    simulatorDownload: simulator,
  );
}

DeploymentOutputsSnapshot _outputs(
  Map<String, dynamic> values, {
  DateTime? deployedAt,
}) {
  return DeploymentOutputsSnapshot.fromJson({
    'schema_version': DeploymentOutputsSnapshot.supportedSchemaVersion,
    'outputs': values,
    'deployed_at': deployedAt?.toIso8601String(),
    'source_deployment': null,
    'redacted': true,
  });
}

DeploymentOperationViewState _operation({
  DeploymentOperationType operationType = DeploymentOperationType.deploy,
  List<DeploymentLogEntry> logs = const [],
  int lastEventId = 0,
  bool showLogs = true,
}) {
  return DeploymentOperationViewState(
    phase: DeploymentOperationViewPhase.streaming,
    operationType: operationType,
    session: OperationSession(
      sessionId: 'session-1',
      sseUrl: '/sse/deploy/session-1',
    ),
    logs: logs,
    lastEventId: lastEventId,
    showLogs: showLogs,
  );
}

DeploymentLogEntry _log(
  int eventId, {
  String sessionId = 'session-1',
  String message = 'Log event',
  String operationType = 'deploy',
}) {
  return DeploymentLogEntry(
    eventId: eventId,
    sessionId: sessionId,
    timestamp: DateTime.utc(2026, 7, 14, 12, 0, eventId % 60),
    level: 'info',
    message: message,
    operationType: operationType,
  );
}

DeploymentLogPage _page({
  int afterEventId = 0,
  List<DeploymentLogEntry> logs = const [],
  bool hasMore = false,
  int? nextAfterEventId,
  int? latestEventId,
}) {
  return DeploymentLogPage(
    schemaVersion: DeploymentLogPage.supportedSchemaVersion,
    twinId: 'test-id',
    sessionId: 'session-1',
    afterEventId: afterEventId,
    limit: 500,
    logs: logs,
    hasMore: hasMore,
    nextAfterEventId:
        nextAfterEventId ?? (logs.isEmpty ? afterEventId : logs.last.eventId),
    latestEventId:
        latestEventId ?? (logs.isEmpty ? afterEventId : logs.last.eventId),
  );
}

void _stubOperationStart(MockApiService api) {
  when(() => api.deployTwin('test-id')).thenAnswer(
    (_) async => const OperationSession(
      sessionId: 'session-1',
      sseUrl: '/sse/deploy/session-1',
    ),
  );
}

void _stubConfiguredLoad(MockApiService api) {
  _stubLoad(
    api,
    status: const DeploymentStatusSnapshot(
      schemaVersion: DeploymentStatusSnapshot.supportedSchemaVersion,
      state: DeploymentTwinState.configured,
    ),
    readiness: _readiness(ready: true),
  );
}

Future<void> _loadConfigured(TwinOverviewBloc bloc) async {
  bloc.add(const TwinOverviewLoad('test-id'));
  await pumpEventQueue(times: 20);
  expect(bloc.state, isA<TwinOverviewLoaded>());
}

void _stubEmptyLogPage(MockApiService api) {
  when(
    () => api.getDeploymentLogs(
      'test-id',
      sessionId: 'session-1',
      afterEventId: 0,
      limit: 500,
    ),
  ).thenAnswer((_) async => _page());
}

void _stubLoad(
  MockApiService api, {
  required DeploymentStatusSnapshot status,
  required DeploymentReadinessSnapshot readiness,
}) {
  when(() => api.getTwin('test-id')).thenAnswer(
    (_) async => TypedApiFixtures.twin(id: 'test-id', name: 'Test Project'),
  );
  when(
    () => api.getDeploymentStatus('test-id'),
  ).thenAnswer((_) async => status);
  when(() => api.getOptimizerConfig('test-id')).thenAnswer((_) async => null);
  when(() => api.getDeployerConfig('test-id')).thenAnswer((_) async => null);
  when(
    () => api.getDeploymentReadiness('test-id'),
  ).thenAnswer((_) async => readiness);
}

DeploymentReadinessSnapshot _readiness({
  required bool ready,
  DeploymentReadinessSource source = DeploymentReadinessSource.cached,
}) {
  final check = DeploymentReadinessCheck(
    component: ready ? 'deployer' : 'configuration',
    status: ready
        ? DeploymentReadinessCheckStatus.passed
        : DeploymentReadinessCheckStatus.failed,
    code: ready ? 'OK' : 'PREFLIGHT_NOT_RUN',
    message: ready ? 'Access passed.' : 'Preflight has not been run.',
    action: ready ? 'No action required.' : 'Run preflight.',
    permissions: const [],
  );
  return DeploymentReadinessSnapshot(
    schemaVersion: source == DeploymentReadinessSource.cached
        ? DeploymentReadinessSnapshot.cachedSchemaVersion
        : DeploymentReadinessSnapshot.preflightSchemaVersion,
    source: source,
    twinId: 'test-id',
    ready: ready,
    summary: ready ? 'Ready.' : 'Review required.',
    requiredProviders: const [CloudProvider.aws],
    providers: [
      ProviderDeploymentReadiness(
        provider: CloudProvider.aws,
        connectionId: 'connection-1',
        connectionDisplayName: 'AWS deployment',
        ready: ready,
        status: ready
            ? ProviderDeploymentReadinessStatus.ready
            : ProviderDeploymentReadinessStatus.notChecked,
        summary: check.message,
        expectedPermissionSetVersion: 'thesis-demo-v1',
        suppliedPermissionSetVersion: 'thesis-demo-v1',
        permissionSetStatus: PermissionSetReadinessStatus.matched,
        checks: [check],
      ),
    ],
    issues: const [],
  );
}
