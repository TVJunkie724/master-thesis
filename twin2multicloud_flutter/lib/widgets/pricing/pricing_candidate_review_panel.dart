import 'package:flutter/material.dart';

import '../../models/pricing_candidate_review.dart';
import '../../theme/spacing.dart';
import 'pricing_review_strings.dart';

typedef PricingDecisionCallback =
    void Function(String reportId, String decision);

class PricingCandidateReviewPanel extends StatelessWidget {
  final List<PricingCandidateReport> reports;
  final Map<String, String> selectedCandidateIds;
  final Map<String, PricingTrace> tracesByReportId;
  final Map<String, String> traceErrorsByReportId;
  final Set<String> loadingTraceReportIds;
  final Set<String> savingDecisionReportIds;
  final Map<String, PricingReviewDecision> decisionsByReportId;
  final void Function(String reportId, String candidateId) onCandidateSelected;
  final ValueChanged<String> onTraceRequested;
  final PricingDecisionCallback onDecisionRequested;

  const PricingCandidateReviewPanel({
    super.key,
    required this.reports,
    required this.selectedCandidateIds,
    required this.tracesByReportId,
    required this.traceErrorsByReportId,
    required this.loadingTraceReportIds,
    required this.savingDecisionReportIds,
    required this.decisionsByReportId,
    required this.onCandidateSelected,
    required this.onTraceRequested,
    required this.onDecisionRequested,
  });

  @override
  Widget build(BuildContext context) {
    if (reports.isEmpty) {
      return Text(
        PricingReviewStrings.noCandidateEvidence,
        style: Theme.of(context).textTheme.bodySmall,
      );
    }
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      title: Text(PricingReviewStrings.reviewResults(reports.length)),
      subtitle: const Text(PricingReviewStrings.candidateEvidenceCollapsed),
      children: [for (final report in reports) _buildReport(context, report)],
    );
  }

  Widget _buildReport(BuildContext context, PricingCandidateReport report) {
    final selectedId = selectedCandidateIds[report.reportId];
    final saved = decisionsByReportId[report.reportId];
    final isSaving = savingDecisionReportIds.contains(report.reportId);
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: AppSpacing.md),
      title: Text(report.intentId),
      subtitle: Text(
        PricingReviewStrings.candidateCount(
          report.reviewState,
          report.candidates.length,
        ),
      ),
      children: [
        RadioGroup<String>(
          groupValue: selectedId,
          onChanged: saved == null
              ? (value) {
                  if (value != null) {
                    onCandidateSelected(report.reportId, value);
                  }
                }
              : (_) {},
          child: Column(
            children: [
              for (final candidate in report.candidates)
                RadioListTile<String>(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  value: candidate.candidateId,
                  enabled: saved == null,
                  title: Text(
                    PricingReviewStrings.candidateValue(
                      candidate.value,
                      candidate.currency,
                      candidate.unit,
                    ),
                  ),
                  subtitle: Text(_candidateContext(report, candidate)),
                ),
            ],
          ),
        ),
        _InfoLine(
          icon: report.aiSuggestion.enabled
              ? Icons.auto_awesome
              : Icons.auto_awesome_outlined,
          text: report.aiSuggestion.enabled
              ? PricingReviewStrings.aiSuggests(
                  report.aiSuggestion.candidateId,
                  report.aiSuggestion.rationale,
                )
              : PricingReviewStrings.aiDisabled,
        ),
        if (saved != null)
          _InfoLine(
            icon: Icons.check_circle_outline,
            text: PricingReviewStrings.savedDecision(saved.decision),
          )
        else
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              FilledButton.icon(
                onPressed: selectedId == null || isSaving
                    ? null
                    : () => onDecisionRequested(
                        report.reportId,
                        selectedId == report.deterministicSelection.candidateId
                            ? 'approve'
                            : 'select_alternative',
                      ),
                icon: const Icon(Icons.check),
                label: const Text(PricingReviewStrings.saveSelection),
              ),
              TextButton(
                onPressed: isSaving
                    ? null
                    : () => onDecisionRequested(report.reportId, 'defer'),
                child: const Text(PricingReviewStrings.decideLater),
              ),
            ],
          ),
        const SizedBox(height: AppSpacing.sm),
        _buildTrace(context, report.reportId),
      ],
    );
  }

  Widget _buildTrace(BuildContext context, String reportId) {
    final trace = tracesByReportId[reportId];
    final error = traceErrorsByReportId[reportId];
    final loading = loadingTraceReportIds.contains(reportId);
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      title: const Text(PricingReviewStrings.traceTitle),
      onExpansionChanged: (expanded) {
        if (expanded && trace == null && error == null) {
          onTraceRequested(reportId);
        }
      },
      children: [
        if (loading) const LinearProgressIndicator(),
        if (error != null)
          _InlineError(
            message: error,
            onRetry: () => onTraceRequested(reportId),
          ),
        if (trace != null)
          Align(
            alignment: Alignment.centerLeft,
            child: SelectableText(
              PricingReviewStrings.traceText(trace),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
      ],
    );
  }

  String _candidateContext(
    PricingCandidateReport report,
    PricingReviewCandidate candidate,
  ) {
    final labels = <String>[
      candidate.sourceLabel,
      candidate.fieldPath,
      if (candidate.candidateId == report.deterministicSelection.candidateId)
        PricingReviewStrings.contractSelection,
      if (report.aiSuggestion.enabled &&
          candidate.candidateId == report.aiSuggestion.candidateId)
        PricingReviewStrings.aiSuggestion,
    ];
    return labels.join(' · ');
  }
}

class _InfoLine extends StatelessWidget {
  final IconData icon;
  final String text;

  const _InfoLine({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: AppSpacing.iconMd),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}

class _InlineError extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _InlineError({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          Icons.warning_amber,
          color: Theme.of(context).colorScheme.error,
          size: AppSpacing.iconMd,
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(child: Text(message)),
        TextButton(
          onPressed: onRetry,
          child: const Text(PricingReviewStrings.retry),
        ),
      ],
    );
  }
}
