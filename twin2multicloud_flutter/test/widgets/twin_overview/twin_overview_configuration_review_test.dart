import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/optimizer_config.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_code_artifact.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_configuration_review.dart';

import '../../fixtures/typed_api_fixtures.dart';

void main() {
  Widget buildWidget({
    required TwinOverviewLoaded state,
    ValueChanged<TwinOverviewCodeArtifact>? onViewArtifact,
    ValueChanged<TwinOverviewCodeArtifact>? onDownloadArtifact,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: TwinOverviewConfigurationReview(
            state: state,
            onViewArtifact: onViewArtifact ?? (_) {},
            onDownloadArtifact: onDownloadArtifact ?? (_) {},
          ),
        ),
      ),
    );
  }

  group('TwinOverviewConfigurationReview', () {
    testWidgets('renders optimization summary and architecture', (
      tester,
    ) async {
      await tester.pumpWidget(buildWidget(state: _state()));

      expect(find.text('CONFIGURATION REVIEW'), findsOneWidget);
      expect(find.text('Provider Architecture'), findsOneWidget);
      expect(find.text('Optimization Summary'), findsOneWidget);
      expect(find.textContaining(r'$42.50/month'), findsOneWidget);
      expect(find.text('Devices: '), findsOneWidget);
      expect(find.text('12'), findsOneWidget);
    });

    testWidgets('surfaces pricing artifacts through callbacks', (tester) async {
      TwinOverviewCodeArtifact? viewed;
      TwinOverviewCodeArtifact? downloaded;

      await tester.pumpWidget(
        buildWidget(
          state: _state(),
          onViewArtifact: (artifact) => viewed = artifact,
          onDownloadArtifact: (artifact) => downloaded = artifact,
        ),
      );

      await tester.tap(find.text('Pricing Data'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('View').first);
      await tester.tap(find.byTooltip('Download').first);

      expect(viewed?.filename, 'aws_pricing.json');
      expect(viewed?.content, contains('"messages"'));
      expect(downloaded?.filename, 'aws_pricing.json');
    });

    testWidgets('uses provider-specific deployment artifact names', (
      tester,
    ) async {
      TwinOverviewCodeArtifact? viewed;

      await tester.pumpWidget(
        buildWidget(
          state: _state(
            cheapestPath: const CheapestPath(
              l2: CloudProvider.gcp,
              l4: CloudProvider.azure,
            ),
          ),
          onViewArtifact: (artifact) => viewed ??= artifact,
        ),
      );

      await tester.ensureVisible(find.text('Configuration Files'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Configuration Files'));
      await tester.pumpAndSettle();

      expect(find.text('google_cloud_workflow.yaml'), findsOneWidget);
      expect(find.text('azure_hierarchy.json'), findsOneWidget);
      expect(find.text('3DScenesConfiguration.json'), findsOneWidget);

      await tester.ensureVisible(find.byTooltip('View').first);
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('View').first);
      expect(viewed?.filename, 'config_events.json');
    });

    testWidgets('renders user function provider filename convention', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(
          state: _state(
            cheapestPath: const CheapestPath(l2: CloudProvider.azure),
          ),
        ),
      );

      await tester.ensureVisible(find.text('User Functions'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('User Functions'));
      await tester.pumpAndSettle();

      expect(find.text('processor-a/function_app.py'), findsOneWidget);
    });
  });
}

TwinOverviewLoaded _state({
  CheapestPath cheapestPath = const CheapestPath(
    l2: CloudProvider.aws,
    l4: CloudProvider.aws,
  ),
}) {
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
  final calculatedAt = DateTime.parse('2026-06-21T10:00:00Z');
  return TwinOverviewLoaded(
    twinId: 'twin-1',
    projectName: 'Demo Twin',
    cloudResourceName: 'cloud-demo',
    twinState: 'configured',
    canDeploy: true,
    canDestroy: false,
    canEdit: true,
    canDelete: true,
    optimizerConfig: OptimizerConfigData(
      id: 'optimizer-twin-1',
      twinId: 'twin-1',
      params: params,
      optimization: optimization,
      cheapestPath: cheapestPath,
      calculatedAt: calculatedAt,
      pricingSnapshots: {
        for (final provider in CloudProvider.values)
          provider: ProviderPricingSnapshot(
            provider: provider,
            payload: {'messages': provider.index + 0.1},
            updatedAt: calculatedAt,
          ),
      },
      updatedAt: calculatedAt,
    ),
    deployerConfig: TypedApiFixtures.deployerConfig,
  );
}
