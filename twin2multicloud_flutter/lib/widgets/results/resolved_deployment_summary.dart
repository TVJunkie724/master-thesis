import 'package:flutter/material.dart';

import '../../bloc/wizard/wizard_state.dart';
import '../../models/cloud_connection.dart';
import '../../models/resolved_deployment_specification.dart';
import '../../models/resolved_twin_architecture.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'deployment_selection_status.dart';
import 'resolved_architecture_review.dart';

class ResolvedDeploymentSummary extends StatelessWidget {
  final ResolvedDeploymentReview review;
  final bool isSelecting;
  final VoidCallback? onRetrySelection;
  final VoidCallback onRecalculateArchitecture;
  final ResolvedArchitecturePhase architecturePhase;
  final ResolvedTwinArchitectureRead? resolvedArchitecture;
  final String? resolvedArchitectureError;
  final VoidCallback? onRetryResolvedArchitecture;

  const ResolvedDeploymentSummary({
    super.key,
    required this.review,
    required this.isSelecting,
    required this.onRetrySelection,
    required this.onRecalculateArchitecture,
    this.architecturePhase = ResolvedArchitecturePhase.idle,
    this.resolvedArchitecture,
    this.resolvedArchitectureError,
    this.onRetryResolvedArchitecture,
  });

  @override
  Widget build(BuildContext context) {
    final specification = review.supportedV2Specification;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Resolved cloud resources',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const Divider(),
          DeploymentSelectionStatus(
            review: review,
            isSelecting: isSelecting,
            onRetry: onRetrySelection,
          ),
          const SizedBox(height: AppSpacing.md),
          ResolvedArchitectureReview(
            phase: architecturePhase,
            resolved: resolvedArchitecture,
            error: resolvedArchitectureError,
            onRetry: onRetryResolvedArchitecture,
          ),
          if (specification != null) ...[
            _V2SpecificationOverview(specification: specification),
            const SizedBox(height: AppSpacing.md),
            _V2ReadinessEvidence(readiness: specification.readiness),
            const SizedBox(height: AppSpacing.md),
            for (final selection in specification.componentSelections)
              _V2ComponentSelectionRow(selection: selection),
            const SizedBox(height: AppSpacing.sm),
            _V2TechnicalEvidence(specification: specification),
          ] else if (review.state ==
              ResolvedDeploymentReviewState.unsupported) ...[
            const SizedBox(height: AppSpacing.sm),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: onRecalculateArchitecture,
                icon: const Icon(Icons.calculate_outlined),
                label: const Text('Recalculate architecture'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _V2SpecificationOverview extends StatelessWidget {
  final ResolvedDeploymentSpecificationV2 specification;

  const _V2SpecificationOverview({required this.specification});

  @override
  Widget build(BuildContext context) {
    final providerCount = specification.providers.length;
    return Text(
      '${specification.logicalComponentCount} architecture responsibilities | '
      '${specification.componentSelections.length} service selections | '
      '$providerCount ${providerCount == 1 ? 'provider' : 'providers'} | '
      'digest ${_shortDigest(specification.digest)}',
      style: Theme.of(context).textTheme.bodySmall?.copyWith(
        color: Theme.of(context).colorScheme.onSurfaceVariant,
      ),
    );
  }
}

class _V2ReadinessEvidence extends StatelessWidget {
  final SixLayerReadiness readiness;

  const _V2ReadinessEvidence({required this.readiness});

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.tertiaryContainer,
      borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
    ),
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            readiness.evaluationOnly
                ? 'Live capacity evidence pending'
                : 'Deployment capacity evidence complete',
            style: Theme.of(
              context,
            ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          if (readiness.blockingGateIds.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            for (final gate in readiness.blockingGateIds)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: SelectableText('• $gate'),
              ),
          ],
        ],
      ),
    ),
  );
}

class _V2ComponentSelectionRow extends StatelessWidget {
  final SixLayerComponentSelection selection;

