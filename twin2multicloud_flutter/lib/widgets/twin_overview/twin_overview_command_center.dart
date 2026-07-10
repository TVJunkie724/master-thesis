import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import '../../utils/twin_state_utils.dart';
import '../deployment_terminal.dart';
import '../terraform_outputs_card.dart';

const _primaryActionHeight = 56.0;
const _utilityActionHeight = 40.0;
const _terminalHeight = 300.0;
const _primaryActionSpinnerSize = 20.0;
const _utilityActionSpinnerSize = 16.0;
const _utilityActionIconSize = 18.0;

class TwinOverviewCommandCenter extends StatelessWidget {
  final TwinOverviewLoaded state;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onDeploy;
  final VoidCallback onDestroy;
  final VoidCallback onStartLogTrace;
  final VoidCallback onDownloadSimulator;
  final VoidCallback onViewLogs;
  final VoidCallback onCloseTerminal;
  final ValueChanged<String> onOutputCopyFeedback;

  const TwinOverviewCommandCenter({
    super.key,
    required this.state,
    required this.onEdit,
    required this.onDelete,
    required this.onDeploy,
    required this.onDestroy,
    required this.onStartLogTrace,
    required this.onDownloadSimulator,
    required this.onViewLogs,
    required this.onCloseTerminal,
    required this.onOutputCopyFeedback,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: AppSpacing.cardElevation,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _CommandHeader(state: state, onEdit: onEdit, onDelete: onDelete),
            const SizedBox(height: AppSpacing.sm),
            Text(
              TwinStateUtils.getDescription(state.twinState),
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            _DeploymentActions(
              state: state,
              onDeploy: onDeploy,
              onDestroy: onDestroy,
            ),
            if (state.twinState == 'deployed') ...[
              const SizedBox(height: AppSpacing.md),
              _TestingUtilities(
                state: state,
                onStartLogTrace: onStartLogTrace,
                onDownloadSimulator: onDownloadSimulator,
              ),
            ],
            if (state.twinState == 'error' && state.lastError != null) ...[
              const SizedBox(height: AppSpacing.md),
              _DeploymentErrorBanner(
                message: state.lastError!,
                onViewLogs: onViewLogs,
              ),
            ],
            if (state.showTerminal) ...[
              const SizedBox(height: AppSpacing.md),
              _DeploymentTerminalPanel(
                state: state,
                onCloseTerminal: onCloseTerminal,
              ),
            ],
            if (state.deploymentOutputs != null &&
                state.deploymentOutputs!.isNotEmpty &&
                state.twinState == 'deployed') ...[
              const SizedBox(height: AppSpacing.md),
              TerraformOutputsCard(
                outputs: state.deploymentOutputs!,
                deployedAt: state.outputsTimestamp,
                onCopyFeedback: onOutputCopyFeedback,
              ),
            ],
            if (state.outputsError != null) ...[
              const SizedBox(height: AppSpacing.sm),
              _OutputsErrorBanner(message: state.outputsError!),
            ],
          ],
        ),
      ),
    );
  }
}

class _CommandHeader extends StatelessWidget {
  final TwinOverviewLoaded state;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  const _CommandHeader({
    required this.state,
    required this.onEdit,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        TwinStateUtils.buildBadge(context, state.twinState),
        const Spacer(),
        Tooltip(
          message: state.canEdit
              ? 'Edit configuration'
              : 'Cannot edit deployed twin - destroy resources first',
          child: OutlinedButton.icon(
            onPressed: state.canEdit ? onEdit : null,
            icon: const Icon(Icons.edit),
            label: const Text('Edit'),
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Tooltip(
          message: state.canDelete
              ? 'Delete twin'
              : 'Destroy cloud resources before deleting',
          child: OutlinedButton.icon(
            onPressed: state.canDelete ? onDelete : null,
            icon: const Icon(Icons.delete_outline),
            label: const Text('Delete'),
            style: OutlinedButton.styleFrom(foregroundColor: AppColors.error),
          ),
        ),
      ],
    );
  }
}

class _DeploymentActions extends StatelessWidget {
  final TwinOverviewLoaded state;
  final VoidCallback onDeploy;
  final VoidCallback onDestroy;

  const _DeploymentActions({
    required this.state,
    required this.onDeploy,
    required this.onDestroy,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final actions = [
          _PrimaryActionButton(
            label: state.twinState == 'error' ? 'RETRY DEPLOY' : 'DEPLOY',
            icon: Icons.rocket_launch,
            enabled: state.canDeploy,
            busy: state.isDeploying,
            color: AppColors.success,
            onPressed: onDeploy,
          ),
          _PrimaryActionButton(
            label: state.twinState == 'error' ? 'CLEANUP' : 'DESTROY',
            icon: Icons.delete_forever,
            enabled: state.canDestroy,
            busy: state.isDestroying,
            color: AppColors.error,
            onPressed: onDestroy,
          ),
        ];

        if (constraints.maxWidth < 720) {
          return Column(
            children: [
              for (final action in actions)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: action,
                ),
            ],
          );
        }

        return Row(
          children: [
            Expanded(child: actions[0]),
            const SizedBox(width: AppSpacing.md),
            Expanded(child: actions[1]),
          ],
        );
      },
    );
  }
}

