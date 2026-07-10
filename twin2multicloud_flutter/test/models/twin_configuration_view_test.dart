import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/models/twin_configuration_view.dart';

void main() {
  group('TwinConfigurationView', () {
    test('maps optimizer result, workload params and pricing snapshots', () {
      final view = TwinConfigurationView.fromState(_state());

      expect(view.pathSegments, ['L1_AWS', 'L2_Azure', 'L4_GCP']);
      expect(view.optimization.hasResult, isTrue);
      expect(view.optimization.totalCost, 42.5);
      expect(view.optimization.numberOfDevices, '12');
      expect(view.optimization.messagesPerHour, '12.0');
      expect(view.optimization.retention, '6 months');
      expect(view.optimization.calculatedAt, '2026-06-21T10:00:00Z');
      expect(view.pricingSnapshots, hasLength(3));
      expect(view.pricingSnapshots.first.filename, 'aws_pricing.json');
      expect(
        view.pricingSnapshots.first.artifactContent,
        contains('"messages"'),
      );
    });

    test('maps provider-specific deployment artifact filenames', () {
      final view = TwinConfigurationView.fromState(
        _state(cheapestPath: const {'l2': 'gcp', 'l4': 'azure'}),
      );

      expect(
        view.configurationArtifacts.map((artifact) => artifact.filename),
        containsAll([
          'google_cloud_workflow.yaml',
          'azure_hierarchy.json',
          '3DScenesConfiguration.json',
          'config_user.json',
        ]),
      );
      expect(view.functionGroups.single.title, 'Processors');
      expect(
        view.functionGroups.single.artifacts.single.filename,
        'processor-a/main.py',
      );
    });

    test('omits empty optional artifacts defensively', () {
      final view = TwinConfigurationView.fromState(
        _state(
          optimizerResult: null,
          optimizerParams: null,
          deployerConfig: const {},
          pricingAws: null,
          pricingAwsUpdatedAt: null,
        ),
      );

      expect(view.pathSegments, isEmpty);
      expect(view.optimization.hasResult, isFalse);
      expect(view.optimization.messagesPerHour, isNull);
      expect(view.configurationArtifacts, isEmpty);
      expect(view.functionGroups, isEmpty);
      expect(view.pricingSnapshots.first.hasData, isFalse);
    });
  });
}

TwinOverviewLoaded _state({
  Map<String, dynamic>? optimizerResult = const {
    'totalCost': 42.5,
    'cheapestPath': ['L1_AWS', 'L2_Azure', 'L4_GCP'],
  },
  Map<String, dynamic>? optimizerParams = const {
    'numberOfDevices': 12,
    'deviceSendingIntervalInMinutes': 5,
    'hotStorageDurationInMonths': 1,
    'coolStorageDurationInMonths': 2,
    'archiveStorageDurationInMonths': 3,
  },
  Map<String, dynamic>? cheapestPath = const {'l2': 'aws', 'l4': 'aws'},
  Map<String, dynamic>? pricingAws = const {'messages': 0.1},
  String? pricingAwsUpdatedAt = '2026-06-21T10:00:00Z',
  Map<String, dynamic>? deployerConfig = const {
    'config_events_json': '{"events":[]}',
    'state_machine_content': 'workflow',
    'hierarchy_content': '{"hierarchy":[]}',
    'scene_config_content': '{"scenes":[]}',
    'user_config_content': '{"users":[]}',
    'processor_contents': {'processor-a': 'def handler(): pass'},
  },
}) {
  return TwinOverviewLoaded(
    twinId: 'twin-1',
    projectName: 'Demo Twin',
    cloudResourceName: 'cloud-demo',
    twinState: 'configured',
    canDeploy: true,
    canDestroy: false,
    canEdit: true,
    canDelete: true,
    optimizerResult: optimizerResult,
    optimizerParams: optimizerParams,
    calculatedAt: '2026-06-21T10:00:00Z',
    cheapestPath: cheapestPath,
    pricingAws: pricingAws,
    pricingAwsUpdatedAt: pricingAwsUpdatedAt,
    pricingAzure: const {'messages': 0.2},
    pricingAzureUpdatedAt: '2026-06-21T10:00:00Z',
    pricingGcp: const {'messages': 0.3},
    pricingGcpUpdatedAt: '2026-06-21T10:00:00Z',
    deployerConfig: deployerConfig,
  );
}
