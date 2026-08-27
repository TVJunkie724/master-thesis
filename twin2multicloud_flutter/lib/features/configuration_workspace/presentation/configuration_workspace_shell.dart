import 'package:flutter/material.dart';

import '../../../theme/spacing.dart';
import '../domain/configuration_journey.dart';
import 'configuration_task_selector.dart';
import 'configuration_task_sidebar.dart';

class ConfigurationWorkspaceShell extends StatelessWidget {
  final ConfigurationJourney journey;
  final ValueChanged<ConfigurationTaskId> onTaskSelected;
  final Widget child;

  const ConfigurationWorkspaceShell({
    super.key,
    required this.journey,
    required this.onTaskSelected,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < AppSpacing.workspaceSidebarBreakpoint) {
          return Column(
            children: [
              ConfigurationTaskSelector(
                journey: journey,
                onTaskSelected: onTaskSelected,
              ),
              const Divider(height: 1),
              Expanded(child: child),
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: AppSpacing.workspaceSidebarWidth,
              child: ConfigurationTaskSidebar(
                journey: journey,
                onTaskSelected: onTaskSelected,
              ),
            ),
            const VerticalDivider(width: 1),
            Expanded(child: child),
          ],
        );
      },
    );
  }
}
