import 'package:flutter/material.dart';

import '../../bloc/wizard/wizard_state.dart';
import '../../models/cloud_connection.dart';
import '../../models/resolved_twin_architecture.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'logical_resolved_flow.dart';

const _digestPreviewLength = 20;

class ResolvedArchitectureReview extends StatelessWidget {
  final ResolvedArchitecturePhase phase;
  final ResolvedTwinArchitectureRead? resolved;
  final String? error;
  final VoidCallback? onRetry;

  const ResolvedArchitectureReview({
    super.key,
    required this.phase,
    required this.resolved,
    required this.error,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    if (phase == ResolvedArchitecturePhase.loading) {
      return const _ReviewState(
        icon: Icons.hourglass_top,
        title: 'Loading resolved architecture',
        message: 'Validating the selected run and pinned profile.',
        progress: true,
      );
    }
    if (phase == ResolvedArchitecturePhase.error ||
        phase == ResolvedArchitecturePhase.incompatible) {
      return _ReviewState(
        icon: phase == ResolvedArchitecturePhase.incompatible
            ? Icons.history_toggle_off
            : Icons.error_outline,
        title: phase == ResolvedArchitecturePhase.incompatible
            ? 'Resolved architecture is not compatible'
            : 'Resolved architecture could not be loaded',
        message: error ?? 'Retry the Management read.',
        actionLabel: onRetry == null ? null : 'Retry',
        onAction: onRetry,
      );
    }
    final value = resolved;
    if (phase != ResolvedArchitecturePhase.ready || value == null) {
      return const _ReviewState(
        icon: Icons.account_tree_outlined,
        title: 'No resolved architecture selected',
        message:
            'Calculate and select one complete optimizer run to inspect its immutable component and connection evidence.',
      );
    }

    final architecture = value.architecture;
    final sixLayer =
        architecture.profileRef.id == 'six-layer-eventing' &&
        architecture.profileRef.version == '1';
    final eventLayer = architecture.componentAssignments
        .where((item) => item.logicalComponentId == 'component.eventing')
        .toList(growable: false);
    final primary = architecture.componentAssignments
        .where(
          (item) =>
              item.required && item.logicalComponentId != 'component.eventing',
        )
        .toList(growable: false);
    final supporting = architecture.componentAssignments
        .where(
          (item) =>
              !item.required && item.logicalComponentId != 'component.eventing',
        )
        .toList(growable: false);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            Chip(
              avatar: const Icon(Icons.account_tree_outlined),
              label: Text(
                '${architecture.profileRef.id}@${architecture.profileRef.version}',
              ),
            ),
            const Chip(
              avatar: Icon(Icons.verified_outlined),
              label: Text('Functionally complete'),
            ),
            if (sixLayer)
              const Chip(
                avatar: Icon(Icons.hub_outlined),
                label: Text('Independent Event Layer'),
              ),
            Chip(
              label: Text(
                '${architecture.providers.length} ${architecture.providers.length == 1 ? 'provider' : 'providers'}',
              ),
            ),
            Chip(
              label: Text(
                '${architecture.costSummary.monthlyTotal} ${architecture.costSummary.currency} / month',
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        Text('Logical flow', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: AppSpacing.sm),
        LogicalResolvedFlow(architecture: architecture),
        if (eventLayer.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          Text(
            'Event Layer delta',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          Text(
            'Always-on event transport, delivery and bridge responsibility for the thesis comparison.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          for (final assignment in eventLayer)
            _AssignmentRow(assignment: assignment),
        ],
        const SizedBox(height: AppSpacing.md),
        Text(
          'Primary components',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        for (final assignment in primary)
          _AssignmentRow(assignment: assignment),
        if (supporting.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text('Supporting resources (${supporting.length})'),
            children: [
              for (final assignment in supporting)
                _AssignmentRow(assignment: assignment),
            ],
          ),
        ],
        const SizedBox(height: AppSpacing.md),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('Cost and evidence'),
          children: [
            _EvidenceRow(
              label: 'Monthly total',
              value:
                  '${architecture.costSummary.monthlyTotal} '
                  '${architecture.costSummary.currency}',
            ),
            for (final item in architecture.costSummary.responsibilityTotals)
              _EvidenceRow(
                label: item.itemId,
                value:
                    '${item.monthlyAmount} '
                    '${architecture.costSummary.currency}',
              ),
            _EvidenceRow(
              label: 'Completeness validator',
              value:
                  'v${architecture.functionalCompleteness.validatorVersion} · '
                  '${architecture.functionalCompleteness.validationDigest}',
            ),
            for (final digest in architecture.pricingEvidenceDigests)
              _EvidenceRow(label: 'Pricing evidence', value: digest),
          ],
        ),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: Text('Connections (${architecture.resolvedEdges.length})'),
          children: [
            if (architecture.resolvedEdges.isEmpty)
              const ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('No bridge or transfer connection is required.'),
              ),
            for (final edge in architecture.resolvedEdges) _EdgeRow(edge: edge),
          ],
        ),
        if (architecture.extensionBindings.isNotEmpty)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text(
              'User logic (${architecture.extensionBindings.length})',
            ),
            children: [
              for (final binding in architecture.extensionBindings)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(binding.slotId),
                  subtitle: Text(
                    '${binding.logicalComponentId} · ${_shortDigest(binding.artifactDigest)}',
                  ),
                ),
            ],
          ),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('Technical evidence'),
          children: [
            _EvidenceRow(
              label: 'Profile',
              value:
                  '${architecture.profileRef.id}@${architecture.profileRef.version}',
            ),
            _EvidenceRow(label: 'Origin', value: value.origin.apiValue),
            _EvidenceRow(label: 'Resolution', value: architecture.resolutionId),
            _EvidenceRow(label: 'Run', value: architecture.calculationRunId),
            _EvidenceRow(
              label: 'Content digest',
              value: architecture.contentDigest,
            ),
            _EvidenceRow(
              label: 'Deployment digest',
              value: architecture.deploymentSpecificationDigest,
            ),
          ],
        ),
      ],
    );
  }
}

