import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../bloc/wizard/wizard.dart';
import '../../../theme/spacing.dart';

class ArchitectureProfileChangeDialog extends StatelessWidget {
  const ArchitectureProfileChangeDialog({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<WizardBloc, WizardState>(
      listenWhen: (previous, current) =>
          previous.architectureChangePhase != current.architectureChangePhase,
      listener: (context, state) {
        if ({
          ArchitectureChangePhase.idle,
          ArchitectureChangePhase.conflict,
        }.contains(state.architectureChangePhase)) {
          Navigator.of(context).pop();
        }
      },
      builder: (context, state) {
        final preview = state.architectureChangePreview;
        final busy =
            state.architectureChangePhase == ArchitectureChangePhase.submitting;
        return Focus(
          autofocus: true,
          onKeyEvent: (_, event) {
            if (event is KeyDownEvent &&
                event.logicalKey == LogicalKeyboardKey.escape &&
                !busy) {
              context.read<WizardBloc>().add(
                const WizardArchitectureProfileChangeCancelled(),
              );
              return KeyEventResult.handled;
            }
            return KeyEventResult.ignored;
          },
          child: PopScope(
            canPop: {
              ArchitectureChangePhase.idle,
              ArchitectureChangePhase.conflict,
            }.contains(state.architectureChangePhase),
            onPopInvokedWithResult: (didPop, _) {
              if (didPop || busy) {
                return;
              }
              context.read<WizardBloc>().add(
                const WizardArchitectureProfileChangeCancelled(),
              );
            },
            child: AlertDialog(
              title: const Text('Change architecture profile?'),
              content: ConstrainedBox(
                constraints: const BoxConstraints(
                  maxWidth: AppSpacing.dialogContentMaxWidth,
                ),
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Management calculated the exact effects of this change. Review them before continuing.',
                      ),
                      const SizedBox(height: AppSpacing.md),
                      if (preview != null) ...[
                        _EffectGroup(
                          title: 'Workload fields',
                          values: preview.incompatibleWorkloadFields
                              .map((item) => item.displayLabel)
                              .toList(growable: false),
                        ),
                        _EffectGroup(
                          title: 'User-function bindings',
                          values: preview.incompatibleExtensionBindings
                              .map((item) => item.slotId)
                              .toList(growable: false),
                        ),
                        _EffectGroup(
                          title: 'Deployment readiness',
                          values: preview.deploymentReadinessSections,
                        ),
                        if (preview.selectedCalculationRunId != null)
                          _EffectGroup(
                            title: 'Selected optimizer run',
                            values: [preview.selectedCalculationRunId!],
                          ),
                        if (preview.incompatibleWorkloadFields.isEmpty &&
                            preview.incompatibleExtensionBindings.isEmpty &&
                            preview.deploymentReadinessSections.isEmpty &&
                            preview.selectedCalculationRunId == null)
                          const Text(
                            'No persisted configuration is invalidated.',
                          ),
                      ],
                      if (state.architectureChangeError != null) ...[
                        const SizedBox(height: AppSpacing.md),
                        Text(
                          state.architectureChangeError!,
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                color: Theme.of(context).colorScheme.error,
                              ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: busy
                      ? null
                      : () => context.read<WizardBloc>().add(
                          const WizardArchitectureProfileChangeCancelled(),
                        ),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: busy || preview == null
                      ? null
                      : () => context.read<WizardBloc>().add(
                          const WizardArchitectureProfileChangeConfirmed(),
                        ),
                  child: busy
                      ? const SizedBox.square(
                          dimension: AppSpacing.iconSm,
                          child: CircularProgressIndicator(
                            strokeWidth:
                                AppSpacing.compactProgressIndicatorStrokeWidth,
                          ),
                        )
                      : const Text('Change profile'),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _EffectGroup extends StatelessWidget {
  final String title;
  final List<String> values;

  const _EffectGroup({required this.title, required this.values});

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Semantics(
        label: '$title: ${values.join(', ')}',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            for (final value in values) Text('• $value'),
          ],
        ),
      ),
    );
  }
}
