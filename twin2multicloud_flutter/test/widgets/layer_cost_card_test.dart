import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';
import 'package:twin2multicloud_flutter/widgets/results/layer_cost_card.dart';
import 'package:twin2multicloud_flutter/theme/colors.dart';

import '../fixtures/test_fixtures.dart';

void main() {
  // Helper to build widget with MaterialApp wrapper
  Widget buildTestWidget({
    required String layer,
    LayerCost? awsLayer,
    LayerCost? azureLayer,
    LayerCost? gcpLayer,
    List<String> cheapestPath = const [],
  }) {
    return MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: LayerCostCard(
            layer: layer,
            awsLayer: awsLayer,
            azureLayer: azureLayer,
            gcpLayer: gcpLayer,
            cheapestPath: cheapestPath,
          ),
        ),
      ),
    );
  }

  group('LayerCostCard', () {
    // ============================================================
    // Happy Path Tests
    // ============================================================

    testWidgets('renders layer title', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        layer: 'L1 - Data Ingestion',
      ));

      expect(find.text('L1 - Data Ingestion'), findsOneWidget);
    });

    testWidgets('shows provider costs', (tester) async {
      final awsLayer = LayerCost(cost: 10.50, components: {'IoT Core': 10.5});
      final azureLayer = LayerCost(cost: 12.00, components: {'IoT Hub': 12.0});
      
      await tester.pumpWidget(buildTestWidget(
        layer: 'L1 - Data Ingestion',
        awsLayer: awsLayer,
        azureLayer: azureLayer,
        cheapestPath: ['L1_AWS'],
      ));

      expect(find.text('AWS'), findsOneWidget);
      expect(find.text('Azure'), findsOneWidget);
      expect(find.text('\$10.50'), findsOneWidget);
      expect(find.text('\$12.00'), findsOneWidget);
    });

    testWidgets('shows N/A for null provider costs', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        layer: 'L4 - Twin Management',
        awsLayer: LayerCost(cost: 15.0, components: {}),
        azureLayer: LayerCost(cost: 18.0, components: {}),
        // gcpLayer is null (not supported)
        cheapestPath: ['L4_AWS'],
      ));

      expect(find.text('N/A'), findsOneWidget); // GCP
    });

    testWidgets('highlights selected provider from cheapest path', (tester) async {
      final awsLayer = LayerCost(cost: 10.0, components: {});
      
      await tester.pumpWidget(buildTestWidget(
        layer: 'L1 - Data Ingestion',
        awsLayer: awsLayer,
        cheapestPath: ['L1_AWS'],
      ));

      // Find check icon indicating selection
      expect(find.byIcon(Icons.check_circle), findsOneWidget);
    });

    // ============================================================
    // Edge Case Tests
    // ============================================================

    testWidgets('handles empty cheapest path', (tester) async {
      final awsLayer = LayerCost(cost: 10.0, components: {});
      
      await tester.pumpWidget(buildTestWidget(
        layer: 'L1 - Data Ingestion',
        awsLayer: awsLayer,
        cheapestPath: [], // Empty
      ));

      // Should not show check icon
      expect(find.byIcon(Icons.check_circle), findsNothing);
    });

    testWidgets('shows "Includes Glue Code" badge for dispatcher', (tester) async {
      final awsLayer = LayerCost(
        cost: 10.0, 
        components: {'dispatcher': 5.0, 'IoT Core': 5.0},
      );
      
      await tester.pumpWidget(buildTestWidget(
        layer: 'L1 - Data Ingestion',
        awsLayer: awsLayer,
        cheapestPath: ['L1_AWS'],
      ));

      expect(find.text('Includes Glue Code'), findsOneWidget);
    });

    testWidgets('shows info button for breakdown dialog', (tester) async {
      final awsLayer = LayerCost(cost: 10.0, components: {});
      
      await tester.pumpWidget(buildTestWidget(
        layer: 'L1 - Data Ingestion',
        awsLayer: awsLayer,
        cheapestPath: [],
      ));

      expect(find.byIcon(Icons.info_outline), findsOneWidget);
    });

    testWidgets('info button opens breakdown dialog', (tester) async {
      final awsLayer = LayerCost(
        cost: 10.0, 
        components: {'IoT Core': 5.0, 'Lambda': 5.0},
      );
      
      await tester.pumpWidget(buildTestWidget(
        layer: 'L1 - Data Ingestion',
        awsLayer: awsLayer,
        cheapestPath: [],
      ));

      // Tap info button
      await tester.tap(find.byIcon(Icons.info_outline));
      await tester.pumpAndSettle();

      // Dialog should show
      expect(find.byType(AlertDialog), findsOneWidget);
      expect(find.text('Close'), findsOneWidget);
    });

    group('L3 storage tiers', () {
      testWidgets('correctly identifies L3_hot from cheapest path', (tester) async {
        final gcpLayer = LayerCost(cost: 1.8, components: {'GCS': 1.8});
        
        await tester.pumpWidget(buildTestWidget(
          layer: 'L3 Hot Storage',
          gcpLayer: gcpLayer,
          cheapestPath: ['L3_hot_GCP'],
        ));

        // GCP should be selected
        expect(find.byIcon(Icons.check_circle), findsOneWidget);
      });
    });
  });
}
