import 'package:flutter/material.dart';

import '../../models/resolved_deployment_specification.dart';
import '../../theme/spacing.dart';

class DeploymentSelectionStatus extends StatelessWidget {
  final ResolvedDeploymentReview review;
  final bool isSelecting;
  final VoidCallback? onRetry;

  const DeploymentSelectionStatus({
    super.key,
    required this.review,
    required this.isSelecting,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final presentation = _presentation(review.state);
    final canRetry =
        !isSelecting &&
        onRetry != null &&
        {
          ResolvedDeploymentReviewState.selectionRequired,
          ResolvedDeploymentReviewState.failed,
        }.contains(review.state);

    return Semantics(
      container: true,
      label: 'Deployment selection: ${presentation.title}',
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (isSelecting)
              const SizedBox.square(
                dimension: AppSpacing.iconMd,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Icon(
                presentation.icon,
                size: AppSpacing.iconMd,
                color: presentation.color(context),
              ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    presentation.title,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    presentation.description,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            if (canRetry) ...[
              const SizedBox(width: AppSpacing.sm),
              TextButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: Text(
                  review.state ==
                          ResolvedDeploymentReviewState.selectionRequired
                      ? 'Verify'
                      : 'Retry',
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StatusPresentation {
  final String title;
  final String description;
  final IconData icon;
  final Color Function(BuildContext) color;

  const _StatusPresentation({
    required this.title,
    required this.description,
    required this.icon,
    required this.color,
  });
}

_StatusPresentation _presentation(ResolvedDeploymentReviewState state) =>
    switch (state) {
      ResolvedDeploymentReviewState.ready => _StatusPresentation(
        title: 'Deployment selection ready',
        description:
            'This optimizer run is verified and selected for deployment.',
        icon: Icons.verified_outlined,
        color: (context) => Theme.of(context).colorScheme.primary,
      ),
      ResolvedDeploymentReviewState.selecting => _StatusPresentation(
        title: 'Verifying deployment selection',
        description: 'Pricing evidence and account context are being verified.',
        icon: Icons.sync,
        color: (context) => Theme.of(context).colorScheme.primary,
      ),
      ResolvedDeploymentReviewState.selectionRequired => _StatusPresentation(
        title: 'Deployment verification required',
        description:
            'Verify this resolved architecture before preparing deployment.',
        icon: Icons.pending_actions_outlined,
        color: (context) => Theme.of(context).colorScheme.tertiary,
      ),
      ResolvedDeploymentReviewState.failed => _StatusPresentation(
        title: 'Deployment verification needs attention',
        description:
            'The calculation is available, but deployment remains blocked.',
        icon: Icons.error_outline,
        color: (context) => Theme.of(context).colorScheme.error,
      ),
      ResolvedDeploymentReviewState.legacy => _StatusPresentation(
        title: 'Architecture recalculation required',
        description:
            'This saved result predates deployable resource specifications.',
        icon: Icons.history_outlined,
        color: (context) => Theme.of(context).colorScheme.tertiary,
      ),
      ResolvedDeploymentReviewState.unsupported => _StatusPresentation(
        title: 'Specification version unsupported',
        description:
            'Recalculate with this app version before preparing deployment.',
        icon: Icons.system_update_alt_outlined,
        color: (context) => Theme.of(context).colorScheme.error,
      ),
      ResolvedDeploymentReviewState.absent => _StatusPresentation(
        title: 'Deployment selection not available',
        description:
            'Calculate an architecture to resolve deployable cloud resources.',
        icon: Icons.info_outline,
        color: (context) => Theme.of(context).colorScheme.onSurfaceVariant,
      ),
    };