  const _V2ComponentSelectionRow({required this.selection});

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final wide =
          constraints.maxWidth >= AppSpacing.resolvedDeploymentWideBreakpoint;
      final service = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SelectableText(
            selection.implementationComponentId,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            '${selection.region} | ${selection.dimensions.length} dimensions',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      );
      return Container(
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
                  SizedBox(
                    width: AppSpacing.resolvedDeploymentSlotColumnWidth,
                    child: Text(_v2LogicalLabel(selection.logicalComponentId)),
                  ),
                  SizedBox(
                    width: AppSpacing.resolvedDeploymentProviderColumnWidth,
                    child: _ProviderLabel(provider: selection.provider),
                  ),
                  Expanded(child: service),
                ],
              )
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: AppSpacing.md,
                    runSpacing: AppSpacing.xs,
                    children: [
                      Text(
                        _v2LogicalLabel(selection.logicalComponentId),
                        style: Theme.of(context).textTheme.labelLarge,
                      ),
                      _ProviderLabel(provider: selection.provider),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  service,
                ],
              ),
      );
    },
  );
}

class _V2TechnicalEvidence extends StatelessWidget {
  final ResolvedDeploymentSpecificationV2 specification;

  const _V2TechnicalEvidence({required this.specification});

  @override
  Widget build(BuildContext context) => ExpansionTile(
    tilePadding: EdgeInsets.zero,
    childrenPadding: const EdgeInsets.only(bottom: AppSpacing.sm),
    title: const Text('Show technical evidence'),
    children: [
      _ResolvedDeploymentEvidenceRow(
        label: 'Architecture profile',
        value:
            '${specification.architectureProfileRef.id}@${specification.architectureProfileRef.version}',
      ),
      _ResolvedDeploymentEvidenceRow(
        label: 'Readiness',
        value: specification.readiness.status,
      ),
      _ResolvedDeploymentEvidenceRow(
        label: 'Calculation run',
        value: specification.calculationRunId,
      ),
      _ResolvedDeploymentEvidenceRow(
        label: 'Specification digest',
        value: specification.digest,
      ),
      for (final entry in specification.optimizationReferences.entries)
        _ResolvedDeploymentEvidenceRow(
          label: entry.key,
          value:
              '${entry.value.id}@${entry.value.version} | ${entry.value.digest}',
        ),
      for (final entry in specification.fixedDimensions.entries)
        _ResolvedDeploymentEvidenceRow(
          label: entry.key,
          value: '${entry.value}',
        ),
      for (final selection in specification.componentSelections) ...[
        const Divider(),
        _ResolvedDeploymentEvidenceRow(
          label: _v2LogicalLabel(selection.logicalComponentId),
          value:
              '${selection.selectionId} | ${selection.provider.label} | ${selection.implementationComponentDigest}',
        ),
        for (final dimension in selection.dimensions)
          _ResolvedDeploymentEvidenceRow(
            label: dimension.dimensionId,
            value: [
              '${dimension.value} ${dimension.unit}',
              dimension.classification.apiValue,
              'formula ${dimension.formulaReference}',
              'evidence ${dimension.evidenceReference}',
              if (dimension.terraformTarget != null)
                'Terraform ${dimension.terraformTarget}',
            ].join(' | '),
          ),
      ],
    ],
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

class _ResolvedDeploymentEvidenceRow extends StatelessWidget {
  final String label;
  final String value;

  const _ResolvedDeploymentEvidenceRow({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: AppSpacing.resolvedDeploymentSlotColumnWidth,
          child: Text(label, style: Theme.of(context).textTheme.labelMedium),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: SelectableText(
            value,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
      ],
    ),
  );
}

String _shortDigest(String digest) {
  final value = digest.startsWith('sha256:') ? digest.substring(7) : digest;
  return value.length <= 12
      ? value
      : '${value.substring(0, 6)}...${value.substring(value.length - 6)}';
}

String _v2LogicalLabel(String logicalComponentId) =>
    switch (logicalComponentId) {
      'component.ingestion' => 'L1 Acquisition',
      'component.processing' => 'L2 Processing',
      'component.hot-storage' => 'L3 Hot',
      'component.cool-storage' => 'L3 Cool',
      'component.archive-storage' => 'L3 Archive',
      'component.eventing' => 'Event Layer',
      'component.twin-state' => 'L4 Twin',
      'component.visualization' => 'L5 Visualization',
      _ => logicalComponentId,
    };
