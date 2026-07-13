// lib/screens/twin_overview/twin_overview_screen.dart
// Overview page for configured Digital Twins (Phase 2 implementation)

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../bloc/twin_overview/twin_overview_bloc.dart';
import '../../bloc/twin_overview/twin_overview_event.dart';
import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../bloc/deployment_verification/deployment_verification.dart';
import '../../providers/twins_provider.dart';
import '../../providers/theme_provider.dart';
import '../../utils/file_download_utils.dart';
import '../../widgets/branded_app_bar.dart';
import '../../widgets/code_viewer_dialog.dart';
import '../../widgets/selectable_scaffold.dart';
import '../../widgets/deployment_verification_card.dart';
import '../../widgets/twin_overview/twin_overview_code_artifact.dart';
import '../../widgets/twin_overview/twin_overview_command_center.dart';
import '../../widgets/twin_overview/twin_overview_configuration_review.dart';
import '../../widgets/twin_overview/twin_overview_name_header.dart';

/// Twin Overview Screen - Entry point with BlocProvider
class TwinOverviewScreen extends ConsumerWidget {
  final String twinId;

  const TwinOverviewScreen({super.key, required this.twinId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.read(apiServiceProvider);
    final logStreamClientFactory = ref.read(logStreamClientFactoryProvider);

    return BlocProvider(
      create: (context) => TwinOverviewBloc(
        api: api,
        logStreamClientFactory: logStreamClientFactory,
      )..add(TwinOverviewLoad(twinId)),
      child: TwinOverviewView(twinId: twinId),
    );
  }
}

/// Main view consuming BLoC state
class TwinOverviewView extends ConsumerWidget {
  final String twinId;

  const TwinOverviewView({super.key, required this.twinId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MultiBlocListener(
      listeners: [
        // Navigate after delete
        BlocListener<TwinOverviewBloc, TwinOverviewState>(
          listenWhen: (prev, curr) =>
              curr is TwinOverviewLoaded && curr.successMessage == 'deleted',
          listener: (context, state) {
            context.go('/dashboard');
          },
        ),
        // Handle simulator bytes - trigger save dialog
        BlocListener<TwinOverviewBloc, TwinOverviewState>(
          listenWhen: (prev, curr) =>
              curr is TwinOverviewLoaded &&
              curr.simulatorBytes != null &&
              (prev is! TwinOverviewLoaded || prev.simulatorBytes == null),
          listener: (context, state) async {
            if (state is! TwinOverviewLoaded || state.simulatorBytes == null) {
              return;
            }
            final l1 = (state.cheapestPath?['l1'] as String?) ?? 'unknown';
            final name = state.cloudResourceName ?? state.projectName;
            final filename = 'simulator_${name}_$l1.zip';

            final result = await saveBinaryFile(
              bytes: state.simulatorBytes!,
              suggestedName: filename,
            );

            if (!context.mounted) return;
            final bloc = context.read<TwinOverviewBloc>();
            if (result.success) {
              bloc.add(
                TwinOverviewShowMessage(result.message!, MessageType.success),
              );
            } else if (!result.cancelled && result.error != null) {
              bloc.add(
                TwinOverviewShowMessage(result.error!, MessageType.error),
              );
            }
            bloc.add(const TwinOverviewClearSimulatorBytes());
          },
        ),
      ],
      child: BlocBuilder<TwinOverviewBloc, TwinOverviewState>(
        builder: (context, state) {
          return SelectableScaffold(
            appBar: _buildAppBar(context, ref),
            body: Column(
              children: [
                // Header section with back button and twin name
                _buildHeader(context, state),
                // Alert banners for messages
                _buildAlertBanners(context, state),
                // Main content
                Expanded(child: _buildBody(context, state, ref)),
              ],
            ),
          );
        },
      ),
    );
  }

  PreferredSizeWidget _buildAppBar(BuildContext context, WidgetRef ref) {
    return BrandedAppBar(
      title: 'Twin2MultiCloud',
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
        const SizedBox(width: 8),
      ],
    );
  }

