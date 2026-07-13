// test/bloc/twin_overview/twin_overview_bloc_test.dart
// Unit tests for terminal state management in TwinOverviewBloc

import 'dart:typed_data';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_bloc.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_event.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/models/deployment_operations.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/services/log_stream_client.dart';

// Mock ApiService
class MockApiService extends Mock implements ApiService {}

class MockLogStreamClient extends Mock implements LogStreamClient {}

TwinOverviewBloc buildBloc(MockApiService api) {
  return TwinOverviewBloc(
    api: api,
    logStreamClientFactory: MockLogStreamClient.new,
  );
}

void main() {
  // ============================================================
  // TwinOverviewLoaded State Tests
  // ============================================================

  group('TwinOverviewLoaded State', () {
    test('showTerminal defaults to false', () {
      const state = TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'draft',
        canDeploy: true,
        canDestroy: false,
        canEdit: true,
        canDelete: true,
      );
      expect(state.showTerminal, isFalse);
      expect(state.terminalLogs, isEmpty);
    });

    test('copyWith preserves showTerminal when not specified', () {
      const state = TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deployed',
        canDeploy: false,
        canDestroy: true,
        canEdit: false,
        canDelete: false,
        showTerminal: true,
        terminalLogs: ['Log 1', 'Log 2'],
      );

      final updated = state.copyWith(twinState: 'destroying');

      expect(updated.showTerminal, isTrue);
      expect(updated.terminalLogs, ['Log 1', 'Log 2']);
      expect(updated.twinState, 'destroying');
    });

    test('copyWith updates showTerminal correctly', () {
      const state = TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deployed',
        canDeploy: false,
        canDestroy: true,
        canEdit: false,
        canDelete: false,
        showTerminal: true,
      );

      final updated = state.copyWith(showTerminal: false);

      expect(updated.showTerminal, isFalse);
    });

    test('props includes showTerminal and terminalLogs', () {
      const state1 = TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'draft',
        canDeploy: true,
        canDestroy: false,
        canEdit: true,
        canDelete: true,
        showTerminal: false,
      );

      const state2 = TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'draft',
        canDeploy: true,
        canDestroy: false,
        canEdit: true,
        canDelete: true,
        showTerminal: true,
      );

      expect(state1.props.contains(false), isTrue); // showTerminal
      expect(state2.props.contains(true), isTrue); // showTerminal
      expect(state1 == state2, isFalse); // Different due to showTerminal
    });

    test('copyWith explicitly clears every nullable operation artifact', () {
      final state = TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'error',
        canDeploy: true,
        canDestroy: true,
        canEdit: true,
        canDelete: true,
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

      expect(cleared.traceId, isNull);
      expect(cleared.lastError, isNull);
      expect(cleared.deploymentOutputs, isNull);
      expect(cleared.outputsTimestamp, isNull);
      expect(cleared.simulatorBytes, isNull);
      expect(cleared.simulatorFilename, isNull);
    });
  });

  // ============================================================
  // TwinOverviewCloseTerminal Event Tests
  // ============================================================

  group('TwinOverviewCloseTerminal Event', () {
    test('has correct props (empty)', () {
      const event = TwinOverviewCloseTerminal();
      expect(event.props, isEmpty);
    });

    test('equals another TwinOverviewCloseTerminal', () {
      const event1 = TwinOverviewCloseTerminal();
      const event2 = TwinOverviewCloseTerminal();
      expect(event1, equals(event2));
    });
  });

  // ============================================================
  // BLoC Happy Path Tests
  // ============================================================

  group('TwinOverviewBloc - Terminal Happy Paths', () {
    late MockApiService mockApi;

    setUp(() {
      mockApi = MockApiService();
    });

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'CloseTerminal sets showTerminal false and clears logs',
      seed: () => const TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deployed',
        canDeploy: false,
        canDestroy: true,
        canEdit: false,
        canDelete: false,
        showTerminal: true,
        terminalLogs: ['Log 1', 'Log 2', 'Log 3'],
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) => bloc.add(const TwinOverviewCloseTerminal()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((s) => s.showTerminal, 'showTerminal', false)
            .having((s) => s.terminalLogs, 'terminalLogs', isEmpty),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'LogReceived appends to terminalLogs',
      seed: () => const TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deploying',
        canDeploy: false,
        canDestroy: false,
        canEdit: false,
        canDelete: false,
        isDeploying: true,
        showTerminal: true,
        terminalLogs: ['> Starting deployment...'],
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) {
        bloc.add(const TwinOverviewLogReceived('Initializing...'));
        bloc.add(const TwinOverviewLogReceived('Creating resources...'));
      },
      expect: () => [
        isA<TwinOverviewLoaded>().having(
          (s) => s.terminalLogs.length,
          'log count',
          2,
        ),
        isA<TwinOverviewLoaded>().having(
          (s) => s.terminalLogs.length,
          'log count',
          3,
        ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'DeploymentComplete preserves showTerminal and terminalLogs',
      seed: () => const TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deploying',
        canDeploy: false,
        canDestroy: false,
        canEdit: false,
        canDelete: false,
        isDeploying: true,
        showTerminal: true,
        terminalLogs: ['Log 1', 'Log 2'],
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) => bloc.add(
        const TwinOverviewDeploymentComplete(
          success: true,
          newState: 'deployed',
          message: 'Deployment successful',
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((s) => s.isDeploying, 'isDeploying', false)
            .having((s) => s.showTerminal, 'showTerminal', true)
            .having((s) => s.terminalLogs, 'logs preserved', [
              'Log 1',
              'Log 2',
            ]),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'successful destroy clears stale error, outputs, and output timestamp',
      seed: () => TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'destroying',
        canDeploy: false,
        canDestroy: false,
        canEdit: false,
        canDelete: false,
        isDestroying: true,
        lastError: 'Previous deployment failed',
        deploymentOutputs: const {'endpoint': 'old'},
        outputsTimestamp: DateTime.utc(2026, 7, 14),
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) => bloc.add(
        const TwinOverviewDeploymentComplete(
          success: true,
          newState: 'destroyed',
          message: 'Resources destroyed',
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((state) => state.lastError, 'lastError', isNull)
            .having(
              (state) => state.deploymentOutputs,
              'deploymentOutputs',
              isNull,
            )
            .having(
              (state) => state.outputsTimestamp,
              'outputsTimestamp',
              isNull,
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'completion without current outputs does not retain stale outputs',
      seed: () => TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deploying',
        canDeploy: false,
        canDestroy: false,
        canEdit: false,
        canDelete: false,
        isDeploying: true,
        deploymentOutputs: const {'endpoint': 'previous-deployment'},
        outputsTimestamp: DateTime.utc(2026, 7, 13),
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) => bloc.add(
        const TwinOverviewDeploymentComplete(
          success: true,
          newState: 'deployed',
          message: 'Deployment successful',
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.deploymentOutputs,
              'deploymentOutputs',
              isNull,
            )
            .having(
              (state) => state.outputsTimestamp,
              'outputsTimestamp',
              isNull,
            ),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'simulator download keeps server filename with transient bytes',
      seed: () => TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deployed',
        canDeploy: false,
        canDestroy: true,
        canEdit: false,
        canDelete: false,
        errorMessage: 'Previous download failed',
        simulatorBytes: Uint8List.fromList([9]),
        simulatorFilename: 'simulator_old.zip',
      ),
      setUp: () {
        when(() => mockApi.downloadSimulator('test-id')).thenAnswer(
          (_) async => BinaryDownload(
            bytes: Uint8List.fromList([1, 2, 3]),
            filename: 'simulator_server_name.zip',
            mediaType: 'application/zip',
          ),
        );
      },
      build: () => buildBloc(mockApi),
      act: (bloc) => bloc.add(const TwinOverviewDownloadSimulator()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.isDownloadingSimulator,
              'isDownloadingSimulator',
              true,
            )
            .having(
              (state) => state.infoMessage,
              'infoMessage',
              'Downloading simulator...',
            )
            .having((state) => state.errorMessage, 'errorMessage', isNull)
            .having((state) => state.simulatorBytes, 'simulatorBytes', isNull)
            .having(
              (state) => state.simulatorFilename,
              'simulatorFilename',
              isNull,
            ),
        isA<TwinOverviewLoaded>()
            .having(
              (state) => state.isDownloadingSimulator,
              'isDownloadingSimulator',
              false,
            )
            .having(
              (state) => state.simulatorFilename,
              'simulatorFilename',
              'simulator_server_name.zip',
            )
            .having((state) => state.simulatorBytes, 'simulatorBytes', [
              1,
              2,
              3,
            ]),
      ],
    );
  });

  // ============================================================
  // BLoC Error Cases Tests
  // ============================================================

  group('TwinOverviewBloc - Terminal Error Cases', () {
    late MockApiService mockApi;

    setUp(() {
      mockApi = MockApiService();
    });

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'CloseTerminal on non-Loaded state is no-op',
      build: () => buildBloc(mockApi),
      // Initial state is TwinOverviewLoading
      act: (bloc) => bloc.add(const TwinOverviewCloseTerminal()),
      expect: () => [], // No state change
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'DeploymentComplete with failure keeps showTerminal true',
      seed: () => const TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deploying',
        canDeploy: false,
        canDestroy: false,
        canEdit: false,
        canDelete: false,
        isDeploying: true,
        showTerminal: true,
        terminalLogs: ['Log 1', 'Error log'],
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) => bloc.add(
        const TwinOverviewDeploymentComplete(
          success: false,
          newState: 'error',
          message: 'Deployment failed',
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((s) => s.showTerminal, 'showTerminal', true)
            .having((s) => s.terminalLogs, 'logs preserved', [
              'Log 1',
              'Error log',
            ])
            .having((s) => s.canDestroy, 'canDestroy', true)
            .having((s) => s.canDeploy, 'canDeploy', true),
      ],
    );
  });

  // ============================================================
  // Permission Recalculation Tests
  // ============================================================

  group('TwinOverviewBloc - Permission Recalculation', () {
    late MockApiService mockApi;

    setUp(() {
      mockApi = MockApiService();
    });

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'DeploymentComplete success sets canDestroy=true and canDeploy=false',
      seed: () => const TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deploying',
        canDeploy: false,
        canDestroy: false,
        canEdit: false,
        canDelete: false,
        isDeploying: true,
        showTerminal: true,
        terminalLogs: ['Log 1'],
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) => bloc.add(
        const TwinOverviewDeploymentComplete(
          success: true,
          newState: 'deployed',
          message: 'Deployment successful',
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((s) => s.twinState, 'twinState', 'deployed')
            .having((s) => s.canDeploy, 'canDeploy', false)
            .having((s) => s.canDestroy, 'canDestroy', true)
            .having((s) => s.canEdit, 'canEdit', false)
            .having((s) => s.canDelete, 'canDelete', false),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'DeploymentComplete failure from configured state enables cleanup',
      seed: () => const TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deploying',
        canDeploy: false,
        canDestroy: false,
        canEdit: false,
        canDelete: false,
        isDeploying: true,
        showTerminal: true,
        terminalLogs: ['Log 1'],
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) => bloc.add(
        const TwinOverviewDeploymentComplete(
          success: false,
          newState: 'error',
          message: 'Terraform apply failed',
        ),
      ),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((s) => s.twinState, 'twinState', 'error')
            .having((s) => s.canDeploy, 'canDeploy', true)
            .having((s) => s.canDestroy, 'canDestroy', true)
            .having((s) => s.canEdit, 'canEdit', true)
            .having((s) => s.canDelete, 'canDelete', true),
      ],
    );
  });

  // ============================================================
  // BLoC Edge Cases Tests
  // ============================================================

  group('TwinOverviewBloc - Terminal Edge Cases', () {
    late MockApiService mockApi;

    setUp(() {
      mockApi = MockApiService();
    });

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'Multiple LogReceived events accumulate correctly',
      seed: () => const TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deploying',
        canDeploy: false,
        canDestroy: false,
        canEdit: false,
        canDelete: false,
        isDeploying: true,
        showTerminal: true,
        terminalLogs: [],
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) {
        for (int i = 0; i < 5; i++) {
          bloc.add(TwinOverviewLogReceived('Log $i'));
        }
      },
      expect: () => [
        isA<TwinOverviewLoaded>().having(
          (s) => s.terminalLogs.length,
          'length',
          1,
        ),
        isA<TwinOverviewLoaded>().having(
          (s) => s.terminalLogs.length,
          'length',
          2,
        ),
        isA<TwinOverviewLoaded>().having(
          (s) => s.terminalLogs.length,
          'length',
          3,
        ),
        isA<TwinOverviewLoaded>().having(
          (s) => s.terminalLogs.length,
          'length',
          4,
        ),
        isA<TwinOverviewLoaded>()
            .having((s) => s.terminalLogs.length, 'length', 5)
            .having((s) => s.terminalLogs.last, 'last log', 'Log 4'),
      ],
    );

    blocTest<TwinOverviewBloc, TwinOverviewState>(
      'Close during active deployment clears state',
      seed: () => const TwinOverviewLoaded(
        twinId: 'test-id',
        projectName: 'Test Project',
        twinState: 'deploying',
        canDeploy: false,
        canDestroy: false,
        canEdit: false,
        canDelete: false,
        isDeploying: true,
        showTerminal: true,
        terminalLogs: ['Active log'],
      ),
      build: () => buildBloc(mockApi),
      act: (bloc) => bloc.add(const TwinOverviewCloseTerminal()),
      expect: () => [
        isA<TwinOverviewLoaded>()
            .having((s) => s.showTerminal, 'showTerminal', false)
            .having((s) => s.terminalLogs, 'terminalLogs', isEmpty)
            .having((s) => s.isDeploying, 'isDeploying still true', true),
      ],
    );
  });
}
