import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

import '../fixtures/architecture_profile_fixtures.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  late _MockManagementApi api;
  late ArchitectureProfileDetail canonicalDetail;
  late TwinArchitectureSelection canonicalSelection;

  setUp(() {
    api = _MockManagementApi();
    canonicalDetail = ArchitectureProfileDetail.fromJson(
      architectureProfileDetailJson(
        profileId: 'six-layer-eventing',
        profileVersion: '1',
        withExtensionSlot: false,
      ),
    );
    canonicalSelection = TwinArchitectureSelection.fromJson(
      architectureSelectionJson(
        profileId: 'six-layer-eventing',
        profileVersion: '1',
      ),
    );
  });

  test(
    'loads and verifies the one canonical contract for a persisted Twin',
    () async {
      when(
        () => api.getCanonicalArchitectureContract(),
      ).thenAnswer((_) async => canonicalDetail);
      when(
        () => api.getTwinArchitectureContract('twin-1'),
      ).thenAnswer((_) async => canonicalSelection);
      final bloc = WizardBloc(
        api: api,
        initialState: const WizardState(
          status: WizardStatus.ready,
          twinId: 'twin-1',
          twinName: 'Factory twin',
        ),
      );
      addTearDown(bloc.close);

      final completed = bloc.stream.firstWhere(
        (state) =>
            state.architectureDetailPhase == ArchitectureDetailPhase.ready,
      );
      bloc.add(const WizardCanonicalArchitectureLoadRequested());
      final state = await completed;

      expect(state.architectureProfileDetail, canonicalDetail);
      expect(state.architectureSelection, canonicalSelection);
      expect(state.architectureWorkflowReady, isTrue);
      expect(state.canProceedToStep2, isTrue);
    },
  );

  test('loads contract metadata before a new Twin is persisted', () async {
    when(
      () => api.getCanonicalArchitectureContract(),
    ).thenAnswer((_) async => canonicalDetail);
    final bloc = WizardBloc(
      api: api,
      initialState: const WizardState(
        status: WizardStatus.ready,
        twinName: 'New twin',
      ),
    );
    addTearDown(bloc.close);

    final completed = bloc.stream.firstWhere(
      (state) => state.architectureDetailPhase == ArchitectureDetailPhase.ready,
    );
    bloc.add(const WizardCanonicalArchitectureLoadRequested());
    final state = await completed;

    expect(state.architectureProfileDetail, canonicalDetail);
    expect(state.architectureSelection, isNull);
    expect(state.architectureWorkflowReady, isFalse);
    verifyNever(() => api.getTwinArchitectureContract(any()));
  });

  test('rejects a Twin pinned to a different profile', () async {
    final incompatible = TwinArchitectureSelection.fromJson(
      architectureSelectionJson(),
    );
    when(
      () => api.getCanonicalArchitectureContract(),
    ).thenAnswer((_) async => canonicalDetail);
    when(
      () => api.getTwinArchitectureContract('twin-1'),
    ).thenAnswer((_) async => incompatible);
    final bloc = WizardBloc(
      api: api,
      initialState: const WizardState(
        status: WizardStatus.ready,
        twinId: 'twin-1',
        twinName: 'Historical twin',
      ),
    );
    addTearDown(bloc.close);

    final completed = bloc.stream.firstWhere(
      (state) => state.architectureDetailPhase == ArchitectureDetailPhase.error,
    );
    bloc.add(const WizardCanonicalArchitectureLoadRequested());
    final state = await completed;

    expect(state.architectureProfileDetail, isNull);
    expect(state.architectureSelection, isNull);
    expect(state.architectureWorkflowReady, isFalse);
    expect(state.architectureDetailError, contains('canonical'));
  });

  test('rejects a selection whose pinned digest differs', () async {
    final mismatched = TwinArchitectureSelection.fromJson(
      architectureSelectionJson(
        profileId: 'six-layer-eventing',
        profileVersion: '1',
        profileDigest: fixtureDigestB,
      ),
    );
    when(
      () => api.getCanonicalArchitectureContract(),
    ).thenAnswer((_) async => canonicalDetail);
    when(
      () => api.getTwinArchitectureContract('twin-1'),
    ).thenAnswer((_) async => mismatched);
    final bloc = WizardBloc(
      api: api,
      initialState: const WizardState(
        status: WizardStatus.ready,
        twinId: 'twin-1',
      ),
    );
    addTearDown(bloc.close);

    final completed = bloc.stream.firstWhere(
      (state) => state.architectureDetailPhase == ArchitectureDetailPhase.error,
    );
    bloc.add(const WizardCanonicalArchitectureLoadRequested());
    final state = await completed;

    expect(state.architectureWorkflowReady, isFalse);
    expect(state.architectureDetailError, contains('canonical'));
  });

  test('fails closed when canonical detail cannot be loaded', () async {
    when(
      () => api.getCanonicalArchitectureContract(),
    ).thenThrow(Exception('offline'));
    final bloc = WizardBloc(
      api: api,
      initialState: const WizardState(status: WizardStatus.ready),
    );
    addTearDown(bloc.close);

    final completed = bloc.stream.firstWhere(
      (state) => state.architectureDetailPhase == ArchitectureDetailPhase.error,
    );
    bloc.add(const WizardCanonicalArchitectureLoadRequested());
    final state = await completed;

    expect(state.architectureWorkflowReady, isFalse);
    expect(state.architectureDetailError, isNotEmpty);
  });
}
