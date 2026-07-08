import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/pricing_review_state.dart';
import 'package:twin2multicloud_flutter/widgets/pricing/pricing_review_details.dart';

void main() {
  Widget buildWidget(PricingReviewStateResponse reviewState) {
    return MaterialApp(
      home: Scaffold(body: PricingReviewDetails(reviewState: reviewState)),
    );
  }

  group('PricingReviewDetails', () {
    testWidgets('renders provider state and review evidence details', (
      tester,
    ) async {
      await tester.pumpWidget(buildWidget(_reviewState()));

      await tester.tap(find.text('Review details'));
      await tester.pumpAndSettle();

      expect(find.text('Optimizer'), findsOneWidget);
      expect(
        find.text('schema_version: pricing-review-state.v1'),
        findsOneWidget,
      );
      expect(find.text('AWS'), findsOneWidget);
      expect(find.text('State: review_required'), findsOneWidget);
      expect(find.text('Calculation source: last_known_good'), findsOneWidget);
      expect(find.text('Pricing freshness: stale'), findsOneWidget);
      expect(find.text('Review reasons'), findsOneWidget);
      expect(
        find.textContaining('ambiguous (api.request_million)'),
        findsOneWidget,
      );
      expect(find.text('Missing keys'), findsOneWidget);
      expect(find.text('pricing.aws.iot'), findsOneWidget);
      expect(find.text('Recommended actions'), findsOneWidget);
      expect(find.text('Review AWS pricing evidence'), findsOneWidget);
    });

    testWidgets('renders an explicit empty evidence state', (tester) async {
      await tester.pumpWidget(
        buildWidget(
          const PricingReviewStateResponse(
            schemaVersion: 'pricing-review-state.v1',
            providers: {},
          ),
        ),
      );

      await tester.tap(find.text('Review details'));
      await tester.pumpAndSettle();

      expect(find.text('No review evidence available'), findsOneWidget);
      expect(
        find.text('Refresh pricing to load provider review evidence.'),
        findsOneWidget,
      );
    });
  });
}

PricingReviewStateResponse _reviewState() {
  return const PricingReviewStateResponse(
    schemaVersion: 'pricing-review-state.v1',
    optimizer: {'schema_version': 'pricing-review-state.v1'},
    providers: {
      'aws': ProviderPricingReviewState(
        provider: 'aws',
        state: 'review_required',
        reviewRequired: true,
        canCalculate: true,
        calculationSource: 'last_known_good',
        pricingFreshness: 'stale',
        age: '9 days',
        status: 'valid',
        isFresh: false,
        thresholdDays: 7,
        missingKeys: ['pricing.aws.iot'],
        actions: ['Review AWS pricing evidence'],
        reviewReasons: [
          PricingReviewReason(
            status: 'ambiguous',
            reason: 'Multiple provider pricing candidates match this intent.',
            intentId: 'api.request_million',
            errors: ['Multiple paid candidates matched'],
            missingKeys: ['pricing.aws.iot'],
          ),
        ],
      ),
    },
  );
}
