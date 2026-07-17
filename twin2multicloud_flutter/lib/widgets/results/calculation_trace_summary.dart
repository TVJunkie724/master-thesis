import 'package:flutter/material.dart';

import '../../models/calc_result.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import '../pricing/pricing_catalog_evidence.dart';
import 'pricing_field_trace_details.dart';

class CalculationTraceSummary extends StatelessWidget {
  final CalcResult result;

  const CalculationTraceSummary({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    final trace = result.intentTrace;
    final profile = result.optimizationProfile ?? trace?.profile;

    return Card(
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.fact_check_outlined,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  'Calculation trace',
                  style: Theme.of(
                    context,
                  ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            if (trace == null)
              Text(
                'No intent trace metadata is available for this calculation result.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              )
            else ...[
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: [
                  _TraceChip(
                    label: trace.publishable ? 'Publishable' : 'Review needed',
                    icon: trace.publishable
                        ? Icons.check_circle_outline
                        : Icons.warning_amber_outlined,
                    color: trace.publishable
                        ? AppColors.success
                        : AppColors.warning,
                  ),
                  _TraceChip(
                    label: '${trace.summary.recordCount} records',
                    icon: Icons.receipt_long_outlined,
                  ),
                  _TraceChip(
                    label:
                        '${trace.summary.selectedRecordCount} selected records',
                    icon: Icons.checklist_outlined,
                  ),
                  _TraceChip(
                    label:
                        '${trace.summary.reviewRequiredCount} review required',
                    icon: Icons.rate_review_outlined,
                    color: trace.summary.reviewRequiredCount > 0
                        ? AppColors.warning
                        : null,
                  ),
                  _TraceChip(
                    label: '${trace.summary.transferSegmentCount} transfers',
                    icon: Icons.route_outlined,
                  ),
                  if (result.fieldTraceRecords.isNotEmpty)
                    _TraceChip(
                      label: '${result.fieldTraceRecords.length} field records',
                      icon: Icons.account_tree_outlined,
                    ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                childrenPadding: EdgeInsets.zero,
                title: const Text('Trace details'),
                children: [
                  _TraceDetails(
                    profile: profile,
                    schemaVersion:
                        result.traceSchemaVersion ?? trace.schemaVersion,
                    evidenceReferenceCount:
                        result.evidenceReferences?.length ?? 0,
                  ),
                  if (result.fieldTraceRecords.isNotEmpty)
                    PricingFieldTraceDetails(
                      schemaVersion: result.fieldTraceSchemaVersion,
                      records: result.fieldTraceRecords,
                    ),
                ],
              ),
            ],
            const SizedBox(height: AppSpacing.sm),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              childrenPadding: EdgeInsets.zero,
              title: const Text(PricingCatalogEvidenceStrings.title),
              children: [
                PricingCatalogEvidence(
                  references:
                      result.pricingCatalogContext?.catalogs.values ?? const [],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _TraceChip extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color? color;

  const _TraceChip({required this.label, required this.icon, this.color});

  @override
  Widget build(BuildContext context) {
    final effectiveColor = color ?? Theme.of(context).colorScheme.primary;

    return Chip(
      avatar: Icon(icon, color: effectiveColor, size: 18),
      label: Text(label),
      side: BorderSide(color: effectiveColor.withAlpha(96)),
    );
  }
}

class _TraceDetails extends StatelessWidget {
  final OptimizationProfileTrace? profile;
  final String? schemaVersion;
  final int evidenceReferenceCount;

  const _TraceDetails({
    required this.profile,
    required this.schemaVersion,
    required this.evidenceReferenceCount,
  });

  @override
  Widget build(BuildContext context) {
    final values = [
      if (schemaVersion != null) 'Trace schema: $schemaVersion',
      if (profile?.profileId != null) 'Profile: ${profile!.profileId}',
      if (profile?.objective != null) 'Objective: ${profile!.objective}',
      if (profile?.pricingRegistryVersion != null)
        'Pricing registry: ${profile!.pricingRegistryVersion}',
      'Evidence references: $evidenceReferenceCount',
    ];

    return Align(
      alignment: Alignment.centerLeft,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: values
            .map(
              (value) => Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: Text(
                  value,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            )
            .toList(),
      ),
    );
  }
}
