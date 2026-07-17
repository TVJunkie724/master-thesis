import 'package:flutter/material.dart';

import '../../models/calc_result.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

class PricingFieldTraceDetails extends StatelessWidget {
  final String? schemaVersion;
  final List<PricingFieldTraceRecord> records;

  const PricingFieldTraceDetails({
    super.key,
    required this.schemaVersion,
    required this.records,
  });

  @override
  Widget build(BuildContext context) {
    final grouped = <String, List<PricingFieldTraceRecord>>{};
    for (final record in records) {
      grouped.putIfAbsent(record.provider, () => []).add(record);
    }

    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      title: const Text('Field-level audit'),
      subtitle: Text(
        schemaVersion == null
            ? '${records.length} records'
            : '${records.length} records · $schemaVersion',
      ),
      children: grouped.entries
          .map(
            (entry) => ExpansionTile(
              tilePadding: EdgeInsets.zero,
              childrenPadding: const EdgeInsets.only(left: AppSpacing.sm),
              title: Text(entry.key.toUpperCase()),
              subtitle: Text(
                '${entry.value.where((item) => item.isSelected).length} selected · '
                '${entry.value.where((item) => item.isUnsupported).length} unsupported',
              ),
              children: entry.value
                  .map((record) => _FieldTraceRecordTile(record: record))
                  .toList(growable: false),
            ),
          )
          .toList(growable: false),
    );
  }
}

class _FieldTraceRecordTile extends StatelessWidget {
  final PricingFieldTraceRecord record;

  const _FieldTraceRecordTile({required this.record});

  @override
  Widget build(BuildContext context) {
    final statusColor = switch (record.selectionStatus) {
      'selected' => AppColors.success,
      'unsupported' => AppColors.error,
      _ => Theme.of(context).colorScheme.onSurfaceVariant,
    };
    final contribution = record.costContribution == null
        ? 'No result amount'
        : '${record.costContribution!.toStringAsFixed(6)} ${record.outputMetricUnit ?? ''}'
              .trim();

    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(
        left: AppSpacing.sm,
        right: AppSpacing.sm,
        bottom: AppSpacing.sm,
      ),
      title: Text('${record.layer} · ${record.service}'),
      subtitle: Wrap(
        spacing: AppSpacing.sm,
        runSpacing: AppSpacing.xs,
        children: [
          Text(
            record.selectionStatus,
            style: TextStyle(color: statusColor, fontWeight: FontWeight.w600),
          ),
          Text(record.intentId),
        ],
      ),
      children: [
        _DetailLine(label: 'Formula', value: record.formulaRef),
        _DetailLine(label: 'Source', value: record.sourceType),
        _DetailLine(label: 'Verification', value: record.verificationStatus),
        _DetailLine(label: 'Result scope', value: record.costContributionScope),
        _DetailLine(label: 'Amount', value: contribution),
        if (!record.costContributionIsAdditive)
          const _DetailLine(
            label: 'Precision',
            value: 'Shared diagnostic amount; do not add across field records.',
          ),
        if (record.selectedEvidenceId != null)
          _DetailLine(label: 'Evidence', value: record.selectedEvidenceId!),
        _DetailLine(
          label: 'Provider alternatives',
          value: '${record.alternativeRecordIds.length}',
        ),
        _DetailLine(
          label: 'Rejected evidence rows',
          value: '${record.rejectedEvidenceIds.length}',
        ),
      ],
    );
  }
}

class _DetailLine extends StatelessWidget {
  final String label;
  final String value;

  const _DetailLine({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final labelStyle = Theme.of(
      context,
    ).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w600);

    return LayoutBuilder(
      builder: (context, constraints) {
        final content = constraints.maxWidth < 360
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: labelStyle),
                  const SizedBox(height: AppSpacing.xs),
                  SelectableText(value),
                ],
              )
            : Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(width: 136, child: Text(label, style: labelStyle)),
                  Expanded(child: SelectableText(value)),
                ],
              );

        return Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.xs),
          child: content,
        );
      },
    );
  }
}
