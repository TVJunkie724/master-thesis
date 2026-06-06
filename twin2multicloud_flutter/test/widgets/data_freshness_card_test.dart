import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/pricing_review_state.dart';
import 'package:twin2multicloud_flutter/theme/colors.dart';
import 'package:twin2multicloud_flutter/widgets/data_freshness_card.dart';

void main() {
  // Helper to build widget with MaterialApp wrapper
  Widget buildTestWidget({
    required String provider,
    Map<String, dynamic>? status,
    ProviderPricingReviewState? reviewState,
    VoidCallback? onRefresh,
    bool enabled = true,
    String? disabledReason,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: DataFreshnessCard(
          provider: provider,
          status: status,
          reviewState: reviewState,
          onRefresh: onRefresh,
          enabled: enabled,
          disabledReason: disabledReason,
        ),
      ),
    );
  }

  group('DataFreshnessCard', () {
    // ============================================================
    // Happy Path Tests
    // ============================================================

    testWidgets('renders provider name in header', (tester) async {
      await tester.pumpWidget(buildTestWidget(provider: 'aws'));
      expect(find.text('AWS PRICING'), findsOneWidget);
    });

    testWidgets('shows refresh icon when enabled', (tester) async {
      await tester.pumpWidget(buildTestWidget(provider: 'aws', enabled: true));
      expect(find.byIcon(Icons.refresh), findsOneWidget);
      expect(find.byIcon(Icons.lock_outline), findsNothing);
    });

    testWidgets('shows lock icon when disabled', (tester) async {
      await tester.pumpWidget(buildTestWidget(provider: 'aws', enabled: false));
      expect(find.byIcon(Icons.lock_outline), findsOneWidget);
      expect(find.byIcon(Icons.refresh), findsNothing);
    });

    testWidgets('onRefresh called when enabled and tapped', (tester) async {
      bool wasPressed = false;
      await tester.pumpWidget(
        buildTestWidget(
          provider: 'aws',
          enabled: true,
          onRefresh: () => wasPressed = true,
        ),
      );

      await tester.tap(find.text('Refresh'));
      await tester.pump();

      expect(wasPressed, isTrue);
    });

    testWidgets('onRefresh NOT called when disabled and tapped', (
      tester,
    ) async {
      bool wasPressed = false;
      await tester.pumpWidget(
        buildTestWidget(
          provider: 'aws',
          enabled: false,
          onRefresh: () => wasPressed = true,
        ),
      );

      await tester.tap(find.text('Refresh'));
      await tester.pump();

      expect(wasPressed, isFalse);
    });

    // ============================================================
    // Status Badge Tests
    // ============================================================

    testWidgets('shows Fresh badge when is_fresh is true', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(
          provider: 'azure',
          status: {'is_fresh': true, 'age': '2 hours'},
        ),
      );
      expect(find.text('Fresh'), findsOneWidget);
    });

    testWidgets('shows Stale badge when is_fresh is false', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(
          provider: 'gcp',
          status: {'is_fresh': false, 'age': '10 days'},
        ),
      );
      expect(find.text('Stale'), findsOneWidget);
    });

    testWidgets('shows Error badge on error status', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(provider: 'aws', status: {'error': 'Failed to fetch'}),
      );
      expect(find.text('Error'), findsOneWidget);
      expect(find.text('Error loading status'), findsOneWidget);
    });

    // ============================================================
    // Provider Color Tests
    // ============================================================

    testWidgets('AWS uses orange color', (tester) async {
      await tester.pumpWidget(buildTestWidget(provider: 'aws'));
      final icon = tester.widget<Icon>(find.byIcon(Icons.cloud));
      expect(icon.color, AppColors.aws);
    });

    testWidgets('Azure uses blue color', (tester) async {
      await tester.pumpWidget(buildTestWidget(provider: 'azure'));
      final icon = tester.widget<Icon>(find.byIcon(Icons.cloud_queue));
      expect(icon.color, AppColors.azure);
    });

    testWidgets('GCP uses green color', (tester) async {
      await tester.pumpWidget(buildTestWidget(provider: 'gcp'));
      final icon = tester.widget<Icon>(find.byIcon(Icons.cloud_circle));
      expect(icon.color, AppColors.gcp);
    });

    // ============================================================
    // Pricing Review State Tests
    // ============================================================

    testWidgets('shows typed fresh review state', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(
          provider: 'aws',
          reviewState: const ProviderPricingReviewState(
            provider: 'aws',
            state: 'fresh',
            reviewRequired: false,
            canCalculate: true,
            calculationSource: 'fresh',
            pricingFreshness: 'fresh',
            age: '2 hours',
            isFresh: true,
            thresholdDays: 7,
          ),
        ),
      );

      expect(find.text('Fresh'), findsOneWidget);
      expect(find.text('Ready for calculation'), findsOneWidget);
      expect(find.text('Fresh pricing'), findsOneWidget);
    });

    testWidgets('shows typed stale review state', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(
          provider: 'azure',
          reviewState: const ProviderPricingReviewState(
            provider: 'azure',
            state: 'stale',
            reviewRequired: false,
            canCalculate: true,
            calculationSource: 'stale',
            pricingFreshness: 'stale',
            age: '10 days',
            isFresh: false,
            thresholdDays: 7,
          ),
        ),
      );

      expect(find.text('Stale'), findsOneWidget);
      expect(
        find.text('Refresh recommended before calculation'),
        findsOneWidget,
      );
      expect(find.text('Stale cached pricing'), findsOneWidget);
    });

    testWidgets('shows typed review-required state', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(
          provider: 'gcp',
          reviewState: const ProviderPricingReviewState(
            provider: 'gcp',
            state: 'review_required',
            reviewRequired: true,
            canCalculate: true,
            calculationSource: 'last_known_good',
            pricingFreshness: 'last_known_good',
            age: '1 day',
            isFresh: false,
            thresholdDays: 7,
            reviewReasons: [
              PricingReviewReason(
                status: 'ambiguous',
                reason:
                    'Multiple provider pricing candidates match this intent.',
                intentId: 'api.request_million',
              ),
            ],
            lastKnownGoodUpdatedAt: '2026-06-01T00:00:00+00:00',
          ),
        ),
      );

      expect(find.text('Review'), findsOneWidget);
      expect(
        find.text('Multiple provider pricing candidates match this intent.'),
        findsOneWidget,
      );
      expect(find.text('Using last-known-good'), findsOneWidget);
      expect(
        find.text('Last-known-good: 2026-06-01T00:00:00+00:00'),
        findsOneWidget,
      );
    });

    testWidgets('shows typed failed state', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(
          provider: 'aws',
          reviewState: const ProviderPricingReviewState(
            provider: 'aws',
            state: 'failed',
            reviewRequired: true,
            canCalculate: false,
            calculationSource: 'unavailable',
            pricingFreshness: 'unavailable',
            isFresh: false,
            reviewReasons: [
              PricingReviewReason(
                status: 'failed',
                reason: 'Optimizer pricing status failed.',
              ),
            ],
          ),
        ),
      );

      expect(find.text('Failed'), findsOneWidget);
      expect(find.text('Optimizer pricing status failed.'), findsOneWidget);
      expect(find.text('No calculation pricing'), findsOneWidget);
    });

    testWidgets('shows typed missing state', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(
          provider: 'azure',
          reviewState: const ProviderPricingReviewState(
            provider: 'azure',
            state: 'missing',
            reviewRequired: true,
            canCalculate: false,
            calculationSource: 'unavailable',
            pricingFreshness: 'unavailable',
            isFresh: false,
          ),
        ),
      );

      expect(find.text('Missing'), findsOneWidget);
      expect(find.text('Pricing data is missing'), findsOneWidget);
    });
  });
}
