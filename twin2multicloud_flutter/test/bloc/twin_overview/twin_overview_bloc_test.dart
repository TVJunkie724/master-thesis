// test/bloc/twin_overview/twin_overview_bloc_test.dart
// Unit tests for terminal state management in TwinOverviewBloc

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_bloc.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_event.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

// Mock ApiService
class MockApiService extends Mock implements ApiService {}

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
      build: () => TwinOverviewBloc(api: mockApi),
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
      build: () => TwinOverviewBloc(api: mockApi),
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
      build: () => TwinOverviewBloc(api: mockApi),
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
      build: () => TwinOverviewBloc(api: mockApi),
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
      build: () => TwinOverviewBloc(api: mockApi),
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
      build: () => TwinOverviewBloc(api: mockApi),
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
      build: () => TwinOverviewBloc(api: mockApi),
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
      build: () => TwinOverviewBloc(api: mockApi),
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
      build: () => TwinOverviewBloc(api: mockApi),
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
