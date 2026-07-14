import 'package:flutter/material.dart';

import '../../theme/spacing.dart';
import '../../utils/twin_state_utils.dart';

class TwinOverviewNavigationHeader extends StatelessWidget {
  final String twinState;
  final bool canEdit;
  final bool canDelete;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  const TwinOverviewNavigationHeader({
    super.key,
    required this.twinState,
    required this.canEdit,
    required this.canDelete,
    required this.onEdit,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final actions = Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.sm,
      children: [
        Tooltip(
          message: canEdit
              ? 'Edit configuration'
              : 'Cannot edit deployed twin - destroy resources first',
          child: OutlinedButton.icon(
            onPressed: canEdit ? onEdit : null,
            icon: const Icon(Icons.edit),
            label: const Text('Edit'),
          ),
        ),
        Tooltip(
          message: canDelete
              ? 'Delete twin'
              : 'Destroy cloud resources before deleting',
          child: OutlinedButton.icon(
            onPressed: canDelete ? onDelete : null,
            icon: const Icon(Icons.delete_outline),
            label: const Text('Delete'),
            style: OutlinedButton.styleFrom(
              foregroundColor: theme.colorScheme.error,
            ),
          ),
        ),
      ],
    );

    return LayoutBuilder(
      builder: (context, constraints) {
        final status = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TwinStateUtils.buildBadge(context, twinState),
            const SizedBox(height: AppSpacing.xs),
            Text(
              TwinStateUtils.getDescription(twinState),
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        );
        if (constraints.maxWidth < AppSpacing.twinOverviewCompactBreakpoint) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              status,
              const SizedBox(height: AppSpacing.sm),
              actions,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: status),
            const SizedBox(width: AppSpacing.md),
            actions,
          ],
        );
      },
    );
  }
}
