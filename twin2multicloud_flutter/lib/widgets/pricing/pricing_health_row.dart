import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/pricing_review_state.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

class PricingHealthRow extends StatelessWidget {
  final AsyncValue<PricingReviewStateResponse> reviewState;
  final VoidCallback onOpenReview;
  final VoidCallback onRetry;

  const PricingHealthRow({
    super.key,
    required this.reviewState,
    required this.onOpenReview,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return reviewState.when(
      data: (data) => _PricingHealthContent(
        providers: data.providers,
        onOpenReview: onOpenReview,
      ),
      loading: () => _PricingHealthShell(
        cards: _providers
            .map((provider) => _PricingHealthCard.loading(provider: provider))
            .toList(),
        onOpenReview: onOpenReview,
      ),
      error: (error, _) => Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            children: [
              const Icon(Icons.warning_amber, color: AppColors.warning),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Text(
                  'Pricing readiness could not be loaded.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              OutlinedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PricingHealthContent extends StatelessWidget {
  final Map<String, ProviderPricingReviewState> providers;
  final VoidCallback onOpenReview;

  const _PricingHealthContent({
    required this.providers,
    required this.onOpenReview,
  });

  @override
  Widget build(BuildContext context) {
    return _PricingHealthShell(
      cards: _providers
          .map(
            (provider) => _PricingHealthCard(
              provider: provider,
              state: providers[provider],
            ),
          )
          .toList(),
      onOpenReview: onOpenReview,
    );
  }
}

class _PricingHealthShell extends StatelessWidget {
  final List<Widget> cards;
  final VoidCallback onOpenReview;

  const _PricingHealthShell({required this.cards, required this.onOpenReview});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.price_check,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  'Pricing readiness',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const Spacer(),
                FilledButton.icon(
                  onPressed: onOpenReview,
                  icon: const Icon(Icons.manage_search),
                  label: const Text('Review pricing'),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            LayoutBuilder(
              builder: (context, constraints) {
                if (constraints.maxWidth < 760) {
                  return Column(
                    children: cards
                        .map(
                          (card) => Padding(
                            padding: const EdgeInsets.only(
                              bottom: AppSpacing.sm,
                            ),
                            child: card,
                          ),
                        )
                        .toList(),
                  );
                }

                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (var index = 0; index < cards.length; index++)
                      Expanded(
                        child: Padding(
                          padding: EdgeInsets.only(
                            right: index == cards.length - 1
                                ? 0
                                : AppSpacing.sm,
                          ),
                          child: cards[index],
                        ),
                      ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _PricingHealthCard extends StatelessWidget {
  final String provider;
  final ProviderPricingReviewState? state;
  final bool isLoading;

  const _PricingHealthCard({required this.provider, required this.state})
    : isLoading = false;

  const _PricingHealthCard.loading({required this.provider})
    : state = null,
      isLoading = true;

  @override
  Widget build(BuildContext context) {
    final providerColor = AppColors.getProviderColor(provider);
    final label = provider.toUpperCase();
    final badgeLabel = isLoading ? 'Loading' : (state?.badgeLabel ?? 'Unknown');
    final message = isLoading
        ? 'Checking pricing state'
        : (state?.primaryMessage ?? 'No pricing status available');
    final source = isLoading ? null : state?.sourceLabel;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        border: Border.all(color: providerColor.withAlpha(80)),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.cloud, color: providerColor, size: AppSpacing.lg),
              const SizedBox(width: AppSpacing.sm),
              Text(label, style: Theme.of(context).textTheme.labelLarge),
              const Spacer(),
              _StatusBadge(label: badgeLabel, state: state?.state),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(message, style: Theme.of(context).textTheme.bodySmall),
          if (source != null) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(
              source,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final String label;
  final String? state;

  const _StatusBadge({required this.label, required this.state});

  @override
  Widget build(BuildContext context) {
    final color = switch (state) {
      'fresh' => AppColors.success,
      'stale' => AppColors.warning,
      'review_required' => AppColors.warning,
      'missing' => AppColors.error,
      'failed' => AppColors.error,
      _ => Theme.of(context).colorScheme.outline,
    };

    return DecoratedBox(
      decoration: BoxDecoration(
        color: color.withAlpha(32),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.sm,
          vertical: AppSpacing.xs,
        ),
        child: Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: color,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

const _providers = ['aws', 'azure', 'gcp'];
