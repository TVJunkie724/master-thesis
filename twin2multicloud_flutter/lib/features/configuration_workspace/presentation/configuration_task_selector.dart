import 'package:flutter/material.dart';

import '../../../theme/spacing.dart';
import '../domain/configuration_journey.dart';
import 'configuration_workspace_strings.dart';

class ConfigurationTaskSelector extends StatelessWidget {
  final ConfigurationJourney journey;
  final bool isEnabled;
  final ValueChanged<ConfigurationTaskId> onTaskSelected;

  const ConfigurationTaskSelector({
    super.key,
    required this.journey,
    required this.isEnabled,
    required this.onTaskSelected,
  });

  @override
  Widget build(BuildContext context) {
    final current = journey.task(journey.currentTaskId);
    final tasks = journey.currentPhase.tasks;
    final taskIndex = tasks.indexWhere((task) => task.id == current.id) + 1;
    final status = _statusLabel(current.status);
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.xs,
        AppSpacing.lg,
        AppSpacing.sm,
      ),
      child: Tooltip(
        message: isEnabled
            ? status
            : ConfigurationWorkspaceStrings.commandInProgress,
        child: MenuAnchor(
          menuChildren: [
            for (final task in tasks)
              MenuItemButton(
                leadingIcon: Icon(_icon(task.status), size: AppSpacing.iconMd),
                trailingIcon: task.id == current.id
                    ? const Icon(Icons.check, size: AppSpacing.iconMd)
                    : null,
                onPressed: isEnabled && task.isNavigable
                    ? () => onTaskSelected(task.id)
                    : null,
                child: _TaskMenuLabel(task: task),
              ),
          ],
          builder: (context, controller, child) => Semantics(
            button: true,
            enabled: isEnabled,
            label:
                '${ConfigurationWorkspaceStrings.taskPrefix}$taskIndex'
                '${ConfigurationWorkspaceStrings.ofSeparator}${tasks.length}, '
                '${current.label}, $status',
            child: ExcludeSemantics(
              child: OutlinedButton(
                onPressed: isEnabled
                    ? () {
                        controller.isOpen
                            ? controller.close()
                            : controller.open();
                      }
                    : null,
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(
                    AppSpacing.actionButtonHeight,
                  ),
                  alignment: Alignment.centerLeft,
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                ),
                child: Row(
                  children: [
                    Icon(_icon(current.status), size: AppSpacing.iconMd),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${ConfigurationWorkspaceStrings.taskPrefix}'
                            '$taskIndex'
                            '${ConfigurationWorkspaceStrings.ofSeparator}'
                            '${tasks.length}',
                            style: Theme.of(context).textTheme.labelSmall,
                          ),
                          Text(current.label),
                        ],
                      ),
                    ),
                    const Icon(Icons.expand_more),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TaskMenuLabel extends StatelessWidget {
  final ConfigurationTask task;

  const _TaskMenuLabel({required this.task});

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(task.label),
      if (task.blockingReason != null)
        Text(
          task.blockingReason!,
          style: Theme.of(context).textTheme.bodySmall,
        ),
    ],
  );
}

IconData _icon(ConfigurationTaskStatus status) => switch (status) {
  ConfigurationTaskStatus.complete => Icons.check_circle,
  ConfigurationTaskStatus.attention => Icons.error_outline,
  ConfigurationTaskStatus.available => Icons.circle_outlined,
  ConfigurationTaskStatus.blocked => Icons.lock_outline,
  ConfigurationTaskStatus.notRequired => Icons.remove_circle_outline,
};

String _statusLabel(ConfigurationTaskStatus status) => switch (status) {
  ConfigurationTaskStatus.complete => ConfigurationWorkspaceStrings.complete,
  ConfigurationTaskStatus.attention =>
    ConfigurationWorkspaceStrings.needsAttention,
  ConfigurationTaskStatus.available => ConfigurationWorkspaceStrings.available,
  ConfigurationTaskStatus.blocked => ConfigurationWorkspaceStrings.blocked,
  ConfigurationTaskStatus.notRequired =>
    ConfigurationWorkspaceStrings.notRequired,
};
