import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/user.dart';
import '../providers/auth_provider.dart';
import '../providers/theme_provider.dart';
import '../providers/twins_provider.dart';
import '../theme/colors.dart';
import '../theme/spacing.dart';
import '../utils/api_error_handler.dart';
import '../widgets/branded_app_bar.dart';
import '../widgets/cloud_connections/cloud_accounts_panel.dart';
import '../widgets/selectable_scaffold.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final user = authState.user;
    final backButton = IconButton(
      icon: const Icon(Icons.arrow_back),
      tooltip: 'Back',
      onPressed: () {
        if (context.canPop()) {
          context.pop();
        } else {
          context.go('/dashboard');
        }
      },
    );

    return SelectableScaffold(
      appBar: BrandedAppBar(
        title: 'Settings',
        showLogo: false,
        leading: backButton,
        actions: [
          IconButton(
            icon: Icon(
              ref.watch(themeProvider) == ThemeMode.dark
                  ? Icons.light_mode
                  : Icons.dark_mode,
            ),
            onPressed: () => ref.read(themeProvider.notifier).toggle(),
            tooltip: 'Toggle theme',
          ),
          const SizedBox(width: AppSpacing.sm),
          PopupMenuButton<String>(
            offset: const Offset(0, AppSpacing.actionButtonHeight),
            tooltip: 'Profile menu',
            onSelected: (value) {
              if (value == 'logout') {
                ref.read(authProvider.notifier).logout();
                context.go('/login');
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'settings',
                enabled: false,
                child: Row(
                  children: [
                    Icon(Icons.settings, size: AppSpacing.iconMd),
                    SizedBox(width: AppSpacing.md),
                    Text('Settings'),
                  ],
                ),
              ),
              const PopupMenuDivider(),
              PopupMenuItem(
                value: 'logout',
                child: Row(
                  children: [
                    const Icon(
                      Icons.logout,
                      size: AppSpacing.iconMd,
                      color: AppColors.error,
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Text(
                      'Logout',
                      style: Theme.of(
                        context,
                      ).textTheme.bodyMedium?.copyWith(color: AppColors.error),
                    ),
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
      ),
      body: user == null
          ? const Center(child: Text('Not logged in'))
          : _SettingsContent(user: user),
    );
  }
}

class _SettingsContent extends ConsumerWidget {
  final User user;

  const _SettingsContent({required this.user});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cloudConnections = ref.watch(cloudConnectionsProvider);

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppSpacing.maxContentWidthMedium,
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _ProfileSection(user: user),
              const SizedBox(height: AppSpacing.xl),
              _LoginAccountsSection(user: user),
              const SizedBox(height: AppSpacing.xl),
              CloudAccountsPanel(
                connections: cloudConnections,
                onRetry: () => ref.invalidate(cloudConnectionsProvider),
                onCreate: (request) => _runCloudAccountAction(
                  context,
                  ref,
                  successMessage:
                      '${request.provider.label} Cloud Connection created.',
                  action: () => ref
                      .read(apiServiceProvider)
                      .createCloudConnection(request),
                ),
                onValidate: (connection) => _runCloudAccountAction(
                  context,
                  ref,
                  successMessage:
                      '${connection.displayName} validation completed.',
                  action: () => ref
                      .read(apiServiceProvider)
                      .validateCloudConnection(connection.id),
                ),
                onDelete: (connection) => _runCloudAccountAction(
                  context,
                  ref,
                  successMessage: '${connection.displayName} deleted.',
                  action: () => ref
                      .read(apiServiceProvider)
                      .deleteCloudConnection(connection.id),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _runCloudAccountAction(
    BuildContext context,
    WidgetRef ref, {
    required String successMessage,
    required Future<void> Function() action,
  }) async {
    try {
      await action();
      ref.invalidate(cloudConnectionsProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(successMessage)));
      }
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(ApiErrorHandler.extractMessage(error))),
        );
      }
    }
  }
}

class _ProfileSection extends StatelessWidget {
  final User user;

  const _ProfileSection({required this.user});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Row(
          children: [
            CircleAvatar(
              radius: AppSpacing.terminalLogHeight / 6,
              backgroundColor: Theme.of(context).colorScheme.primaryContainer,
              foregroundImage: user.pictureUrl == null
                  ? null
                  : NetworkImage(user.pictureUrl!),
              child: user.pictureUrl != null
                  ? null
                  : Text(
                      _initialFor(user),
                      style: Theme.of(context).textTheme.headlineMedium
                          ?.copyWith(
                            color: Theme.of(
                              context,
                            ).colorScheme.onPrimaryContainer,
                          ),
                    ),
            ),
            const SizedBox(width: AppSpacing.lg),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    user.name ?? 'Unknown User',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    user.email,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  _AuthProviderBadge(provider: user.authProvider),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _initialFor(User user) {
    final name = user.name?.trim();
    if (name != null && name.isNotEmpty) return name[0].toUpperCase();
    return user.email.isNotEmpty ? user.email[0].toUpperCase() : '?';
  }
}

class _AuthProviderBadge extends StatelessWidget {
  final String provider;

  const _AuthProviderBadge({required this.provider});

  @override
  Widget build(BuildContext context) {
    final isGoogle = provider == 'google';
    final color = isGoogle ? AppColors.azure : Theme.of(context).primaryColor;
    final icon = isGoogle ? Icons.g_mobiledata : Icons.school;
    final label = isGoogle ? 'Google Account' : 'UIBK Account';

    return DecoratedBox(
      decoration: BoxDecoration(
        color: color.withAlpha(30),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
        border: Border.all(color: color.withAlpha(100)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: AppSpacing.iconMd, color: color),
            const SizedBox(width: AppSpacing.sm),
            Text(
              'Logged in with $label',
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: color,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LoginAccountsSection extends StatelessWidget {
  final User user;

  const _LoginAccountsSection({required this.user});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Login Accounts',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Account linking is shown as read-only until OAuth linking is '
              'implemented in the Management API.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            _AccountLinkRow(
              icon: Icons.g_mobiledata,
              label: 'Google',
              isLinked: user.googleLinked || user.authProvider == 'google',
              color: AppColors.azure,
            ),
            const Divider(height: AppSpacing.xl),
            _AccountLinkRow(
              icon: Icons.school,
              label: 'UIBK (University of Innsbruck)',
              isLinked: user.uibkLinked || user.authProvider == 'uibk',
              color: Theme.of(context).primaryColor,
            ),
          ],
        ),
      ),
    );
  }
}

class _AccountLinkRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isLinked;
  final Color color;

  const _AccountLinkRow({
    required this.icon,
    required this.label,
    required this.isLinked,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        DecoratedBox(
          decoration: BoxDecoration(
            color: color.withAlpha(30),
            borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
          ),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.sm),
            child: Icon(icon, color: color),
          ),
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: Theme.of(context).textTheme.titleSmall),
              Text(
                isLinked ? 'Connected' : 'Not connected',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: isLinked
                      ? AppColors.success
                      : Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        Icon(
          isLinked ? Icons.check_circle : Icons.radio_button_unchecked,
          color: isLinked
              ? AppColors.success
              : Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ],
    );
  }
}
