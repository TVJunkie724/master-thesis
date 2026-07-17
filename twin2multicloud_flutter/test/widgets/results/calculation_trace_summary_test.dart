import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';
import 'package:twin2multicloud_flutter/widgets/results/calculation_trace_summary.dart';

void main() {
  Widget buildWidget(
    CalcResult result, {
    ThemeMode themeMode = ThemeMode.light,
  }) {
    return MaterialApp(
      theme: ThemeData.light(),
      darkTheme: ThemeData.dark(),
      themeMode: themeMode,
      home: Scaffold(
        body: SingleChildScrollView(
          child: CalculationTraceSummary(result: result),
        ),
      ),
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
      expect(find.text('1 field records'), findsOneWidget);

      await tester.tap(find.text('Trace details'));
      await tester.pumpAndSettle();

      expect(find.text('Trace schema: intent-result-trace.v1'), findsOneWidget);
      expect(find.text('Profile: cost-default'), findsOneWidget);
      expect(find.text('Objective: cost'), findsOneWidget);
      expect(find.text('Evidence references: 1'), findsOneWidget);

      await tester.tap(find.text('Field-level audit'));
      await tester.pumpAndSettle();
      expect(find.text('AWS'), findsOneWidget);

      await tester.tap(find.text('AWS'));
      await tester.pumpAndSettle();
      expect(find.text('iot · AWSIoT'), findsOneWidget);

      await tester.tap(find.text('iot · AWSIoT'));
      await tester.pumpAndSettle();
      expect(
        find.text('Shared diagnostic amount; do not add across field records.'),
        findsOneWidget,
      );
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

    testWidgets('distinguishes alternative unsupported and review states', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(
          _resultWithTrace(
            fieldTraceRecords: const [
              _selectedFieldRecord,
              _alternativeFieldRecord,
              _unsupportedFieldRecord,
            ],
          ),
        ),
      );

      await tester.tap(find.text('Trace details'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Field-level audit'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('AZURE'));
      await tester.pumpAndSettle();
      expect(find.text('alternative'), findsOneWidget);
      await tester.ensureVisible(find.text('iot · AzureIoTHub'));
      await tester.tap(find.text('iot · AzureIoTHub'));
      await tester.pumpAndSettle();
      expect(find.text('review_required'), findsOneWidget);

      await tester.ensureVisible(find.text('GCP'));
      await tester.tap(find.text('GCP'));
      await tester.pumpAndSettle();
      expect(find.text('unsupported'), findsOneWidget);
    });

    testWidgets('remains usable in a narrow dark viewport', (tester) async {
      await tester.binding.setSurfaceSize(const Size(420, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        buildWidget(_resultWithTrace(), themeMode: ThemeMode.dark),
      );
      await tester.tap(find.text('Trace details'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Field-level audit'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('AWS'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('iot · AWSIoT'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Evidence'), findsOneWidget);
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
  List<PricingFieldTraceRecord> fieldTraceRecords = const [
    _selectedFieldRecord,
  ],
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
    fieldTraceSchemaVersion: 'intent-to-result-trace.v1',
    fieldTraceRecords: fieldTraceRecords,
    inputParamsUsed: const InputParamsUsed(),
  );
}

const _selectedFieldRecord = PricingFieldTraceRecord(
  traceId: 'aws.iot.message_ingest.L1.v1',
  provider: 'aws',
  layer: 'iot',
  service: 'AWSIoT',
  intentId: 'iot.message_ingest',
  formulaRef: 'tiered_unit_cost',
  sourceType: 'provider_api',
  selectedEvidenceId: 'aws.iot.message_ingest.mapping:2026.06.08',
  selectionStatus: 'selected',
  costContribution: 1,
  costContributionScope: 'component_total',
  costContributionIsAdditive: false,
  resultComponentKey: 'iot_core',
  outputMetricUnit: 'USD/month',
  verificationStatus: 'passed',
  alternativeRecordIds: ['azure.iot'],
  rejectedEvidenceIds: [],
);

const _alternativeFieldRecord = PricingFieldTraceRecord(
  traceId: 'azure.iot.message_ingest.L1.v1',
  provider: 'azure',
  layer: 'iot',
  service: 'AzureIoTHub',
  intentId: 'iot.message_ingest',
  formulaRef: 'tiered_unit_cost',
  sourceType: 'provider_api',
  selectedEvidenceId: null,
  selectionStatus: 'alternative',
  costContribution: 2,
  costContributionScope: 'layer_total_shared',
  costContributionIsAdditive: false,
  resultComponentKey: null,
  outputMetricUnit: 'USD/month',
  verificationStatus: 'review_required',
  alternativeRecordIds: ['aws.iot'],
  rejectedEvidenceIds: ['azure.iot.rejected'],
);

const _unsupportedFieldRecord = PricingFieldTraceRecord(
  traceId: 'gcp.iot.message_ingest.L1.v1',
  provider: 'gcp',
  layer: 'iot',
  service: 'GcpIoT',
  intentId: 'iot.message_ingest',
  formulaRef: 'not_applicable',
  sourceType: 'unsupported',
  selectedEvidenceId: null,
  selectionStatus: 'unsupported',
  costContribution: null,
  costContributionScope: 'none',
  costContributionIsAdditive: false,
  resultComponentKey: null,
  outputMetricUnit: null,
  verificationStatus: 'not_applicable',
  alternativeRecordIds: [],
  rejectedEvidenceIds: [],
);
