import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/pricing_review_state.dart';

void main() {
  group('PricingReviewStateResponse', () {
    test('parses provider states and optimizer metadata', () {
      final response = PricingReviewStateResponse.fromJson({
        'schema_version': 'pricing-review.v1',
        'optimizer': {
          'version': 'test-optimizer',
          'pricing_registry_version': 'pricing-registry.v1',
        },
        'providers': {
          'aws': {
            'provider': 'aws',
            'state': 'review_required',
            'review_required': true,
            'can_calculate': true,
            'calculation_source': 'last_known_good',
            'pricing_freshness': 'stale',
            'age': '8 days',
            'status': 'valid',
            'is_fresh': false,
            'threshold_days': 7,
            'missing_keys': ['aws.iot.messages'],
            'actions': ['Review candidate selection'],
            'last_known_good_updated_at': '2026-06-21T10:00:00Z',
            'review_reasons': [
              {
                'status': 'ambiguous',
                'reason': 'Multiple candidates match the intent.',
                'intent_id': 'aws.iot.messages',
                'errors': ['candidate-score-tie'],
                'missing_keys': ['sku'],
              },
            ],
          },
        },
      });

      expect(response.schemaVersion, 'pricing-review.v1');
      expect(response.optimizer['version'], 'test-optimizer');

      final aws = response.provider('AWS');
      expect(aws, isNotNull);
      expect(aws!.badgeLabel, 'Review');
      expect(aws.sourceLabel, 'Using last-known-good');
      expect(aws.primaryMessage, 'Multiple candidates match the intent.');
      expect(aws.missingKeys, ['aws.iot.messages']);
      expect(aws.actions, ['Review candidate selection']);
      expect(aws.reviewReasons.single.intentId, 'aws.iot.messages');
      expect(aws.reviewReasons.single.errors, ['candidate-score-tie']);
    });
  });
}
