import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../models/deployment_readiness.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

abstract class _ReadinessStrings {
  static const title = 'Deployment readiness';
  static const runPreflight = 'Run preflight';
  static const cloudAccounts = 'Cloud accounts';
  static const details = 'Provider details';
  static const notLoaded = 'Readiness has not been loaded yet.';
  static const checking = 'Checking required provider access...';
  static const neverChecked = 'Not checked';
  static const expectedVersion = 'Expected';
  static const suppliedVersion = 'Supplied';
  static const lastChecked = 'Last checked';
}

class DeploymentReadinessPanel extends StatelessWidget {
  final DeploymentReadinessViewState state;
  final VoidCallback onRunPreflight;
  final VoidCallback onOpenCloudAccounts;

  const DeploymentReadinessPanel({
    super.key,
    required this.state,
    required this.onRunPreflight,
    required this.onOpenCloudAccounts,
  });

  @override
  Widget build(BuildContext context) {
    final snapshot = state.snapshot;
    final isLoading = state.phase == DeploymentReadinessViewPhase.loading;
    final isBlocking = !state.isDeployable;
    final summary = _summary(snapshot);

    return Semantics(
      container: true,
      label: '${_ReadinessStrings.title}. $summary',
      child: Card(
        elevation: AppSpacing.cardElevationLow,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _Header(state: state),
              const SizedBox(height: AppSpacing.sm),
              Text(summary, style: Theme.of(context).textTheme.bodyMedium),
              if (snapshot?.checkedAt != null) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(
                  '${_ReadinessStrings.lastChecked}: '
                  '${_formatTimestamp(snapshot!.checkedAt!)}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
              if (isLoading) ...[
                const SizedBox(height: AppSpacing.md),
                const LinearProgressIndicator(),
              ],
              if (snapshot != null && snapshot.providers.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.sm,
                  children: snapshot.providers
                      .map((provider) => _ProviderBadge(provider: provider))
                      .toList(growable: false),
                ),
              ],
              if (snapshot != null) ...[
                const SizedBox(height: AppSpacing.sm),
                _ReadinessDetails(
                  key: ValueKey(state.phase),
                  snapshot: snapshot,
                  initiallyExpanded: isBlocking,
                ),
              ],
              const SizedBox(height: AppSpacing.md),
              _Actions(
                isLoading: isLoading,
                onRunPreflight: onRunPreflight,
                onOpenCloudAccounts: onOpenCloudAccounts,
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _summary(DeploymentReadinessSnapshot? snapshot) {
    if (state.phase == DeploymentReadinessViewPhase.loading) {
      return _ReadinessStrings.checking;
    }
    if (state.phase == DeploymentReadinessViewPhase.failed) {
      return state.errorMessage ?? 'Readiness could not be loaded.';
    }
    return snapshot?.summary ?? _ReadinessStrings.notLoaded;
  }
}

String _formatTimestamp(DateTime value) {
  return value.toLocal().toString().split('.').first;
}

class _Header extends StatelessWidget {
  final DeploymentReadinessViewState state;

  const _Header({required this.state});

  @override
  Widget build(BuildContext context) {
    final visual = _phaseVisual(state.phase);
    return Row(
      children: [
        Icon(visual.icon, color: visual.color, size: AppSpacing.iconMd),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            _ReadinessStrings.title,
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        Chip(
          avatar: Icon(
            visual.icon,
            color: visual.color,
            size: AppSpacing.iconSm,
          ),
          label: Text(visual.label),
          visualDensity: VisualDensity.compact,
        ),
      ],
    );
  }
}

class _ProviderBadge extends StatelessWidget {
  final ProviderDeploymentReadiness provider;

  const _ProviderBadge({required this.provider});

  @override
  Widget build(BuildContext context) {
    final providerColor = AppColors.getProviderColor(provider.provider.label);
    final statusIcon = provider.ready
        ? Icons.check_circle_outline
        : switch (provider.status) {
            ProviderDeploymentReadinessStatus.notChecked => Icons.schedule,
            ProviderDeploymentReadinessStatus.stale => Icons.update,
            _ => Icons.error_outline,
          };
    return Semantics(
      label: '${provider.provider.label}: ${provider.summary}',
      child: Chip(
        avatar: Icon(statusIcon, color: providerColor, size: AppSpacing.iconSm),
        label: Text(provider.provider.label),
        visualDensity: VisualDensity.compact,
      ),
    );
  }
}

class _ReadinessDetails extends StatelessWidget {
  final DeploymentReadinessSnapshot snapshot;
  final bool initiallyExpanded;

  const _ReadinessDetails({
    super.key,
    required this.snapshot,
    required this.initiallyExpanded,
  });

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      initiallyExpanded: initiallyExpanded,
      title: const Text(_ReadinessStrings.details),
      children: [
        for (final issue in snapshot.issues)
          _CheckRow(check: issue, providerLabel: 'Architecture'),
        for (var index = 0; index < snapshot.providers.length; index += 1) ...[
          if (index > 0 || snapshot.issues.isNotEmpty) const Divider(),
          _ProviderDetails(provider: snapshot.providers[index]),
        ],
      ],
    );
  }
}

class _ProviderDetails extends StatelessWidget {
  final ProviderDeploymentReadiness provider;

  const _ProviderDetails({required this.provider});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(provider.provider.label, style: theme.textTheme.titleSmall),
          const SizedBox(height: AppSpacing.xs),
          Text(
            provider.connectionDisplayName ?? 'No deployment connection',
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            '${_ReadinessStrings.expectedVersion}: '
            '${provider.expectedPermissionSetVersion}  |  '
            '${_ReadinessStrings.suppliedVersion}: '
            '${provider.suppliedPermissionSetVersion ?? 'missing'}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          for (final check in provider.checks)
            _CheckRow(check: check, providerLabel: provider.provider.label),
        ],
      ),
    );
  }
}

