import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/widgets/pricing/pricing_readiness_summary.dart';

void main() {
  Widget subject({
    PricingHealthResponse? health,
    bool isLoading = false,
    String? error,
    VoidCallback? onRetry,
  }) => MaterialApp(
    home: Scaffold(
      body: PricingReadinessSummary(
        health: health,
        isLoading: isLoading,
        error: error,
        onRetry: onRetry ?? () {},
      ),
    ),
  );

  testWidgets('shows three compact states and last-known-good context', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1200, 500));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(subject(health: _health()));

    expect(find.text('AWS  Stale'), findsOneWidget);
    expect(find.text('AZURE  Fresh'), findsOneWidget);
    expect(find.text('GCP  Review'), findsOneWidget);
    expect(find.textContaining('last-known-good'), findsOneWidget);
    expect(find.textContaining('Pricing Review'), findsNothing);
    expect(find.text('Refresh'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('shows failed provider as calculation unavailable', (
    tester,
  ) async {
    await tester.pumpWidget(subject(health: _health(gcpCanCalculate: false)));

    expect(find.text('gcp pricing status'), findsOneWidget);
  });

  testWidgets('shows retryable load error without hiding the boundary', (
    tester,
  ) async {
    var retried = false;
    await tester.pumpWidget(
      subject(
        error: 'Management API unavailable',
        onRetry: () => retried = true,
      ),
    );

    expect(find.text('Management API unavailable'), findsOneWidget);
    await tester.tap(find.byTooltip('Retry pricing readiness'));
    await tester.pump();
    expect(retried, isTrue);
  });

  testWidgets('stacks safely on compact width', (tester) async {
    await tester.binding.setSurfaceSize(const Size(420, 700));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(subject(health: _health()));

    expect(find.byType(PricingReadinessSummary), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('offers retry for an incomplete provider contract', (
    tester,
  ) async {
    var retried = false;
    final complete = _health();
    final incomplete = PricingHealthResponse(
      schemaVersion: complete.schemaVersion,
      providers: {...complete.providers}..remove('gcp'),
    );

    await tester.pumpWidget(
      subject(health: incomplete, onRetry: () => retried = true),
    );

    expect(
      find.text('Pricing readiness response is incomplete.'),
      findsOneWidget,
    );
    await tester.tap(find.byTooltip('Retry pricing readiness'));
    await tester.pump();
    expect(retried, isTrue);
  });

  testWidgets('offers retry for an unsupported contract version', (
    tester,
  ) async {
    final health = _health();
    await tester.pumpWidget(
      subject(
        health: PricingHealthResponse(
          schemaVersion: 'pricing-health.v2',
          providers: health.providers,
        ),
      ),
    );

    expect(
      find.text('Pricing readiness contract is not supported.'),
      findsOneWidget,
    );
    expect(find.byTooltip('Retry pricing readiness'), findsOneWidget);
  });

  testWidgets('labels an explicitly permitted static fallback', (tester) async {
    final health = _health();
    final azure = health.providers['azure']!;
    final fallback = PricingHealthResponse(
      schemaVersion: health.schemaVersion,
      providers: {
        ...health.providers,
        'azure': ProviderPricingHealth(
          provider: azure.provider,
          state: 'review_required',
          severity: 'warning',
          reviewRequired: true,
          canCalculate: true,
          calculationSource: 'fallback_static',
          pricingFreshness: azure.pricingFreshness,
          sourceLabel: azure.sourceLabel,
          credentialSummary: azure.credentialSummary,
          primaryMessage: azure.primaryMessage,
        ),
      },
    );

    await tester.pumpWidget(subject(health: fallback));

    expect(find.textContaining('static fallback pricing'), findsOneWidget);
  });
}

PricingHealthResponse _health({bool gcpCanCalculate = true}) =>
    PricingHealthResponse.fromJson({
      'schema_version': 'pricing-health.v1',
      'providers': {
        'aws': _provider('aws', 'stale', source: 'last_known_good'),
        'azure': _provider('azure', 'fresh'),
        'gcp': _provider(
          'gcp',
          gcpCanCalculate ? 'review_required' : 'failed',
          source: 'last_known_good',
          canCalculate: gcpCanCalculate,
        ),
      },
    });

Map<String, dynamic> _provider(
  String provider,
  String state, {
  String source = 'fresh',
  bool canCalculate = true,
}) => {
  'provider': provider,
  'state': state,
  'severity': state == 'fresh' ? 'success' : 'warning',
  'review_required': state == 'review_required',
  'can_calculate': canCalculate,
  'calculation_source': source,
  'pricing_freshness': state == 'fresh' ? 'fresh' : 'stale',
  'source_label': '${provider.toUpperCase()} source with a long account label',
  'credential_summary': {
    'provider': provider,
    'purpose': 'pricing',
    'scope': provider == 'azure' ? 'public' : 'user',
    'identity_label': '$provider pricing',
    'status': 'active',
  },
  'primary_message': '$provider pricing status',
};
