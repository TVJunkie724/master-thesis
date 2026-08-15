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

  for (final width in [640.0, 799.0, 800.0, 1439.0, 1440.0]) {
    testWidgets('guide remains reachable at ${width.toInt()}px and 200%', (
      tester,
    ) async {
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
            ).copyWith(textScaler: const TextScaler.linear(2)),
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

final class _FakeBootstrapApi implements CloudBootstrapApi {
  final List<CloudBootstrapSession> sessions;

  _FakeBootstrapApi({this.sessions = const []});

  late final CloudBootstrapGuide guide = CloudBootstrapGuide.fromJson(
    _fixture('aws-guide.json'),
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

Map<String, dynamic> _fixture(String name) => Map<String, dynamic>.from(
  jsonDecode(
        File(
          'assets/contracts/cloud-bootstrap/v1/fixtures/valid/$name',
        ).readAsStringSync(),
      )
      as Map,
);
