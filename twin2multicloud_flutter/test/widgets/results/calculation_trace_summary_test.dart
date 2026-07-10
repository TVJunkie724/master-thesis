import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';
import 'package:twin2multicloud_flutter/widgets/results/calculation_trace_summary.dart';

void main() {
  Widget buildWidget(CalcResult result) {
    return MaterialApp(
      home: Scaffold(body: CalculationTraceSummary(result: result)),
    );
  }

  group('CalculationTraceSummary', () {
    testWidgets('renders fallback when trace is unavailable', (tester) async {
      await tester.pumpWidget(buildWidget(_resultWithoutTrace()));

      expect(find.text('Calculation trace'), findsOneWidget);
      expect(
        find.text(
          'No intent trace metadata is available for this calculation result.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('renders publishable trace summary and details', (
      tester,
    ) async {
      await tester.pumpWidget(buildWidget(_resultWithTrace()));

      expect(find.text('Publishable'), findsOneWidget);
      expect(find.text('2 records'), findsOneWidget);
      expect(find.text('1 selected records'), findsOneWidget);
      expect(find.text('0 review required'), findsOneWidget);
      expect(find.text('1 transfers'), findsOneWidget);

      await tester.tap(find.text('Trace details'));
      await tester.pumpAndSettle();

      expect(find.text('Trace schema: intent-result-trace.v1'), findsOneWidget);
      expect(find.text('Profile: cost-default'), findsOneWidget);
      expect(find.text('Objective: cost'), findsOneWidget);
      expect(find.text('Evidence references: 1'), findsOneWidget);
    });

    testWidgets('shows review-needed status when trace is not publishable', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(
          _resultWithTrace(publishable: false, reviewRequiredCount: 2),
        ),
      );

      expect(find.text('Review needed'), findsOneWidget);
      expect(find.text('2 review required'), findsOneWidget);
    });
  });
}

CalcResult _resultWithoutTrace() {
  return CalcResult(
    totalCost: 1,
    cheapestPath: const [],
    awsCosts: ProviderCosts(),
    azureCosts: ProviderCosts(),
    gcpCosts: ProviderCosts(),
    inputParamsUsed: const InputParamsUsed(),
  );
}

CalcResult _resultWithTrace({
  bool publishable = true,
  int reviewRequiredCount = 0,
}) {
  return CalcResult(
    totalCost: 1,
    cheapestPath: const [],
    awsCosts: ProviderCosts(),
    azureCosts: ProviderCosts(),
    gcpCosts: ProviderCosts(),
    traceSchemaVersion: 'intent-result-trace.v1',
    optimizationProfile: const OptimizationProfileTrace(
      profileId: 'cost-default',
      objective: 'cost',
      pricingRegistryVersion: 'pricing-registry.v1',
    ),
    evidenceReferences: const {'aws.iot': 'pricing_registry:aws.iot'},
    intentTrace: IntentResultTrace(
      schemaVersion: 'intent-result-trace.v1',
      summary: IntentTraceSummary(
        recordCount: 2,
        selectedRecordCount: 1,
        reviewRequiredCount: reviewRequiredCount,
        transferSegmentCount: 1,
        publishable: publishable,
      ),
    ),
    inputParamsUsed: const InputParamsUsed(),
  );
}
