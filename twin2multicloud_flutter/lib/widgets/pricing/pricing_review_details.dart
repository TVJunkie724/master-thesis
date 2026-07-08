import 'package:flutter/material.dart';

import '../../models/pricing_review_state.dart';
import '../../theme/spacing.dart';

class PricingReviewDetails extends StatelessWidget {
  final PricingReviewStateResponse reviewState;

  const PricingReviewDetails({super.key, required this.reviewState});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.fact_check_outlined),
        title: const Text('Review details'),
        subtitle: const Text(
          'Provider state, reasons, missing keys and recommended actions',
        ),
        childrenPadding: const EdgeInsets.all(AppSpacing.md),
        children: [
          if (reviewState.optimizer.isNotEmpty)
            PricingDetailsSection(
              title: 'Optimizer',
              values: reviewState.optimizer.entries
                  .map((entry) => '${entry.key}: ${entry.value}')
                  .toList(),
            ),
          ...reviewState.providers.entries.map(
            (entry) =>
                ProviderPricingDetails(provider: entry.key, state: entry.value),
          ),
        ],
      ),
    );
  }
}

class ProviderPricingDetails extends StatelessWidget {
  final String provider;
  final ProviderPricingReviewState state;

  const ProviderPricingDetails({
    super.key,
    required this.provider,
    required this.state,
  });

  @override
  Widget build(BuildContext context) {
    final values = <String>[
      'State: ${state.state}',
      'Calculation source: ${state.calculationSource}',
      'Pricing freshness: ${state.pricingFreshness}',
      'Can calculate: ${state.canCalculate}',
      if (state.status != null) 'Schema status: ${state.status}',
      if (state.age != null) 'Age: ${state.age}',
      if (state.lastKnownGoodUpdatedAt != null)
        'Last-known-good: ${state.lastKnownGoodUpdatedAt}',
    ];

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PricingDetailsSection(title: provider.toUpperCase(), values: values),
          if (state.reviewReasons.isNotEmpty)
            PricingDetailsSection(
              title: 'Review reasons',
              values: state.reviewReasons.map((reason) {
                final intent = reason.intentId == null
                    ? ''
                    : ' (${reason.intentId})';
                final details = <String>[
                  if (reason.errors.isNotEmpty)
                    'errors=${reason.errors.join(", ")}',
                  if (reason.missingKeys.isNotEmpty)
                    'missing=${reason.missingKeys.join(", ")}',
                ].join(' | ');
                final suffix = details.isEmpty ? '' : ' | $details';
                return '${reason.status}$intent: ${reason.reason}$suffix';
              }).toList(),
            ),
          if (state.missingKeys.isNotEmpty)
            PricingDetailsSection(
              title: 'Missing keys',
              values: state.missingKeys,
            ),
          if (state.actions.isNotEmpty)
            PricingDetailsSection(
              title: 'Recommended actions',
              values: state.actions,
            ),
        ],
      ),
    );
  }
}

class PricingDetailsSection extends StatelessWidget {
  final String title;
  final List<String> values;

  const PricingDetailsSection({
    super.key,
    required this.title,
    required this.values,
  });

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: AppSpacing.xs),
          ...values.map(
            (value) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: Text(
                value,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
