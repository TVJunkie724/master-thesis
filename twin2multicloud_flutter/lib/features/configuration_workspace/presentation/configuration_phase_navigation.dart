import 'package:flutter/material.dart';

import '../../../theme/spacing.dart';
import '../domain/configuration_journey.dart';
import 'configuration_workspace_strings.dart';

class ConfigurationPhaseNavigation extends StatelessWidget {
  final ConfigurationJourney journey;
  final bool isEnabled;
  final ValueChanged<ConfigurationTaskId> onTaskSelected;

  const ConfigurationPhaseNavigation({
    super.key,
    required this.journey,
    required this.isEnabled,
    required this.onTaskSelected,
  });

  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    label: ConfigurationWorkspaceStrings.configurationPhases,
    child: Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.sm,
        AppSpacing.lg,
        AppSpacing.xs,
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final textScale = MediaQuery.textScalerOf(context).scale(1);
          final compact =
              MediaQuery.sizeOf(context).width <
                  AppSpacing.maxContentWidthMedium ||
              textScale > AppSpacing.resolvedArchitectureWideTextScaleLimit;
          final buttons = <Widget>[
            for (var index = 0; index < journey.phases.length; index++)
              _PhaseButton(
                index: index,
                phase: journey.phases[index],
                currentTaskId: journey.currentTaskId,
                selected: journey.phases[index].id == journey.currentPhase.id,
                isEnabled: isEnabled,
                onTaskSelected: onTaskSelected,
              ),
          ];

          if (!compact) {
            return Row(
              children: [
                for (var index = 0; index < buttons.length; index++) ...[
                  if (index > 0) const SizedBox(width: AppSpacing.sm),
                  Expanded(child: buttons[index]),
                ],
              ],
            );
          }

          final itemWidth = (constraints.maxWidth - AppSpacing.sm) / 2;
          return Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              for (final button in buttons)
                SizedBox(width: itemWidth, child: button),
            ],
          );
        },
      ),
    ),
  );
}

class _PhaseButton extends StatelessWidget {
  final int index;
  final ConfigurationPhase phase;
  final ConfigurationTaskId currentTaskId;
  final bool selected;
  final bool isEnabled;
  final ValueChanged<ConfigurationTaskId> onTaskSelected;

  const _PhaseButton({
    required this.index,
    required this.phase,
    required this.currentTaskId,
    required this.selected,
    required this.isEnabled,
    required this.onTaskSelected,
  });

  @override
  Widget build(BuildContext context) {
    final target = phase.taskTarget(currentTaskId);
    final enabled = isEnabled && target != null;
    final status = _status(context, target);
    final blocker = target == null ? _blockingReason() : '';
    final tooltip = !isEnabled
        ? ConfigurationWorkspaceStrings.commandInProgress
        : enabled
        ? status.label
        : blocker;
    final selectionLabel = selected
        ? '${ConfigurationWorkspaceStrings.currentPhase}, '
        : '';
    final label =
        '${ConfigurationWorkspaceStrings.phasePrefix}${index + 1}, '
        '${phase.label}, $selectionLabel${status.label}';
    final colors = Theme.of(context).colorScheme;

    return Tooltip(
      message: tooltip,
      child: Semantics(
        button: true,
        selected: selected,
        enabled: enabled,
        label: label,
        child: ExcludeSemantics(
          child: OutlinedButton(
            onPressed: enabled ? () => onTaskSelected(target) : null,
            style: OutlinedButton.styleFrom(
              alignment: Alignment.centerLeft,
              minimumSize: const Size.fromHeight(AppSpacing.actionButtonHeight),
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm,
              ),
              backgroundColor: selected ? colors.primaryContainer : null,
              foregroundColor: selected ? colors.onPrimaryContainer : null,
            ),
            child: Row(
              children: [
                Icon(status.icon, size: AppSpacing.iconMd, color: status.color),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    '${index + 1}. ${phase.label}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  ({IconData icon, String label, Color color}) _status(
    BuildContext context,
    ConfigurationTaskId? target,
  ) {
    final colors = Theme.of(context).colorScheme;
    if (phase.complete) {
      return (
        icon: Icons.check_circle,
        label: ConfigurationWorkspaceStrings.complete,
        color: colors.primary,
      );
    }
    if (phase.requiresAttention) {
      return (
        icon: Icons.error_outline,
        label: ConfigurationWorkspaceStrings.needsAttention,
        color: colors.error,
      );
    }
    if (target == null) {
      return (
        icon: Icons.lock_outline,
        label: ConfigurationWorkspaceStrings.blocked,
        color: colors.outlineVariant,
      );
    }
    return (
      icon: Icons.circle_outlined,
      label: ConfigurationWorkspaceStrings.available,
      color: colors.outline,
    );
  }

  String _blockingReason() {
    for (final task in phase.tasks) {
      final reason = task.blockingReason;
      if (reason != null && reason.isNotEmpty) return reason;
    }
    return ConfigurationWorkspaceStrings.completeEarlierPhases;
  }
}
