import 'package:flutter/material.dart';

import '../../models/pricing_health.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

class PricingReadinessSummary extends StatelessWidget {
  static const _providers = ['aws', 'azure', 'gcp'];

  final PricingHealthResponse? health;
  final bool isLoading;
  final String? error;
  final VoidCallback onRetry;

  const PricingReadinessSummary({
    super.key,
    required this.health,
    required this.isLoading,
    required this.error,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final unsupportedContract =
        health != null &&
        health!.schemaVersion != PricingHealthResponse.supportedSchemaVersion;
    final contractIncomplete =
        health != null &&
        _providers.any((provider) => health!.provider(provider) == null);
    final contractUnavailable = unsupportedContract || contractIncomplete;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.price_check_outlined),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    'Pricing readiness',
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                if (isLoading)
                  const SizedBox.square(
                    dimension: AppSpacing.iconMd,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                if ((error != null || contractUnavailable) && !isLoading)
                  IconButton(
                    onPressed: onRetry,
                    icon: const Icon(Icons.refresh),
                    tooltip: 'Retry pricing readiness',
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            if (error != null)
              Text(
                error!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.error,
                ),
              )
            else if (health == null)
              Text(
                isLoading
                    ? 'Checking calculation pricing...'
                    : 'Pricing readiness is unavailable.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              )
            else ...[
              LayoutBuilder(
                builder: (context, constraints) {
                  final stack =
                      constraints.maxWidth <
                      AppSpacing.pricingReviewCardBreakpoint;
                  final width = stack
                      ? constraints.maxWidth
                      : (constraints.maxWidth - (AppSpacing.sm * 2)) / 3;
                  return Wrap(
                    spacing: AppSpacing.sm,
                    runSpacing: AppSpacing.sm,
                    children: _providers
                        .map(
                          (provider) => SizedBox(
                            width: width,
                            child: _ProviderReadiness(
                              provider: provider,
                              health: health!.provider(provider),
                            ),
                          ),
                        )
                        .toList(growable: false),
                  );
                },
              ),
              if (contractUnavailable) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  unsupportedContract
                      ? 'Pricing readiness contract is not supported.'
                      : 'Pricing readiness response is incomplete.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.error,
                  ),
                ),
              ],
            ],
            const SizedBox(height: AppSpacing.sm),
            Text(
              _footerMessage,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  String get _footerMessage {
    final providers = health?.providers.values ?? const [];
    final usesStaticFallback = providers.any(
      (provider) => provider.calculationSource == 'fallback_static',
    );
    if (usesStaticFallback) {
      return 'Pricing is managed from the Dashboard. Calculation uses static fallback pricing where shown.';
    }
    final usesLastKnownGood = providers.any(
      (provider) => provider.calculationSource == 'last_known_good',
    );
    if (usesLastKnownGood) {
      return 'Pricing is managed from the Dashboard. Calculation uses last-known-good pricing where shown.';
    }
    return 'Pricing is managed from the Dashboard.';
  }
}

class _ProviderReadiness extends StatelessWidget {
  final String provider;
  final ProviderPricingHealth? health;

  const _ProviderReadiness({required this.provider, required this.health});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = health?.state ?? 'missing';
    final color = _statusColor(status);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(_statusIcon(status), size: AppSpacing.iconMd, color: color),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${provider.toUpperCase()}  ${_statusLabel(status)}',
                style: theme.textTheme.labelLarge?.copyWith(color: color),
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                health?.sourceLabel.isNotEmpty == true
                    ? health!.sourceLabel
                    : 'No pricing source',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              if (health?.canCalculate == false) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(
                  health!.primaryMessage.isEmpty
                      ? 'Calculation unavailable'
                      : health!.primaryMessage,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.error,
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

String _statusLabel(String status) => switch (status) {
  'fresh' => 'Fresh',
  'stale' => 'Stale',
  'review_required' => 'Review',
  'failed' => 'Failed',
  _ => 'Missing',
};

IconData _statusIcon(String status) => switch (status) {
  'fresh' => Icons.check_circle_outline,
  'stale' || 'review_required' => Icons.warning_amber_outlined,
  _ => Icons.error_outline,
};

Color _statusColor(String status) => switch (status) {
  'fresh' => AppColors.success,
  'stale' || 'review_required' => AppColors.warning,
  _ => AppColors.error,
};
