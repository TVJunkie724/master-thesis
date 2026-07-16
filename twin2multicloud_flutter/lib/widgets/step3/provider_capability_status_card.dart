import 'package:flutter/material.dart';

import '../../models/provider_capability.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

abstract final class ProviderCapabilityStrings {
  static const loading = 'Checking platform capability';
  static const loadingMessage =
      'Loading the current provider capability contract.';
  static const unavailable = 'Platform capability unavailable';
  static const unavailableMessage =
      'The capability contract could not be validated. Retry before configuring this layer.';
  static const retry = 'Retry';
  static const planned =
      'Future implementation is tracked; this path remains unavailable.';
}

class ProviderCapabilityStatusCard extends StatelessWidget {
  final String layer;
  final String provider;
  final PlatformLayerCapability? capability;
  final bool isLoading;
  final String? loadError;
  final VoidCallback onRetry;

  const ProviderCapabilityStatusCard({
    super.key,
    required this.layer,
    required this.provider,
    required this.capability,
    required this.isLoading,
    required this.loadError,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final state = capability?.availability;
    final accent = state == CapabilityAvailability.disabled
        ? AppColors.error
        : AppColors.warning;
    final title = isLoading
        ? ProviderCapabilityStrings.loading
        : capability == null
        ? ProviderCapabilityStrings.unavailable
        : '${provider.toUpperCase()} ${layer.toUpperCase()} ${state!.name}';
    final message = isLoading
        ? ProviderCapabilityStrings.loadingMessage
        : capability?.reason ??
              (loadError?.isNotEmpty == true
                  ? loadError!
                  : ProviderCapabilityStrings.unavailableMessage);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        border: Border.all(color: accent),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (isLoading)
            SizedBox.square(
              dimension: AppSpacing.iconMd,
              child: CircularProgressIndicator(
                strokeWidth: AppSpacing.xxs,
                color: accent,
              ),
            )
          else
            Icon(
              state == CapabilityAvailability.disabled
                  ? Icons.pause_circle_outline
                  : Icons.block,
              color: accent,
              size: AppSpacing.iconMd,
            ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.titleSmall?.copyWith(
                    color: accent,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(message, style: theme.textTheme.bodySmall),
                if (capability?.roadmap == CapabilityRoadmap.planned) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    ProviderCapabilityStrings.planned,
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
                if (!isLoading && capability == null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  TextButton.icon(
                    onPressed: onRetry,
                    icon: const Icon(Icons.refresh),
                    label: const Text(ProviderCapabilityStrings.retry),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
