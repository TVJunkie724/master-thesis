import 'package:flutter/material.dart';

import '../domain/configuration_journey.dart';

class ConfigurationTaskSidebar extends StatelessWidget {
  final ConfigurationJourney journey;
  final ValueChanged<ConfigurationTaskId> onTaskSelected;

  const ConfigurationTaskSidebar({
    super.key,
    required this.journey,
    required this.onTaskSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Configuration tasks',
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 16),
        itemCount: journey.phases.length,
        separatorBuilder: (_, _) => const SizedBox(height: 4),
        itemBuilder: (context, index) {
          final phase = journey.phases[index];
          final expanded = phase.id == journey.currentPhase.id;
          return _PhaseGroup(
            phase: phase,
            expanded: expanded,
            onTaskSelected: onTaskSelected,
          );
        },
      ),
    );
  }
}

class _PhaseGroup extends StatelessWidget {
  final ConfigurationPhase phase;
  final bool expanded;
  final ValueChanged<ConfigurationTaskId> onTaskSelected;

  const _PhaseGroup({
    required this.phase,
    required this.expanded,
    required this.onTaskSelected,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
          child: Row(
            children: [
              _PhaseStatusIcon(phase: phase),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  phase.label,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: expanded ? colors.primary : colors.onSurface,
                    fontWeight: expanded ? FontWeight.w700 : FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
        if (expanded)
          for (final task in phase.tasks)
            _TaskTile(task: task, onSelected: onTaskSelected),
      ],
    );
  }
}

class _PhaseStatusIcon extends StatelessWidget {
  final ConfigurationPhase phase;

  const _PhaseStatusIcon({required this.phase});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final (icon, color) = phase.complete
        ? (Icons.check_circle, colors.primary)
        : phase.requiresAttention
        ? (Icons.error_outline, colors.error)
        : (Icons.circle_outlined, colors.outline);
    return Icon(icon, size: 20, color: color);
  }
}

class _TaskTile extends StatelessWidget {
  final ConfigurationTask task;
  final ValueChanged<ConfigurationTaskId> onSelected;

  const _TaskTile({required this.task, required this.onSelected});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final selected = task.status == ConfigurationTaskStatus.current;
    final enabled = task.isNavigable;
    final description = task.blockingReason ?? _statusLabel(task.status);

    return Semantics(
      button: enabled,
      selected: selected,
      enabled: enabled,
      label: '${task.label}, $description',
      child: Tooltip(
        message: enabled ? '' : description,
        child: ListTile(
          dense: true,
          selected: selected,
          selectedTileColor: colors.primaryContainer,
          contentPadding: const EdgeInsets.only(left: 48, right: 16),
          leading: Icon(
            _statusIcon(task.status),
            size: 18,
            color: _statusColor(colors, task.status),
          ),
          title: Text(task.label, maxLines: 2, overflow: TextOverflow.ellipsis),
          subtitle: task.blockingReason == null
              ? null
              : Text(
                  task.blockingReason!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
          onTap: enabled ? () => onSelected(task.id) : null,
        ),
      ),
    );
  }
}

String _statusLabel(ConfigurationTaskStatus status) => switch (status) {
  ConfigurationTaskStatus.complete => 'Complete',
  ConfigurationTaskStatus.current => 'Current task',
  ConfigurationTaskStatus.attention => 'Needs attention',
  ConfigurationTaskStatus.available => 'Available',
  ConfigurationTaskStatus.blocked => 'Blocked',
  ConfigurationTaskStatus.notRequired => 'Not required',
};

IconData _statusIcon(ConfigurationTaskStatus status) => switch (status) {
  ConfigurationTaskStatus.complete => Icons.check_circle,
  ConfigurationTaskStatus.current => Icons.radio_button_checked,
  ConfigurationTaskStatus.attention => Icons.error_outline,
  ConfigurationTaskStatus.available => Icons.circle_outlined,
  ConfigurationTaskStatus.blocked => Icons.lock_outline,
  ConfigurationTaskStatus.notRequired => Icons.remove_circle_outline,
};

Color _statusColor(ColorScheme colors, ConfigurationTaskStatus status) =>
    switch (status) {
      ConfigurationTaskStatus.complete => colors.primary,
      ConfigurationTaskStatus.current => colors.primary,
      ConfigurationTaskStatus.attention => colors.error,
      ConfigurationTaskStatus.available => colors.outline,
      ConfigurationTaskStatus.blocked => colors.outlineVariant,
      ConfigurationTaskStatus.notRequired => colors.outlineVariant,
    };
