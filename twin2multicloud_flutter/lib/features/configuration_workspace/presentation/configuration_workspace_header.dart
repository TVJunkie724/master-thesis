import 'package:flutter/material.dart';

import '../../../theme/spacing.dart';

class ConfigurationWorkspaceHeader extends StatelessWidget {
  final bool isCreateMode;
  final String phaseLabel;
  final String taskLabel;
  final VoidCallback? onClose;
  final String closeDisabledReason;

  const ConfigurationWorkspaceHeader({
    super.key,
    required this.isCreateMode,
    required this.phaseLabel,
    required this.taskLabel,
    required this.onClose,
    this.closeDisabledReason = '',
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: theme.scaffoldBackgroundColor,
        boxShadow: [
          BoxShadow(
            color: theme.shadowColor.withValues(alpha: 0.08),
            blurRadius: AppSpacing.sm,
            offset: const Offset(0, AppSpacing.xxs),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.md,
        ),
        child: Row(
          children: [
            Tooltip(
              message: onClose == null ? closeDisabledReason : 'Close',
              child: IconButton(
                icon: const Icon(Icons.close),
                onPressed: onClose,
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    isCreateMode ? 'Create Digital Twin' : 'Edit Digital Twin',
                    style: theme.textTheme.headlineSmall,
                  ),
                  const SizedBox(height: AppSpacing.xxs),
                  Text(
                    '$phaseLabel · $taskLabel',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
