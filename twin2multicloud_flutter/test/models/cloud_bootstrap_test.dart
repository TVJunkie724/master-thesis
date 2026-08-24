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
    expect(guide.apiBaseline, isNull);
    expect(guide.target.summary, '123456789012 / eu-central-1');
    expect(guide.credentialFields.map((item) => item.id), [
      'access_key_id',
      'secret_access_key',
    ]);
    expect(session.state, CloudBootstrapSessionState.ready);
    expect(session.connection?.permissionSetVersion, 'thesis-demo-v2');
    expect(session.commandPermissions, isEmpty);
  });

  test('parses the supervised live execution-mode contract', () {
    final liveGuide = fixture('aws-guide.json')
      ..['execution_mode'] = 'supervised_live';

    expect(
      CloudBootstrapGuide.fromJson(liveGuide).executionMode,
      CloudBootstrapExecutionMode.supervisedLive,
    );
    expect(
      CloudBootstrapExecutionMode.supervisedLive.label,
      'Supervised setup — creates bounded cloud access',
    );
  });

  test('parses a strict GCP Phase 8 API baseline', () {
    final guideJson = _gcpGuideFixture();
    final guide = CloudBootstrapGuide.fromJson(guideJson);

    expect(guide.bootstrapAuthorityPack.id, 'bootstrap.gcp.admin-v3');
    expect(guide.apiBaseline?.id, 'gcp.phase8-api-baseline.v1');
    expect(guide.apiBaseline?.services, hasLength(19));
    expect(guide.apiBaseline?.retainEnabled, isTrue);

    final unsorted = _gcpGuideFixture();
    final baseline = unsorted['api_baseline'] as Map<String, dynamic>;
    baseline['services'] = List<String>.from(baseline['services'] as List)
      ..setAll(0, [
        'cloudbilling.googleapis.com',
        'artifactregistry.googleapis.com',
      ]);
    expect(() => CloudBootstrapGuide.fromJson(unsorted), throwsFormatException);

    final emptyLimitations = _gcpGuideFixture();
    (emptyLimitations['api_baseline'] as Map<String, dynamic>)['limitations'] =
        <String>[];
    expect(
      () => CloudBootstrapGuide.fromJson(emptyLimitations),
      throwsFormatException,
    );

    final invalidService = _gcpGuideFixture();
    final invalidBaseline =
        invalidService['api_baseline'] as Map<String, dynamic>;
    invalidBaseline['services'] = [
      ...List<String>.from(invalidBaseline['services'] as List).skip(1),
      'not-a-google-api.example.com',
    ]..sort();
    expect(
      () => CloudBootstrapGuide.fromJson(invalidService),
      throwsFormatException,
    );

    final organizationTarget = _gcpGuideFixture();
    organizationTarget['target'] = {
      'provider': 'gcp',
      'mode': 'organization',
      'bootstrap_project_id': 'thesis-admin-project',
      'organization_id': '123456789',
      'billing_account_id': 'ABCDEF-123456-ABCDEF',
      'region': 'europe-west1',
    };
    expect(
      () => CloudBootstrapGuide.fromJson(organizationTarget),
      throwsFormatException,
    );
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

Map<String, dynamic> _gcpGuideFixture() {
  final baseline = Map<String, dynamic>.from(
    jsonDecode(
          File(
            'assets/contracts/cloud-bootstrap/v1/gcp-phase8-api-baseline.json',
          ).readAsStringSync(),
        )
        as Map,
  );
  final guide = fixtureForGcp();
  guide['api_baseline'] = {
    'id': baseline['baseline_id'],
    'digest': 'sha256:${List.filled(64, 'a').join()}',
    'services': baseline['services'],
    'retain_enabled': baseline['retain_enabled'],
    'mutation_summary': baseline['mutation_summary'],
    'limitations': baseline['limitations'],
    'artifact_url': 'https://example.com/gcp/api-baseline',
  };
  return guide;
}

Map<String, dynamic> fixtureForGcp() {
  final guide = Map<String, dynamic>.from(
    jsonDecode(
          File(
            'assets/contracts/cloud-bootstrap/v1/fixtures/valid/aws-guide.json',
          ).readAsStringSync(),
        )
        as Map,
  );
  guide['provider'] = 'gcp';
  guide['target'] = {
    'provider': 'gcp',
    'mode': 'existing_project',
    'project_id': 'thesis-project',
    'region': 'europe-west1',
  };
  guide['bootstrap_authority_pack'] = {
    'id': 'bootstrap.gcp.admin-v3',
    'version': '3',
    'digest': 'sha256:${List.filled(64, 'b').join()}',
    'scope_summary': 'One existing project.',
    'limitations': ['Existing-project PoC path only.'],
    'artifact_url': 'https://example.com/gcp/authority',
  };
  guide['generated_deployment_pack'] = {
    'id': 'gcp.thesis-demo-v2.service-account-v1',
    'version': 'thesis-demo-v2',
    'digest': 'sha256:${List.filled(64, 'c').join()}',
    'scope_summary': 'One generated deployment service account.',
    'limitations': ['Offline validation only.'],
    'artifact_url': 'https://example.com/gcp/deployment',
  };
  guide['credential_fields'] = [
    {
      'id': 'service_account_json',
      'label': 'Service-account JSON',
      'input_type': 'json',
      'required': true,
      'redaction_rule': 'private_key_document',
    },
  ];
  return guide;
}
