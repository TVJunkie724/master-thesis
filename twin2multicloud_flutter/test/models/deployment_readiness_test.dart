import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_readiness.dart';

void main() {
  test('parses cached and preflight readiness contracts', () {
    final cached = DeploymentReadinessSnapshot.fromCachedJson(
      _document(DeploymentReadinessSnapshot.cachedSchemaVersion),
    );
    final preflight = DeploymentReadinessSnapshot.fromPreflightJson(
      _document(DeploymentReadinessSnapshot.preflightSchemaVersion),
    );

    expect(cached.source, DeploymentReadinessSource.cached);
    expect(preflight.source, DeploymentReadinessSource.preflight);
    expect(cached.ready, isTrue);
    expect(cached.requiredProviders, [CloudProvider.aws]);
    expect(
      cached.providers.single.status,
      ProviderDeploymentReadinessStatus.ready,
    );
    expect(cached.providers.single.checks, hasLength(2));
    expect(cached.providers.single.requirements, hasLength(1));
    expect(cached.preparationPlan?.needsReview, isFalse);
    expect(cached.checkedAt, DateTime.parse('2026-07-14T09:00:00Z'));
  });

  test('rejects wrong schema and inconsistent aggregate readiness', () {
    final wrongSchema = _document('deployment-readiness.v2');
    final inconsistent = _document(
      DeploymentReadinessSnapshot.cachedSchemaVersion,
    )..['ready'] = false;

    expect(
      () => DeploymentReadinessSnapshot.fromCachedJson(wrongSchema),
      throwsContractError,
    );
    expect(
      () => DeploymentReadinessSnapshot.fromCachedJson(inconsistent),
      throwsContractError,
    );
    expect(
      () => DeploymentReadinessSnapshot.fromCachedJson(
        _document(DeploymentReadinessSnapshot.cachedSchemaVersion),
        expectedTwinId: 'another-twin',
      ),
      throwsContractError,
    );
  });

  test(
    'rejects provider ordering, unknown statuses, and oversized evidence',
    () {
      final wrongProvider = _document(
        DeploymentReadinessSnapshot.cachedSchemaVersion,
      );
      (wrongProvider['providers'] as List).single['provider'] = 'gcp';

      final unknownStatus = _document(
        DeploymentReadinessSnapshot.cachedSchemaVersion,
      );
      (unknownStatus['providers'] as List).single['status'] = 'maybe';

      final inconsistentChecks = _document(
        DeploymentReadinessSnapshot.cachedSchemaVersion,
      );
      ((inconsistentChecks['providers'] as List).single['checks'] as List)
              .first['status'] =
          'failed';

      final oversized = _document(
        DeploymentReadinessSnapshot.cachedSchemaVersion,
      );
      (oversized['providers'] as List).single['summary'] = List.filled(
        2001,
        'x',
      ).join();

      for (final document in [
        wrongProvider,
        unknownStatus,
        inconsistentChecks,
        oversized,
      ]) {
        expect(
          () => DeploymentReadinessSnapshot.fromCachedJson(document),
          throwsContractError,
        );
      }
    },
  );

  test('returns immutable provider and check collections', () {
    final snapshot = DeploymentReadinessSnapshot.fromCachedJson(
      _document(DeploymentReadinessSnapshot.cachedSchemaVersion),
    );

    expect(
      () => snapshot.requiredProviders.add(CloudProvider.gcp),
      throwsUnsupportedError,
    );
    expect(
      () => snapshot.providers.single.checks.add(
        snapshot.providers.single.checks.first,
      ),
      throwsUnsupportedError,
    );
    expect(
      () => snapshot.providers.single.checks.first.permissions.add('iam:test'),
      throwsUnsupportedError,
    );
  });

  test('accepts passed access checks with a preparable graph requirement', () {
    final document = _document(
      DeploymentReadinessSnapshot.preflightSchemaVersion,
    );
    document['ready'] = false;
    document['summary'] = 'Provider preparation is required.';
    document['required_providers'] = ['gcp'];
    final provider = (document['providers'] as List).single as Map;
    provider['provider'] = 'gcp';
    provider['ready'] = false;
    provider['status'] = 'review_required';
    provider['summary'] = 'One project API can be enabled.';
    final requirement = Map<String, dynamic>.from(
      (provider['requirements'] as List).single as Map,
    );
    provider['requirements'] = [requirement];
    requirement['provider'] = 'gcp';
    requirement['requirement_id'] = 'gcp:serviceusage.googleapis.com';
    requirement['capability_id'] = 'serviceusage.googleapis.com';
    requirement['preparation_mode'] = 'confirmed_account';
    requirement['status'] = 'preparable';
    requirement['message'] = 'The project API can be enabled.';
    requirement['action'] = 'Confirm provider preparation.';
    final plan = document['preparation_plan'] as Map;
    plan['actions'] = [
      {
        'action_id': 'gcp:enable:serviceusage.googleapis.com',
        'provider': 'gcp',
        'action_type': 'enable_project_api',
        'capability_id': 'serviceusage.googleapis.com',
        'scope': 'project',
        'requirement_ids': ['gcp:serviceusage.googleapis.com'],
        'reason': 'Required by the resolved graph.',
        'persistent_after_destroy': true,
        'destructive': false,
      },
    ];

    final snapshot = DeploymentReadinessSnapshot.fromPreflightJson(document);

    expect(snapshot.ready, isFalse);
    expect(
      snapshot.providers.single.requirements.single.status,
      DeploymentRequirementReadinessStatus.preparable,
    );
    expect(snapshot.preparationPlan?.needsReview, isTrue);
  });

  test('binds preparation responses to the confirmed evidence digests', () {
    final request = DeploymentPreparationRequest(
      planDigest: _planDigest,
      requirementsDigest: _requirementsDigest,
      manualRequirementIds: const ['manual-b', 'manual-a', 'manual-a'],
    );
    expect(request.manualRequirementIds, ['manual-a', 'manual-b']);
    final response = {
      'schema_version': DeploymentPreparationResponse.schemaVersion,
      'twin_id': 'twin-1',
      'plan_digest': _planDigest,
      'requirements_digest': _requirementsDigest,
      'status': 'ready',
      'completed_actions': <Object>[],
      'failed_actions': <Object>[],
      'remaining_action_ids': <String>[],
      'acknowledged_manual_requirement_ids': ['manual-a', 'manual-b'],
      'pending_manual_requirement_ids': <String>[],
      'retry_safe': true,
      'readiness': _document(
        DeploymentReadinessSnapshot.preflightSchemaVersion,
      ),
    };

    expect(
      DeploymentPreparationResponse.fromJson(
        response,
        expectedTwinId: 'twin-1',
        expectedRequest: request,
      ).readiness.ready,
      isTrue,
    );
    expect(
      () => DeploymentPreparationResponse.fromJson(
        {...response, 'plan_digest': _graphDigest},
        expectedTwinId: 'twin-1',
        expectedRequest: request,
      ),
      throwsContractError,
    );
  });
}

