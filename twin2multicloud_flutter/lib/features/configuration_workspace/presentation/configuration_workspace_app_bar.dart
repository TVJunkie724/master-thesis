import 'package:flutter/material.dart';

import '../../../theme/spacing.dart';
import '../../../widgets/branded_app_bar.dart';
import 'configuration_workspace_strings.dart';

class ConfigurationWorkspaceAppBar extends StatelessWidget
    implements PreferredSizeWidget {
  final bool isDarkMode;
  final bool navigationEnabled;
  final VoidCallback onToggleTheme;
  final VoidCallback onOpenCloudAccess;

  const ConfigurationWorkspaceAppBar({
    super.key,
    required this.isDarkMode,
    this.navigationEnabled = true,
    required this.onToggleTheme,
    required this.onOpenCloudAccess,
  });

  @override
  Size get preferredSize => const BrandedAppBar(title: '').preferredSize;

  @override
  Widget build(BuildContext context) {
    return BrandedAppBar(
      title: ConfigurationWorkspaceStrings.appTitle,
      actions: [
        IconButton(
          icon: Icon(isDarkMode ? Icons.light_mode : Icons.dark_mode),
          onPressed: onToggleTheme,
          tooltip: ConfigurationWorkspaceStrings.toggleThemeTooltip,
        ),
        const SizedBox(width: AppSpacing.sm),
        IconButton(
          onPressed: navigationEnabled ? onOpenCloudAccess : null,
          icon: const Icon(Icons.cloud_outlined),
          tooltip: navigationEnabled
              ? ConfigurationWorkspaceStrings.openCloudAccess
              : ConfigurationWorkspaceStrings.commandInProgress,
        ),
        const SizedBox(width: AppSpacing.sm),
      ],
    );
  }
}
