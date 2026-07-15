import 'package:flutter/material.dart';

import '../../../theme/colors.dart';
import '../../../theme/spacing.dart';

enum WorkspaceExitChoice { discard, save }

enum WorkspaceInvalidationChoice { restore, proceed }

abstract final class ConfigurationWorkspaceDialogs {
  static Future<void> showUnconfiguredProviders(
    BuildContext context,
    Set<String> providers,
  ) {
    return showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        icon: const Icon(
          Icons.warning_amber,
          color: AppColors.warning,
          size: AppSpacing.xxl,
        ),
        title: const Text('Unconfigured Providers'),
        content: Text(
          'The following providers are required by your selected architecture '
          'but do not have deployment access:\n\n'
          '${providers.map((provider) => '• $provider').join('\n')}\n\n'
          'Open Cloud access and bind a valid deployment connection for each provider.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  static Future<WorkspaceExitChoice?> showInvalidatedExit(
    BuildContext context,
  ) {
    return showDialog<WorkspaceExitChoice>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const _WarningTitle(text: 'Configuration Changed'),
        content: const Text(
          'Your new calculation affects deployment preparation.\n\n'
          'If you save now, dependent deployment artifacts will be reset to '
          'match the new architecture.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () =>
                Navigator.pop(dialogContext, WorkspaceExitChoice.discard),
            child: const Text('Leave Without Saving'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(dialogContext, WorkspaceExitChoice.save),
            child: const Text('Save & Leave'),
          ),
        ],
      ),
    );
  }

  static Future<WorkspaceExitChoice?> showUnsavedExit(BuildContext context) {
    return showDialog<WorkspaceExitChoice>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Leave Wizard?'),
        content: const Text(
          'You have unsaved changes. What would you like to do?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () =>
                Navigator.pop(dialogContext, WorkspaceExitChoice.discard),
            child: const Text('Discard Changes'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(dialogContext, WorkspaceExitChoice.save),
            child: const Text('Save & Leave'),
          ),
        ],
      ),
    );
  }

  static Future<WorkspaceInvalidationChoice?> showInvalidationChoice(
    BuildContext context, {
    required bool canRestore,
  }) {
    return showDialog<WorkspaceInvalidationChoice>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const _WarningTitle(text: 'Configuration Changed'),
        content: Text(
          'Your new calculation has different parameters that may affect '
          'deployment preparation.\n\nWhat would you like to do?'
          '${!canRestore ? '\n\n(Discard not available - no saved version exists)' : ''}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          OutlinedButton(
            onPressed: canRestore
                ? () => Navigator.pop(
                    dialogContext,
                    WorkspaceInvalidationChoice.restore,
                  )
                : null,
            child: const Text('Discard Changes'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(
              dialogContext,
              WorkspaceInvalidationChoice.proceed,
            ),
            child: const Text('Keep New Results'),
          ),
        ],
      ),
    );
  }
}

class _WarningTitle extends StatelessWidget {
  final String text;

  const _WarningTitle({required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(
          Icons.warning_amber_rounded,
          color: AppColors.warning,
          size: AppSpacing.lg + AppSpacing.xs,
        ),
        const SizedBox(width: AppSpacing.md - AppSpacing.xs),
        Expanded(child: Text(text)),
      ],
    );
  }
}
