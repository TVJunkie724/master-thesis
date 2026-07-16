import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/user.dart';
import '../bloc/cloud_access/cloud_access.dart';
import '../providers/auth_provider.dart';
import '../providers/theme_provider.dart';
import '../providers/twins_provider.dart';
import '../theme/colors.dart';
import '../theme/spacing.dart';
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
            onSelected: (value) async {
              if (value == 'logout') {
                await ref.read(authProvider.notifier).logout();
                if (context.mounted) context.go('/login');
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
          : _SettingsCloudAccessScope(user: user),
    );
  }
}

class _SettingsCloudAccessScope extends ConsumerStatefulWidget {
  final User user;

  const _SettingsCloudAccessScope({required this.user});

  @override
  ConsumerState<_SettingsCloudAccessScope> createState() =>
      _SettingsCloudAccessScopeState();
}

class _SettingsCloudAccessScopeState
    extends ConsumerState<_SettingsCloudAccessScope> {
  late final CloudAccessBloc _cloudAccessBloc;

  @override
  void initState() {
    super.initState();
    _cloudAccessBloc = CloudAccessBloc(ref.read(apiServiceProvider))
      ..add(const CloudAccessStarted());
  }

  @override
  void dispose() {
    _cloudAccessBloc.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider.value(
      value: _cloudAccessBloc,
      child: _SettingsContent(user: widget.user),
    );
  }
}

class _SettingsContent extends StatelessWidget {
  final User user;

  const _SettingsContent({required this.user});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppSpacing.maxContentWidthLarge,
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
              BlocConsumer<CloudAccessBloc, CloudAccessState>(
                listenWhen: (previous, current) =>
                    previous.feedback != current.feedback &&
                    current.feedback != null,
                listener: (context, state) {
                  final feedback = state.feedback!;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(feedback.message),
                      backgroundColor: feedback.isError
                          ? Theme.of(context).colorScheme.error
                          : null,
                    ),
                  );
                  context.read<CloudAccessBloc>().add(
                    const CloudAccessFeedbackCleared(),
                  );
                },
                builder: (context, state) => CloudAccountsPanel(
                  inventory: state.inventory,
                  isLoading: state.isLoading,
                  loadError: state.loadError,
                  busyConnectionIds: state.busyConnectionIds,
                  isCreating: state.isCreating,
                  onRetry: () => context.read<CloudAccessBloc>().add(
                    const CloudAccessReloadRequested(),
                  ),
                  onCreate: (request) => context.read<CloudAccessBloc>().add(
                    CloudAccessCreateRequested(request),
                  ),
                  onValidate: (entry) => context.read<CloudAccessBloc>().add(
                    CloudAccessValidateRequested(entry.connectionId!),
                  ),
                  onSetDefault: (entry) => context.read<CloudAccessBloc>().add(
                    CloudAccessDefaultRequested(entry.connectionId!),
                  ),
                  onDelete: (entry) => context.read<CloudAccessBloc>().add(
                    CloudAccessDeleteRequested(entry.connectionId!),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
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
              radius: AppSpacing.profileAvatarRadius,
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
