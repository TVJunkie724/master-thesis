import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_bootstrap.dart';

void main() {
  Map<String, dynamic> fixture(String name) => Map<String, dynamic>.from(
    jsonDecode(
          File(
            'assets/contracts/cloud-bootstrap/v1/fixtures/valid/$name',
          ).readAsStringSync(),
        )
        as Map,
  );

  test('parses the frozen guide and ready-session contracts', () {
    final guide = CloudBootstrapGuide.fromJson(fixture('aws-guide.json'));
    final session = CloudBootstrapSession.fromJson(
      fixture('aws-ready-session.json'),
    );

    expect(guide.executionMode, CloudBootstrapExecutionMode.deterministicFake);
    expect(guide.target.summary, '123456789012 / eu-central-1');
    expect(guide.credentialFields.map((item) => item.id), [
      'access_key_id',
      'secret_access_key',
    ]);
    expect(session.state, CloudBootstrapSessionState.ready);
    expect(session.connection?.permissionSetVersion, 'thesis-demo-v2');
    expect(session.commandPermissions, isEmpty);
  });

  test(
    'fails closed for versions, states, links, and response secret keys',
    () {
      final unknownState = fixture('aws-ready-session.json')
        ..['state'] = 'surprise';
      final secretResponse = fixture('aws-ready-session.json')
        ..['client_secret'] = 'must-not-render';
      final insecureGuide = fixture('aws-guide.json');
      (insecureGuide['preparation_steps'] as List).first['official_url'] =
          'http://insecure.example.test';

      expect(
        () => CloudBootstrapSession.fromJson(unknownState),
        throwsFormatException,
      );
      expect(
        () => CloudBootstrapSession.fromJson(secretResponse),
        throwsFormatException,
      );
      expect(
        () => CloudBootstrapGuide.fromJson(insecureGuide),
        throwsFormatException,
      );
    },
  );

  test('rejects inconsistent state actions, provider, and permission pack', () {
    final wrongActions = fixture('aws-ready-session.json')
      ..['command_permissions'] = ['execute'];
    final wrongProvider = fixture('aws-ready-session.json');
    (wrongProvider['connection'] as Map)['provider'] = 'gcp';
    final wrongPack = fixture('aws-ready-session.json');
    (wrongPack['connection'] as Map)['permission_set_version'] =
        'thesis-demo-v1';

    expect(
      () => CloudBootstrapSession.fromJson(wrongActions),
      throwsFormatException,
    );
    expect(
      () => CloudBootstrapSession.fromJson(wrongProvider),
      throwsFormatException,
    );
    expect(
      () => CloudBootstrapSession.fromJson(wrongPack),
      throwsFormatException,
    );
  });

  test('rejects impossible connection and lifecycle combinations', () {
    final connectionInDraft = fixture('aws-ready-session.json')
      ..['state'] = 'draft'
      ..['command_permissions'] = ['execute', 'cancel']
      ..remove('credential_origin')
      ..remove('disposal_status')
      ..remove('credential_expires_at')
      ..remove('safe_credential_identifier');
    final readyWithoutDisposal = fixture('aws-ready-session.json')
      ..remove('disposal_status');
    final invalidRevision = fixture('aws-ready-session.json')..['revision'] = 0;
    final reversedTimestamps = fixture('aws-ready-session.json')
      ..['updated_at'] = '2026-01-01T00:00:00Z';

    expect(
      () => CloudBootstrapSession.fromJson(connectionInDraft),
      throwsFormatException,
    );
    expect(
      () => CloudBootstrapSession.fromJson(readyWithoutDisposal),
      throwsFormatException,
    );
    expect(
      () => CloudBootstrapSession.fromJson(invalidRevision),
      throwsFormatException,
    );
    expect(
      () => CloudBootstrapSession.fromJson(reversedTimestamps),
      throwsFormatException,
    );
  });

  test('validates GCP target identifiers before a guide request', () {
    expect(
      () => CloudBootstrapTarget.gcpExistingProject(
        projectId: 'INVALID_PROJECT',
        region: 'europe-west1',
      ),
      throwsArgumentError,
    );
    expect(
      () => CloudBootstrapTarget.fromJson(const {
        'provider': 'gcp',
        'mode': 'organization',
        'bootstrap_project_id': 'valid-project',
        'organization_id': 'not-digits',
        'billing_account_id': 'ABCDEF-123456-ABCDEF',
        'region': 'europe-west1',
      }),
      throwsFormatException,
    );
  });

  test(
    'execute request is one-use and diagnostics never reveal the secret',
    () {
      const secret = 'submitted-bootstrap-secret';
      final request = CloudBootstrapExecuteRequest(
        expectedRevision: 1,
        idempotencyKey: 'execute-command-00000001',
        credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
        credential: const {
          'provider': 'aws',
          'access_key_id': 'AKIAEXAMPLE00000001',
          'secret_access_key': secret,
        },
      );

      expect(request.toString(), isNot(contains(secret)));
      expect(
        request.takeJson()['credential'],
        containsPair('secret_access_key', secret),
      );
      expect(request.takeJson, throwsStateError);
    },
  );

  test('execute request rejects invalid command and provider shapes', () {
    expect(
      () => CloudBootstrapExecuteRequest(
        expectedRevision: 0,
        idempotencyKey: 'too-short',
        credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
        credential: const {
          'provider': 'aws',
          'access_key_id': 'AKIAEXAMPLE00000001',
          'secret_access_key': 'submitted-bootstrap-secret',
        },
      ),
      throwsArgumentError,
    );
    expect(
      () => CloudBootstrapExecuteRequest(
        expectedRevision: 1,
        idempotencyKey: 'execute-command-00000003',
        credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
        credential: const {
          'provider': 'gcp',
          'type': 'service_account',
          'project_id': 'thesis-project',
          'private_key_id': 'key-id',
          'private_key': 'submitted-private-key',
          'client_email': 'bootstrap@example.test',
          'client_id': '123456789',
          'unexpected_secret': 'must-not-pass',
        },
      ),
      throwsArgumentError,
    );
  });
}
