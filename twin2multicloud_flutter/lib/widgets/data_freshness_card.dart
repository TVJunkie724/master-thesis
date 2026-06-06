import 'package:flutter/material.dart';

import '../models/pricing_review_state.dart';
import '../theme/colors.dart';
import '../theme/spacing.dart';

/// Card showing data freshness status for a cloud provider
class DataFreshnessCard extends StatelessWidget {
  final String provider;
  final String label; // e.g., 'Pricing', 'Regions'
  final Map<String, dynamic>? status;
  final ProviderPricingReviewState? reviewState;
  final VoidCallback? onRefresh;
  final bool enabled;
  final String? disabledReason;

  const DataFreshnessCard({
    super.key,
    required this.provider,
    this.label = 'Pricing',
    this.status,
    this.reviewState,
    this.onRefresh,
    this.enabled = true,
    this.disabledReason,
  });

  @override
  Widget build(BuildContext context) {
    // Optimizer API returns: age (string), status (schema validity), is_fresh (bool), threshold_days (int)
    final hasError =
        status?['error'] != null ||
        status?['status'] == 'error' ||
        status?['status'] == 'missing';
    final ageString =
        reviewState?.age ?? status?['age'] as String? ?? 'Unknown';
    final isFresh =
        reviewState?.state == 'fresh' ||
        (reviewState == null && (status?['is_fresh'] as bool? ?? false));
    final thresholdDays =
        reviewState?.thresholdDays ?? status?['threshold_days'] as int? ?? 7;

    final providerColor = AppColors.getProviderColor(provider);
    IconData providerIcon;
    switch (provider.toLowerCase()) {
      case 'aws':
        providerIcon = Icons.cloud;
        break;
      case 'azure':
        providerIcon = Icons.cloud_queue;
        break;
      case 'gcp':
        providerIcon = Icons.cloud_circle;
        break;
      default:
        providerIcon = Icons.cloud_outlined;
    }

    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with provider + label (e.g., "AWS PRICING")
            Row(
              children: [
                Icon(providerIcon, color: providerColor),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  '${provider.toUpperCase()} ${label.toUpperCase()}',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: providerColor,
                  ),
                ),
                const Spacer(),
                _buildStatusBadge(isFresh, hasError, reviewState),
              ],
            ),
            const SizedBox(height: AppSpacing.md),

            // Age info
            if (reviewState != null)
              _buildReviewStateDetails(
                context,
                reviewState!,
                ageString,
                thresholdDays,
              )
            else if (hasError)
              _buildDetailText(context, 'Error loading status', AppColors.error)
            else
              _buildLegacyDetails(context, ageString, thresholdDays),

            const SizedBox(height: AppSpacing.md),

            // Refresh button with disabled state
            SizedBox(
              width: double.infinity,
              child: Tooltip(
                message: enabled ? '' : (disabledReason ?? 'Refresh disabled'),
                child: OutlinedButton.icon(
                  onPressed: enabled ? onRefresh : null,
                  icon: Icon(
                    enabled ? Icons.refresh : Icons.lock_outline,
                    size: 16,
                  ),
                  label: const Text('Refresh'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: enabled ? providerColor : Colors.grey,
                    side: BorderSide(
                      color: enabled ? providerColor : Colors.grey.shade400,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBadge(
    bool isFresh,
    bool hasError,
    ProviderPricingReviewState? reviewState,
  ) {
    if (reviewState != null) {
      final color = _reviewStateColor(reviewState.state);
      return _badge(reviewState.badgeLabel, color);
    }

    if (hasError) {
      return _badge('Error', AppColors.error);
    }

    return _badge(
      isFresh ? 'Fresh' : 'Stale',
      isFresh ? AppColors.success : AppColors.warning,
    );
  }

  Widget _badge(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: color.withAlpha(32),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildReviewStateDetails(
    BuildContext context,
    ProviderPricingReviewState reviewState,
    String ageString,
    int thresholdDays,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildDetailText(
          context,
          reviewState.primaryMessage,
          reviewState.reviewRequired ? AppColors.warning : Colors.grey[700]!,
        ),
        const SizedBox(height: AppSpacing.xs),
        _buildDetailText(context, reviewState.sourceLabel, Colors.grey[600]!),
        const SizedBox(height: AppSpacing.xs),
        _buildDetailText(
          context,
          'Age: $ageString · Max age: $thresholdDays days',
          Colors.grey[500]!,
        ),
        if (reviewState.lastKnownGoodUpdatedAt != null) ...[
          const SizedBox(height: AppSpacing.xs),
          _buildDetailText(
            context,
            'Last-known-good: ${reviewState.lastKnownGoodUpdatedAt}',
            Colors.grey[500]!,
          ),
        ],
      ],
    );
  }

  Widget _buildLegacyDetails(
    BuildContext context,
    String ageString,
    int thresholdDays,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildDetailText(context, 'Age: $ageString', Colors.grey[600]!),
        const SizedBox(height: AppSpacing.xs),
        _buildDetailText(
          context,
          'Max age: $thresholdDays days',
          Colors.grey[500]!,
        ),
      ],
    );
  }

  Widget _buildDetailText(BuildContext context, String text, Color color) {
    return Text(
      text,
      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: color),
    );
  }

  Color _reviewStateColor(String state) {
    return switch (state) {
      'fresh' => AppColors.success,
      'stale' => AppColors.warning,
      'review_required' => AppColors.warning,
      'missing' => AppColors.error,
      'failed' => AppColors.error,
      _ => Colors.grey,
    };
  }
}