  Widget _buildHeader(BuildContext context, TwinOverviewState state) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: BoxDecoration(
        color: Theme.of(
          context,
        ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor.withValues(alpha: 0.5),
          ),
        ),
      ),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1200),
          child: Row(
            children: [
              TextButton.icon(
                icon: const Icon(Icons.arrow_back),
                label: const Text('Back to Dashboard'),
                onPressed: () => context.go('/dashboard'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAlertBanners(BuildContext context, TwinOverviewState state) {
    if (state is! TwinOverviewLoaded) return const SizedBox.shrink();

    if (state.errorMessage != null) {
      return _buildBanner(
        context,
        message: state.errorMessage!,
        color: Colors.red,
        icon: Icons.error,
        onDismiss: () => context.read<TwinOverviewBloc>().add(
          const TwinOverviewClearMessages(),
        ),
      );
    } else if (state.successMessage != null &&
        state.successMessage != 'deleted') {
      return _buildBanner(
        context,
        message: state.successMessage!,
        color: Colors.green,
        icon: Icons.check_circle,
        onDismiss: () => context.read<TwinOverviewBloc>().add(
          const TwinOverviewClearMessages(),
        ),
      );
    } else if (state.infoMessage != null) {
      return _buildBanner(
        context,
        message: state.infoMessage!,
        color: Colors.blue,
        icon: Icons.info,
        onDismiss: () => context.read<TwinOverviewBloc>().add(
          const TwinOverviewClearMessages(),
        ),
      );
    }
    return const SizedBox.shrink();
  }

  Widget _buildBanner(
    BuildContext context, {
    required String message,
    required MaterialColor color,
    required IconData icon,
    required VoidCallback onDismiss,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      decoration: BoxDecoration(
        color: color.shade50,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1200),
          child: Row(
            children: [
              Icon(icon, color: color.shade700),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  message,
                  style: TextStyle(
                    color: color.shade700,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              IconButton(
                icon: Icon(Icons.close, color: color.shade700, size: 20),
                onPressed: onDismiss,
                tooltip: 'Dismiss',
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBody(
    BuildContext context,
    TwinOverviewState state,
    WidgetRef ref,
  ) {
    if (state is TwinOverviewLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Loading twin configuration...'),
          ],
        ),
      );
    }

    if (state is TwinOverviewError) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red[400]),
            const SizedBox(height: 16),
            Text(
              'Failed to load twin',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              state.message,
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: Colors.grey[600]),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: () => context.read<TwinOverviewBloc>().add(
                TwinOverviewLoad(twinId),
              ),
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (state is TwinOverviewLoaded) {
      return _buildLoadedContent(context, state, ref);
    }

    // Initial state
    return const Center(child: CircularProgressIndicator());
  }

  Widget _buildLoadedContent(
    BuildContext context,
    TwinOverviewLoaded state,
    WidgetRef ref,
  ) {
    return SingleChildScrollView(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1200),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Dual Name Header
                TwinOverviewNameHeader(
                  projectName: state.projectName,
                  cloudResourceName: state.cloudResourceName,
                ),
                const SizedBox(height: 24),

                // Command Center (always visible)
                TwinOverviewCommandCenter(
                  state: state,
                  onEdit: () => context.go('/wizard/${state.twinId}'),
                  onDelete: () => _showDeleteConfirmation(context, state),
                  onDeploy: () => _showDeployConfirmation(context, state),
                  onDestroy: () => _showDestroyConfirmation(context, state),
                  onStartLogTrace: () => context.read<TwinOverviewBloc>().add(
                    const TwinOverviewStartLogTrace(),
                  ),
                  onDownloadSimulator: () => context
                      .read<TwinOverviewBloc>()
                      .add(const TwinOverviewDownloadSimulator()),
                  onViewLogs: () => _showDeploymentLogs(context, state),
                  onCloseTerminal: () => context.read<TwinOverviewBloc>().add(
                    const TwinOverviewCloseTerminal(),
                  ),
                  onOutputCopyFeedback: (message) =>
                      context.read<TwinOverviewBloc>().add(
                        TwinOverviewShowMessage(message, MessageType.success),
                      ),
                ),
                const SizedBox(height: 24),

                // Deployment Verification (only for deployed twins)
                if (state.twinState == 'deployed') ...[
                  BlocProvider(
                    create: (_) => DeploymentVerificationBloc(
                      twinId: state.twinId,
                      api: ref.read(apiServiceProvider),
                      logStreamClientFactory: ref.read(
                        logStreamClientFactoryProvider,
                      ),
                    ),
                    child: DeploymentVerificationCard(
                      payloadsJson:
                          state.deployerConfig?['payloads_json'] as String?,
                      configEventsJson:
                          state.deployerConfig?['config_events_json']
                              as String?,
                    ),
                  ),
                  const SizedBox(height: 24),
                ],

                TwinOverviewConfigurationReview(
                  state: state,
                  onViewArtifact: (artifact) =>
                      _showCodeArtifact(context, artifact),
                  onDownloadArtifact: (artifact) =>
                      _downloadCodeArtifact(context, artifact),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showCodeArtifact(
    BuildContext context,
    TwinOverviewCodeArtifact artifact,
  ) {
    showCodeViewerDialog(
      context,
      title: artifact.title,
      code: artifact.content,
      filename: artifact.filename,
    );
  }

  Future<void> _downloadCodeArtifact(
    BuildContext context,
    TwinOverviewCodeArtifact artifact,
  ) async {
    final result = await downloadCodeFile(
      content: artifact.content,
      filename: artifact.filename,
    );
    if (!context.mounted) return;
    if (result.success) {
      context.read<TwinOverviewBloc>().add(
        TwinOverviewShowMessage(result.message!, MessageType.success),
      );
    } else if (!result.cancelled && result.error != null) {
      context.read<TwinOverviewBloc>().add(
        TwinOverviewShowMessage(result.error!, MessageType.error),
      );
    }
  }

  void _showDeploymentLogs(BuildContext context, TwinOverviewLoaded state) {
    final storedLogs = state.lastDeploymentLogs?.trim();
    final terminalLogs = state.terminalLogs.join('\n').trim();
    final content = storedLogs?.isNotEmpty == true
        ? storedLogs!
        : (terminalLogs.isNotEmpty
              ? terminalLogs
              : 'No deployment logs are available for this twin.');

    showCodeViewerDialog(
      context,
      title: 'Deployment Logs',
      code: content,
      filename: '${state.projectName}_deployment_logs.txt',
    );
  }

  void _showDeployConfirmation(BuildContext context, TwinOverviewLoaded state) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.rocket_launch, color: Colors.blue),
            SizedBox(width: 8),
            Text('Deploy to Cloud?'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('This will provision cloud resources for:'),
            const SizedBox(height: 8),
            Text(
              '• ${state.cloudResourceName ?? state.projectName}',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Text(
              'Estimated time: 5-15 minutes',
              style: TextStyle(color: Colors.grey[600]),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              context.read<TwinOverviewBloc>().add(TwinOverviewDeploy());
            },
            child: const Text('Deploy Now'),
          ),
        ],
      ),
    );
  }

  void _showDestroyConfirmation(
    BuildContext context,
    TwinOverviewLoaded state,
  ) {
    bool confirmed = false;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          title: Row(
            children: [
              Icon(Icons.warning_amber, color: Colors.red[700]),
              const SizedBox(width: 8),
              const Text('Destroy Cloud Resources?'),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('This will PERMANENTLY delete:'),
              const SizedBox(height: 8),
              const Text('• All deployed infrastructure'),
              const Text('• IoT device connections'),
              const Text('• Stored data in hot/cold/archive storage'),
              const SizedBox(height: 16),
              CheckboxListTile(
                value: confirmed,
                onChanged: (v) => setState(() => confirmed = v ?? false),
                title: const Text('I understand this action is irreversible'),
                controlAffinity: ListTileControlAffinity.leading,
                contentPadding: EdgeInsets.zero,
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: confirmed
                  ? () {
                      Navigator.of(ctx).pop();
                      context.read<TwinOverviewBloc>().add(
                        TwinOverviewDestroy(),
                      );
                    }
                  : null,
              style: FilledButton.styleFrom(backgroundColor: Colors.red[700]),
              child: const Text('Destroy'),
            ),
          ],
        ),
      ),
    );
  }

  void _showDeleteConfirmation(BuildContext context, TwinOverviewLoaded state) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.delete_forever, color: Colors.red),
            SizedBox(width: 8),
            Text('Delete Twin?'),
          ],
        ),
        content: Text(
          'Are you sure you want to delete "${state.projectName}"? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              context.read<TwinOverviewBloc>().add(TwinOverviewDelete());
            },
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}
