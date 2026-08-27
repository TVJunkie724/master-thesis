import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/user.dart';
import '../bloc/cloud_access/cloud_access.dart';
import '../providers/profile_provider.dart';
import '../providers/theme_provider.dart';
import '../providers/twins_provider.dart';
import '../theme/spacing.dart';
import '../widgets/branded_app_bar.dart';
import '../widgets/cloud_connections/cloud_accounts_panel.dart';
import '../widgets/selectable_scaffold.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profileState = ref.watch(profileProvider);
    final user = profileState.user;
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
          const CircleAvatar(child: Icon(Icons.person)),
          const SizedBox(width: AppSpacing.sm),
        ],
      ),
      body: user == null
          ? const Center(child: Text('Profile unavailable'))
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
                  connections: state.connections,
                  isLoading: state.isLoading,
                  loadError: state.loadError,
                  busyConnectionIds: state.busyConnectionIds,
                  isCreating: state.isCreating,
                  isImporting: state.isImporting,
                  onRetry: () => context.read<CloudAccessBloc>().add(
                    const CloudAccessReloadRequested(),
                  ),
                  onCreate: (request) => context.read<CloudAccessBloc>().add(
                    CloudAccessCreateRequested(request),
                  ),
                  onImport: (request) => context.read<CloudAccessBloc>().add(
                    CloudAccessImportRequested(request),
                  ),
                  onValidate: (connection) => context
                      .read<CloudAccessBloc>()
                      .add(CloudAccessValidateRequested(connection.id)),
                  onDelete: (connection) => context.read<CloudAccessBloc>().add(
                    CloudAccessDeleteRequested(connection.id),
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
              child: Text(
                _initialFor(user),
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onPrimaryContainer,
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
