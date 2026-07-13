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

  test('returns immutable provider, check, and permission collections', () {
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
        'expected_permission_set_version': 'thesis-demo-v1',
        'supplied_permission_set_version': 'thesis-demo-v1',
        'permission_set_status': 'matched',
        'checked_at': '2026-07-14T09:00:00Z',
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
      },
    ],
    'checked_at': '2026-07-14T09:00:00Z',
    'issues': <Object>[],
  };
}

Matcher get throwsContractError => throwsA(
  isA<AppException>().having(
    (error) => error.code,
    'code',
    'DEPLOYMENT_CONTRACT_INVALID',
  ),
);
