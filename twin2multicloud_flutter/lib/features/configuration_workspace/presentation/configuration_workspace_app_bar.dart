import 'package:flutter/material.dart';

import '../../../theme/colors.dart';
import '../../../theme/spacing.dart';
import '../../../widgets/branded_app_bar.dart';

class ConfigurationWorkspaceAppBar extends StatelessWidget
    implements PreferredSizeWidget {
  final bool isDarkMode;
  final bool navigationEnabled;
  final VoidCallback onToggleTheme;
  final VoidCallback onOpenSettings;
  final VoidCallback onLogout;

  const ConfigurationWorkspaceAppBar({
    super.key,
    required this.isDarkMode,
    this.navigationEnabled = true,
    required this.onToggleTheme,
    required this.onOpenSettings,
    required this.onLogout,
  });

  @override
  Size get preferredSize => const BrandedAppBar(title: '').preferredSize;

  @override
  Widget build(BuildContext context) {
    return BrandedAppBar(
      title: 'Twin2MultiCloud',
      actions: [
        IconButton(
          icon: Icon(isDarkMode ? Icons.light_mode : Icons.dark_mode),
          onPressed: onToggleTheme,
          tooltip: 'Toggle theme',
        ),
        const SizedBox(width: AppSpacing.sm),
        PopupMenuButton<_WorkspaceProfileAction>(
          enabled: navigationEnabled,
          offset: const Offset(0, AppSpacing.xxl + AppSpacing.sm),
          tooltip: navigationEnabled
              ? 'Profile menu'
              : 'Wait for the current command to finish',
          onSelected: (action) {
            switch (action) {
              case _WorkspaceProfileAction.settings:
                onOpenSettings();
              case _WorkspaceProfileAction.logout:
                onLogout();
            }
          },
          itemBuilder: (context) => const [
            PopupMenuItem(
              value: _WorkspaceProfileAction.settings,
              child: Row(
                children: [
                  Icon(Icons.settings, size: AppSpacing.iconMd),
                  SizedBox(width: AppSpacing.md - AppSpacing.xs),
                  Text('Settings'),
                ],
              ),
            ),
            PopupMenuDivider(),
            PopupMenuItem(
              value: _WorkspaceProfileAction.logout,
              child: Row(
                children: [
                  Icon(
                    Icons.logout,
                    size: AppSpacing.iconMd,
                    color: AppColors.error,
                  ),
                  SizedBox(width: AppSpacing.md - AppSpacing.xs),
                  Text('Logout', style: TextStyle(color: AppColors.error)),
                ],
              ),
            ),
          ],
          child: const Padding(
            padding: EdgeInsets.symmetric(horizontal: AppSpacing.sm),
            child: CircleAvatar(child: Icon(Icons.person)),
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
      ],
    );
  }
}

enum _WorkspaceProfileAction { settings, logout }
