import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../models/deployment_operations.dart';
import '../../theme/spacing.dart';
import '../deployment_terminal.dart';

class DeploymentOperationsPanel extends StatelessWidget {
  final String twinState;
  final bool canDeploy;
  final bool canDestroy;
  final DeploymentReadinessViewState readiness;
  final DeploymentOperationViewState operation;
  final String? lastError;
  final VoidCallback onDeploy;
  final VoidCallback onDestroy;
  final VoidCallback onViewLogs;
  final VoidCallback onCloseTerminal;

  const DeploymentOperationsPanel({
    super.key,
    required this.twinState,
    required this.canDeploy,
    required this.canDestroy,
    required this.readiness,
    required this.operation,
    required this.lastError,
    required this.onDeploy,
    required this.onDestroy,
    required this.onViewLogs,
    required this.onCloseTerminal,
  });

  bool get _isDeploying =>
      operation.isActive &&
      operation.operationType == DeploymentOperationType.deploy;

  bool get _isDestroying =>
      operation.isActive &&
      operation.operationType == DeploymentOperationType.destroy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final deployEnabled = canDeploy && readiness.isDeployable;

    return Card(
      elevation: AppSpacing.cardElevation,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Operations', style: theme.textTheme.titleLarge),
            const SizedBox(height: AppSpacing.md),
            _DeploymentActions(
              twinState: twinState,
              deployEnabled: deployEnabled,
              destroyEnabled: canDestroy,
              isDeploying: _isDeploying,
              isDestroying: _isDestroying,
              onDeploy: onDeploy,
              onDestroy: onDestroy,
            ),
            if (canDeploy && !readiness.isDeployable) ...[
              const SizedBox(height: AppSpacing.sm),
              Semantics(
                liveRegion: true,
                label:
                    'Deployment blocked. Run provider preflight successfully before deployment.',
                child: Text(
                  'Deployment is blocked until the current provider preflight passes.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.error,
                  ),
                ),
              ),
            ],
            if (twinState == 'error' && lastError != null) ...[
              const SizedBox(height: AppSpacing.md),
              _DeploymentErrorBanner(
                message: lastError!,
                onViewLogs: onViewLogs,
              ),
            ],
            if (operation.showLogs) ...[
              const SizedBox(height: AppSpacing.md),
              _DeploymentTerminalPanel(
                operation: operation,
                onCloseTerminal: onCloseTerminal,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class DeploymentOutputsError extends StatelessWidget {
  final String message;

  const DeploymentOutputsError({super.key, required this.message});

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
          Icon(
            Icons.warning_amber,
            color: theme.colorScheme.error,
            size: AppSpacing.iconMd,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onErrorContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DeploymentActions extends StatelessWidget {
  final String twinState;
  final bool deployEnabled;
  final bool destroyEnabled;
  final bool isDeploying;
  final bool isDestroying;
  final VoidCallback onDeploy;
  final VoidCallback onDestroy;

  const _DeploymentActions({
    required this.twinState,
    required this.deployEnabled,
    required this.destroyEnabled,
    required this.isDeploying,
    required this.isDestroying,
    required this.onDeploy,
    required this.onDestroy,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return LayoutBuilder(
      builder: (context, constraints) {
        final actions = [
          _PrimaryActionButton(
            label: twinState == 'error' ? 'RETRY DEPLOY' : 'DEPLOY',
            icon: Icons.rocket_launch,
            enabled: deployEnabled,
            busy: isDeploying,
            backgroundColor: colors.primary,
            foregroundColor: colors.onPrimary,
            onPressed: onDeploy,
          ),
          _PrimaryActionButton(
            label: twinState == 'error' ? 'CLEANUP' : 'DESTROY',
            icon: Icons.delete_forever,
            enabled: destroyEnabled,
            busy: isDestroying,
            backgroundColor: colors.error,
            foregroundColor: colors.onError,
            onPressed: onDestroy,
          ),
        ];

        if (constraints.maxWidth < AppSpacing.twinOverviewCompactBreakpoint) {
          return Column(
            children: [
              actions.first,
              const SizedBox(height: AppSpacing.sm),
              actions.last,
            ],
          );
        }
        return Row(
          children: [
            Expanded(child: actions.first),
            const SizedBox(width: AppSpacing.md),
            Expanded(child: actions.last),
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
  final Color backgroundColor;
  final Color foregroundColor;
  final VoidCallback onPressed;

  const _PrimaryActionButton({
    required this.label,
    required this.icon,
    required this.enabled,
    required this.busy,
    required this.backgroundColor,
    required this.foregroundColor,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      height: AppSpacing.actionButtonHeight,
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: enabled ? onPressed : null,
        icon: busy
            ? SizedBox.square(
                dimension: AppSpacing.iconMd,
                child: CircularProgressIndicator(
                  strokeWidth: AppSpacing.xxs,
                  color: foregroundColor,
                ),
              )
            : Icon(icon, size: AppSpacing.lg),
        label: Text(
          label,
          style: theme.textTheme.labelLarge?.copyWith(
            fontWeight: FontWeight.bold,
          ),
        ),
        style: FilledButton.styleFrom(
          backgroundColor: backgroundColor,
          foregroundColor: foregroundColor,
        ),
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
    final detail = Row(
      crossAxisAlignment: CrossAxisAlignment.start,
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
      ],
    );

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        border: Border.all(
          color: theme.colorScheme.error.withValues(alpha: 0.38),
        ),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          if (constraints.maxWidth < AppSpacing.twinOverviewCompactBreakpoint) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                detail,
                const SizedBox(height: AppSpacing.sm),
                TextButton(
                  onPressed: onViewLogs,
                  child: const Text('View Logs'),
                ),
              ],
            );
          }
          return Row(
            children: [
              Expanded(child: detail),
              TextButton(onPressed: onViewLogs, child: const Text('View Logs')),
            ],
          );
        },
      ),
    );
  }
}

class _DeploymentTerminalPanel extends StatelessWidget {
  final DeploymentOperationViewState operation;
  final VoidCallback onCloseTerminal;

  const _DeploymentTerminalPanel({
    required this.operation,
    required this.onCloseTerminal,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      children: [
        Row(
          children: [
            Icon(
              Icons.terminal,
              size: AppSpacing.iconSm,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(width: AppSpacing.sm),
            Text('Deployment Output', style: theme.textTheme.labelLarge),
            const Spacer(),
            IconButton(
              icon: const Icon(Icons.close, size: AppSpacing.iconMd),
              onPressed: onCloseTerminal,
              tooltip: 'Close terminal',
            ),
          ],
        ),
        if (operation.message != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              operation.message!,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
        const SizedBox(height: AppSpacing.sm),
        SizedBox(
          height: AppSpacing.terminalLogHeight,
          child: DeploymentTerminal(
            logs: operation.formattedLogs,
            isConnected:
                operation.phase == DeploymentOperationViewPhase.streaming,
            isComplete: operation.isComplete,
            isReconnecting: operation.isReconnecting,
          ),
        ),
      ],
    );
  }
}
