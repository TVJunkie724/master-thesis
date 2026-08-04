import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';

import '../fixtures/architecture_profile_fixtures.dart';

void main() {
  group('architecture profile contracts', () {
    test('parses a strict active summary and detail', () {
      final summary = ArchitectureProfileSummary.fromJson(
        architectureProfileSummaryJson(),
      );
      final detail = ArchitectureProfileDetail.fromJson(
        architectureProfileDetailJson(),
      );

      expect(summary.profileId, 'fixture-profile');
      expect(summary.workloadFieldIds, {'workload.telemetry-update-count'});
      expect(summary.availableProviders.single.provider.apiValue, 'aws');
      expect(
        detail.logicalComponents.single.componentId,
        'component.ingestion',
      );
      expect(detail.visualization.nodes.single.label, 'Ingestion');
    });

    test('rejects inactive, additional, duplicate, and unresolved data', () {
      expect(
        () => ArchitectureProfileSummary.fromJson({
          ...architectureProfileSummaryJson(),
          'lifecycle_status': 'deprecated',
        }),
        throwsFormatException,
      );
      expect(
        () => ArchitectureProfileSummary.fromJson({
          ...architectureProfileSummaryJson(),
          'terraform_workspace': '/tmp/forbidden',
        }),
        throwsFormatException,
      );
      final duplicate = architectureProfileDetailJson();
      duplicate['logical_components'] = [
        ...(duplicate['logical_components'] as List),
        (duplicate['logical_components'] as List).single,
      ];
      expect(
        () => ArchitectureProfileDetail.fromJson(duplicate),
        throwsFormatException,
      );
      final unresolved = architectureProfileDetailJson();
      unresolved['visualization'] = {
        'nodes': [
          {
            'id': 'unknown.component',
            'label': 'Unknown',
            'responsibility_id': 'responsibility.ingestion',
          },
        ],
        'edges': <Map<String, dynamic>>[],
      };
      expect(
        () => ArchitectureProfileDetail.fromJson(unresolved),
        throwsFormatException,
      );
    });

    test('round-trips exact revision-bound change commands', () {
      final preview = ArchitectureProfileChangePreview.fromJson(
        architecturePreviewJson(),
      );
      final request = ArchitectureProfileSelectRequest.fromPreview(preview);
      final result = ArchitectureProfileSelectionResult.fromJson(
        architectureSelectionResultJson(),
      );

      expect(request.toJson(), {
        'profile_id': 'fixture-profile',
        'profile_version': '2',
        'expected_revision': 1,
        'invalidation_digest': fixtureDigestB,
      });
      expect(result.revision, 2);
      expect(result.clearedWorkloadFieldIds, ['legacy.field']);
    });
  });
}
