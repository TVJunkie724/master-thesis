import 'package:flutter/material.dart';

import '../../models/cleanup_evidence.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

/// Presents persisted post-Destroy evidence without inferring missing proof.
class CleanupEvidencePanel extends StatelessWidget {
  final CleanupEvidence? evidence;
  final String? errorMessage;

  const CleanupEvidencePanel({
    super.key,
    required this.evidence,
    this.errorMessage,
  });

  @override
  Widget build(BuildContext context) {
    final visual = _visual(evidence?.status, errorMessage);
    return Semantics(
      container: true,
      label: 'Cleanup evidence. ${visual.label}.',
      child: Card(
        elevation: AppSpacing.cardElevationLow,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(visual.icon, color: visual.color),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      'Cleanup evidence',
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
              ),
              const SizedBox(height: AppSpacing.md),
              if (errorMessage != null)
                _Notice(
                  icon: Icons.error_outline,
                  color: AppColors.error,
                  text: errorMessage!,
                )
              else if (evidence == null)
                const Text(
                  'No persisted cleanup evidence is available for this Twin.',
                )
              else
                _EvidenceBody(evidence: evidence!),
            ],
          ),
        ),
      ),
    );
  }
}

class _EvidenceBody extends StatelessWidget {
  final CleanupEvidence evidence;

  const _EvidenceBody({required this.evidence});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _InventoryRow(
          label: 'Terraform state',
          status: evidence.terraform.postDestroyInventory,
          residualCount: evidence.terraform.residualResourceCount,
          detail:
              'Destroy ${_words(evidence.terraform.destroyStatus.apiValue)}',
        ),
        for (final provider in evidence.providers) ...[
          const Divider(),
          _InventoryRow(
            label: provider.provider.toUpperCase(),
            status: provider.postDestroyInventory,
            residualCount: provider.residualResourceCount,
            detail:
                '${provider.discoveredDuringCleanupCount ?? 0} resources inspected',
          ),
          if (provider.discoveredResourceKinds.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.xs),
              child: Text(
                provider.discoveredResourceKinds.join(', '),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ],
        if (evidence.retainedSharedPrerequisites.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.sm),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            childrenPadding: EdgeInsets.zero,
            title: const Text('Retained shared prerequisites'),
            subtitle: Text(
              '${evidence.retainedSharedPrerequisites.length} account-level capabilities retained',
            ),
            children: [
              for (final item in evidence.retainedSharedPrerequisites)
                _Notice(
                  icon: Icons.info_outline,
                  color: Theme.of(context).colorScheme.primary,
                  text:
                      '${item.provider.toUpperCase()} · ${item.capabilityId} · ${item.scope}',
                ),
            ],
          ),
        ],
        if (evidence.residualFailures.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.sm),
          ExpansionTile(
            key: const Key('cleanup-residual-failures'),
            tilePadding: EdgeInsets.zero,
            childrenPadding: EdgeInsets.zero,
            initiallyExpanded:
                evidence.status == CleanupEvidenceStatus.incomplete,
            title: const Text('Residual failures'),
            subtitle: Text(
              '${evidence.residualFailures.length} cleanup checks require attention',
            ),
            children: [
              for (final failure in evidence.residualFailures)
                _Notice(
                  icon: Icons.error_outline,
                  color: AppColors.error,
                  text: [
                    if (failure.provider != null)
                      failure.provider!.toUpperCase(),
                    _words(failure.scope),
                    _words(failure.reason),
                  ].join(' · '),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _InventoryRow extends StatelessWidget {
  final String label;
  final CleanupInventoryStatus status;
  final int? residualCount;
  final String detail;

  const _InventoryRow({
    required this.label,
    required this.status,
    required this.residualCount,
    required this.detail,
  });

  @override
  Widget build(BuildContext context) {
    final isEmpty = status == CleanupInventoryStatus.empty;
    final color = isEmpty
        ? AppColors.success
        : status == CleanupInventoryStatus.notRun
        ? AppColors.warning
        : AppColors.error;
    return Semantics(
      label: '$label inventory ${_words(status.apiValue)}',
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            isEmpty ? Icons.check_circle_outline : Icons.warning_amber,
            color: color,
            size: AppSpacing.iconMd,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: Theme.of(context).textTheme.titleSmall),
                Text(
                  '${_words(status.apiValue)}'
                  '${residualCount == null ? '' : ' · $residualCount residual'}'
                  ' · $detail',
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String text;

  const _Notice({required this.icon, required this.color, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: AppSpacing.iconMd),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}

({String label, IconData icon, Color color}) _visual(
  CleanupEvidenceStatus? status,
  String? error,
) {
  if (error != null) {
    return (
      label: 'EVIDENCE INVALID',
      icon: Icons.error_outline,
      color: AppColors.error,
    );
  }
  return switch (status) {
    CleanupEvidenceStatus.complete => (
      label: 'COMPLETE',
      icon: Icons.verified_outlined,
      color: AppColors.success,
    ),
    CleanupEvidenceStatus.incomplete => (
      label: 'INCOMPLETE',
      icon: Icons.error_outline,
      color: AppColors.error,
    ),
    CleanupEvidenceStatus.dryRun => (
      label: 'DRY RUN',
      icon: Icons.science_outlined,
      color: AppColors.warning,
    ),
    null => (
      label: 'UNAVAILABLE',
      icon: Icons.help_outline,
      color: AppColors.warning,
    ),
  };
}

String _words(String value) => value.replaceAll('_', ' ');
