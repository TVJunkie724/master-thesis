import 'package:flutter/material.dart';

import '../../theme/spacing.dart';
import '../file_inputs/zip_upload_block.dart';

class Step3QuickUploadSection extends StatelessWidget {
  final Widget uploadBlock;

  const Step3QuickUploadSection({
    super.key,
    this.uploadBlock = const ZipUploadBlock(),
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppSpacing.maxContentWidthMedium,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.folder_zip,
                  size: AppSpacing.xl - AppSpacing.xs,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: AppSpacing.md - AppSpacing.xs),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Quick Upload',
                        style: theme.textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        'Import an existing deployment project',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md - AppSpacing.xs),
            Text(
              'Upload a complete project ZIP file to automatically populate all configuration fields below. '
              'This is the fastest way to configure your deployment if you have an existing project structure. '
              'Alternatively, you can manually configure each section below.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                height: 1.5,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            uploadBlock,
          ],
        ),
      ),
    );
  }
}

class Step3ManualSeparator extends StatelessWidget {
  const Step3ManualSeparator({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppSpacing.maxContentWidthMedium,
        ),
        child: Row(
          children: [
            Expanded(child: Divider(color: theme.dividerColor)),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
              child: Text(
                'Or configure manually',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            Expanded(child: Divider(color: theme.dividerColor)),
          ],
        ),
      ),
    );
  }
}

class Step3FlowHeader extends StatelessWidget {
  final bool showFlowchart;
  final double flowchartWidth;

  const Step3FlowHeader({
    super.key,
    required this.showFlowchart,
    required this.flowchartWidth,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final editorsHeader = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.edit_document,
              size: AppSpacing.lg,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: AppSpacing.md - AppSpacing.xs),
            Expanded(
              child: Text(
                'Configuration Files',
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.xs),
        Text(
          'Upload or edit configuration files for your deployment',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );

    if (!showFlowchart) return editorsHeader;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: flowchartWidth,
          child: Column(
            children: [
              Text(
                'Data Flow',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Component architecture',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: AppSpacing.xl),
        Expanded(child: editorsHeader),
      ],
    );
  }
}

class Step3FlowFooter extends StatelessWidget {
  final bool showFlowchart;
  final double flowchartWidth;
  final Widget? legend;

  const Step3FlowFooter({
    super.key,
    required this.showFlowchart,
    required this.flowchartWidth,
    this.legend,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final infoBox = Container(
      padding: const EdgeInsets.all(AppSpacing.md - AppSpacing.xxs),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
        border: Border.all(color: theme.colorScheme.primary.withAlpha(96)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.info_outline,
            color: theme.colorScheme.primary,
            size: AppSpacing.lg - AppSpacing.xs,
          ),
          const SizedBox(width: AppSpacing.md - AppSpacing.xs),
          Expanded(
            child: Text(
              'Click "Finish Configuration" when ready.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onPrimaryContainer,
              ),
            ),
          ),
        ],
      ),
    );

    if (!showFlowchart) return infoBox;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: flowchartWidth,
          child: legend ?? const SizedBox.shrink(),
        ),
        const SizedBox(width: AppSpacing.xl),
        Expanded(child: infoBox),
      ],
    );
  }
}

class Step3LayerRow extends StatelessWidget {
  final bool showFlowchart;
  final double flowchartWidth;
  final Widget flowchart;
  final List<Widget> editors;

  const Step3LayerRow({
    super.key,
    required this.showFlowchart,
    required this.flowchartWidth,
    required this.flowchart,
    required this.editors,
  });

  @override
  Widget build(BuildContext context) {
    final editorsColumn = ConstrainedBox(
      constraints: const BoxConstraints(
        maxWidth: AppSpacing.maxContentWidthMedium,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: editors,
      ),
    );

    if (!showFlowchart) {
      return Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.lg),
        child: Center(child: editorsColumn),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: flowchartWidth, child: flowchart),
        const SizedBox(width: AppSpacing.xl),
        Flexible(
          child: Align(alignment: Alignment.topLeft, child: editorsColumn),
        ),
      ],
    );
  }
}

class Step3ArrowRow extends StatelessWidget {
  final double flowchartWidth;

  const Step3ArrowRow({super.key, required this.flowchartWidth});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        children: [
          SizedBox(
            width: flowchartWidth,
            child: Center(
              child: Icon(
                Icons.arrow_downward,
                size: AppSpacing.lg,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.xl),
          const Expanded(child: SizedBox.shrink()),
        ],
      ),
    );
  }
}

class Step3NoResultMessage extends StatelessWidget {
  const Step3NoResultMessage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.warning_amber_rounded,
            size: AppSpacing.xxl + AppSpacing.md,
            color: Colors.orange,
          ),
          const SizedBox(height: AppSpacing.md),
          Text('No Optimization Result', style: theme.textTheme.headlineSmall),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Please complete Step 2 (Optimizer) first.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}
