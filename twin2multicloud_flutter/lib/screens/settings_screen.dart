import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/docs_config.dart';
import '../models/cloud_connection.dart';
import '../bloc/cloud_access/cloud_access.dart';
import '../providers/theme_provider.dart';
import '../providers/twins_provider.dart';
import '../theme/spacing.dart';
import '../widgets/branded_app_bar.dart';
import '../widgets/cloud_connections/cloud_accounts_panel.dart';
import '../widgets/cloud_connections/cloud_connection_strings.dart';
import '../widgets/selectable_scaffold.dart';

typedef SetupGuideLauncher = Future<bool> Function(Uri uri);

class SettingsScreen extends ConsumerWidget {
  final SetupGuideLauncher setupGuideLauncher;

  const SettingsScreen({
    super.key,
    this.setupGuideLauncher = _launchSetupGuideExternally,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
        title: CloudConnectionStrings.cloudAccessTitle,
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
        ],
      ),
      body: _SettingsCloudAccessScope(setupGuideLauncher: setupGuideLauncher),
    );
  }
}

class _SettingsCloudAccessScope extends ConsumerStatefulWidget {
  final SetupGuideLauncher setupGuideLauncher;

  const _SettingsCloudAccessScope({required this.setupGuideLauncher});

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
      child: _SettingsContent(setupGuideLauncher: widget.setupGuideLauncher),
    );
  }
}

class _SettingsContent extends StatelessWidget {
  final SetupGuideLauncher setupGuideLauncher;

  const _SettingsContent({required this.setupGuideLauncher});

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
                  onOpenSetupGuide: (provider) =>
                      _openSetupGuide(context, provider),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _openSetupGuide(
    BuildContext context,
    CloudProvider provider,
  ) async {
    try {
      final opened = await setupGuideLauncher(
        Uri.parse(DocsConfig.getCloudSetupGuideUrl(provider.apiValue)),
      );
      if (opened) return;
    } catch (_) {
      // The user receives one provider-neutral, non-sensitive failure message.
    }
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Could not open the setup guide.')),
    );
  }
}

Future<bool> _launchSetupGuideExternally(Uri uri) =>
    launchUrl(uri, mode: LaunchMode.externalApplication);
