import 'package:flutter/material.dart';

import '../../models/deployer_artifact_validation.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

class ArtifactValidationFeedbackView extends StatelessWidget {
  final DeployerArtifactValidationFeedback? feedback;
  final bool isValidating;

  const ArtifactValidationFeedbackView({
    super.key,
    this.feedback,
    this.isValidating = false,
  });

  @override
  Widget build(BuildContext context) {
    if (!isValidating && feedback == null) return const SizedBox.shrink();
    final theme = Theme.of(context);
    final valid = feedback?.valid == true;
    final color = valid ? AppColors.success : AppColors.error;

    return Semantics(
      liveRegion: true,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
          border: Border.all(color: color),
        ),
        child: Row(
          children: [
            if (isValidating)
              const SizedBox.square(
                dimension: AppSpacing.iconSm,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Icon(
                valid ? Icons.check_circle_outline : Icons.error_outline,
                color: color,
                size: AppSpacing.iconMd,
              ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                isValidating ? 'Validating...' : feedback!.message,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(color: color),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
