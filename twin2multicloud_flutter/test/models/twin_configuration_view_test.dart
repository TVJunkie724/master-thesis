import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployer_config.dart';
import 'package:twin2multicloud_flutter/models/optimizer_config.dart';
import 'package:twin2multicloud_flutter/models/twin_configuration_view.dart';

import '../fixtures/typed_api_fixtures.dart';

void main() {
  group('TwinConfigurationView', () {
    test('maps optimizer result, workload params and pricing evidence', () {
      final view = TwinConfigurationView.fromState(_state());

      expect(view.pathSegments, ['L1_AWS', 'L2_Azure', 'L4_GCP']);
      expect(view.optimization.hasResult, isTrue);
      expect(view.optimization.totalCost, 42.5);
      expect(view.optimization.numberOfDevices, '12');
      expect(view.optimization.messagesPerHour, '12.0');
      expect(view.optimization.retention, '6 months');
      expect(view.optimization.calculatedAt, '2026-06-21T10:00:00.000Z');
      expect(
        view.pricingCatalogContext?.reference(CloudProvider.aws).pricingRegion,
        'eu-central-1',
      );
    });

    test('maps provider-specific deployment artifact filenames', () {
      final view = TwinConfigurationView.fromState(
        _state(
          cheapestPath: const CheapestPath(
            l2: CloudProvider.gcp,
            l4: CloudProvider.azure,
          ),
        ),
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
          includeOptimizer: false,
          deployerConfig: const DeployerConfigData(),
        ),
      );

      expect(view.pathSegments, isEmpty);
      expect(view.optimization.hasResult, isFalse);
      expect(view.optimization.messagesPerHour, isNull);
      expect(view.configurationArtifacts, isEmpty);
      expect(view.functionGroups, isEmpty);
      expect(view.pricingCatalogContext, isNull);
    });
  });
}

TwinOverviewLoaded _state({
  bool includeOptimizer = true,
  CheapestPath cheapestPath = const CheapestPath(
    l2: CloudProvider.aws,
    l4: CloudProvider.aws,
  ),
  DeployerConfigData deployerConfig = TypedApiFixtures.deployerConfig,
}) {
  final calculatedAt = DateTime.parse('2026-06-21T10:00:00Z');
  final params = CalcParams.fromJson({
    ...CalcParams.defaultParams().toJson(),
    'numberOfDevices': 12,
    'deviceSendingIntervalInMinutes': 5,
    'hotStorageDurationInMonths': 1,
    'coolStorageDurationInMonths': 2,
    'archiveStorageDurationInMonths': 3,
  });
  final optimization = TypedApiFixtures.optimization(
    totalCost: 42.5,
    cheapestPath: const ['L1_AWS', 'L2_Azure', 'L4_GCP'],
  );
  return TwinOverviewLoaded(
    twinId: 'twin-1',
    projectName: 'Demo Twin',
    cloudResourceName: 'cloud-demo',
    twinState: 'configured',
    canDeploy: true,
    canDestroy: false,
    canEdit: true,
    canDelete: true,
    optimizerConfig: includeOptimizer
        ? OptimizerConfigData(
            id: 'optimizer-twin-1',
            twinId: 'twin-1',
            params: params,
            optimization: optimization,
            cheapestPath: cheapestPath,
            calculatedAt: calculatedAt,
            pricingCatalogContext: optimization.result.pricingCatalogContext,
            updatedAt: calculatedAt,
          )
        : null,
    deployerConfig: deployerConfig,
  );
}
