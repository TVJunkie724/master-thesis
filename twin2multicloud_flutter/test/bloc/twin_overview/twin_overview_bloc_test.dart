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
          traceId: 'TRACE-1',
          lastError: 'Old deployment error',
          deploymentOutputs: const {'endpoint': 'old'},
          outputsTimestamp: DateTime.utc(2026, 7, 14),
          simulatorBytes: Uint8List.fromList([1, 2, 3]),
          simulatorFilename: 'simulator_test.zip',
        );

        final cleared = state.copyWith(
          clearTraceId: true,
          clearLastError: true,
          clearDeploymentOutputs: true,
          clearOutputsTimestamp: true,
          clearSimulatorBytes: true,
          clearSimulatorFilename: true,
        );

        expect(cleared.deploymentOperation, state.deploymentOperation);
        expect(cleared.traceId, isNull);
        expect(cleared.lastError, isNull);
        expect(cleared.deploymentOutputs, isNull);
        expect(cleared.outputsTimestamp, isNull);
        expect(cleared.simulatorBytes, isNull);
        expect(cleared.simulatorFilename, isNull);
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
      'keeps trace diagnostics independent from deployment logs',
      seed: () => _loaded(
        operation: _operation(logs: [_log(1)], lastEventId: 1, showLogs: false),
        showTraceTerminal: true,
        traceTerminalLogs: const ['Trace event'],
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewCloseTerminal()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((state) => state.showTraceTerminal, 'trace hidden', isFalse)
            .having(
              (state) => state.traceTerminalLogs,
              'trace cleared',
              isEmpty,
            )
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
        deploymentOutputs: const {'endpoint': 'old'},
        outputsTimestamp: DateTime.utc(2026, 7, 14),
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
            .having((state) => state.outputsTimestamp, 'timestamp', isNull)
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
        expect(loaded.deploymentOutputs, {'endpoint': 'https://example.test'});
        expect(loaded.outputsTimestamp, DateTime.utc(2026, 7, 14, 12));
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

  group('TwinOverviewBloc simulator download', () {
    late MockApiService api;

    setUp(() => api = MockApiService());

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'keeps server filename with transient bytes and clears prior errors',
      seed: () => _loaded(
        twinState: 'deployed',
        simulatorBytes: Uint8List.fromList([9]),
        simulatorFilename: 'simulator_old.zip',
      ).copyWith(errorMessage: 'Previous download failed'),
      setUp: () => when(() => api.downloadSimulator('test-id')).thenAnswer(
        (_) async => BinaryDownload(
          bytes: Uint8List.fromList([1, 2, 3]),
          filename: 'simulator_server_name.zip',
          mediaType: 'application/zip',
        ),
      ),
      build: () => _buildBloc(api),
      act: (bloc) => bloc.add(const TwinOverviewDownloadSimulator()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.isDownloadingSimulator,
              'downloading',
              isTrue,
            )
            .having((state) => state.errorMessage, 'error', isNull)
            .having((state) => state.simulatorBytes, 'old bytes', isNull),
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.isDownloadingSimulator,
              'downloading',
              isFalse,
            )
            .having(
              (state) => state.simulatorFilename,
              'filename',
              'simulator_server_name.zip',
            )
            .having((state) => state.simulatorBytes, 'bytes', [1, 2, 3]),
      ],
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
  String? traceId,
  String? lastError,
  bool showTraceTerminal = false,
  List<String> traceTerminalLogs = const [],
  Map<String, dynamic>? deploymentOutputs,
  DateTime? outputsTimestamp,
  Uint8List? simulatorBytes,
  String? simulatorFilename,
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
    traceId: traceId,
    lastError: lastError,
    showTraceTerminal: showTraceTerminal,
    traceTerminalLogs: traceTerminalLogs,
    deploymentOutputs: deploymentOutputs,
    outputsTimestamp: outputsTimestamp,
    simulatorBytes: simulatorBytes,
    simulatorFilename: simulatorFilename,
  );
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
  when(
    () => api.getTwin('test-id'),
  ).thenAnswer((_) async => {'id': 'test-id', 'name': 'Test Project'});
  when(
    () => api.getDeploymentStatus('test-id'),
  ).thenAnswer((_) async => status);
  when(() => api.getOptimizerConfig('test-id')).thenThrow(Exception('missing'));
  when(() => api.getDeployerConfig('test-id')).thenThrow(Exception('missing'));
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
