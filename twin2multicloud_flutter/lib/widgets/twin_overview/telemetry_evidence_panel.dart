import 'package:flutter/material.dart';

import '../../models/deployment_verification.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

/// Read-only presentation of durable telemetry roundtrip evidence.
class TelemetryEvidencePanel extends StatelessWidget {
  final bool isLoading;
  final bool isRunning;
  final String? historyError;
  final String? activeVerificationId;
  final TelemetryVerificationEvidence? terminalEvidence;
  final TelemetryVerificationRecord? latestRecord;
  final List<TelemetryVerificationRecord> history;

  const TelemetryEvidencePanel({
    super.key,
    required this.isLoading,
    required this.isRunning,
    required this.historyError,
    required this.activeVerificationId,
    required this.terminalEvidence,
    required this.latestRecord,
    required this.history,
  });

  @override
  Widget build(BuildContext context) {
    final evidence = terminalEvidence ?? latestRecord?.result;
    final status = isRunning
        ? TelemetryVerificationStatus.running
        : evidence?.status ?? latestRecord?.status;
    final earlier = latestRecord == null
        ? history
        : history.where((record) => record.id != latestRecord!.id).toList();

    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerLowest,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        side: BorderSide(color: Theme.of(context).dividerColor),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _Header(status: status),
            if (isLoading && latestRecord == null && !isRunning) ...[
              const SizedBox(height: AppSpacing.md),
              const LinearProgressIndicator(),
              const SizedBox(height: AppSpacing.sm),
              const Text('Loading persisted verification evidence...'),
            ] else if (isRunning) ...[
              const SizedBox(height: AppSpacing.md),
              Text(
                activeVerificationId == null
                    ? 'Starting one telemetry roundtrip...'
                    : 'Verification $activeVerificationId is running.',
              ),
            ] else if (latestRecord == null && terminalEvidence == null) ...[
              const SizedBox(height: AppSpacing.md),
              const Text('No persisted telemetry verification is available.'),
            ] else ...[
              const SizedBox(height: AppSpacing.md),
              _LatestEvidence(record: latestRecord, evidence: evidence),
            ],
            if (historyError != null) ...[
              const SizedBox(height: AppSpacing.md),
              _ErrorNotice(message: historyError!),
            ],
            if (evidence != null && evidence.evidence.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              _PhaseEvidence(evidence: evidence),
            ],
            if (earlier.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              _EarlierRuns(records: earlier),
            ],
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  final TelemetryVerificationStatus? status;

  const _Header({required this.status});

  @override
  Widget build(BuildContext context) {
    final visual = _visual(status);
    return Row(
      children: [
        Icon(visual.icon, color: visual.color),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            'Persisted telemetry evidence',
            style: Theme.of(context).textTheme.titleSmall,
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

class _LatestEvidence extends StatelessWidget {
  final TelemetryVerificationRecord? record;
  final TelemetryVerificationEvidence? evidence;

  const _LatestEvidence({required this.record, required this.evidence});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (evidence != null) ...[
          Wrap(
            spacing: AppSpacing.lg,
            runSpacing: AppSpacing.sm,
            children: [
              _Fact(label: 'Trace', value: evidence!.traceId),
              _Fact(
                label: 'Checks',
                value:
                    '${evidence!.passCount} pass · ${evidence!.failCount} fail · ${evidence!.skipCount} skip',
              ),
              _Fact(
                label: 'Elapsed',
                value: '${evidence!.totalTime.toStringAsFixed(2)} s',
              ),
            ],
          ),
          if (evidence!.failedPhase != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Failed phase: ${evidence!.failedPhase}',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: AppColors.error,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ] else if (record != null) ...[
          Text(
            record!.errorMessage ?? 'The verification produced no phase proof.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: record!.status == TelemetryVerificationStatus.notRun
                  ? AppColors.warning
                  : AppColors.error,
            ),
          ),
        ],
        if (record != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Requested ${_timestamp(record!.requestedAt)}'
            '${record!.completedAt == null ? '' : ' · completed ${_timestamp(record!.completedAt!)}'}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ],
    );
  }
}

class _Fact extends StatelessWidget {
  final String label;
  final String value;

  const _Fact({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '$label $value',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          Text(value, style: Theme.of(context).textTheme.bodyMedium),
        ],
      ),
    );
  }
}

class _PhaseEvidence extends StatelessWidget {
  final TelemetryVerificationEvidence evidence;

  const _PhaseEvidence({required this.evidence});

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      key: const Key('telemetry-phase-evidence'),
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      initiallyExpanded: evidence.status == TelemetryVerificationStatus.fail,
      title: const Text('Phase evidence'),
      subtitle: Text('${evidence.evidence.length} persisted phase records'),
      children: [
        for (final phase in evidence.evidence)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(
              Icons.check_circle_outline,
              color: AppColors.success,
            ),
            title: Text(
              'Phase ${phase.phase} · ${_words(phase.kind.apiValue)}',
            ),
            subtitle: Text(
              [
                phase.provider.toUpperCase(),
                if (phase.recordCount != null)
                  '${phase.recordCount} correlated record',
                if (phase.correlation != null)
                  'correlation ${_words(phase.correlation!)}',
              ].join(' · '),
            ),
          ),
      ],
    );
  }
}

class _EarlierRuns extends StatelessWidget {
  final List<TelemetryVerificationRecord> records;

  const _EarlierRuns({required this.records});

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      key: const Key('telemetry-earlier-runs'),
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      title: const Text('Earlier persisted runs'),
      subtitle: Text('${records.length} earlier verification records'),
      children: [
        for (final record in records)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(
              _visual(record.status).icon,
              color: _visual(record.status).color,
            ),
            title: Text(record.traceId ?? record.id),
            subtitle: Text(
              '${_visual(record.status).label} · ${_timestamp(record.requestedAt)}',
            ),
          ),
      ],
    );
  }
}

class _ErrorNotice extends StatelessWidget {
  final String message;

  const _ErrorNotice({required this.message});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.error_outline, color: AppColors.error),
        const SizedBox(width: AppSpacing.sm),
        Expanded(child: Text('History unavailable: $message')),
      ],
    );
  }
}

({String label, IconData icon, Color color}) _visual(
  TelemetryVerificationStatus? status,
) => switch (status) {
  TelemetryVerificationStatus.running => (
    label: 'RUNNING',
    icon: Icons.sync,
    color: AppColors.warning,
  ),
  TelemetryVerificationStatus.pass => (
    label: 'PASS',
    icon: Icons.verified_outlined,
    color: AppColors.success,
  ),
  TelemetryVerificationStatus.fail => (
    label: 'FAIL',
    icon: Icons.error_outline,
    color: AppColors.error,
  ),
  TelemetryVerificationStatus.notRun => (
    label: 'NOT RUN',
    icon: Icons.block_outlined,
    color: AppColors.warning,
  ),
  null => (
    label: 'NO EVIDENCE',
    icon: Icons.history_toggle_off,
    color: AppColors.warning,
  ),
};

String _words(String value) => value.replaceAll('_', ' ');

String _timestamp(DateTime value) =>
    value.toLocal().toString().split('.').first;
