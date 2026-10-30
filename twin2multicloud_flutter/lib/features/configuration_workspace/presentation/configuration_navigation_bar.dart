import 'package:flutter/material.dart';

import '../../../theme/colors.dart';
import '../../../theme/spacing.dart';
import 'configuration_workspace_strings.dart';

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
                final textScale = MediaQuery.textScalerOf(context).scale(1);
                if (constraints.maxWidth <
                        AppSpacing.configurationNavigationWideBreakpoint ||
                    textScale >
                        AppSpacing.resolvedArchitectureWideTextScaleLimit) {
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
        Row(
          children: [
            Expanded(child: _buildBackButton()),
            const SizedBox(width: AppSpacing.sm),
            Expanded(child: _buildSaveButton()),
          ],
        ),
        if (showCalculation) ...[
          const SizedBox(height: AppSpacing.sm),
          SizedBox(
            width: double.infinity,
            child: _buildForwardButton(primary: false),
          ),
        ],
        const SizedBox(height: AppSpacing.sm),
        SizedBox(
          width: double.infinity,
          child: showCalculation
              ? _buildCalculateButton(context)
              : _buildForwardButton(primary: true),
        ),
      ],
    );
  }

  Widget _buildWide(BuildContext context) {
    return Row(
      children: [
        _buildBackButton(),
        const Spacer(),
        _buildSaveButton(),
        const SizedBox(width: AppSpacing.md),
        if (showCalculation) ...[
          _buildForwardButton(primary: false),
          const SizedBox(width: AppSpacing.md),
          _buildCalculateButton(context),
        ] else
          _buildForwardButton(primary: true),
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
        label: Text(
          isCalculating
              ? ConfigurationWorkspaceStrings.calculating
              : ConfigurationWorkspaceStrings.calculate,
        ),
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
        label: const Text(ConfigurationWorkspaceStrings.save),
      ),
    );
  }

  Widget _buildForwardButton({required bool primary}) {
    final label = showFinish
        ? ConfigurationWorkspaceStrings.finishConfiguration
        : ConfigurationWorkspaceStrings.continueAction;
    final icon = showFinish ? Icons.check_circle : Icons.arrow_forward;
    final button = primary
        ? FilledButton.icon(
            onPressed: onForward,
            icon: Icon(icon),
            label: Text(label),
          )
        : OutlinedButton.icon(
            onPressed: onForward,
            icon: Icon(icon),
            label: Text(label),
          );
    return Tooltip(message: forwardDisabledReason, child: button);
  }
}
