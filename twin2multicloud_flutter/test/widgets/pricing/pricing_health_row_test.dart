import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/pricing_review_state.dart';
import 'package:twin2multicloud_flutter/widgets/pricing/pricing_health_row.dart';

void main() {
  Widget buildWidget({
    required AsyncValue<PricingReviewStateResponse> reviewState,
    VoidCallback? onOpenReview,
    VoidCallback? onRetry,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: PricingHealthRow(
          reviewState: reviewState,
          onOpenReview: onOpenReview ?? () {},
          onRetry: onRetry ?? () {},
        ),
      ),
    );
  }

  group('PricingHealthRow', () {
    testWidgets('renders provider readiness cards', (tester) async {
      await tester.pumpWidget(
        buildWidget(
          reviewState: AsyncValue.data(
            PricingReviewStateResponse(
              schemaVersion: 'pricing-review.v1',
              providers: {
                'aws': _providerState('aws', 'fresh', false),
                'azure': _providerState('azure', 'stale', false),
                'gcp': _providerState('gcp', 'review_required', true),
              },
            ),
          ),
        ),
      );

      expect(find.text('Pricing readiness'), findsOneWidget);
      expect(find.text('AWS'), findsOneWidget);
      expect(find.text('AZURE'), findsOneWidget);
      expect(find.text('GCP'), findsOneWidget);
      expect(find.text('Fresh'), findsOneWidget);
      expect(find.text('Stale'), findsOneWidget);
      expect(find.text('Review'), findsOneWidget);
    });

    testWidgets('opens the pricing review screen from the action', (
      tester,
    ) async {
      var opened = false;
      await tester.pumpWidget(
        buildWidget(
          reviewState: const AsyncValue.data(
            PricingReviewStateResponse(
              schemaVersion: 'pricing-review.v1',
              providers: {},
            ),
          ),
          onOpenReview: () => opened = true,
        ),
      );

      await tester.tap(find.text('Review pricing'));
      await tester.pump();

      expect(opened, isTrue);
    });

    testWidgets('renders retry action for load failures', (tester) async {
      var retried = false;
      await tester.pumpWidget(
        buildWidget(
          reviewState: AsyncValue.error(Exception('boom'), StackTrace.current),
          onRetry: () => retried = true,
        ),
      );

      expect(
        find.text('Pricing readiness could not be loaded.'),
        findsOneWidget,
      );

      await tester.tap(find.text('Retry'));
      await tester.pump();

      expect(retried, isTrue);
    });
  });
}

ProviderPricingReviewState _providerState(
  String provider,
  String state,
  bool reviewRequired,
) {
  return ProviderPricingReviewState(
    provider: provider,
    state: state,
    reviewRequired: reviewRequired,
    canCalculate: true,
    calculationSource: state == 'fresh' ? 'fresh' : 'last_known_good',
    pricingFreshness: state == 'fresh' ? 'fresh' : 'stale',
    age: state == 'fresh' ? '1 hour' : '9 days',
    isFresh: state == 'fresh',
    thresholdDays: 7,
  );
}
