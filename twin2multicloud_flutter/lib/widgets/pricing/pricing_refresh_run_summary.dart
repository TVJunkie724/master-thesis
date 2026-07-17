import 'package:flutter/material.dart';

import '../../models/pricing_refresh_run.dart';
import '../../theme/spacing.dart';
import 'pricing_catalog_evidence.dart';
import 'pricing_review_strings.dart';

class PricingRefreshRunSummary extends StatelessWidget {
  final PricingRefreshRun run;

  const PricingRefreshRunSummary({super.key, required this.run});

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: AppSpacing.sm),
      title: const Text(PricingReviewStrings.latestRefresh),
      subtitle: Text(
        '${run.status} · '
        '${PricingReviewStrings.runAccessLabel(run.credentialSummary)}',
      ),
      children: [
        PricingCatalogEvidence(
          references: [
            if (run.activeCalculationReference case final reference?) reference,
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        if (run.awsTwinMakerContext case final context?)
          _AwsTwinMakerPlanSummary(
            context: context,
            refreshRunId: run.refreshRunId,
          ),
        _RunDiagnostics(run: run),
      ],
    );
  }
}

class _AwsTwinMakerPlanSummary extends StatelessWidget {
  final AwsTwinMakerPricingContext context;
  final String refreshRunId;

  const _AwsTwinMakerPlanSummary({
    required this.context,
    required this.refreshRunId,
  });

  @override
  Widget build(BuildContext context) {
    final warnings = _warnings();
    return Semantics(
      container: true,
      label: PricingReviewStrings.awsTwinMakerPlan,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            PricingReviewStrings.awsTwinMakerPlan,
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: AppSpacing.sm),
          LayoutBuilder(
            builder: (context, constraints) {
              final fields = [
                _SummaryField(
                  label: PricingReviewStrings.currentPlan,
                  value: PricingReviewStrings.planMode(
                    this.context.currentPlan.mode,
                  ),
                ),
                _SummaryField(
                  label: PricingReviewStrings.account,
                  value:
                      this.context.verifiedAccountId ??
                      PricingReviewStrings.unavailable,
                ),
                _SummaryField(
                  label: PricingReviewStrings.observed,
                  value: PricingReviewStrings.relativeObservation(
                    this.context.observedAt,
                  ),
                ),
                _SummaryField(
                  label: PricingReviewStrings.pendingPlan,
                  value: PricingReviewStrings.pendingPlanDescription(
                    this.context.pendingPlan,
                  ),
                ),
              ];
              if (constraints.maxWidth <
                  AppSpacing.pricingReviewCardBreakpoint) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (var index = 0; index < fields.length; index++) ...[
                      if (index > 0) const SizedBox(height: AppSpacing.xs),
                      fields[index],
                    ],
                  ],
                );
              }
              return Wrap(
                spacing: AppSpacing.lg,
                runSpacing: AppSpacing.xs,
                children: fields,
              );
            },
          ),
          for (final warning in warnings) ...[
            const SizedBox(height: AppSpacing.sm),
            _WarningText(message: warning),
          ],
          const SizedBox(height: AppSpacing.xs),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            childrenPadding: const EdgeInsets.only(
              left: AppSpacing.md,
              bottom: AppSpacing.sm,
            ),
            title: const Text(PricingReviewStrings.technicalDetails),
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: SelectableText(_technicalDetails()),
              ),
            ],
          ),
        ],
      ),
    );
  }

  List<String> _warnings() {
    final observationAge = DateTime.now().toUtc().difference(
      context.observedAt,
    );
    return [
      if (context.currentPlan.mode == AwsTwinMakerPricingPlanMode.basic)
        PricingReviewStrings.twinMakerBasicWarning,
      if (context.currentPlan.mode == AwsTwinMakerPricingPlanMode.tieredBundle)
        PricingReviewStrings.twinMakerBundleWarning,
      if (context.pendingPlan != null)
        PricingReviewStrings.twinMakerPendingWarning,
      if (!observationAge.isNegative &&
          observationAge > const Duration(days: 7))
        PricingReviewStrings.twinMakerStaleWarning,
    ];
  }

  String _technicalDetails() {
    final bundle = context.currentPlan.bundle;
    return [
      '${PricingReviewStrings.region}: ${context.region}',
      '${PricingReviewStrings.billableEntities}: '
          '${context.currentPlan.billableEntityCount}',
      if (bundle != null)
        '${PricingReviewStrings.bundle}: '
            '${PricingReviewStrings.bundleDescription(bundle)}',
      '${PricingReviewStrings.contextSchema}: ${context.schemaVersion}',
      if (context.connectionId != null)
        '${PricingReviewStrings.pricingConnection}: ${context.connectionId}',
      '${PricingReviewStrings.exactObservation}: '
          '${PricingReviewStrings.formatTimestamp(context.observedAt)}',
      '${PricingReviewStrings.refreshRun}: $refreshRunId',
    ].join('\n');
  }
}

class _SummaryField extends StatelessWidget {
  final String label;
  final String value;

  const _SummaryField({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Text.rich(
      TextSpan(
        children: [
          TextSpan(
            text: '$label: ',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
          TextSpan(text: value),
        ],
      ),
    );
  }
}

class _WarningText extends StatelessWidget {
  final String message;

  const _WarningText({required this.message});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.error;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.warning_amber, color: color, size: AppSpacing.iconMd),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            message,
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(color: color),
          ),
        ),
      ],
    );
  }
}

class _RunDiagnostics extends StatelessWidget {
  final PricingRefreshRun run;

  const _RunDiagnostics({required this.run});

  @override
  Widget build(BuildContext context) {
    final failureMessage = run.succeeded
        ? null
        : PricingReviewStrings.twinMakerFailureMessage(
            run.errorCode,
            run.errorMessage,
          );
    return Align(
      alignment: Alignment.centerLeft,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (failureMessage != null) ...[
            _WarningText(message: failureMessage),
            const SizedBox(height: AppSpacing.xs),
          ],
          SelectableText(PricingReviewStrings.runId(run.refreshRunId)),
        ],
      ),
    );
  }
}
