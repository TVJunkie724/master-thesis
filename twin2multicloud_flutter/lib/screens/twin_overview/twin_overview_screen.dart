// lib/screens/twin_overview/twin_overview_screen.dart
// Operational overview for configured Digital Twins.

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
import '../../theme/spacing.dart';
import '../../utils/file_download_utils.dart';
import '../../widgets/branded_app_bar.dart';
import '../../widgets/code_viewer_dialog.dart';
import '../../widgets/selectable_scaffold.dart';
import '../../widgets/deployment_verification_card.dart';
import '../../widgets/twin_overview/twin_overview_code_artifact.dart';
import '../../widgets/twin_overview/twin_overview_content.dart';
import '../../widgets/twin_overview/twin_overview_operation_dialogs.dart';

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
        // Save the one-shot simulator payload outside Equatable state handling.
        BlocListener<TwinOverviewBloc, TwinOverviewState>(
          listenWhen: (previous, current) {
            if (current is! TwinOverviewLoaded ||
                current.simulatorDownload.phase !=
                    SimulatorDownloadViewPhase.readyToSave) {
              return false;
            }
            return previous is! TwinOverviewLoaded ||
                previous.simulatorDownload.requestToken !=
                    current.simulatorDownload.requestToken;
          },
          listener: (context, state) async {
            if (state is! TwinOverviewLoaded) {
              return;
            }
            final pending = state.simulatorDownload.pendingDownload;
            if (pending == null) {
              context.read<TwinOverviewBloc>().add(
                const TwinOverviewSimulatorSaveFailed(
                  'Simulator package was not available for saving.',
                ),
              );
              return;
            }

            final bloc = context.read<TwinOverviewBloc>();
            bloc.add(const TwinOverviewSimulatorSaveStarted());
            final result = await saveBinaryFile(
              bytes: pending.bytes,
              suggestedName: pending.filename,
            );

            if (!context.mounted) return;
            if (result.success) {
              bloc.add(TwinOverviewSimulatorSaveCompleted(result.message!));
            } else if (result.cancelled) {
              bloc.add(const TwinOverviewSimulatorSaveCancelled());
            } else if (!result.cancelled && result.error != null) {
              bloc.add(TwinOverviewSimulatorSaveFailed(result.error!));
            }
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
        const SizedBox(width: AppSpacing.sm),
      ],
    );
  }

  Widget _buildHeader(BuildContext context, TwinOverviewState state) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.md,
      ),
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
          constraints: const BoxConstraints(
            maxWidth: AppSpacing.maxContentWidthLarge,
          ),
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
    final colors = Theme.of(context).colorScheme;

    if (state.errorMessage != null) {
      return _buildBanner(
        context,
        message: state.errorMessage!,
        backgroundColor: colors.errorContainer,
        foregroundColor: colors.onErrorContainer,
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
        backgroundColor: colors.tertiaryContainer,
        foregroundColor: colors.onTertiaryContainer,
        icon: Icons.check_circle,
        onDismiss: () => context.read<TwinOverviewBloc>().add(
          const TwinOverviewClearMessages(),
        ),
      );
    } else if (state.infoMessage != null) {
      return _buildBanner(
        context,
        message: state.infoMessage!,
        backgroundColor: colors.secondaryContainer,
        foregroundColor: colors.onSecondaryContainer,
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
    required Color backgroundColor,
    required Color foregroundColor,
    required IconData icon,
    required VoidCallback onDismiss,
  }) {
    return Semantics(
      container: true,
      liveRegion: true,
      label: message,
      child: Material(
        color: backgroundColor,
        elevation: AppSpacing.cardElevationLow,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.sm,
          ),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: AppSpacing.maxContentWidthLarge,
              ),
              child: Row(
                children: [
                  Icon(icon, color: foregroundColor),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text(
                      message,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: foregroundColor,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  IconButton(
                    icon: Icon(
                      Icons.close,
                      color: foregroundColor,
                      size: AppSpacing.iconMd,
                    ),
                    onPressed: onDismiss,
                    tooltip: 'Dismiss message',
                  ),
                ],
              ),
            ),
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
            SizedBox(height: AppSpacing.md),
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
            Icon(
              Icons.error_outline,
              size: AppSpacing.xxl,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              'Failed to load twin',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              state.message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
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
    final deploymentVerification = state.twinState == 'deployed'
        ? BlocProvider(
            create: (_) => DeploymentVerificationBloc(
              twinId: state.twinId,
              api: ref.read(apiServiceProvider),
              logStreamClientFactory: ref.read(logStreamClientFactoryProvider),
            ),
            child: DeploymentVerificationCard(
              payloadsJson: state.deployerConfig?.payloadsJson,
              configEventsJson: state.deployerConfig?.configEventsJson,
            ),
          )
        : null;
    return TwinOverviewContent(
      state: state,
      deploymentVerification: deploymentVerification,
      onEdit: () => context.go('/wizard/${state.twinId}'),
      onDelete: () => _confirmDelete(context, state),
      onRunPreflight: () => context.read<TwinOverviewBloc>().add(
        const TwinOverviewRunDeploymentPreflight(),
      ),
      onOpenCloudAccounts: () => context.go('/settings'),
      onDeploy: () => _confirmDeploy(context, state),
      onDestroy: () => _confirmDestroy(context),
      onViewLogs: () => _showDeploymentLogs(context, state),
      onCloseTerminal: () => context.read<TwinOverviewBloc>().add(
        const TwinOverviewCloseTerminal(),
      ),
      onStartTrace: () => context.read<TwinOverviewBloc>().add(
        const TwinOverviewStartLogTrace(),
      ),
      onCancelTrace: () => context.read<TwinOverviewBloc>().add(
        const TwinOverviewCancelLogTrace(),
      ),
      onDownloadSimulator: () => _confirmSimulatorDownload(context, state),
      onOutputCopyFeedback: (message) => context.read<TwinOverviewBloc>().add(
        TwinOverviewShowMessage(message, MessageType.success),
      ),
      onViewArtifact: (artifact) => _showCodeArtifact(context, artifact),
      onDownloadArtifact: (artifact) =>
          _downloadCodeArtifact(context, artifact),
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

  Future<void> _confirmSimulatorDownload(
    BuildContext context,
    TwinOverviewLoaded state,
  ) async {
    final provider = state.l1ProviderLabel.toUpperCase();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => SimulatorDownloadConfirmationDialog(provider: provider),
    );

    if (confirmed == true && context.mounted) {
      context.read<TwinOverviewBloc>().add(
        const TwinOverviewDownloadSimulator(
          acknowledgedSensitiveCredentials: true,
        ),
      );
    }
  }

  Future<void> _confirmDeploy(
    BuildContext context,
    TwinOverviewLoaded state,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => DeployTwinConfirmationDialog(
        resourceName: state.cloudResourceName ?? state.projectName,
      ),
    );
    if (confirmed == true && context.mounted) {
      context.read<TwinOverviewBloc>().add(TwinOverviewDeploy());
    }
  }

  Future<void> _confirmDestroy(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => const DestroyTwinConfirmationDialog(),
    );
    if (confirmed == true && context.mounted) {
      context.read<TwinOverviewBloc>().add(TwinOverviewDestroy());
    }
  }

  Future<void> _confirmDelete(
    BuildContext context,
    TwinOverviewLoaded state,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) =>
          DeleteTwinConfirmationDialog(projectName: state.projectName),
    );
    if (confirmed == true && context.mounted) {
      context.read<TwinOverviewBloc>().add(TwinOverviewDelete());
    }
  }
}
