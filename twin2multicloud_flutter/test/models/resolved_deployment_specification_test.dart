import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';

void main() {
  group('ResolvedDeploymentSpecificationData', () {
    for (final fixtureName in const [
      'all-aws.json',
      'all-azure.json',
      'mixed-providers.json',
    ]) {
      test('parses and verifies backend fixture $fixtureName', () {
        final json = _fixture(fixtureName);

        final specification = ResolvedDeploymentSpecificationData.fromJson(
          json,
        );

        expect(specification, isA<ResolvedDeploymentSpecificationV1>());
        final v1 = specification as ResolvedDeploymentSpecificationV1;
        expect(
          v1.digest,
          ResolvedDeploymentSpecificationData.calculateDigest(json),
        );
        expect(v1.architectureComponents.map((item) => item.slot).toSet(), {
          ResolvedDeploymentSlot.l1Ingestion,
          ResolvedDeploymentSlot.l2Processing,
          ResolvedDeploymentSlot.l3HotStorage,
          ResolvedDeploymentSlot.l3CoolStorage,
          ResolvedDeploymentSlot.l3ArchiveStorage,
          ResolvedDeploymentSlot.l4TwinState,
          ResolvedDeploymentSlot.l5Visualization,
        });
        expect(v1.optimizationContext.catalogReferences, hasLength(3));
      });
    }

    test('rejects a tampered known-version specification', () {
      final json = _fixture('all-aws.json');
      final components = json['components']! as List<dynamic>;
      final firstComponent = components.first as Map<String, dynamic>;
      firstComponent['service_id'] = 'aws.tampered';

      expect(
        () => ResolvedDeploymentSpecificationData.fromJson(json),
        throwsFormatException,
      );
    });

    test('keeps a future version inspectable but unsupported', () {
      final json = _fixture('all-aws.json')
        ..['schema_version'] = 'resolved-deployment-specification.v2';

      final specification = ResolvedDeploymentSpecificationData.fromJson(json);

      expect(specification, isA<UnsupportedResolvedDeploymentSpecification>());
      expect(specification.isSupported, isFalse);
      expect(specification.calculationRunId, isNotEmpty);
    });
  });

  group('OptimizerDeploymentRunData', () {
    test('requires ready run metadata to match the specification', () {
      final specification = _fixture('mixed-providers.json');
      final detail = _detail(specification);

      final run = OptimizerDeploymentRunData.fromDetailJson(detail);

      expect(run.compatibility, DeploymentCompatibility.ready);
      expect(run.specification, isA<ResolvedDeploymentSpecificationV1>());
      expect(run.selectedForDeploymentAt, isNull);
    });

    test('parses a legacy run without modern optimizer result fields', () {
      final run = OptimizerDeploymentRunData.fromDetailJson({
        'id': 'legacy-run',
        'twin_id': 'twin-1',
        'status': 'succeeded',
        'deployment_compatibility_status': 'legacy_not_deployable',
        'deployment_specification_digest': null,
        'deployment_specification_version': null,
        'resolved_deployment_specification': null,
        'created_at': '2026-07-17T08:00:00Z',
        'selected_for_deployment_at': null,
      });

      expect(run.specification, isNull);
      expect(
        ResolvedDeploymentReview.fromRun(run).state,
        ResolvedDeploymentReviewState.legacy,
      );
    });

    test('rejects run and specification identity mismatch', () {
      final specification = _fixture('all-azure.json');
      final detail = _detail(specification)..['id'] = 'different-run';

      expect(
        () => OptimizerDeploymentRunData.fromDetailJson(detail),
        throwsFormatException,
      );
    });

    test('rejects non-UTC and causally invalid run timestamps', () {
      final specification = _fixture('all-azure.json');

      expect(
        () => OptimizerDeploymentRunData.fromDetailJson({
          ..._detail(specification),
          'created_at': '2026-07-17T08:00:00',
        }),
        throwsFormatException,
      );
      expect(
        () => OptimizerDeploymentRunData.fromDetailJson({
          ..._detail(specification),
          'selected_for_deployment_at': '2026-07-17T07:59:59Z',
        }),
        throwsFormatException,
      );
    });

    test('selection response must preserve immutable run identity', () {
      final specification = _fixture('all-aws.json');
      final selectedAt = '2026-07-17T09:00:00Z';
      final runSummary = _detail(specification)
        ..remove('resolved_deployment_specification')
        ..['selected_for_deployment_at'] = selectedAt;

      final selection = OptimizerRunSelectionData.fromJson({
        'run': runSummary,
        'selected_for_deployment_at': selectedAt,
        'resolved_deployment_specification': specification,
      });

      expect(selection.run.selectedForDeploymentAt, DateTime.parse(selectedAt));
      expect(
        ResolvedDeploymentReview.fromRun(selection.run).state,
        ResolvedDeploymentReviewState.ready,
      );
    });

    test('rejects a selection that changes immutable run identity', () {
      final specification = _fixture('all-aws.json');
      final run = OptimizerDeploymentRunData.fromDetailJson(
        _detail(specification),
      );
      final changedSpecification = _fixture('all-azure.json');
      final selectedAt = DateTime.parse('2026-07-17T09:00:00Z');
      final changedRun = OptimizerDeploymentRunData.fromDetailJson({
        ..._detail(changedSpecification),
        'selected_for_deployment_at': selectedAt.toIso8601String(),
      });

      expect(
        () => run.applySelection(
          OptimizerRunSelectionData(
            run: changedRun,
            selectedForDeploymentAt: selectedAt,
          ),
        ),
        throwsFormatException,
      );
    });
  });
}

Map<String, dynamic> _fixture(String filename) {
  final file = File(
    '../twin2multicloud_backend/src/contracts/generated/'
    'resolved-deployment-specification/v1/fixtures/valid/$filename',
  );
  return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
}

Map<String, dynamic> _detail(Map<String, dynamic> specification) => {
  'id': specification['calculation_run_id'],
  'twin_id': 'twin-1',
  'status': 'succeeded',
  'deployment_compatibility_status': 'ready',
  'deployment_specification_digest': specification['digest'],
  'deployment_specification_version': specification['schema_version'],
  'resolved_deployment_specification': specification,
  'created_at': '2026-07-17T08:00:00Z',
  'selected_for_deployment_at': null,
};
