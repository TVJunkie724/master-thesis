import 'package:flutter/material.dart';

import '../../models/cloud_access_inventory.dart';
import '../../models/pricing_health.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'pricing_review_strings.dart';

class PricingProviderWorkspace extends StatelessWidget {
  final String provider;
  final ProviderPricingHealth? health;
  final CloudAccessEntry? access;
  final bool isLoading;
  final bool isRefreshing;
  final bool canRefresh;
  final String? error;
  final String? reportError;
  final VoidCallback onRefresh;
  final VoidCallback onRetry;

  const PricingProviderWorkspace({
    super.key,
    required this.provider,
    required this.health,
    required this.access,
    required this.isLoading,
    required this.isRefreshing,
    required this.canRefresh,
    required this.error,
    required this.reportError,
    required this.onRefresh,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        border: Border.all(
          color: AppColors.getProviderColor(provider).withAlpha(80),
        ),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          LayoutBuilder(
            builder: (context, constraints) {
              final summary = _ProviderSummary(
                provider: provider,
                healthLabel: PricingReviewStrings.healthLabel(health?.state),
                accountLabel: PricingReviewStrings.accessLabel(access),
                isLoading: isLoading,
                canRefresh: canRefresh,
              );
              final button = FilledButton.icon(
                onPressed: canRefresh ? onRefresh : null,
                icon: isRefreshing
                    ? const SizedBox.square(
                        dimension: AppSpacing.iconSm,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh),
                label: Text(
                  isRefreshing
                      ? PricingReviewStrings.fetching
                      : PricingReviewStrings.refresh,
                ),
              );
              if (constraints.maxWidth <
                  AppSpacing.pricingReviewCardBreakpoint) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    summary,
                    const SizedBox(height: AppSpacing.sm),
                    button,
                  ],
                );
              }
              return Row(
                children: [
                  Expanded(child: summary),
                  const SizedBox(width: AppSpacing.md),
                  button,
                ],
              );
            },
          ),
          if (error != null) ...[
            const SizedBox(height: AppSpacing.sm),
            _CompactError(message: error!, onRetry: onRetry),
          ],
          if (health?.primaryMessage.isNotEmpty == true) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              health!.primaryMessage,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
          if (isRefreshing) ...[
            const SizedBox(height: AppSpacing.md),
            const LinearProgressIndicator(),
            const SizedBox(height: AppSpacing.xs),
            Text(
              PricingReviewStrings.fetchingMayTakeSeveralMinutes,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
          if (reportError != null) ...[
            const SizedBox(height: AppSpacing.sm),
            _CompactError(message: reportError!, onRetry: onRetry),
          ],
        ],
      ),
    );
  }
}

class _ProviderSummary extends StatelessWidget {
  final String provider;
  final String healthLabel;
  final String accountLabel;
  final bool isLoading;
  final bool canRefresh;

  const _ProviderSummary({
    required this.provider,
    required this.healthLabel,
    required this.accountLabel,
    required this.isLoading,
    required this.canRefresh,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(Icons.cloud, color: AppColors.getProviderColor(provider)),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                isLoading
                    ? PricingReviewStrings.loadingPricingAccess
                    : '$healthLabel · $accountLabel',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              if (!isLoading && !canRefresh)
                Text(
                  PricingReviewStrings.configurePricingAccess,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _CompactError extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _CompactError({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          Icons.warning_amber,
          color: Theme.of(context).colorScheme.error,
          size: AppSpacing.iconMd,
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(child: Text(message)),
        IconButton(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          tooltip: PricingReviewStrings.retry,
        ),
      ],
    );
  }
}
