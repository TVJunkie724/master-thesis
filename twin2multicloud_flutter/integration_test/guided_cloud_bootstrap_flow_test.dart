import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/bloc/cloud_bootstrap/cloud_bootstrap.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/cloud_bootstrap.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/widgets/cloud_connections/cloud_bootstrap_flow.dart';

const _submittedSecretSentinel =
    'phase8-submitted-bootstrap-secret-never-persist';
final _runtime = AppRuntimeConfig.fromEnvironment();
final _apiUri =
    _runtime.managementApiBaseUri ??
    (throw StateError('Integration runtime requires a Management API origin.'));
final _authToken =
    _runtime.initialAuthToken ??
    (throw StateError('Integration tests require the development profile.'));
final _api = ApiService(baseUri: _apiUri, initialAuthToken: _authToken);
final _raw = Dio(
  BaseOptions(
    baseUrl: _apiUri.toString(),
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $_authToken',
    },
  ),
);

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('drives the real AWS bootstrap API through the shared UI flow', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(640, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final run = DateTime.now().microsecondsSinceEpoch;
    final target = _target(CloudProvider.aws, run);
    CloudBootstrapConnectionSummary? completed;
    final bloc = CloudBootstrapBloc(
      api: _api,
      provider: CloudProvider.aws,
      entryPoint: CloudBootstrapEntryPoint.settings,
    )..add(CloudBootstrapOpened(initialTarget: target));
    addTearDown(bloc.close);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BlocProvider.value(
            value: bloc,
            child: CloudBootstrapFlow(
              provider: CloudProvider.aws,
              entryPoint: CloudBootstrapEntryPoint.settings,
              onConnectionReady: (connection) => completed = connection,
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
    await tester.tap(find.text('I completed these steps'));
    await tester.pumpAndSettle();
    expect(
      bloc.state.phase,
      CloudBootstrapPhase.authority,
      reason: bloc.state.safeError,
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Access key ID'),
      'AKIAIOSFODNN7EXAMPLE',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Secret access key'),
      _submittedSecretSentinel,
    );
    await tester.ensureVisible(find.text('Create bounded access'));
    await tester.tap(find.text('Create bounded access'));
    await tester.pumpAndSettle();

    expect(find.text('Bounded deployment access created'), findsOneWidget);
    expect(find.textContaining(_submittedSecretSentinel), findsNothing);
    await tester.tap(find.text('Use bounded access'));
    await tester.pump();
    expect(completed?.provider, CloudProvider.aws);
    expect(completed?.permissionSetVersion, 'thesis-demo-v2');
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'executes all provider paths offline and persists only bounded access',
    (tester) async {
      final run = DateTime.now().microsecondsSinceEpoch;
      final readySessions = <CloudBootstrapSession>[];

      for (final provider in CloudProvider.values) {
        final target = _target(provider, run);
        final guide = await _api.getCloudBootstrapGuide(provider, target);
        expect(
          guide.executionMode,
          CloudBootstrapExecutionMode.deterministicFake,
        );
        expect(guide.provider, provider);
        expect(guide.target, target);
        expect(
          guide.bootstrapAuthorityPack.id,
          'bootstrap.${provider.apiValue}.admin-v2',
        );
        expect(guide.bootstrapAuthorityPack.version, '2');
        expect(guide.generatedDeploymentPack.version, 'thesis-demo-v2');
        if (provider == CloudProvider.aws) {
          expect(
            guide.generatedDeploymentPack.id,
            'aws.thesis-demo-v2.iam-user-v1',
          );
        }
        expect(guide.knownBlockers, isEmpty);

        final createKey = _key('create', provider, run);
        final session = await _api.createCloudBootstrapSession(
          guide: guide,
          entryPoint: CloudBootstrapEntryPoint.settings,
          displayName: '${provider.label} guided integration $run',
          idempotencyKey: createKey,
        );
        expect(session.state, CloudBootstrapSessionState.draft);

        final executeKey = _key('execute', provider, run);
        var ready = await _api.executeCloudBootstrapSession(
          session.id,
          CloudBootstrapExecuteRequest(
            expectedRevision: session.revision,
            idempotencyKey: executeKey,
            credentialOrigin:
                CloudBootstrapCredentialOrigin.dedicatedDisposable,
            credential: _credential(provider, target),
          ),
        );
        if (provider == CloudProvider.azure) {
          expect(
            ready.state,
            CloudBootstrapSessionState.manualRevocationRequired,
          );
          expect(ready.disposalStatus, 'manual_revocation_required');
          ready = await _api.acknowledgeCloudBootstrapRevocation(
            ready.id,
            ready.revision,
          );
        }
        expect(ready.state, CloudBootstrapSessionState.ready);
        expect(ready.disposalStatus, 'revoked');
        expect(ready.connection?.provider, provider);
        expect(ready.connection?.permissionSetVersion, 'thesis-demo-v2');
        expect(ready.connection?.validationStatus, 'valid');
        expect(ready.commandPermissions, isEmpty);

        if (provider == CloudProvider.aws) {
          final replay = await _api.executeCloudBootstrapSession(
            session.id,
            CloudBootstrapExecuteRequest(
              expectedRevision: session.revision,
              idempotencyKey: executeKey,
              credentialOrigin:
                  CloudBootstrapCredentialOrigin.dedicatedDisposable,
              credential: {
                ..._credential(provider, target),
                'access_key_id': 'AKIAREPLAY0000000000',
              },
            ),
          );
          expect(replay.revision, ready.revision);
          expect(replay.connection?.id, ready.connection?.id);
        }

        readySessions.add(ready);
      }

      final connections = await _api.listCloudConnections();
      for (final session in readySessions) {
        final persisted = connections.singleWhere(
          (item) => item.id == session.connection!.id,
        );
        expect(persisted.provider, session.provider);
        expect(persisted.purpose, CloudConnectionPurpose.deployment);
        expect(persisted.validationStatus, 'valid');
        expect(_containsSecretKey(persisted.payloadSummary), isFalse);
        expect(
          jsonEncode({
            'scope': persisted.cloudScope,
            'summary': persisted.payloadSummary,
          }),
          isNot(contains(_submittedSecretSentinel)),
        );
      }
    },
  );

  testWidgets(
    'requires explicit re-entry and never echoes an invalid submitted secret',
    (tester) async {
      final run = DateTime.now().microsecondsSinceEpoch;
      final target = _target(CloudProvider.aws, run);
      final guide = await _api.getCloudBootstrapGuide(
        CloudProvider.aws,
        target,
      );
      final session = await _api.createCloudBootstrapSession(
        guide: guide,
        entryPoint: CloudBootstrapEntryPoint.settings,
        displayName: 'AWS re-entry integration $run',
        idempotencyKey: _key('create-reentry', CloudProvider.aws, run),
      );

      final rejected = await _api.executeCloudBootstrapSession(
        session.id,
        CloudBootstrapExecuteRequest(
          expectedRevision: session.revision,
          idempotencyKey: _key('reject', CloudProvider.aws, run),
          credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
          credential: {
            'provider': 'aws',
            'access_key_id': 'ZZZZIOSFODNN7EXAMPLE',
            'secret_access_key': _submittedSecretSentinel,
          },
        ),
      );
      expect(
        rejected.state,
        CloudBootstrapSessionState.credentialReentryRequired,
      );
      expect(rejected.finding?.code, 'BOOTSTRAP_CREDENTIAL_INVALID');
      expect(rejected.connection, isNull);
      expect(rejected.commandPermissions, {'execute', 'cancel'});
      expect(rejected.toString(), isNot(contains(_submittedSecretSentinel)));

      final ready = await _api.executeCloudBootstrapSession(
        session.id,
        CloudBootstrapExecuteRequest(
          expectedRevision: rejected.revision,
          idempotencyKey: _key('retry', CloudProvider.aws, run),
          credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
          credential: _credential(CloudProvider.aws, target),
        ),
      );
      expect(ready.state, CloudBootstrapSessionState.ready);

      final rawSecret = '$_submittedSecretSentinel-malformed';
      try {
        await _raw.post<Map<String, dynamic>>(
          '/cloud-bootstrap/sessions/${ready.id}/execute',
          data: {
            'expected_revision': ready.revision,
            'idempotency_key': _key('malformed', CloudProvider.aws, run),
            'credential_origin': 'dedicated_disposable',
            'credential': {
              'provider': 'aws',
              'access_key_id': 'short',
              'secret_access_key': rawSecret,
              'unexpected_secret': rawSecret,
            },
          },
        );
        fail('Malformed bootstrap credentials must be rejected.');
      } on DioException catch (error) {
        expect(error.response?.statusCode, 422);
        expect(jsonEncode(error.response?.data), isNot(contains(rawSecret)));
        expect(
          jsonEncode(error.response?.data),
          isNot(contains('unexpected_secret')),
        );
      }
    },
  );

  testWidgets(
    'resumes a server session and keeps cleanup and cancellation explicit',
    (tester) async {
      final run = DateTime.now().microsecondsSinceEpoch;
      final target = _target(CloudProvider.gcp, run);
      final guide = await _api.getCloudBootstrapGuide(
        CloudProvider.gcp,
        target,
      );
      final settingsSession = await _api.createCloudBootstrapSession(
        guide: guide,
        entryPoint: CloudBootstrapEntryPoint.settings,
        displayName: 'GCP shared scope $run',
        idempotencyKey: _key('create-settings', CloudProvider.gcp, run),
      );
      final resumed = await _api.createCloudBootstrapSession(
        guide: guide,
        entryPoint: CloudBootstrapEntryPoint.settings,
        displayName: 'GCP resumed scope $run',
        idempotencyKey: _key('create-resume', CloudProvider.gcp, run),
      );
      expect(resumed.id, settingsSession.id);

      final cancelled = await _api.cancelCloudBootstrapSession(
        settingsSession.id,
        settingsSession.revision,
      );
      expect(cancelled.state, CloudBootstrapSessionState.cancelled);
      expect(cancelled.commandPermissions, {'start_new'});
    },
  );
}

CloudBootstrapTarget _target(CloudProvider provider, int run) {
  return switch (provider) {
    CloudProvider.aws => CloudBootstrapTarget.aws(
      accountId: (run % 1000000000000).toString().padLeft(12, '0'),
      region: 'eu-central-1',
    ),
    CloudProvider.azure => CloudBootstrapTarget.azure(
      tenantId: 'tenant-$run',
      subscriptionId: 'subscription-$run',
      region: 'westeurope',
      bootstrapCredentialKeyId: 'manual-key-$run',
    ),
    CloudProvider.gcp => CloudBootstrapTarget.gcpExistingProject(
      projectId: 'phase8-${run % 100000000}',
      region: 'europe-west1',
    ),
  };
}

Map<String, dynamic> _credential(
  CloudProvider provider,
  CloudBootstrapTarget target,
) {
  return switch (provider) {
    CloudProvider.aws => {
      'provider': 'aws',
      'access_key_id': 'AKIAIOSFODNN7EXAMPLE',
      'secret_access_key': _submittedSecretSentinel,
    },
    CloudProvider.azure => {
      'provider': 'azure',
      'tenant_id': target.values['tenant_id'],
      'subscription_id': target.values['subscription_id'],
      'client_id': 'client-${target.values['tenant_id']}',
      'client_secret': _submittedSecretSentinel,
    },
    CloudProvider.gcp => {
      'provider': 'gcp',
      'type': 'service_account',
      'project_id': target.values['project_id'],
      'private_key_id': 'bootstrap-key-phase8',
      'private_key': _submittedSecretSentinel,
      'client_email':
          'bootstrap@${target.values['project_id']}.iam.gserviceaccount.com',
      'client_id': '12345678901234567890',
      'token_uri': 'https://oauth2.googleapis.com/token',
    },
  };
}

String _key(String operation, CloudProvider provider, int run) {
  return '$operation-${provider.apiValue}-$run';
}

bool _containsSecretKey(Object? value) {
  const forbidden = {
    'access_key_id',
    'secret_access_key',
    'client_secret',
    'private_key',
    'service_account_json',
    'session_token',
  };
  if (value is Map) {
    return value.entries.any(
      (entry) =>
          forbidden.contains(entry.key.toString().toLowerCase()) ||
          _containsSecretKey(entry.value),
    );
  }
  if (value is Iterable) return value.any(_containsSecretKey);
  return false;
}
