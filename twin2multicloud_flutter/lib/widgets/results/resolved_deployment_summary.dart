import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../models/resolved_deployment_specification.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'deployment_selection_status.dart';

class ResolvedDeploymentSummary extends StatelessWidget {
  final ResolvedDeploymentReview review;
  final bool isSelecting;
  final VoidCallback? onRetrySelection;
  final VoidCallback onRecalculateArchitecture;

  const ResolvedDeploymentSummary({
    super.key,
    required this.review,
    required this.isSelecting,
    required this.onRetrySelection,
    required this.onRecalculateArchitecture,
  });

  @override
  Widget build(BuildContext context) {
    final specification = review.supportedSpecification;
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
          if (specification != null) ...[
            _SpecificationOverview(specification: specification),
            const SizedBox(height: AppSpacing.md),
            for (final component in specification.architectureComponents)
              _ResolvedDeploymentComponentRow(component: component),
            if (specification.supportingComponents.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              Text(
                'Supporting runtime',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: AppSpacing.sm),
              for (final component in specification.supportingComponents)
                _ResolvedDeploymentComponentRow(component: component),
            ],
            const SizedBox(height: AppSpacing.sm),
            _TechnicalEvidence(specification: specification),
          ] else if ({
            ResolvedDeploymentReviewState.legacy,
            ResolvedDeploymentReviewState.unsupported,
          }.contains(review.state)) ...[
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

class _SpecificationOverview extends StatelessWidget {
  final ResolvedDeploymentSpecificationV1 specification;

  const _SpecificationOverview({required this.specification});

  @override
  Widget build(BuildContext context) {
    final providerCount = specification.providers.length;
    return Text(
      '${specification.architectureComponents.length} architecture slots | '
      '$providerCount ${providerCount == 1 ? 'provider' : 'providers'} | '
      'digest ${_shortDigest(specification.digest)}',
      style: Theme.of(context).textTheme.bodySmall?.copyWith(
        color: Theme.of(context).colorScheme.onSurfaceVariant,
      ),
    );
  }
}

class _ResolvedDeploymentComponentRow extends StatelessWidget {
  final ResolvedDeploymentComponent component;

  const _ResolvedDeploymentComponentRow({required this.component});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide =
            constraints.maxWidth >= AppSpacing.resolvedDeploymentWideBreakpoint;
        final service = _serviceContent(context);
        return Container(
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
            ),
          ),
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
          child: wide
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: AppSpacing.resolvedDeploymentSlotColumnWidth,
                      child: Text(component.slot.label),
                    ),
                    SizedBox(
                      width: AppSpacing.resolvedDeploymentProviderColumnWidth,
                      child: _ProviderLabel(provider: component.provider),
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
                          component.slot.label,
                          style: Theme.of(context).textTheme.labelLarge,
                        ),
                        _ProviderLabel(provider: component.provider),
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

  Widget _serviceContent(BuildContext context) {
    final dimensions = component.deployableDimensions;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SelectableText(
          component.serviceId,
          style: Theme.of(
            context,
          ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: AppSpacing.xs),
        Text(
          dimensions.isEmpty
              ? 'Provider-managed selection'
              : dimensions.map((item) => item.displayValue).join(' | '),
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
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

class _TechnicalEvidence extends StatelessWidget {
  final ResolvedDeploymentSpecificationV1 specification;

  const _TechnicalEvidence({required this.specification});

  @override
  Widget build(BuildContext context) {
    final contextData = specification.optimizationContext;
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: AppSpacing.sm),
      title: const Text('Show technical evidence'),
      children: [
        _ResolvedDeploymentEvidenceRow(
          label: 'Architecture profile',
          value:
              '${specification.architectureProfile.profileId}@${specification.architectureProfile.profileVersion}',
        ),
        _ResolvedDeploymentEvidenceRow(
          label: 'Calculation strategy',
          value: contextData.calculationStrategyId,
        ),
        _ResolvedDeploymentEvidenceRow(
          label: 'Formula set',
          value: contextData.formulaSetId,
        ),
        _ResolvedDeploymentEvidenceRow(
          label: 'Workload contract',
          value: contextData.workloadContractId,
        ),
        _ResolvedDeploymentEvidenceRow(
          label: 'Pricing registry',
          value: contextData.pricingRegistryVersion,
        ),
        _ResolvedDeploymentEvidenceRow(
          label: 'Calculation run',
          value: specification.calculationRunId,
        ),
        _ResolvedDeploymentEvidenceRow(
          label: 'Specification digest',
          value: specification.digest,
        ),
        for (final entry in contextData.catalogReferences.entries)
          _ResolvedDeploymentEvidenceRow(
            label: '${entry.key.label} catalog',
            value:
                '${entry.value.snapshotId} | ${entry.value.pricingRegion} | ${entry.value.contentDigest}',
          ),
        for (final component in specification.components) ...[
          const Divider(),
          _ResolvedDeploymentEvidenceRow(
            label: component.slot.label,
            value:
                '${component.componentId} | ${component.provider.label} | ${component.serviceId}',
          ),
          for (final dimension in component.dimensions)
            _ResolvedDeploymentEvidenceRow(
              label: dimension.dimensionId,
              value: [
                dimension.displayValue,
                dimension.classification.label,
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