class _AssignmentRow extends StatelessWidget {
  final ResolvedComponentAssignment assignment;

  const _AssignmentRow({required this.assignment});

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final textScale = MediaQuery.textScalerOf(context).scale(1);
      final wide =
          constraints.maxWidth >= AppSpacing.resolvedDeploymentWideBreakpoint &&
          textScale <= AppSpacing.resolvedArchitectureWideTextScaleLimit;
      final details = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SelectableText(
            assignment.serviceId,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
          Text(
            '${assignment.region} · ${assignment.costContribution.monthlyAmount} ${assignment.costContribution.currency}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          Text(
            '${assignment.capabilityEvidence.length} capability evidence · '
            '${assignment.pricingModelRefs.length} pricing model refs',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      );
      return Semantics(
        label:
            '${assignment.logicalComponentId}, ${assignment.provider.label}, ${assignment.serviceId}, ${assignment.required ? 'required' : 'supporting'}',
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
            ),
          ),
          child: wide
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: Text(assignment.logicalComponentId)),
                    SizedBox(
                      width: AppSpacing.resolvedDeploymentProviderColumnWidth,
                      child: _ProviderLabel(provider: assignment.provider),
                    ),
                    Expanded(flex: 2, child: details),
                  ],
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      assignment.logicalComponentId,
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    _ProviderLabel(provider: assignment.provider),
                    const SizedBox(height: AppSpacing.xs),
                    details,
                  ],
                ),
        ),
      );
    },
  );
}

class _EdgeRow extends StatelessWidget {
  final ResolvedArchitectureEdge edge;

  const _EdgeRow({required this.edge});

  @override
  Widget build(BuildContext context) => Semantics(
    label:
        '${edge.edgeId}, ${edge.sourceAssignmentId} to '
        '${edge.destinationAssignmentId}, '
        '${edge.isCrossCloud ? 'cross-cloud bridge' : 'provider-local transport'}, '
        '${edge.mechanism}, ${edge.deliveryMode}, ${edge.ordering}',
    child: ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(edge.isCrossCloud ? Icons.cloud_sync : Icons.arrow_forward),
      title: Text(
        '${edge.sourceAssignmentId} → ${edge.destinationAssignmentId}',
      ),
      subtitle: Text(
        '${edge.mechanism} · ${edge.transferRouteClass} · '
        '${edge.costContribution.monthlyAmount} ${edge.costContribution.currency} · '
        '${edge.transferEvidenceRefs.length} evidence refs',
      ),
    ),
  );
}

class _ProviderLabel extends StatelessWidget {
  final CloudProvider provider;

  const _ProviderLabel({required this.provider});

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(Icons.cloud_outlined, size: AppSpacing.iconSm, color: _color),
      const SizedBox(width: AppSpacing.xs),
      Text(provider.label),
    ],
  );

  Color get _color => switch (provider) {
    CloudProvider.aws => AppColors.aws,
    CloudProvider.azure => AppColors.azure,
    CloudProvider.gcp => AppColors.gcp,
  };
}

class _EvidenceRow extends StatelessWidget {
  final String label;
  final String value;

  const _EvidenceRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: AppSpacing.resolvedArchitectureEvidenceLabelWidth,
          child: Text(label),
        ),
        Expanded(child: SelectableText(value)),
      ],
    ),
  );
}

class _ReviewState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;
  final bool progress;
  final String? actionLabel;
  final VoidCallback? onAction;

  const _ReviewState({
    required this.icon,
    required this.title,
    required this.message,
    this.progress = false,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        children: [
          Icon(icon),
          const SizedBox(height: AppSpacing.sm),
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: AppSpacing.xs),
          Text(message, textAlign: TextAlign.center),
          if (progress) ...[
            const SizedBox(height: AppSpacing.md),
            const LinearProgressIndicator(),
          ],
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: AppSpacing.sm),
            TextButton(onPressed: onAction, child: Text(actionLabel!)),
          ],
        ],
      ),
    ),
  );
}

String _shortDigest(String value) => value.length <= _digestPreviewLength
    ? value
    : '${value.substring(0, _digestPreviewLength)}…';
