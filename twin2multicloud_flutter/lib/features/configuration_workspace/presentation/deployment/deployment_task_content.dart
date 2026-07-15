import 'package:flutter/material.dart';

import '../../../../bloc/wizard/wizard.dart';
import '../../../../theme/spacing.dart';
import '../../../../widgets/architecture_layer_builder.dart';
import '../../../../widgets/file_inputs/collapsible_section.dart';
import '../../../../widgets/step3/step3_layout_widgets.dart';
import '../../domain/configuration_journey.dart';
import 'deployment_config_section.dart';
import 'deployment_contracts.dart';
import 'deployment_layer_overview.dart';

class DeploymentTaskContent extends StatelessWidget {
  static const double flowchartBreakpoint = 900;
  static const double flowchartWidth = 450;

  final WizardState state;
  final ConfigurationTaskId? taskId;
  final WizardEventSink onEvent;
  final Widget zipUploadBlock;
  final VoidCallback onUploadGlb;
  final VoidCallback onDeleteGlb;

  const DeploymentTaskContent({
    super.key,
    required this.state,
    required this.taskId,
    required this.onEvent,
    required this.zipUploadBlock,
    required this.onUploadGlb,
    required this.onDeleteGlb,
  });

  DeploymentTaskFocus get _focus => switch (taskId) {
    ConfigurationTaskId.dataContracts => DeploymentTaskFocus.dataContracts,
    ConfigurationTaskId.userLogic => DeploymentTaskFocus.userLogic,
    ConfigurationTaskId.twinAssets => DeploymentTaskFocus.twinAssets,
    _ => DeploymentTaskFocus.all,
  };

  @override
  Widget build(BuildContext context) {
    final layerBuilder = ArchitectureLayerBuilder(
      calcResult: state.calcResult,
      calcParams: state.calcParams,
    );
    if (_focus == DeploymentTaskFocus.all) {
      return _LayerAlignedDeploymentTask(
        state: state,
        layerBuilder: layerBuilder,
        onEvent: onEvent,
        zipUploadBlock: zipUploadBlock,
        onUploadGlb: onUploadGlb,
        onDeleteGlb: onDeleteGlb,
      );
    }
    return _FocusedDeploymentTask(
      state: state,
      layerBuilder: layerBuilder,
      focus: _focus,
      onEvent: onEvent,
      zipUploadBlock: zipUploadBlock,
      onUploadGlb: onUploadGlb,
      onDeleteGlb: onDeleteGlb,
    );
  }
}

class _FocusedDeploymentTask extends StatelessWidget {
  final WizardState state;
  final ArchitectureLayerBuilder layerBuilder;
  final DeploymentTaskFocus focus;
  final WizardEventSink onEvent;
  final Widget zipUploadBlock;
  final VoidCallback onUploadGlb;
  final VoidCallback onDeleteGlb;

  const _FocusedDeploymentTask({
    required this.state,
    required this.layerBuilder,
    required this.focus,
    required this.onEvent,
    required this.zipUploadBlock,
    required this.onUploadGlb,
    required this.onDeleteGlb,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      key: ValueKey('deployment-task-${focus.name}'),
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: DeploymentTaskContent.flowchartBreakpoint,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (focus == DeploymentTaskFocus.dataContracts) ...[
                Step3QuickUploadSection(uploadBlock: zipUploadBlock),
                const SizedBox(height: AppSpacing.lg),
                const Step3ManualSeparator(),
                const SizedBox(height: AppSpacing.lg),
                DeploymentConfigSection(
                  state: state,
                  layerBuilder: layerBuilder,
                  onEvent: onEvent,
                  showHierarchy: false,
                ),
                const SizedBox(height: AppSpacing.lg),
              ],
              if (focus == DeploymentTaskFocus.twinAssets) ...[
                DeploymentConfigSection(
                  state: state,
                  layerBuilder: layerBuilder,
                  onEvent: onEvent,
                  showCore: false,
                  showGenerated: false,
                ),
                const SizedBox(height: AppSpacing.lg),
              ],
              DeploymentLayerOverview(
                state: state,
                layerBuilder: layerBuilder,
                focus: focus,
                showFlowchart: false,
                flowchartWidth: DeploymentTaskContent.flowchartWidth,
                onEvent: onEvent,
                onUploadGlb: onUploadGlb,
                onDeleteGlb: onDeleteGlb,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LayerAlignedDeploymentTask extends StatelessWidget {
  final WizardState state;
  final ArchitectureLayerBuilder layerBuilder;
  final WizardEventSink onEvent;
  final Widget zipUploadBlock;
  final VoidCallback onUploadGlb;
  final VoidCallback onDeleteGlb;

  const _LayerAlignedDeploymentTask({
    required this.state,
    required this.layerBuilder,
    required this.onEvent,
    required this.zipUploadBlock,
    required this.onUploadGlb,
    required this.onDeleteGlb,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final showFlowchart =
            constraints.maxWidth >= DeploymentTaskContent.flowchartBreakpoint;
        return SingleChildScrollView(
          key: const ValueKey('deployment-task-all'),
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Step3QuickUploadSection(uploadBlock: zipUploadBlock),
              const SizedBox(height: AppSpacing.xl),
              const Step3ManualSeparator(),
              const SizedBox(height: AppSpacing.lg),
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    maxWidth: AppSpacing.maxContentWidthMedium,
                  ),
                  child: CollapsibleSection(
                    sectionNumber: 1,
                    title: 'Configuration Files',
                    description:
                        'Core deployment settings and device definitions',
                    icon: Icons.settings,
                    initiallyExpanded:
                        state.mode == WizardMode.edit && !state.isSection2Valid,
                    isValid: state.isSection2Valid,
                    forceCollapsed: state.forceCollapseSections,
                    child: DeploymentConfigSection(
                      state: state,
                      layerBuilder: layerBuilder,
                      onEvent: onEvent,
                    ),
                  ),
                ),
              ),
              Center(
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    maxWidth: showFlowchart
                        ? DeploymentTaskContent.flowchartWidth +
                              AppSpacing.xl +
                              AppSpacing.maxContentWidthMedium +
                              AppSpacing.xl
                        : AppSpacing.maxContentWidthMedium,
                  ),
                  child: CollapsibleSection(
                    sectionNumber: 2,
                    title: 'User Functions & Assets',
                    description:
                        'Custom processors, workflows, and visualization config',
                    icon: Icons.code,
                    initiallyExpanded:
                        state.mode == WizardMode.edit && !state.isSection3Valid,
                    collapsedMaxWidth: AppSpacing.maxContentWidthMedium,
                    isValid: state.isSection3Valid,
                    forceCollapsed: state.forceCollapseSections,
                    infoHint:
                        'Inputs here depend on Section 1 configuration files (config_events.json, config_iot_devices.json)',
                    child: DeploymentLayerOverview(
                      state: state,
                      layerBuilder: layerBuilder,
                      focus: DeploymentTaskFocus.all,
                      showFlowchart: showFlowchart,
                      flowchartWidth: DeploymentTaskContent.flowchartWidth,
                      onEvent: onEvent,
                      onUploadGlb: onUploadGlb,
                      onDeleteGlb: onDeleteGlb,
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
