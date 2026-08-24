import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/cloud_bootstrap/cloud_bootstrap.dart';
import 'package:twin2multicloud_flutter/models/cloud_bootstrap.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';
import 'package:twin2multicloud_flutter/widgets/cloud_connections/cloud_bootstrap_flow.dart';

void main() {
  testWidgets('shared flow completes simulated bounded AWS access at 640px', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(640, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final api = _FakeBootstrapApi();
    CloudBootstrapConnectionSummary? completed;
    final bloc = CloudBootstrapBloc(
      api: api,
      provider: CloudProvider.aws,
      entryPoint: CloudBootstrapEntryPoint.settings,
    )..add(CloudBootstrapOpened(initialTarget: api.guide.target));
    addTearDown(bloc.close);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BlocProvider.value(
            value: bloc,
            child: CloudBootstrapFlow(
              provider: CloudProvider.aws,
              entryPoint: CloudBootstrapEntryPoint.settings,
              onConnectionReady: (value) => completed = value,
              onClosed: () {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.text('Thesis simulation — no cloud resources are created'),
      findsOneWidget,
    );
    expect(find.text('Limit: Offline validation only.'), findsOneWidget);
    expect(
      find.text('Limit: Requires supervised live validation.'),
      findsOneWidget,
    );
    await tester.tap(find.text('I completed these steps'));
    await tester.pumpAndSettle();
    expect(find.text('Administrator/bootstrap authority'), findsOneWidget);

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Access key ID'),
      'AKIAEXAMPLE00000001',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Secret access key'),
      'submitted-bootstrap-secret',
    );
    await tester.ensureVisible(find.text('Create bounded access'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Create bounded access'));
    await tester.pumpAndSettle();

    expect(api.executeCalls, 1);
    expect(api.submittedProvider, 'aws');
    expect(bloc.state.phase, CloudBootstrapPhase.result);
    expect(
      bloc.state.session?.state,
      CloudBootstrapSessionState.ready,
      reason: bloc.state.safeError,
    );
    expect(bloc.state.completedConnection, isNotNull);
    expect(find.text('Bounded deployment access created'), findsOneWidget);
    expect(find.textContaining('submitted-bootstrap-secret'), findsNothing);
    await tester.tap(find.text('Use bounded access'));
    await tester.pump();

    expect(completed?.permissionSetVersion, 'thesis-demo-v2');
    expect(tester.takeException(), isNull);
  });

  testWidgets('supervised live flow remains blocked without reviewed adapter', (
    tester,
  ) async {
    final liveGuide = _fixture('aws-guide.json')
      ..['execution_mode'] = 'supervised_live'
      ..['known_blockers'] = [
        {
          'code': 'BOOTSTRAP_IDENTITY_CREATION_FAILED',
          'title': 'Supervised provider adapter is not configured',
          'message': 'This build has no reviewed provider adapter wired in.',
          'blocking': true,
          'action': 'Use the offline simulation.',
          'remediation_url': null,
        },
      ];
    final api = _FakeBootstrapApi(guideJson: liveGuide);
    final bloc = CloudBootstrapBloc(
      api: api,
      provider: CloudProvider.aws,
      entryPoint: CloudBootstrapEntryPoint.settings,
    )..add(CloudBootstrapOpened(initialTarget: api.guide.target));
    addTearDown(bloc.close);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BlocProvider.value(
            value: bloc,
            child: CloudBootstrapFlow(
              provider: CloudProvider.aws,
              entryPoint: CloudBootstrapEntryPoint.settings,
              onConnectionReady: (_) {},
              onClosed: () {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.text('Supervised setup — creates bounded cloud access'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'I completed these steps'),
          )
          .onPressed,
      isNull,
    );
    expect(api.executeCalls, 0);
    expect(tester.takeException(), isNull);
  });

  testWidgets('AWS target rejects an invalid STS expiry before guide I/O', (
    tester,
  ) async {
    final api = _FakeBootstrapApi();
    final bloc = CloudBootstrapBloc(
      api: api,
      provider: CloudProvider.aws,
      entryPoint: CloudBootstrapEntryPoint.settings,
    )..add(const CloudBootstrapOpened());
    addTearDown(bloc.close);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BlocProvider.value(
            value: bloc,
            child: CloudBootstrapFlow(
              provider: CloudProvider.aws,
              entryPoint: CloudBootstrapEntryPoint.settings,
              onConnectionReady: (_) {},
              onClosed: () {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'AWS account ID'),
      '123456789012',
    );
    await tester.enterText(
      find.widgetWithText(
        TextFormField,
        'STS session expiry (ISO 8601, optional)',
      ),
      '2020-01-01T00:00:00Z',
    );
    await tester.ensureVisible(find.text('Load provider guide'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Load provider guide'));
    await tester.pump();

    expect(find.text('Enter a future ISO-8601 expiry.'), findsOneWidget);
    expect(api.guideCalls, 0);
  });

  testWidgets(
    'GCP flow is existing-project-only and exposes the API baseline',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(640, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = _FakeBootstrapApi(provider: CloudProvider.gcp);
      final bloc = CloudBootstrapBloc(
        api: api,
        provider: CloudProvider.gcp,
        entryPoint: CloudBootstrapEntryPoint.settings,
      )..add(const CloudBootstrapOpened());
      addTearDown(bloc.close);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BlocProvider.value(
              value: bloc,
              child: CloudBootstrapFlow(
                provider: CloudProvider.gcp,
                entryPoint: CloudBootstrapEntryPoint.settings,
                onConnectionReady: (_) {},
                onClosed: () {},
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.textContaining('one existing billing-enabled project'),
        findsOneWidget,
      );
      expect(
        find.widgetWithText(TextFormField, 'Organization ID'),
        findsNothing,
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Project ID'),
        'twin2mc-test-project',
      );
      await tester.tap(find.text('Load provider guide'));
      await tester.pumpAndSettle();

      expect(find.text('Phase 8 API setup'), findsOneWidget);
      expect(
        find.text('19 reviewed APIs · enabled once and retained'),
        findsOneWidget,
      );
      await tester.ensureVisible(find.text('Phase 8 API setup'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Phase 8 API setup'));
      await tester.pumpAndSettle();
      expect(find.text('• serviceusage.googleapis.com'), findsOneWidget);
      expect(find.text('Open reviewed API baseline'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('credential re-entry shows the safe finding and empty fields', (
    tester,
  ) async {
    final reentryJson = _fixture('aws-ready-session.json')
      ..['revision'] = 3
      ..['state'] = 'credential_reentry_required'
      ..['disposal_status'] = 'released_after_failure'
      ..['finding'] = {
        'code': 'BOOTSTRAP_CREDENTIAL_INVALID',
        'severity': 'error',
        'title': 'Bootstrap could not complete',
        'message': 'The submitted authority did not match the target.',
        'blocking': true,
        'action': 'Review the target and explicitly re-enter the credential.',
      }
      ..remove('connection')
      ..['command_permissions'] = ['execute', 'cancel'];
    final reentry = CloudBootstrapSession.fromJson(reentryJson);
    final api = _FakeBootstrapApi(sessions: [reentry]);
    final bloc = CloudBootstrapBloc(
      api: api,
      provider: CloudProvider.aws,
      entryPoint: CloudBootstrapEntryPoint.settings,
    )..add(const CloudBootstrapOpened());
    addTearDown(bloc.close);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BlocProvider.value(
            value: bloc,
            child: CloudBootstrapFlow(
              provider: CloudProvider.aws,
              entryPoint: CloudBootstrapEntryPoint.settings,
              onConnectionReady: (_) {},
              onClosed: () {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Bootstrap could not complete'), findsOneWidget);
    expect(
      find.textContaining('The submitted authority did not match the target.'),
      findsOneWidget,
    );
    for (final field in tester.widgetList<TextFormField>(
      find.byType(TextFormField),
    )) {
      expect(field.controller?.text ?? '', isEmpty);
    }
  });

  for (final textScale in [1.5, 2.0]) {
    for (final width in [640.0, 799.0, 800.0, 1439.0, 1440.0]) {
      testWidgets('guide remains reachable at ${width.toInt()}px and '
          '${(textScale * 100).toInt()}%', (tester) async {
        await tester.binding.setSurfaceSize(Size(width, 900));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        final api = _FakeBootstrapApi();
        final bloc = CloudBootstrapBloc(
          api: api,
          provider: CloudProvider.aws,
          entryPoint: CloudBootstrapEntryPoint.settings,
        )..add(CloudBootstrapOpened(initialTarget: api.guide.target));
        addTearDown(bloc.close);
        await tester.pumpWidget(
          MaterialApp(
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(
                context,
              ).copyWith(textScaler: TextScaler.linear(textScale)),
              child: child!,
            ),
            home: Scaffold(
              body: BlocProvider.value(
                value: bloc,
                child: CloudBootstrapFlow(
                  provider: CloudProvider.aws,
                  entryPoint: CloudBootstrapEntryPoint.settings,
                  onConnectionReady: (_) {},
                  onClosed: () {},
                ),
              ),
            ),
          ),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.text('I completed these steps'), findsOneWidget);
        expect(find.byType(LinearProgressIndicator), findsOneWidget);
        expect(tester.takeException(), isNull, reason: 'width=$width');
      });
    }
  }
}

final class _FakeBootstrapApi implements CloudBootstrapApi {
  final List<CloudBootstrapSession> sessions;
  final CloudProvider provider;
  final Map<String, dynamic>? guideJson;

  _FakeBootstrapApi({
    this.sessions = const [],
    this.provider = CloudProvider.aws,
    this.guideJson,
  });

  late final CloudBootstrapGuide guide = CloudBootstrapGuide.fromJson(
    guideJson ??
        (provider == CloudProvider.gcp
            ? _gcpGuideFixture()
            : _fixture('aws-guide.json')),
  );
  late final CloudBootstrapSession ready = CloudBootstrapSession.fromJson(
    _fixture('aws-ready-session.json'),
  );
  late final CloudBootstrapSession draft = CloudBootstrapSession.fromJson(
    _draftFixture(),
  );
  int executeCalls = 0;
  int guideCalls = 0;
  String? submittedProvider;

  @override
  Future<CloudBootstrapSession> acknowledgeCloudBootstrapRevocation(
    String sessionId,
    int expectedRevision,
  ) async => ready;

  @override
  Future<CloudBootstrapSession> cancelCloudBootstrapSession(
    String sessionId,
    int expectedRevision,
  ) async => draft;

  @override
  Future<CloudBootstrapSession> createCloudBootstrapSession({
    required CloudBootstrapGuide guide,
    required CloudBootstrapEntryPoint entryPoint,
    required String displayName,
    String? twinId,
    required String idempotencyKey,
  }) async => draft;

  @override
  Future<CloudBootstrapSession> executeCloudBootstrapSession(
    String sessionId,
    CloudBootstrapExecuteRequest request,
  ) async {
    executeCalls += 1;
    final body = request.takeJson();
    submittedProvider = (body['credential'] as Map)['provider']?.toString();
    request.dispose();
    return ready;
  }

  @override
  Future<CloudBootstrapGuide> getCloudBootstrapGuide(
    CloudProvider provider,
    CloudBootstrapTarget target,
  ) async {
    guideCalls += 1;
    return guide;
  }

  @override
  Future<CloudBootstrapSession> getCloudBootstrapSession(
    String sessionId,
  ) async => ready;

  @override
  Future<List<CloudBootstrapSession>> listCloudBootstrapSessions({
    CloudProvider? provider,
    bool active = true,
  }) async => sessions;
}

Map<String, dynamic> _draftFixture() => _fixture('aws-ready-session.json')
  ..['revision'] = 1
  ..['state'] = 'draft'
  ..remove('credential_origin')
  ..remove('disposal_status')
  ..remove('credential_expires_at')
  ..remove('safe_credential_identifier')
  ..remove('finding')
  ..remove('connection')
  ..['command_permissions'] = ['execute', 'cancel'];

Map<String, dynamic> _gcpGuideFixture() {
  final baseline = Map<String, dynamic>.from(
    jsonDecode(
          File(
            'assets/contracts/cloud-bootstrap/v1/gcp-phase8-api-baseline.json',
          ).readAsStringSync(),
        )
        as Map,
  );
  final guide = _fixture('aws-guide.json');
  guide['provider'] = 'gcp';
  guide['target'] = {
    'provider': 'gcp',
    'mode': 'existing_project',
    'project_id': 'twin2mc-test-project',
    'region': 'europe-west1',
  };
  guide['bootstrap_authority_pack'] = {
    ...Map<String, dynamic>.from(guide['bootstrap_authority_pack'] as Map),
    'id': 'bootstrap.gcp.admin-v3',
    'version': '3',
  };
  guide['generated_deployment_pack'] = {
    ...Map<String, dynamic>.from(guide['generated_deployment_pack'] as Map),
    'id': 'gcp.thesis-demo-v2.service-account-v1',
  };
  guide['api_baseline'] = {
    'id': baseline['baseline_id'],
    'digest': 'sha256:${List.filled(64, '0').join()}',
    'services': baseline['services'],
    'retain_enabled': baseline['retain_enabled'],
    'mutation_summary': baseline['mutation_summary'],
    'limitations': baseline['limitations'],
    'artifact_url':
        'https://github.com/TVJunkie724/master-thesis/blob/master/contracts/cloud-bootstrap/v1/gcp-phase8-api-baseline.json',
  };
  return guide;
}

Map<String, dynamic> _fixture(String name) => Map<String, dynamic>.from(
  jsonDecode(
        File(
          'assets/contracts/cloud-bootstrap/v1/fixtures/valid/$name',
        ).readAsStringSync(),
      )
      as Map,
);
