import 'package:flutter/material.dart';

import '../../theme/colors.dart';
import '../../theme/spacing.dart';

class Step3GlbUploadCard extends StatelessWidget {
  final bool isUploaded;
  final bool isBusy;
  final VoidCallback onDelete;
  final VoidCallback onUpload;

  const Step3GlbUploadCard({
    super.key,
    required this.isUploaded,
    this.isBusy = false,
    required this.onDelete,
    required this.onUpload,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
        border: Border.all(
          color: isUploaded ? AppColors.success : theme.dividerColor,
        ),
      ),
      child: Row(
        children: [
          Icon(
            isUploaded ? Icons.check_circle : Icons.view_in_ar,
            color: isUploaded
                ? AppColors.success
                : theme.colorScheme.onSurfaceVariant,
            size: AppSpacing.xl,
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'scene.glb',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  isUploaded
                      ? '3D model uploaded'
                      : 'Upload 3D model for visualization',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: isUploaded
                        ? AppColors.success
                        : theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          if (isBusy)
            const SizedBox(
              width: AppSpacing.lg,
              height: AppSpacing.lg,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          else if (isUploaded)
            IconButton(
              icon: const Icon(Icons.delete_outline, color: AppColors.error),
              tooltip: 'Delete GLB',
              onPressed: onDelete,
            )
          else
            ElevatedButton.icon(
              icon: const Icon(Icons.upload_file, size: 18),
              label: const Text('Upload GLB'),
              onPressed: onUpload,
            ),
        ],
      ),
    );
  }
}
