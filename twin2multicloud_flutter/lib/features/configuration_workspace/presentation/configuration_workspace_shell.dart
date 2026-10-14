import 'package:flutter/material.dart';

import '../domain/configuration_journey.dart';
import 'configuration_phase_navigation.dart';
import 'configuration_task_selector.dart';

class ConfigurationWorkspaceShell extends StatelessWidget {
  final ConfigurationJourney journey;
  final bool isNavigationEnabled;
  final ValueChanged<ConfigurationTaskId> onTaskSelected;
  final Widget child;

  const ConfigurationWorkspaceShell({
    super.key,
    required this.journey,
    required this.isNavigationEnabled,
    required this.onTaskSelected,
    required this.child,
  });

  @override
  Widget build(BuildContext context) => Column(
    children: [
      ConfigurationPhaseNavigation(
        journey: journey,
        isEnabled: isNavigationEnabled,
        onTaskSelected: onTaskSelected,
      ),
      ConfigurationTaskSelector(
        journey: journey,
        isEnabled: isNavigationEnabled,
        onTaskSelected: onTaskSelected,
      ),
      const Divider(height: 1),
      Expanded(child: child),
    ],
  );
}
