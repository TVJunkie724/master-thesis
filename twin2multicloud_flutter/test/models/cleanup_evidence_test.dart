import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cleanup_evidence.dart';

void main() {
  group('CleanupEvidence', () {
    test(
      'parses complete multi-provider proof with retained prerequisites',
      () {
        final evidence = CleanupEvidence.fromJson(
          completeCleanupEvidence(providers: const ['aws', 'azure', 'gcp'])
            ..['retained_shared_prerequisites'] = [
              {
                'provider': 'azure',
                'requirement_type': 'resource_provider',
                'capability_id': 'Microsoft.DigitalTwins',
                'scope': 'subscription',
                'reason': 'persistent_account_prerequisite',
              },
              {
                'provider': 'gcp',
                'requirement_type': 'api',
                'capability_id': 'run.googleapis.com',
                'scope': 'project',
                'reason': 'persistent_account_prerequisite',
              },
            ],
        );

        expect(evidence.status, CleanupEvidenceStatus.complete);
        expect(evidence.providers, hasLength(3));
        expect(evidence.retainedSharedPrerequisites, hasLength(2));
        expect(evidence.residualFailures, isEmpty);
      },
    );

    test('parses incomplete residual evidence without claiming success', () {
      final value = completeCleanupEvidence()
        ..['status'] = 'incomplete'
        ..['providers'] = [
          {
            ...(completeCleanupEvidence()['providers'] as List).single as Map,
            'post_destroy_inventory': 'residual',
            'residual_resource_count': 1,
          },
        ]
        ..['residual_failures'] = [
          {
            'scope': 'provider_inventory',
            'provider': 'aws',
            'reason': 'resources_remain',
          },
        ];

      final evidence = CleanupEvidence.fromJson(value);

      expect(evidence.status, CleanupEvidenceStatus.incomplete);
      expect(evidence.providers.single.residualResourceCount, 1);
      expect(evidence.residualFailures.single.reason, 'resources_remain');
    });

    test('rejects duplicate providers and unknown fields', () {
      final duplicate = completeCleanupEvidence()
        ..['providers'] = [
          ...(completeCleanupEvidence()['providers'] as List),
          ...(completeCleanupEvidence()['providers'] as List),
        ];
      expect(() => CleanupEvidence.fromJson(duplicate), throwsFormatException);

      final unknown = completeCleanupEvidence()..['secret_token'] = 'hidden';
      expect(() => CleanupEvidence.fromJson(unknown), throwsFormatException);
    });

    test('rejects inconsistent complete and provider inventory evidence', () {
      final residualComplete = completeCleanupEvidence()
        ..['residual_failures'] = [
          {
            'scope': 'terraform_state',
            'provider': null,
            'reason': 'resources_remain',
          },
        ];
      expect(
        () => CleanupEvidence.fromJson(residualComplete),
        throwsFormatException,
      );

      final invalidInventory = completeCleanupEvidence();
      ((invalidInventory['providers'] as List).single
              as Map)['residual_resource_count'] =
          2;
      expect(
        () => CleanupEvidence.fromJson(invalidInventory),
        throwsFormatException,
      );
    });
  });
}

Map<String, dynamic> completeCleanupEvidence({
  List<String> providers = const ['aws'],
}) => {
  'schema_version': 'cleanup-evidence.v1',
  'status': 'complete',
  'terraform': {
    'destroy_status': 'completed',
    'observed_before_resource_count': 9,
    'post_destroy_inventory': 'empty',
    'residual_resource_count': 0,
  },
  'providers': [
    for (final provider in providers)
      {
        'provider': provider,
        'cleanup_status': 'completed',
        'discovered_during_cleanup_count': 4,
        'discovered_resource_kinds': ['Cloud Functions'],
        'post_destroy_inventory': 'empty',
        'residual_resource_count': 0,
      },
  ],
  'retained_shared_prerequisites': <Object>[],
  'residual_failures': <Object>[],
};
