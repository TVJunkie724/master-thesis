import 'package:flutter/material.dart';

import '../domain/configuration_journey.dart';

class ConfigurationTaskSelector extends StatelessWidget {
  final ConfigurationJourney journey;
  final ValueChanged<ConfigurationTaskId> onTaskSelected;

  const ConfigurationTaskSelector({
    super.key,
    required this.journey,
    required this.onTaskSelected,
  });

  @override
  Widget build(BuildContext context) {
    final current = journey.task(journey.currentTaskId);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      child: MenuAnchor(
        menuChildren: [
          for (final phase in journey.phases) ...[
            _PhaseLabel(label: phase.label),
            for (final task in phase.tasks)
              MenuItemButton(
                leadingIcon: Icon(_icon(task.status), size: 18),
                onPressed: task.isNavigable
                    ? () => onTaskSelected(task.id)
                    : null,
                child: Text(
                  task.blockingReason == null
                      ? task.label
                      : '${task.label} - ${task.blockingReason}',
                ),
              ),
          ],
        ],
        builder: (context, controller, child) => OutlinedButton(
          onPressed: () {
            controller.isOpen ? controller.close() : controller.open();
          },
          style: OutlinedButton.styleFrom(
            minimumSize: const Size.fromHeight(48),
            alignment: Alignment.centerLeft,
          ),
          child: Row(
            children: [
              Icon(_icon(current.status), size: 20),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      journey.currentPhase.label,
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                    Text(current.label, overflow: TextOverflow.ellipsis),
                  ],
                ),
              ),
              const Icon(Icons.expand_more),
            ],
          ),
        ),
      ),
    );
  }
}

class _PhaseLabel extends StatelessWidget {
  final String label;

  const _PhaseLabel({required this.label});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
    child: Text(label, style: Theme.of(context).textTheme.labelMedium),
  );
}

IconData _icon(ConfigurationTaskStatus status) => switch (status) {
  ConfigurationTaskStatus.complete => Icons.check_circle,
  ConfigurationTaskStatus.current => Icons.radio_button_checked,
  ConfigurationTaskStatus.attention => Icons.error_outline,
  ConfigurationTaskStatus.available => Icons.circle_outlined,
  ConfigurationTaskStatus.blocked => Icons.lock_outline,
  ConfigurationTaskStatus.notRequired => Icons.remove_circle_outline,
};
