import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/widgets/pricing/pricing_health_row.dart';

void main() {
  Widget buildWidget({
    required AsyncValue<PricingHealthResponse> pricingHealth,
    VoidCallback? onOpenReview,
    VoidCallback? onRetry,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: PricingHealthRow(
          pricingHealth: pricingHealth,
          onOpenReview: onOpenReview ?? () {},
          onRetry: onRetry ?? () {},
        ),
      ),
    );
  }

  testWidgets('renders compact provider readiness cards', (tester) async {
    tester.view.physicalSize = const Size(420, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      buildWidget(pricingHealth: AsyncValue.data(_health())),
    );

    expect(find.text('Pricing readiness'), findsOneWidget);
    expect(find.text('AWS'), findsOneWidget);
    expect(find.text('AZURE'), findsOneWidget);
    expect(find.text('GCP'), findsOneWidget);
    expect(find.text('Fresh'), findsOneWidget);
    expect(find.text('Stale'), findsOneWidget);
    expect(find.text('Review'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('opens pricing review from the single dashboard action', (
    tester,
  ) async {
    var opened = false;
    await tester.pumpWidget(
      buildWidget(
        pricingHealth: const AsyncValue.data(
          PricingHealthResponse(
            schemaVersion: 'pricing-health.v1',
            providers: {},
          ),
        ),
        onOpenReview: () => opened = true,
      ),
    );

    await tester.tap(find.text('Review pricing'));
    expect(opened, isTrue);
  });

  testWidgets('renders retry action for load failures', (tester) async {
    var retried = false;
    await tester.pumpWidget(
      buildWidget(
        pricingHealth: AsyncValue.error(Exception('boom'), StackTrace.current),
        onRetry: () => retried = true,
      ),
    );

    await tester.tap(find.text('Retry'));
    expect(retried, isTrue);
  });
}

PricingHealthResponse _health() => PricingHealthResponse.fromJson({
  'schema_version': 'pricing-health.v1',
  'providers': {
    for (final entry in const {
      'aws': 'fresh',
      'azure': 'stale',
      'gcp': 'review_required',
    }.entries)
      entry.key: {
        'provider': entry.key,
        'state': entry.value,
        'severity': entry.value == 'fresh' ? 'success' : 'warning',
        'can_calculate': true,
        'pricing_freshness': entry.value == 'fresh' ? 'fresh' : 'stale',
        'primary_message': '${entry.key} pricing state',
        'age': '1 hour',
        'credential_summary': {},
      },
  },
});
