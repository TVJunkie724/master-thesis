import 'package:flutter/material.dart';

import '../../../theme/colors.dart';
import '../../../theme/spacing.dart';

class ConfigurationNavigationBar extends StatelessWidget {
  final String backLabel;
  final String backDisabledReason;
  final VoidCallback? onBack;
  final bool showCalculation;
  final bool isCalculating;
  final String calculationDisabledReason;
  final VoidCallback? onCalculate;
  final bool isSaving;
  final bool hasUnsavedChanges;
  final String saveDisabledReason;
  final VoidCallback? onSave;
  final bool showFinish;
  final String forwardDisabledReason;
  final VoidCallback? onForward;

  const ConfigurationNavigationBar({
    super.key,
    required this.backLabel,
    this.backDisabledReason = '',
    required this.onBack,
    required this.showCalculation,
    required this.isCalculating,
    required this.calculationDisabledReason,
    required this.onCalculate,
    required this.isSaving,
    required this.hasUnsavedChanges,
    required this.saveDisabledReason,
    required this.onSave,
    required this.showFinish,
    required this.forwardDisabledReason,
    required this.onForward,
  });

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: Theme.of(context).dividerColor)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.md - AppSpacing.xs,
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppSpacing.maxContentWidthLarge,
            ),
            child: LayoutBuilder(
              builder: (context, constraints) {
                if (constraints.maxWidth <
                    AppSpacing.configurationNavigationWideBreakpoint) {
                  return _buildCompact(context);
                }
                return _buildWide(context);
              },
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCompact(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (showCalculation) ...[
          _buildCalculateButton(context),
          const SizedBox(height: AppSpacing.sm),
        ],
        Row(
          children: [
            Expanded(child: _buildBackButton()),
            const SizedBox(width: AppSpacing.sm),
            Expanded(child: _buildSaveButton()),
            const SizedBox(width: AppSpacing.sm),
            Expanded(child: _buildForwardButton()),
          ],
        ),
      ],
    );
  }

  Widget _buildWide(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Align(
            alignment: Alignment.centerLeft,
            child: _buildBackButton(),
          ),
        ),
        Expanded(
          child: Center(
            child: showCalculation
                ? _buildCalculateButton(context)
                : const SizedBox.shrink(),
          ),
        ),
        Expanded(
          child: Align(
            alignment: Alignment.centerRight,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildSaveButton(),
                const SizedBox(width: AppSpacing.md),
                _buildForwardButton(),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildBackButton() {
    return Tooltip(
      message: backDisabledReason,
      child: OutlinedButton.icon(
        onPressed: onBack,
        icon: const Icon(Icons.arrow_back),
        label: Text(backLabel),
      ),
    );
  }

  Widget _buildCalculateButton(BuildContext context) {
    return Tooltip(
      message: calculationDisabledReason,
      child: FilledButton.icon(
        onPressed: onCalculate,
        icon: isCalculating
            ? const SizedBox(
                width: AppSpacing.iconMd,
                height: AppSpacing.iconMd,
                child: CircularProgressIndicator(strokeWidth: AppSpacing.xxs),
              )
            : const Icon(Icons.calculate),
        label: Text(isCalculating ? 'CALCULATING...' : 'CALCULATE'),
      ),
    );
  }

  Widget _buildSaveButton() {
    return Tooltip(
      message: saveDisabledReason,
      child: OutlinedButton.icon(
        onPressed: onSave,
        icon: Stack(
          clipBehavior: Clip.none,
          children: [
            if (isSaving)
              const SizedBox(
                width: AppSpacing.iconMd,
                height: AppSpacing.iconMd,
                child: CircularProgressIndicator(strokeWidth: AppSpacing.xxs),
              )
            else
              const Icon(Icons.save),
            if (hasUnsavedChanges && !isSaving)
              Positioned(
                right: -AppSpacing.xs,
                top: -AppSpacing.xs,
                child: Container(
                  width: AppSpacing.sm + AppSpacing.xxs,
                  height: AppSpacing.sm + AppSpacing.xxs,
                  decoration: const BoxDecoration(
                    color: AppColors.warning,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
          ],
        ),
        label: const Text('Save'),
      ),
    );
  }

  Widget _buildForwardButton() {
    return Tooltip(
      message: forwardDisabledReason,
      child: showFinish
          ? FilledButton.icon(
              onPressed: onForward,
              icon: const Icon(Icons.check_circle),
              label: const Text('Finish Configuration'),
            )
          : FilledButton.icon(
              onPressed: onForward,
              icon: const Icon(Icons.arrow_forward),
              label: const Text('Continue'),
            ),
    );
  }
}