class _CheckRow extends StatelessWidget {
  final DeploymentReadinessCheck check;
  final String providerLabel;

  const _CheckRow({required this.check, required this.providerLabel});

  @override
  Widget build(BuildContext context) {
    final passed = check.status == DeploymentReadinessCheckStatus.passed;
    final color = passed ? AppColors.success : AppColors.error;
    final permissions = check.permissions.isEmpty
        ? null
        : 'Permissions: ${check.permissions.join(', ')}';
    return Semantics(
      label: '$providerLabel ${check.component}: ${check.message}',
      child: Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              passed ? Icons.check_circle_outline : Icons.error_outline,
              color: color,
              size: AppSpacing.iconMd,
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${check.component}: ${check.message}',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  if (!passed) ...[
                    const SizedBox(height: AppSpacing.xs),
                    Text(check.action),
                  ],
                  if (permissions != null) ...[
                    const SizedBox(height: AppSpacing.xs),
                    SelectableText(permissions),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Actions extends StatelessWidget {
  final bool isLoading;
  final VoidCallback onRunPreflight;
  final VoidCallback onOpenCloudAccounts;

  const _Actions({
    required this.isLoading,
    required this.onRunPreflight,
    required this.onOpenCloudAccounts,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact =
            constraints.maxWidth < AppSpacing.twinOverviewCompactBreakpoint;
        final preflight = SizedBox(
          height: AppSpacing.actionButtonHeight,
          child: FilledButton.icon(
            onPressed: isLoading ? null : onRunPreflight,
            icon: isLoading
                ? const SizedBox.square(
                    dimension: AppSpacing.iconSm,
                    child: CircularProgressIndicator(
                      strokeWidth: AppSpacing.xxs,
                    ),
                  )
                : const Icon(Icons.fact_check_outlined),
            label: const Text(_ReadinessStrings.runPreflight),
          ),
        );
        final accounts = SizedBox(
          height: AppSpacing.actionButtonHeight,
          child: OutlinedButton.icon(
            onPressed: onOpenCloudAccounts,
            icon: const Icon(Icons.cloud_outlined),
            label: const Text(_ReadinessStrings.cloudAccounts),
          ),
        );
        if (compact) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              preflight,
              const SizedBox(height: AppSpacing.sm),
              accounts,
            ],
          );
        }
        return Row(
          children: [
            preflight,
            const SizedBox(width: AppSpacing.sm),
            accounts,
          ],
        );
      },
    );
  }
}

({IconData icon, Color color, String label}) _phaseVisual(
  DeploymentReadinessViewPhase phase,
) {
  return switch (phase) {
    DeploymentReadinessViewPhase.ready => (
      icon: Icons.verified_outlined,
      color: AppColors.success,
      label: 'Ready',
    ),
    DeploymentReadinessViewPhase.loading => (
      icon: Icons.sync,
      color: AppColors.warning,
      label: 'Checking',
    ),
    DeploymentReadinessViewPhase.failed => (
      icon: Icons.cloud_off_outlined,
      color: AppColors.error,
      label: 'Unavailable',
    ),
    DeploymentReadinessViewPhase.reviewRequired => (
      icon: Icons.warning_amber_outlined,
      color: AppColors.warning,
      label: 'Review required',
    ),
    DeploymentReadinessViewPhase.initial => (
      icon: Icons.schedule,
      color: AppColors.warning,
      label: _ReadinessStrings.neverChecked,
    ),
  };
}
