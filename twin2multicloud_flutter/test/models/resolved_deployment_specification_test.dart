import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';

void main() {
  group('ResolvedDeploymentSpecificationData', () {
    test('parses and verifies the canonical Six-layer fixture', () {
      final json = _fixture();

      final specification = ResolvedDeploymentSpecificationData.fromJson(json);

      expect(specification, isA<ResolvedDeploymentSpecificationV2>());
      final v2 = specification as ResolvedDeploymentSpecificationV2;
      expect(v2.architectureProfileRef.id, 'six-layer-eventing');
      expect(v2.architectureProfileRef.version, '1');
      expect(v2.logicalComponentCount, 8);
      expect(v2.componentSelections, hasLength(25));
      expect(v2.providers, {CloudProvider.aws, CloudProvider.azure});
      expect(v2.readiness.evaluationOnly, isTrue);
      expect(v2.readiness.blockingGateIds, isNotEmpty);
      expect(
        v2.componentSelections.any(
          (item) => item.logicalComponentId == 'component.eventing',
        ),
        isTrue,
      );
      expect(
        v2.digest,
        ResolvedDeploymentSpecificationData.calculateDigest(json),
      );
    });

    test('rejects digest tampering and unknown fields', () {
      final tampered = _fixture();
      (tampered['component_selections'] as List).first['region'] =
          'invalid-region';
      expect(
        () => ResolvedDeploymentSpecificationData.fromJson(tampered),
        throwsFormatException,
      );

      final unknown = _fixture()
        ..['client_secret'] = 'must-not-render'
        ..['digest'] = '';
      unknown['digest'] = ResolvedDeploymentSpecificationData.calculateDigest(
        unknown,
      );
      expect(
        () => ResolvedDeploymentSpecificationData.fromJson(unknown),
        throwsFormatException,
      );
    });

    test('keeps a future version inspectable but unsupported', () {
      final json = _fixture()
        ..['schema_version'] = 'resolved-deployment-specification.v3';

      final specification = ResolvedDeploymentSpecificationData.fromJson(json);

      expect(specification, isA<UnsupportedResolvedDeploymentSpecification>());
      expect(specification.isSupported, isFalse);
      expect(specification.calculationRunId, isNotEmpty);
    });

    test('enforces frozen PoC dimensions and required selections', () {
      final changedDimension = _fixture();
      final fixed =
          changedDimension['fixed_dimensions'] as Map<String, dynamic>;
      fixed['reader_timeout_seconds'] = 30;
      changedDimension['digest'] =
          ResolvedDeploymentSpecificationData.calculateDigest(changedDimension);
      expect(
        () => ResolvedDeploymentSpecificationData.fromJson(changedDimension),
        throwsFormatException,
      );

      final optionalSelection = _fixture();
      final selections = optionalSelection['component_selections'] as List;
      (selections.first as Map<String, dynamic>)['required'] = false;
      optionalSelection['digest'] =
          ResolvedDeploymentSpecificationData.calculateDigest(
            optionalSelection,
          );
      expect(
        () => ResolvedDeploymentSpecificationData.fromJson(optionalSelection),
        throwsFormatException,
      );
    });

    test('rejects unresolved deployment-dimension bindings', () {
      final unresolved = _fixture();
      final bindings = unresolved['bindings'] as List;
      (bindings.first as Map<String, dynamic>)['source_ref'] =
          'dimension.missing';
      unresolved['digest'] =
          ResolvedDeploymentSpecificationData.calculateDigest(unresolved);

      expect(
        () => ResolvedDeploymentSpecificationData.fromJson(unresolved),
        throwsFormatException,
      );
    });
  });

  group('OptimizerDeploymentRunData', () {
    test('keeps offline Six-layer evidence reviewable but not selectable', () {
      final run = OptimizerDeploymentRunData.fromDetailJson(
        _detail(_fixture()),
      );
      final review = ResolvedDeploymentReview.fromRun(run);

      expect(review.state, ResolvedDeploymentReviewState.evaluationOnly);
      expect(review.ready, isFalse);
      expect(review.supportedV2Specification, isNotNull);
      expect(review.supportedV2Specification!.providers, hasLength(2));
    });

    test('requires run metadata to match its specification', () {
      final specification = _fixture();
      final detail = _detail(specification)..['id'] = 'different-run';

      expect(
        () => OptimizerDeploymentRunData.fromDetailJson(detail),
        throwsFormatException,
      );
    });

    test('rejects non-UTC run timestamps', () {
      expect(
        () => OptimizerDeploymentRunData.fromDetailJson({
          ..._detail(_fixture()),
          'created_at': '2026-07-17T08:00:00',
        }),
        throwsFormatException,
      );
    });
  });
}

Map<String, dynamic> _fixture() {
  final file = File(
    '../contracts/resolved-deployment-specification/v2/fixtures/valid/'
    'six-layer-aws-azure-eventing-small.json',
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