class _PrimaryActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool enabled;
  final bool busy;
  final Color color;
  final VoidCallback onPressed;

  const _PrimaryActionButton({
    required this.label,
    required this.icon,
    required this.enabled,
    required this.busy,
    required this.color,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SizedBox(
      height: _primaryActionHeight,
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: enabled ? onPressed : null,
        icon: busy
            ? SizedBox(
                width: _primaryActionSpinnerSize,
                height: _primaryActionSpinnerSize,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: theme.colorScheme.onPrimary,
                ),
              )
            : Icon(icon, size: AppSpacing.lg),
        label: Text(
          label,
          style: theme.textTheme.labelLarge?.copyWith(
            color: theme.colorScheme.onPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
        style: FilledButton.styleFrom(
          backgroundColor: color,
          foregroundColor: theme.colorScheme.onPrimary,
        ),
      ),
    );
  }
}

class _TestingUtilities extends StatelessWidget {
  final TwinOverviewLoaded state;
  final VoidCallback onStartLogTrace;
  final VoidCallback onDownloadSimulator;

  const _TestingUtilities({
    required this.state,
    required this.onStartLogTrace,
    required this.onDownloadSimulator,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      children: [
        Row(
          children: [
            Expanded(child: Divider(color: theme.dividerColor)),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
              child: Text(
                'TESTING UTILITIES',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 1.2,
                ),
              ),
            ),
            Expanded(child: Divider(color: theme.dividerColor)),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        LayoutBuilder(
          builder: (context, constraints) {
            final buttons = [
              _UtilityButton(
                label: state.isTracing ? 'Tracing...' : 'Send Test Message',
                icon: Icons.sms_outlined,
                busy: state.isTracing,
                enabled: !state.isTracing,
                onPressed: onStartLogTrace,
              ),
              _UtilityButton(
                label: state.isDownloadingSimulator
                    ? 'Downloading...'
                    : 'Download ${_l1ProviderLabel(state)} Simulator',
                icon: Icons.download_outlined,
                busy: state.isDownloadingSimulator,
                enabled: !state.isDownloadingSimulator,
                onPressed: onDownloadSimulator,
              ),
            ];

            if (constraints.maxWidth < 720) {
              return Column(
                children: [
                  for (final button in buttons)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: button,
                    ),
                ],
              );
            }

            return Row(
              children: [
                Expanded(child: buttons[0]),
                const SizedBox(width: AppSpacing.sm),
                Expanded(child: buttons[1]),
              ],
            );
          },
        ),
      ],
    );
  }

  String _l1ProviderLabel(TwinOverviewLoaded state) {
    return (state.cheapestPath?['l1'] as String?)?.toUpperCase() ?? 'L1';
  }
}

class _UtilityButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool busy;
  final bool enabled;
  final VoidCallback onPressed;

  const _UtilityButton({
    required this.label,
    required this.icon,
    required this.busy,
    required this.enabled,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: _utilityActionHeight,
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: enabled ? onPressed : null,
        icon: busy
            ? const SizedBox(
                width: _utilityActionSpinnerSize,
                height: _utilityActionSpinnerSize,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : Icon(icon, size: _utilityActionIconSize),
        label: Text(label, style: Theme.of(context).textTheme.labelSmall),
      ),
    );
  }
}

class _DeploymentErrorBanner extends StatelessWidget {
  final String message;
  final VoidCallback onViewLogs;

  const _DeploymentErrorBanner({
    required this.message,
    required this.onViewLogs,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        border: Border.all(color: AppColors.error.withAlpha(96)),
      ),
      child: Row(
        children: [
          Icon(Icons.error, color: theme.colorScheme.error),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Deployment Failed',
                  style: theme.textTheme.titleSmall?.copyWith(
                    color: theme.colorScheme.onErrorContainer,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  message,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onErrorContainer,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Orphaned cloud resources may exist. Run CLEANUP before retrying deployment.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onErrorContainer,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
          TextButton(onPressed: onViewLogs, child: const Text('View Logs')),
        ],
      ),
    );
  }
}

class _DeploymentTerminalPanel extends StatelessWidget {
  final TwinOverviewLoaded state;
  final VoidCallback onCloseTerminal;

  const _DeploymentTerminalPanel({
    required this.state,
    required this.onCloseTerminal,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      children: [
        Row(
          children: [
            Icon(Icons.terminal, size: 16, color: theme.colorScheme.primary),
            const SizedBox(width: AppSpacing.sm),
            Text(
              state.isTracing ? 'Log Trace Output' : 'Deployment Output',
              style: theme.textTheme.labelLarge,
            ),
            const Spacer(),
            IconButton(
              icon: const Icon(Icons.close, size: 18),
              onPressed: onCloseTerminal,
              tooltip: 'Close terminal',
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        SizedBox(
          height: _terminalHeight,
          child: DeploymentTerminal(
            logs: state.terminalLogs,
            isConnected:
                state.isDeploying || state.isDestroying || state.isTracing,
            isComplete:
                !state.isDeploying && !state.isDestroying && !state.isTracing,
            isReconnecting: false,
          ),
        ),
      ],
    );
  }
}

class _OutputsErrorBanner extends StatelessWidget {
  final String message;

  const _OutputsErrorBanner({required this.message});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
      ),
      child: Row(
        children: [
          Icon(Icons.warning_amber, color: theme.colorScheme.error, size: 20),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: theme.colorScheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
