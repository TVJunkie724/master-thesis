import 'package:flutter/material.dart';

import '../../../theme/spacing.dart';
import 'configuration_workspace_strings.dart';

class ConfigurationWorkspaceHeader extends StatelessWidget {
  final int phaseIndex;
  final int phaseCount;
  final String phaseLabel;
  final String taskLabel;
  final VoidCallback? onClose;
  final String closeDisabledReason;

  const ConfigurationWorkspaceHeader({
    super.key,
    required this.phaseIndex,
    required this.phaseCount,
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
        border: Border(bottom: BorderSide(color: theme.dividerColor)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.md,
        ),
        child: Row(
          children: [
            Tooltip(
              message: onClose == null
                  ? closeDisabledReason
                  : ConfigurationWorkspaceStrings.backToExperiments,
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
                    ConfigurationWorkspaceStrings.configureExperiment,
                    style: theme.textTheme.headlineSmall,
                  ),
                  const SizedBox(height: AppSpacing.xxs),
                  Text(
                    '${ConfigurationWorkspaceStrings.phasePrefix}$phaseIndex'
                    '${ConfigurationWorkspaceStrings.ofSeparator}$phaseCount'
                    ' · $phaseLabel · $taskLabel',
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
