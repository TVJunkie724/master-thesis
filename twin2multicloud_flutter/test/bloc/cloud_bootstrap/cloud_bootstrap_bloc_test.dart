import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/cloud_bootstrap/cloud_bootstrap.dart';
import 'package:twin2multicloud_flutter/models/cloud_bootstrap.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

final class _MockBootstrapApi extends Mock implements CloudBootstrapApi {}

void main() {
  late _MockBootstrapApi api;
  late CloudBootstrapGuide guide;
  late CloudBootstrapSession draft;
  late CloudBootstrapSession ready;

  setUpAll(() {
    registerFallbackValue(
      CloudBootstrapTarget.aws(
        accountId: '123456789012',
        region: 'eu-central-1',
      ),
    );
    registerFallbackValue(
      CloudBootstrapExecuteRequest(
        expectedRevision: 1,
        idempotencyKey: 'fallback-command-000001',
        credentialOrigin: CloudBootstrapCredentialOrigin.existingUserOwned,
        credential: const {
          'provider': 'aws',
          'access_key_id': 'AKIAFALLBACK000001',
          'secret_access_key': 'fallback-secret-value',
        },
      ),
    );
  });

  setUp(() {
    api = _MockBootstrapApi();
    guide = CloudBootstrapGuide.fromJson(_fixture('aws-guide.json'));
    ready = CloudBootstrapSession.fromJson(_fixture('aws-ready-session.json'));
    final draftJson = _fixture('aws-ready-session.json')
      ..['revision'] = 1
      ..['state'] = 'draft'
      ..remove('credential_origin')
      ..remove('disposal_status')
      ..remove('credential_expires_at')
      ..remove('safe_credential_identifier')
      ..remove('finding')
      ..remove('connection')
      ..['command_permissions'] = ['execute', 'cancel'];
    draft = CloudBootstrapSession.fromJson(draftJson);
  });

  test('guide to execute to ready retains only safe state', () async {
    when(
      () => api.listCloudBootstrapSessions(provider: CloudProvider.aws),
    ).thenAnswer((_) async => const []);
    when(
      () => api.getCloudBootstrapGuide(CloudProvider.aws, any()),
    ).thenAnswer((_) async => guide);
    when(
      () => api.createCloudBootstrapSession(
        guide: guide,
        entryPoint: CloudBootstrapEntryPoint.settings,
        displayName: any(named: 'displayName'),
        twinId: null,
        idempotencyKey: any(named: 'idempotencyKey'),
      ),
    ).thenAnswer((_) async => draft);
    when(
      () => api.executeCloudBootstrapSession(draft.id, any()),
    ).thenAnswer((_) async => ready);
    final bloc = CloudBootstrapBloc(
      api: api,
      provider: CloudProvider.aws,
      entryPoint: CloudBootstrapEntryPoint.settings,
    );

    bloc.add(CloudBootstrapOpened(initialTarget: guide.target));
    await bloc.stream.firstWhere(
      (state) => state.phase == CloudBootstrapPhase.guide,
    );
    bloc.add(const CloudBootstrapSessionStarted('Thesis AWS'));
    await bloc.stream.firstWhere(
      (state) => state.phase == CloudBootstrapPhase.authority,
    );
    const secret = 'submitted-bootstrap-secret';
    bloc.add(
      CloudBootstrapExecuteSubmitted(
        CloudBootstrapExecuteRequest(
          expectedRevision: draft.revision,
          idempotencyKey: 'execute-command-00000001',
          credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
          credential: const {
            'provider': 'aws',
            'access_key_id': 'AKIAEXAMPLE00000001',
            'secret_access_key': secret,
          },
        ),
      ),
    );
    await bloc.stream.firstWhere((state) => state.completedConnection != null);

    expect(bloc.state.phase, CloudBootstrapPhase.result);
    expect(bloc.state.toString(), isNot(contains(secret)));
    verify(() => api.executeCloudBootstrapSession(draft.id, any())).called(1);
    await bloc.close();
  });

  test(
    'lost execute response requires GET recheck and never resubmits',
    () async {
      when(
        () => api.listCloudBootstrapSessions(provider: CloudProvider.aws),
      ).thenAnswer((_) async => [draft]);
      when(
        () => api.getCloudBootstrapGuide(CloudProvider.aws, any()),
      ).thenAnswer((_) async => guide);
      when(
        () => api.executeCloudBootstrapSession(draft.id, any()),
      ).thenThrow(StateError('transport lost'));
      when(
        () => api.getCloudBootstrapSession(draft.id),
      ).thenAnswer((_) async => ready);
      final bloc = CloudBootstrapBloc(
        api: api,
        provider: CloudProvider.aws,
        entryPoint: CloudBootstrapEntryPoint.settings,
      )..add(const CloudBootstrapOpened());
      await bloc.stream.firstWhere(
        (state) => state.phase == CloudBootstrapPhase.authority,
      );

      bloc.add(
        CloudBootstrapExecuteSubmitted(
          CloudBootstrapExecuteRequest(
            expectedRevision: draft.revision,
            idempotencyKey: 'execute-command-00000002',
            credentialOrigin:
                CloudBootstrapCredentialOrigin.dedicatedDisposable,
            credential: const {
              'provider': 'aws',
              'access_key_id': 'AKIAEXAMPLE00000002',
              'secret_access_key': 'lost-response-secret',
            },
          ),
        ),
      );
      await bloc.stream.firstWhere((state) => state.requiresRecheck);
      bloc.add(const CloudBootstrapSessionRechecked());
      await bloc.stream.firstWhere(
        (state) => state.completedConnection != null,
      );

      verify(() => api.executeCloudBootstrapSession(draft.id, any())).called(1);
      verify(() => api.getCloudBootstrapSession(draft.id)).called(1);
      await bloc.close();
    },
  );

  test('resumed remote command can be rechecked or cancelled', () async {
    final running = CloudBootstrapSession.fromJson(
      _sessionFixture('bootstrap_running', ['recheck', 'cancel']),
    );
    final cancelledJson = _sessionFixture('cancelled', ['start_new'])
      ..['revision'] = 3;
    final cancelled = CloudBootstrapSession.fromJson(cancelledJson);
    when(
      () => api.listCloudBootstrapSessions(provider: CloudProvider.aws),
    ).thenAnswer((_) async => [running]);
    when(
      () => api.getCloudBootstrapGuide(CloudProvider.aws, any()),
    ).thenAnswer((_) async => guide);
    when(
      () => api.cancelCloudBootstrapSession(running.id, running.revision),
    ).thenAnswer((_) async => cancelled);
    final bloc = CloudBootstrapBloc(
      api: api,
      provider: CloudProvider.aws,
      entryPoint: CloudBootstrapEntryPoint.settings,
    )..add(const CloudBootstrapOpened());

    await bloc.stream.firstWhere(
      (state) =>
          state.session?.state == CloudBootstrapSessionState.bootstrapRunning,
    );
    expect(bloc.state.commandInProgress, isFalse);
    expect(bloc.state.requiresRecheck, isTrue);
    bloc.add(const CloudBootstrapCancelled());
    await bloc.stream.firstWhere(
      (state) => state.session?.state == CloudBootstrapSessionState.cancelled,
    );
    bloc.add(const CloudBootstrapStartNewRequested());
    await bloc.stream.firstWhere(
      (state) =>
          state.phase == CloudBootstrapPhase.guide && state.session == null,
    );

    verify(
      () => api.cancelCloudBootstrapSession(running.id, running.revision),
    ).called(1);
    await bloc.close();
  });

  test('manual provider cleanup requires explicit acknowledgement', () async {
    final manualJson = _fixture('aws-ready-session.json')
      ..['revision'] = 3
      ..['state'] = 'manual_revocation_required'
      ..['disposal_status'] = 'manual_revocation_required'
      ..['command_permissions'] = ['acknowledge_manual_revocation'];
    final manual = CloudBootstrapSession.fromJson(manualJson);
    when(
      () => api.listCloudBootstrapSessions(provider: CloudProvider.aws),
    ).thenAnswer((_) async => [manual]);
    when(
      () => api.getCloudBootstrapGuide(CloudProvider.aws, any()),
    ).thenAnswer((_) async => guide);
    when(
      () => api.acknowledgeCloudBootstrapRevocation(manual.id, manual.revision),
    ).thenAnswer((_) async => ready);
    final bloc = CloudBootstrapBloc(
      api: api,
      provider: CloudProvider.aws,
      entryPoint: CloudBootstrapEntryPoint.settings,
    )..add(const CloudBootstrapOpened());

    await bloc.stream.firstWhere(
      (state) =>
          state.session?.state ==
          CloudBootstrapSessionState.manualRevocationRequired,
    );
    expect(bloc.state.completedConnection, isNull);
    bloc.add(const CloudBootstrapManualRevocationAcknowledged());
    await bloc.stream.firstWhere((state) => state.completedConnection != null);

    verify(
      () => api.acknowledgeCloudBootstrapRevocation(manual.id, manual.revision),
    ).called(1);
    await bloc.close();
  });

  test(
    'a server-owned scope can resume across Settings and Twin entry points',
    () async {
      final crossEntryJson = _fixture('aws-ready-session.json')
        ..['state'] = 'draft'
        ..['revision'] = 1
        ..['entry_point'] = 'twin_prepare'
        ..['twin_id'] = 'twin-123'
        ..remove('credential_origin')
        ..remove('disposal_status')
        ..remove('credential_expires_at')
        ..remove('safe_credential_identifier')
        ..remove('finding')
        ..remove('connection')
        ..['command_permissions'] = ['execute', 'cancel'];
      final crossEntry = CloudBootstrapSession.fromJson(crossEntryJson);
      when(
        () => api.listCloudBootstrapSessions(provider: CloudProvider.aws),
      ).thenAnswer((_) async => const []);
      when(
        () => api.getCloudBootstrapGuide(CloudProvider.aws, any()),
      ).thenAnswer((_) async => guide);
      when(
        () => api.createCloudBootstrapSession(
          guide: guide,
          entryPoint: CloudBootstrapEntryPoint.settings,
          displayName: any(named: 'displayName'),
          twinId: null,
          idempotencyKey: any(named: 'idempotencyKey'),
        ),
      ).thenAnswer((_) async => crossEntry);
      final bloc = CloudBootstrapBloc(
        api: api,
        provider: CloudProvider.aws,
        entryPoint: CloudBootstrapEntryPoint.settings,
      )..add(CloudBootstrapOpened(initialTarget: guide.target));

      await bloc.stream.firstWhere(
        (state) => state.phase == CloudBootstrapPhase.guide,
      );
      bloc.add(const CloudBootstrapSessionStarted('Thesis AWS'));
      await bloc.stream.firstWhere(
        (state) => state.phase == CloudBootstrapPhase.authority,
      );

      expect(
        bloc.state.session?.entryPoint,
        CloudBootstrapEntryPoint.twinPrepare,
      );
      expect(bloc.state.session?.twinId, 'twin-123');
      await bloc.close();
    },
  );

  test(
    'opening resumes one unambiguous session from another entry point',
    () async {
      final crossEntryJson = _fixture('aws-ready-session.json')
        ..['state'] = 'draft'
        ..['revision'] = 1
        ..['entry_point'] = 'twin_prepare'
        ..['twin_id'] = 'twin-123'
        ..remove('credential_origin')
        ..remove('disposal_status')
        ..remove('credential_expires_at')
        ..remove('safe_credential_identifier')
        ..remove('finding')
        ..remove('connection')
        ..['command_permissions'] = ['execute', 'cancel'];
      final crossEntry = CloudBootstrapSession.fromJson(crossEntryJson);
      when(
        () => api.listCloudBootstrapSessions(provider: CloudProvider.aws),
      ).thenAnswer((_) async => [crossEntry]);
      when(
        () => api.getCloudBootstrapGuide(CloudProvider.aws, crossEntry.target),
      ).thenAnswer((_) async => guide);
      final bloc = CloudBootstrapBloc(
        api: api,
        provider: CloudProvider.aws,
        entryPoint: CloudBootstrapEntryPoint.settings,
      )..add(const CloudBootstrapOpened());

      await bloc.stream.firstWhere(
        (state) => state.phase == CloudBootstrapPhase.authority,
      );

      expect(bloc.state.session, crossEntry);
      expect(bloc.state.target, crossEntry.target);
      await bloc.close();
    },
  );

  test(
    'initial target survives an opening error and can retry the guide',
    () async {
      when(
        () => api.listCloudBootstrapSessions(provider: CloudProvider.aws),
      ).thenThrow(StateError('session lookup failed'));
      when(
        () => api.getCloudBootstrapGuide(CloudProvider.aws, guide.target),
      ).thenAnswer((_) async => guide);
      final bloc = CloudBootstrapBloc(
        api: api,
        provider: CloudProvider.aws,
        entryPoint: CloudBootstrapEntryPoint.settings,
      )..add(CloudBootstrapOpened(initialTarget: guide.target));

      await bloc.stream.firstWhere((state) => state.safeError != null);
      expect(bloc.state.phase, CloudBootstrapPhase.loading);
      expect(bloc.state.target, guide.target);
      bloc.add(CloudBootstrapGuideRequested(guide.target));
      await bloc.stream.firstWhere(
        (state) => state.phase == CloudBootstrapPhase.guide,
      );

      expect(bloc.state.safeError, isNull);
      await bloc.close();
    },
  );

  test('wrong-provider execute request is disposed before API I/O', () async {
    when(
      () => api.listCloudBootstrapSessions(provider: CloudProvider.aws),
    ).thenAnswer((_) async => [draft]);
    when(
      () => api.getCloudBootstrapGuide(CloudProvider.aws, draft.target),
    ).thenAnswer((_) async => guide);
    final bloc = CloudBootstrapBloc(
      api: api,
      provider: CloudProvider.aws,
      entryPoint: CloudBootstrapEntryPoint.settings,
    )..add(const CloudBootstrapOpened());
    await bloc.stream.firstWhere(
      (state) => state.phase == CloudBootstrapPhase.authority,
    );
    final request = CloudBootstrapExecuteRequest(
      expectedRevision: draft.revision,
      idempotencyKey: 'execute-wrong-provider-0001',
      credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
      credential: const {
        'provider': 'gcp',
        'type': 'service_account',
        'project_id': 'thesis-project',
        'private_key_id': 'key-id',
        'private_key': 'submitted-private-key',
        'client_email': 'bootstrap@example.test',
        'client_id': '123456789',
      },
    );

    bloc.add(CloudBootstrapExecuteSubmitted(request));
    await Future<void>.delayed(Duration.zero);

    verifyNever(() => api.executeCloudBootstrapSession(any(), any()));
    expect(request.takeJson, throwsStateError);
    await bloc.close();
  });
}

Map<String, dynamic> _sessionFixture(String state, List<String> commands) =>
    _fixture('aws-ready-session.json')
      ..['revision'] = 2
      ..['state'] = state
      ..remove('credential_origin')
      ..remove('disposal_status')
      ..remove('credential_expires_at')
      ..remove('safe_credential_identifier')
      ..remove('finding')
      ..remove('connection')
      ..['command_permissions'] = commands;

Map<String, dynamic> _fixture(String name) => Map<String, dynamic>.from(
  jsonDecode(
        File(
          'assets/contracts/cloud-bootstrap/v1/fixtures/valid/$name',
        ).readAsStringSync(),
      )
      as Map,
);
