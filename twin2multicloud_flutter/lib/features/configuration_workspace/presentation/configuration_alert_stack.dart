import 'package:flutter/material.dart';

import '../../../theme/colors.dart';
import '../../../theme/spacing.dart';

class ConfigurationAlertStack extends StatelessWidget {
  final String? errorMessage;
  final String? successMessage;
  final String? warningMessage;
  final VoidCallback onDismissError;
  final VoidCallback onDismissNotification;

  const ConfigurationAlertStack({
    super.key,
    required this.errorMessage,
    required this.successMessage,
    required this.warningMessage,
    required this.onDismissError,
    required this.onDismissNotification,
  });

  @override
  Widget build(BuildContext context) {
    if (errorMessage != null) {
      return _ConfigurationAlertBanner(
        message: errorMessage!,
        kind: _ConfigurationAlertKind.error,
        onDismiss: onDismissError,
      );
    }
    if (successMessage != null) {
      return _ConfigurationAlertBanner(
        message: successMessage!,
        kind: _ConfigurationAlertKind.success,
        onDismiss: onDismissNotification,
      );
    }
    if (warningMessage != null) {
      return _ConfigurationAlertBanner(
        message: warningMessage!,
        kind: _ConfigurationAlertKind.warning,
        onDismiss: onDismissNotification,
      );
    }
    return const SizedBox.shrink();
  }
}

class _ConfigurationAlertBanner extends StatelessWidget {
  final String message;
  final _ConfigurationAlertKind kind;
  final VoidCallback onDismiss;

  const _ConfigurationAlertBanner({
    required this.message,
    required this.kind,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final foreground = switch (kind) {
      _ConfigurationAlertKind.error => theme.colorScheme.error,
      _ConfigurationAlertKind.success => AppColors.success,
      _ConfigurationAlertKind.warning => AppColors.warning,
    };
    final icon = switch (kind) {
      _ConfigurationAlertKind.error => Icons.error,
      _ConfigurationAlertKind.success => Icons.check_circle,
      _ConfigurationAlertKind.warning => Icons.warning_amber_rounded,
    };

    return Semantics(
      liveRegion: true,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.md - AppSpacing.xs,
        ),
        decoration: BoxDecoration(
          color: foreground.withValues(alpha: 0.12),
          boxShadow: [
            BoxShadow(
              color: theme.shadowColor.withValues(alpha: 0.08),
              blurRadius: AppSpacing.sm - AppSpacing.xxs,
              offset: const Offset(0, AppSpacing.xxs),
            ),
          ],
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppSpacing.maxContentWidthLarge,
            ),
            child: Row(
              children: [
                Icon(icon, color: foreground),
                const SizedBox(width: AppSpacing.md - AppSpacing.xs),
                Expanded(
                  child: Text(
                    message,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: foreground,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                IconButton(
                  icon: Icon(
                    Icons.close,
                    color: foreground,
                    size: AppSpacing.iconMd,
                  ),
                  onPressed: onDismiss,
                  tooltip: 'Dismiss',
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

enum _ConfigurationAlertKind { error, success, warning }
