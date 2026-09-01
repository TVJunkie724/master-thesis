import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../theme/spacing.dart';
import '../../utils/twin_state_utils.dart';
import 'twin_overview_strings.dart';

class TwinLifecycleSummary extends StatelessWidget {
  final TwinOverviewLoaded state;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  const TwinLifecycleSummary({
    super.key,
    required this.state,
    required this.onEdit,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final nextStep = _nextStep(state);
    final hasCloudResource = state.cloudResourceName?.trim().isNotEmpty == true;
    final resource = hasCloudResource
        ? state.cloudResourceName!
        : TwinOverviewStrings.notConfigured;
    return Semantics(
      container: true,
      label:
          '${state.projectName}. ${TwinStateUtils.getDescription(state.twinState)}. '
          '${TwinOverviewStrings.cloudResource}: $resource. '
          '${TwinOverviewStrings.nextStep}: $nextStep',
      child: Card(
        elevation: AppSpacing.cardElevationLow,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              LayoutBuilder(
                builder: (context, constraints) {
                  final textScale = MediaQuery.textScalerOf(context).scale(1);
                  final compact =
                      constraints.maxWidth <
                          AppSpacing.twinOverviewCompactBreakpoint ||
                      textScale >
                          AppSpacing.resolvedArchitectureWideTextScaleLimit;
                  return compact
                      ? _buildCompact(context, resource, hasCloudResource)
                      : _buildWide(context, resource, hasCloudResource);
                },
              ),
              const SizedBox(height: AppSpacing.md),
              Container(
                padding: const EdgeInsets.all(AppSpacing.md),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(
                    AppSpacing.borderRadiusSm,
                  ),
                ),
                child: Text(
                  '${TwinOverviewStrings.nextStep}: $nextStep',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onPrimaryContainer,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWide(
    BuildContext context,
    String resource,
    bool hasCloudResource,
  ) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Expanded(child: _identity(context, resource, hasCloudResource)),
      const SizedBox(width: AppSpacing.lg),
      _status(context),
      const SizedBox(width: AppSpacing.sm),
      _actions(),
    ],
  );

  Widget _buildCompact(
    BuildContext context,
    String resource,
    bool hasCloudResource,
  ) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: _identity(context, resource, hasCloudResource)),
          _actions(),
        ],
      ),
      const SizedBox(height: AppSpacing.md),
      _status(context),
    ],
  );

  Widget _identity(
    BuildContext context,
    String resource,
    bool hasCloudResource,
  ) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(state.projectName, style: Theme.of(context).textTheme.headlineSmall),
      const SizedBox(height: AppSpacing.xs),
      Text(
        '${TwinOverviewStrings.cloudResource}: $resource',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
          fontFamily: hasCloudResource ? 'monospace' : null,
        ),
      ),
    ],
  );

  Widget _status(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      TwinStateUtils.buildBadge(context, state.twinState),
      const SizedBox(height: AppSpacing.xs),
      Text(
        TwinStateUtils.getDescription(state.twinState),
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    ],
  );

  Widget _actions() => PopupMenuButton<_SummaryAction>(
    tooltip: '${TwinOverviewStrings.moreActions} for ${state.projectName}',
    icon: const Icon(Icons.more_vert),
    onSelected: (action) {
      switch (action) {
        case _SummaryAction.edit:
          onEdit();
        case _SummaryAction.delete:
          onDelete();
      }
    },
    itemBuilder: (context) => [
      PopupMenuItem(
        value: _SummaryAction.edit,
        enabled: state.canEdit,
        child: _MenuLabel(
          icon: Icons.edit_outlined,
          label: TwinOverviewStrings.editConfiguration,
          disabledReason: state.canEdit
              ? null
              : TwinOverviewStrings.editBlocked,
        ),
      ),
      PopupMenuItem(
        value: _SummaryAction.delete,
        enabled: state.canDelete,
        child: _MenuLabel(
          icon: Icons.delete_outline,
          label: TwinOverviewStrings.deleteTwin,
          disabledReason: state.canDelete
              ? null
              : TwinOverviewStrings.deleteBlocked,
        ),
      ),
    ],
  );
}

enum _SummaryAction { edit, delete }

class _MenuLabel extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? disabledReason;

  const _MenuLabel({
    required this.icon,
    required this.label,
    required this.disabledReason,
  });

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Icon(icon, size: AppSpacing.iconMd),
      const SizedBox(width: AppSpacing.sm),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label),
            if (disabledReason != null)
              Text(
                disabledReason!,
                style: Theme.of(context).textTheme.bodySmall,
              ),
          ],
        ),
      ),
    ],
  );
}

String _nextStep(TwinOverviewLoaded state) {
  if (state.isDeploying) return TwinOverviewStrings.deployingNext;
  if (state.isDestroying) return TwinOverviewStrings.destroyingNext;
  return switch (state.twinState) {
    'error' => TwinOverviewStrings.errorNext,
    'deployed' => TwinOverviewStrings.deployedNext,
    'destroyed' => TwinOverviewStrings.destroyedNext,
    'configured' when state.deploymentReadiness.isDeployable =>
      TwinOverviewStrings.deployNext,
    'configured' => TwinOverviewStrings.preflightNext,
    _ => TwinOverviewStrings.configureNext,
  };
}
