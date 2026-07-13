import 'package:flutter/material.dart';

import '../../models/pricing_refresh_run.dart';
import '../../theme/spacing.dart';
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
        Align(
          alignment: Alignment.centerLeft,
          child: SelectableText(PricingReviewStrings.runId(run.refreshRunId)),
        ),
      ],
    );
  }
}
