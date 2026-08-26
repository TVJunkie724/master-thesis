import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';
import 'package:twin2multicloud_flutter/models/resolved_twin_architecture.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

import '../fixtures/architecture_profile_fixtures.dart';
import '../fixtures/architecture_wizard_fixture.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  late _MockManagementApi api;
  late ArchitectureProfileSummary profile;
  late ArchitectureProfileDetail detail;

  setUpAll(() {
    registerFallbackValue(
      const ArchitectureProfileChangePreviewRequest(
        profileId: 'fallback',
        profileVersion: '1',
        expectedRevision: 1,
      ),
    );
    registerFallbackValue(
      const ArchitectureProfileSelectRequest(
        profileId: 'fallback',
        profileVersion: '1',
        expectedRevision: 1,
        invalidationDigest: fixtureDigest,
      ),
    );
  });

  setUp(() {
    api = _MockManagementApi();
    profile = ArchitectureProfileSummary.fromJson(
      architectureProfileSummaryJson(withExtensionSlot: false),
    );
    detail = ArchitectureProfileDetail.fromJson(
      architectureProfileDetailJson(withExtensionSlot: false),
    );
  });

  test(
    'empty catalog preserves a historical selection and blocks work',
    () async {
      final historical = _historicalSelection();
      when(() => api.listArchitectureProfiles()).thenAnswer((_) async => []);
      when(
        () => api.getTwinArchitectureSelection('twin-1'),
      ).thenAnswer((_) async => historical);
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
            state.architectureCatalogPhase == ArchitectureCatalogPhase.empty,
      );
      bloc.add(const WizardArchitectureProfilesLoadRequested());
      final state = await completed;

      expect(state.architectureSelection, historical);
      expect(state.hasHistoricalArchitectureSelection, isTrue);
      expect(state.hasActiveArchitectureProfile, isFalse);
      expect(state.canRequestCalculation, isFalse);
    },
  );

  test(
    'active selected profile loads strict detail and unlocks workload',
    () async {
      final selection = TwinArchitectureSelection.fromJson(
        architectureSelectionJson(),
      );
      when(
        () => api.listArchitectureProfiles(),
      ).thenAnswer((_) async => [profile]);
      when(
        () => api.getTwinArchitectureSelection('twin-1'),
      ).thenAnswer((_) async => selection);
      when(
        () => api.getArchitectureProfile('fixture-profile', '2'),
      ).thenAnswer((_) async => detail);
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
      bloc.add(const WizardArchitectureProfilesLoadRequested());
      final loaded = await completed;

      expect(loaded.architectureWorkflowReady, isFalse);
      expect(loaded.architectureProfileDetail, detail);
      final acknowledged = bloc.stream.firstWhere(
        (state) => state.architectureWorkflowReady,
      );
      bloc.add(const WizardArchitectureUnderstandingAcknowledged());
      final state = await acknowledged;
      expect(state.canProceedToStep2, isTrue);
    },
  );

  test('catalog failure preserves the loaded draft and fails closed', () async {
    final selection = TwinArchitectureSelection.fromJson(
      architectureSelectionJson(),
    );
    when(() => api.listArchitectureProfiles()).thenThrow(
      const DemoApiException(
        'ARCH_CATALOG_UNAVAILABLE',
        'Safe catalog failure',
      ),
    );
    final bloc = WizardBloc(
      api: api,
      initialState: WizardState(
        status: WizardStatus.ready,
        twinId: 'twin-1',
        twinName: 'Factory twin',
        architectureCatalogPhase: ArchitectureCatalogPhase.ready,
        architectureProfiles: [profile],
        architectureSelection: selection,
        architectureDetailPhase: ArchitectureDetailPhase.ready,
        architectureProfileDetail: detail,
        architectureDetailAcknowledged: true,
      ),
    );
    addTearDown(bloc.close);

    final failed = bloc.stream.firstWhere(
      (state) =>
          state.architectureCatalogPhase == ArchitectureCatalogPhase.error,
    );
    bloc.add(const WizardArchitectureProfilesLoadRequested());
    final state = await failed;

    expect(state.architectureCatalogError, 'Safe catalog failure');
    expect(state.architectureProfiles, [profile]);
    expect(state.architectureSelection, selection);
    expect(state.architectureProfileDetail, detail);
    expect(state.architectureWorkflowReady, isFalse);
  });

  test('a late detail response cannot overwrite the latest request', () async {
    final profileB = ArchitectureProfileSummary.fromJson(
      architectureProfileSummaryJson(
        profileId: 'fixture-profile-b',
        profileDigest: fixtureDigestB,
        withExtensionSlot: false,
      ),
    );
    final detailB = ArchitectureProfileDetail.fromJson(
      architectureProfileDetailJson(
        profileId: 'fixture-profile-b',
        profileDigest: fixtureDigestB,
        withExtensionSlot: false,
      ),
    );
    final first = Completer<ArchitectureProfileDetail>();
    final second = Completer<ArchitectureProfileDetail>();
    when(
      () => api.getArchitectureProfile('fixture-profile', '2'),
    ).thenAnswer((_) => first.future);
    when(
      () => api.getArchitectureProfile('fixture-profile-b', '2'),
    ).thenAnswer((_) => second.future);
    final bloc = WizardBloc(
      api: api,
      initialState: WizardState(
        status: WizardStatus.ready,
        architectureCatalogPhase: ArchitectureCatalogPhase.ready,
        architectureProfiles: [profile, profileB],
      ),
    );
    addTearDown(bloc.close);

    bloc.add(WizardArchitectureProfileDetailLoadRequested(profile.ref));
    bloc.add(WizardArchitectureProfileDetailLoadRequested(profileB.ref));
    second.complete(detailB);
    await bloc.stream.firstWhere(
      (state) => state.architectureProfileDetail == detailB,
    );
    first.complete(detail);
    await Future<void>.delayed(Duration.zero);

    expect(bloc.state.architectureProfileDetail, detailB);
  });

  test('a different detail clears stale content while loading', () async {
    final profileB = ArchitectureProfileSummary.fromJson(
      architectureProfileSummaryJson(
        profileId: 'fixture-profile-b',
        profileDigest: fixtureDigestB,
        withExtensionSlot: false,
      ),
    );
    final pending = Completer<ArchitectureProfileDetail>();
    when(
      () => api.getArchitectureProfile('fixture-profile-b', '2'),
    ).thenAnswer((_) => pending.future);
    final bloc = WizardBloc(
      api: api,
      initialState: WizardState(
        status: WizardStatus.ready,
        architectureCatalogPhase: ArchitectureCatalogPhase.ready,
        architectureProfiles: [profile, profileB],
        architectureDetailPhase: ArchitectureDetailPhase.ready,
        architectureProfileDetail: detail,
        architectureDetailAcknowledged: true,
      ),
    );
    addTearDown(bloc.close);

    final loading = bloc.stream.firstWhere(
      (state) =>
          state.architectureDetailPhase == ArchitectureDetailPhase.loading,
    );
    bloc.add(WizardArchitectureProfileDetailLoadRequested(profileB.ref));
    final state = await loading;

    expect(state.architectureProfileDetail, isNull);
    expect(state.architectureDetailAcknowledged, isFalse);
    final failed = bloc.stream.firstWhere(
      (state) => state.architectureDetailPhase == ArchitectureDetailPhase.error,
    );
    pending.completeError(StateError('test cleanup'));
    await failed;
  });

  test('selecting the current profile is a network no-op', () async {
    final selection = TwinArchitectureSelection.fromJson(
      architectureSelectionJson(),
    );
    final initial = WizardState(
      status: WizardStatus.ready,
      twinId: 'twin-1',
      architectureCatalogPhase: ArchitectureCatalogPhase.ready,
      architectureProfiles: [profile],
      architectureSelection: selection,
      architectureDetailPhase: ArchitectureDetailPhase.ready,
      architectureProfileDetail: detail,
      architectureDetailAcknowledged: true,
    );
    final bloc = WizardBloc(api: api, initialState: initial);
    addTearDown(bloc.close);

    bloc.add(WizardArchitectureProfileSelected(profile.ref));
    await Future<void>.delayed(Duration.zero);

    expect(bloc.state, initial);
    verifyNever(() => api.getArchitectureProfile(any(), any()));
    verifyNever(() => api.previewTwinArchitectureProfileChange(any(), any()));
  });

  test('an in-flight profile preview ignores a competing selection', () async {
    final profileB = ArchitectureProfileSummary.fromJson(
      architectureProfileSummaryJson(
        profileId: 'fixture-profile-b',
        profileDigest: fixtureDigestB,
        withExtensionSlot: false,
      ),
    );
    final preview = Completer<ArchitectureProfileChangePreview>();
    when(
      () => api.previewTwinArchitectureProfileChange('twin-1', any()),
    ).thenAnswer((_) => preview.future);
    final bloc = WizardBloc(
      api: api,
      initialState: WizardState(
        status: WizardStatus.ready,
        twinId: 'twin-1',
        architectureCatalogPhase: ArchitectureCatalogPhase.ready,
        architectureProfiles: [profile, profileB],
        architectureSelection: _historicalSelection(),
      ),
    );
    addTearDown(bloc.close);

    bloc.add(WizardArchitectureProfileSelected(profile.ref));
    await bloc.stream.firstWhere(
      (state) =>
          state.architectureChangePhase == ArchitectureChangePhase.previewing,
    );
    bloc.add(WizardArchitectureProfileSelected(profileB.ref));
    await Future<void>.delayed(Duration.zero);

    verify(
      () => api.previewTwinArchitectureProfileChange('twin-1', any()),
    ).called(1);
    final failed = bloc.stream.firstWhere(
      (state) => state.architectureChangePhase == ArchitectureChangePhase.error,
    );
    preview.completeError(StateError('test cleanup'));
    await failed;
  });

  test('profile change applies only server-returned invalidations', () async {
    final historical = _historicalSelection();
    final preview = ArchitectureProfileChangePreview.fromJson(
      architecturePreviewJson(),
    );
    final result = ArchitectureProfileSelectionResult.fromJson(
      architectureSelectionResultJson(),
    );
    when(
      () => api.previewTwinArchitectureProfileChange('twin-1', any()),
    ).thenAnswer((_) async => preview);
    when(
      () => api.selectTwinArchitectureProfile('twin-1', any()),
    ).thenAnswer((_) async => result);
    when(
      () => api.getArchitectureProfile('fixture-profile', '2'),
    ).thenAnswer((_) async => detail);
    final bloc = WizardBloc(
      api: api,
      initialState: WizardState(
        status: WizardStatus.ready,
        twinId: 'twin-1',
        twinName: 'Factory twin',
        architectureCatalogPhase: ArchitectureCatalogPhase.ready,
        architectureProfiles: [profile],
        architectureSelection: historical,
        resolvedArchitecturePhase: ResolvedArchitecturePhase.ready,
        resolvedArchitecture: resolvedArchitectureFixture(),
      ),
    );
    addTearDown(bloc.close);

    final previewed = bloc.stream.firstWhere(
      (state) =>
          state.architectureChangePhase ==
          ArchitectureChangePhase.awaitingConfirmation,
    );
    bloc.add(WizardArchitectureProfileSelected(profile.ref));
    await previewed;
    bloc.add(const WizardArchitectureProfileChangeConfirmed());
    await bloc.stream.firstWhere(
      (state) =>
          state.architectureChangePhase == ArchitectureChangePhase.idle &&
          state.architectureSelection?.revision == 2,
    );

    expect(bloc.state.architectureInvalidatedWorkloadFieldIds, {
      'legacy.field',
    });
    expect(bloc.state.step3Invalidated, isTrue);
    expect(bloc.state.architectureSelection?.profileRef, profile.ref);
    expect(
      bloc.state.resolvedArchitecturePhase,
      ResolvedArchitecturePhase.idle,
    );
    expect(bloc.state.resolvedArchitecture, isNull);
  });

  test(
    'stale preview reloads selection and requires confirmation again',
    () async {
      final historical = _historicalSelection();
      final reloaded = TwinArchitectureSelection.fromJson(
        architectureSelectionJson(revision: 3),
      );
      when(
        () => api.previewTwinArchitectureProfileChange('twin-1', any()),
      ).thenThrow(
        const DemoApiException(
          'ARCH_SELECTION_REVISION_CONFLICT',
          'The architecture selection revision is stale.',
        ),
      );
      when(
        () => api.getTwinArchitectureSelection('twin-1'),
      ).thenAnswer((_) async => reloaded);
      when(
        () => api.getArchitectureProfile('fixture-profile', '2'),
      ).thenAnswer((_) async => detail);
      final bloc = WizardBloc(
        api: api,
        initialState: WizardState(
          status: WizardStatus.ready,
          twinId: 'twin-1',
          twinName: 'Factory twin',
          architectureCatalogPhase: ArchitectureCatalogPhase.ready,
          architectureProfiles: [profile],
          architectureSelection: historical,
        ),
      );
      addTearDown(bloc.close);

      final conflicted = bloc.stream.firstWhere(
        (state) =>
            state.architectureChangePhase == ArchitectureChangePhase.conflict &&
            state.architectureSelection?.revision == 3,
      );
      bloc.add(WizardArchitectureProfileSelected(profile.ref));
      final state = await conflicted;

      expect(state.architectureChangePreview, isNull);
      expect(state.architectureChangeError, contains('fresh preview'));
      verifyNever(() => api.selectTwinArchitectureProfile(any(), any()));
    },
  );

  test(
    'stale invalidation digest reloads selection after confirmation',
    () async {
      final historical = _historicalSelection();
      final reloaded = TwinArchitectureSelection.fromJson(
        architectureSelectionJson(revision: 4),
      );
      final preview = ArchitectureProfileChangePreview.fromJson(
        architecturePreviewJson(),
      );
      when(() => api.selectTwinArchitectureProfile('twin-1', any())).thenThrow(
        const DemoApiException(
          'ARCH_SELECTION_INVALIDATION_STALE',
          'The profile-change preview is stale.',
        ),
      );
      when(
        () => api.getTwinArchitectureSelection('twin-1'),
      ).thenAnswer((_) async => reloaded);
      when(
        () => api.getArchitectureProfile('fixture-profile', '2'),
      ).thenAnswer((_) async => detail);
      final bloc = WizardBloc(
        api: api,
        initialState: WizardState(
          status: WizardStatus.ready,
          twinId: 'twin-1',
          architectureCatalogPhase: ArchitectureCatalogPhase.ready,
          architectureProfiles: [profile],
          architectureSelection: historical,
          architectureChangePhase: ArchitectureChangePhase.awaitingConfirmation,
          architectureChangePreview: preview,
        ),
      );
      addTearDown(bloc.close);

      final conflicted = bloc.stream.firstWhere(
        (state) =>
            state.architectureChangePhase == ArchitectureChangePhase.conflict &&
            state.architectureSelection?.revision == 4,
      );
      bloc.add(const WizardArchitectureProfileChangeConfirmed());
      final state = await conflicted;

      expect(state.architectureChangePreview, isNull);
      expect(state.architectureChangeError, contains('fresh preview'));
      verify(
        () => api.selectTwinArchitectureProfile('twin-1', any()),
      ).called(1);
    },
  );

  test('resolved architecture matches Twin, run, profile, and digest', () async {
    final architecture = Map<String, dynamic>.from(
      jsonDecode(
            File(
              '../contracts/architecture-profiles/v2/fixtures/valid/'
              'six-layer-aws-azure-eventing-small-resolved.json',
            ).readAsStringSync(),
          )
          as Map,
    );
    final runId = architecture['calculation_run_id'].toString();
    final resolved = ResolvedTwinArchitectureRead.fromJson({
      'twin_id': 'twin-1',
      'calculation_run_id': runId,
      'selected_for_deployment_at': '2026-08-03T10:00:00Z',
      'architecture_compatibility_status': 'ready',
      'origin': 'native_v2',
      'architecture': architecture,
    });
    final profileRef = resolved.architecture.profileRef;
    final selection = TwinArchitectureSelection.fromJson({
      ...architectureSelectionJson(),
      'profile_id': profileRef.id,
      'profile_version': profileRef.version,
      'profile_digest': profileRef.digest,
    });
    final activeProfileJson = architectureProfileSummaryJson(
      profileId: profileRef.id,
      profileDigest: profileRef.digest,
      withExtensionSlot: false,
    )..['profile_version'] = profileRef.version;
    final activeProfile = ArchitectureProfileSummary.fromJson(
      activeProfileJson,
    );
    final deploymentSpecification =
        jsonDecode(
              File(
                '../contracts/resolved-deployment-specification/v2/fixtures/valid/'
                'six-layer-aws-azure-eventing-small.json',
              ).readAsStringSync(),
            )
            as Map<String, dynamic>;
    final deploymentRun = OptimizerDeploymentRunData.fromDetailJson({
      'id': runId,
      'twin_id': 'twin-1',
      'status': 'succeeded',
      'deployment_compatibility_status': 'ready',
      'deployment_specification_digest': deploymentSpecification['digest'],
      'deployment_specification_version':
          deploymentSpecification['schema_version'],
      'resolved_deployment_specification': deploymentSpecification,
      'created_at': '2026-08-03T09:59:00Z',
      'selected_for_deployment_at': null,
    });
    when(
      () => api.getRunResolvedArchitecture(runId),
    ).thenAnswer((_) async => resolved);
    final bloc = WizardBloc(
      api: api,
      initialState: WizardState(
        status: WizardStatus.ready,
        twinId: 'twin-1',
        architectureCatalogPhase: ArchitectureCatalogPhase.ready,
        architectureProfiles: [activeProfile],
        architectureSelection: selection,
        deploymentRun: deploymentRun,
      ),
    );
    addTearDown(bloc.close);

    final completed = bloc.stream.firstWhere(
      (state) =>
          state.resolvedArchitecturePhase == ResolvedArchitecturePhase.ready,
    );
    bloc.add(WizardResolvedArchitectureLoadRequested(runId: runId));
    final state = await completed;

    expect(state.resolvedArchitecture, resolved);
    expect(
      state.resolvedArchitecture!.architecture.profileRef,
      selection.profileRef,
    );
    expect(state.requiredDeploymentProviders, {
      CloudProvider.aws,
      CloudProvider.azure,
    });
    expect(state.unconfiguredProviders, {'AWS', 'AZURE'});
    expect(state.warningMessage, isNull);
  });

  test('resolved architecture with a different Twin fails closed', () async {
    final architecture = Map<String, dynamic>.from(
      jsonDecode(
            File(
              '../contracts/architecture-profiles/v2/fixtures/valid/'
              'six-layer-aws-azure-eventing-small-resolved.json',
            ).readAsStringSync(),
          )
          as Map,
    );
    final runId = architecture['calculation_run_id'].toString();
    final resolved = ResolvedTwinArchitectureRead.fromJson({
      'twin_id': 'twin-other',
      'calculation_run_id': runId,
      'selected_for_deployment_at': '2026-08-03T10:00:00Z',
      'architecture_compatibility_status': 'ready',
      'origin': 'native_v2',
      'architecture': architecture,
    });
    final profileRef = resolved.architecture.profileRef;
    final selection = TwinArchitectureSelection.fromJson({
      ...architectureSelectionJson(),
      'profile_id': profileRef.id,
      'profile_version': profileRef.version,
      'profile_digest': profileRef.digest,
    });
    when(
      () => api.getRunResolvedArchitecture(runId),
    ).thenAnswer((_) async => resolved);
    final bloc = WizardBloc(
      api: api,
      initialState: WizardState(
        status: WizardStatus.ready,
        twinId: 'twin-1',
        architectureSelection: selection,
      ),
    );
    addTearDown(bloc.close);

    final completed = bloc.stream.firstWhere(
      (state) =>
          state.resolvedArchitecturePhase ==
          ResolvedArchitecturePhase.incompatible,
    );
    bloc.add(WizardResolvedArchitectureLoadRequested(runId: runId));
    final state = await completed;

    expect(state.resolvedArchitecture, isNull);
    expect(state.resolvedArchitectureError, contains('does not match'));
  });

  test(
    'confirmed invalidation clears persisted legacy profile artifacts',
    () async {
      final bloc = WizardBloc(
        api: api,
        initialState: const WizardState(
          status: WizardStatus.ready,
          step3Invalidated: true,
          payloadsJson: '{"sensor":[]}',
          payloadsValidated: true,
          processorContents: {'sensor': 'processor'},
          processorValidated: {'sensor': true},
          processorRequirements: {'sensor': 'requests==2'},
          eventFeedbackContent: 'feedback',
          eventFeedbackValidated: true,
          eventFeedbackRequirements: 'httpx==1',
          eventActionContents: {'notify': 'action'},
          eventActionValidated: {'notify': true},
          eventActionRequirements: {'notify': 'pydantic==2'},
          stateMachineContent: '{"workflow":true}',
          stateMachineValidated: true,
          hierarchyContent: '{"root":"legacy"}',
          hierarchyValidated: true,
          sceneConfigContent: '{"scene":"legacy"}',
          sceneConfigValidated: true,
          sceneGlbUploaded: true,
          userConfigContent: '{"admin_email":"researcher@example.com"}',
          userConfigValidated: true,
        ),
      );
      addTearDown(bloc.close);

      final completed = bloc.stream.firstWhere(
        (state) => !state.step3Invalidated,
      );
      bloc.add(const WizardProceedWithNewResults());
      final state = await completed;
      final update = state.deployerConfigData.toUpdateRequest().toJson();

      expect(state.payloadsJson, isNull);
      expect(state.processorContents, isEmpty);
      expect(state.processorRequirements, isEmpty);
      expect(state.eventFeedbackContent, isNull);
      expect(state.eventFeedbackRequirements, isNull);
      expect(state.eventActionContents, isEmpty);
      expect(state.eventActionRequirements, isEmpty);
      expect(state.stateMachineContent, isNull);
      expect(state.hierarchyContent, isNull);
      expect(state.hierarchyValidated, isFalse);
      expect(state.sceneConfigContent, isNull);
      expect(state.sceneConfigValidated, isFalse);
      expect(state.sceneGlbUploaded, isFalse);
      expect(state.userConfigContent, isNotNull);
      expect(state.userConfigValidated, isFalse);
      expect(update['event_feedback_content'], isNull);
      expect(update['state_machine_content'], isNull);
      expect(update['hierarchy_content'], isNull);
      expect(update['scene_config_content'], isNull);
    },
  );
}

TwinArchitectureSelection _historicalSelection() =>
    TwinArchitectureSelection.fromJson({
      ...architectureSelectionJson(),
      'profile_id': 'historical-profile',
      'profile_version': '1',
      'profile_digest': fixtureDigestB,
    });