Map<String, dynamic> _document(String schemaVersion) {
  return {
    'schema_version': schemaVersion,
    'twin_id': 'twin-1',
    'ready': true,
    'summary': 'All required providers are ready for deployment.',
    'required_providers': ['aws'],
    'providers': [
      {
        'provider': 'aws',
        'connection_id': 'connection-1',
        'connection_display_name': 'AWS deployment',
        'ready': true,
        'status': 'ready',
        'summary': 'Cloud connection preflight passed',
        'checked_at': '2026-07-14T09:00:00Z',
        'graph_digest': _graphDigest,
        'requirements_digest': _requirementsDigest,
        'checks': [
          {
            'component': 'optimizer',
            'status': 'passed',
            'code': 'OK',
            'message': 'Optimizer access passed.',
            'action': 'No action required.',
            'permissions': ['pricing:GetProducts'],
          },
          {
            'component': 'deployer',
            'status': 'passed',
            'code': 'OK',
            'message': 'Deployer access passed.',
            'action': 'No action required.',
            'permissions': <String>[],
          },
        ],
        'requirements': [_readyRequirement],
      },
    ],
    'checked_at': '2026-07-14T09:00:00Z',
    'graph_digest': _graphDigest,
    'requirements_digest': _requirementsDigest,
    'preparation_plan': {
      'schema_version': DeploymentPreparationPlan.schemaVersion,
      'graph_digest': _graphDigest,
      'requirements_digest': _requirementsDigest,
      'plan_digest': _planDigest,
      'actions': <Object>[],
      'manual_requirements': <Object>[],
    },
    'issues': <Object>[],
  };
}

const _graphDigest =
    'sha256:1111111111111111111111111111111111111111111111111111111111111111';
const _requirementsDigest =
    'sha256:2222222222222222222222222222222222222222222222222222222222222222';
const _planDigest =
    'sha256:3333333333333333333333333333333333333333333333333333333333333333';

const _readyRequirement = {
  'requirement_id': 'aws:provider_scope',
  'requirement_type': 'provider_scope',
  'provider': 'aws',
  'capability_id': 'aws:provider_scope',
  'preparation_mode': 'none',
  'mandatory': true,
  'status': 'ready',
  'message': 'Provider scope is ready.',
  'action': 'No action required.',
  'source_node_ids': <String>[],
  'source_edge_ids': <String>[],
};

Matcher get throwsContractError => throwsA(
  isA<AppException>().having(
    (error) => error.code,
    'code',
    'DEPLOYMENT_CONTRACT_INVALID',
  ),
);
