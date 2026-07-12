import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../bloc/wizard/wizard.dart';
import '../../models/deployer_artifact_validation.dart';
import '../../config/step3_examples.dart';
import '../../config/step3_constraints.dart';
import '../../providers/twins_provider.dart';
import '../../utils/api_error_handler.dart';
import '../../widgets/architecture_layer_builder.dart';
import '../../widgets/file_inputs/file_editor_block.dart';
import '../../widgets/file_inputs/function_package_block.dart';
import '../../widgets/file_inputs/collapsible_section.dart';
import '../../widgets/file_inputs/collapsible_block_wrapper.dart';
import '../../widgets/file_inputs/config_json_visualization_block.dart';
import '../../widgets/file_inputs/config_visualization_block.dart';
import '../../widgets/step3/info_cards.dart';
import '../../widgets/step3/step3_glb_upload_card.dart';
import '../../widgets/step3/step3_layout_widgets.dart';

/// Step 3: Deployer Configuration - BLoC version
///
/// Three collapsible sections:
/// 1. Quick Upload - Project zip file
/// 2. Configuration Files - Core deployment config
/// 3. User Functions & Assets - Layer-aligned file editors
class Step3Deployer extends StatefulWidget {
  const Step3Deployer({super.key});

  @override
  State<Step3Deployer> createState() => _Step3DeployerState();
}

class _Step3DeployerState extends State<Step3Deployer> {
  ArchitectureLayerBuilder? _layerBuilder;

  // Breakpoint for showing flowchart column
  static const double _flowchartBreakpoint = 900;
  static const double _flowchartWidth = 450;

  void _requestValidation(
    BuildContext context,
    WizardState state,
    DeployerArtifactType type,
    String content, {
    String? entityId,
    String? providerOverride,
  }) {
    final provider = switch (type.boundary) {
      DeployerValidationBoundary.config => null,
      DeployerValidationBoundary.layer2 => state.layer2Provider,
      DeployerValidationBoundary.layer4Or5 =>
        providerOverride ?? state.layer4Provider,
    };
    context.read<WizardBloc>().add(
      WizardArtifactValidationRequested(
        DeployerArtifactValidationRequest(
          type: type,
          content: content,
          provider: provider,
          entityId: entityId,
        ),
      ),
    );
  }

  /// Build dynamic L2 inputs based on Section 2 validation state
  List<Widget> _buildL2DynamicInputs(BuildContext context, WizardState state) {
    final widgets = <Widget>[];

    // === PROCESSORS ===
    // Show one processor input per device from validated config_iot_devices.json
    if (!state.configIotDevicesValidated) {
      widgets.add(
        Step3InfoCards.dependencyInfo(
          context,
          'Validate config_iot_devices.json first to enable processor function inputs.',
        ),
      );
    } else if (state.deviceIds.isEmpty) {
      widgets.add(
        Step3InfoCards.emptyState(
          context,
          'No devices found in config_iot_devices.json',
        ),
      );
    } else {
      for (final deviceId in state.deviceIds) {
        widgets.add(
          FunctionPackageBlock(
            codeFilename: 'processors/$deviceId/lambda_function.py',
            description: 'Processor Lambda for $deviceId',
            codeContent: state.processorContents[deviceId] ?? '',
            isCodeValidated: state.processorValidated[deviceId] ?? false,
            isValidating: state.isArtifactValidating('processor:$deviceId'),
            validationFeedback: state.artifactFeedback('processor:$deviceId'),
            onCodeChanged: (content) => context.read<WizardBloc>().add(
              WizardProcessorContentChanged(deviceId, content),
            ),
            requirementsContent: state.processorRequirements[deviceId],
            onRequirementsChanged: (content) => context.read<WizardBloc>().add(
              WizardProcessorRequirementsChanged(deviceId, content),
            ),
            onValidate: (content) => _requestValidation(
              context,
              state,
              DeployerArtifactType.processor,
              content,
              entityId: deviceId,
            ),
            constraints: Step3Constraints.getFunctionConstraints(
              state.layer2Provider,
            ),
            exampleContent: Step3Constraints.getProcessorExample(
              state.layer2Provider,
            ),
            initiallyExpanded: !(state.processorValidated[deviceId] ?? false),
            forceCollapsed: state.forceCollapseSections,
          ),
        );
        widgets.add(const SizedBox(height: 16));
      }
    }

    // === FEEDBACK FUNCTION ===
    if (state.shouldShowFeedbackFunction) {
      widgets.add(
        FunctionPackageBlock(
          codeFilename: 'event-feedback/lambda_function.py',
          description: 'Event feedback Lambda',
          codeContent: state.eventFeedbackContent ?? '',
          isCodeValidated: state.eventFeedbackValidated,
          isValidating: state.isArtifactValidating('event-feedback'),
          validationFeedback: state.artifactFeedback('event-feedback'),
          onCodeChanged: (content) => context.read<WizardBloc>().add(
            WizardEventFeedbackContentChanged(content),
          ),
          requirementsContent: state.eventFeedbackRequirements,
          onRequirementsChanged: (content) => context.read<WizardBloc>().add(
            WizardEventFeedbackRequirementsChanged(content),
          ),
          onValidate: (content) => _requestValidation(
            context,
            state,
            DeployerArtifactType.eventFeedback,
            content,
          ),
          constraints: Step3Constraints.getFunctionConstraints(
            state.layer2Provider,
          ),
          exampleContent: Step3Constraints.getProcessorExample(
            state.layer2Provider,
          ),
          initiallyExpanded: !state.eventFeedbackValidated,
          forceCollapsed: state.forceCollapseSections,
        ),
      );
      widgets.add(const SizedBox(height: 16));
    }

    // === EVENT ACTION FUNCTIONS ===
    if (state.calcParams?.useEventChecking == true) {
      if (!state.configEventsValidated) {
        widgets.add(
          Step3InfoCards.dependencyInfo(
            context,
            'Validate config_events.json first to enable event action function inputs.',
          ),
        );
      } else if (state.eventActionFunctionNames.isEmpty) {
        widgets.add(
          Step3InfoCards.emptyState(
            context,
            'No event actions with functionName defined.',
          ),
        );
      } else {
        for (final funcName in state.eventActionFunctionNames) {
          widgets.add(
            FunctionPackageBlock(
              codeFilename: 'event_actions/$funcName/lambda_function.py',
              description: 'Event action: $funcName',
              codeContent: state.eventActionContents[funcName] ?? '',
              isCodeValidated: state.eventActionValidated[funcName] ?? false,
              isValidating: state.isArtifactValidating(
                'event-action:$funcName',
              ),
              validationFeedback: state.artifactFeedback(
                'event-action:$funcName',
              ),
              onCodeChanged: (content) => context.read<WizardBloc>().add(
                WizardEventActionContentChanged(funcName, content),
              ),
              requirementsContent: state.eventActionRequirements[funcName],
              onRequirementsChanged: (content) => context
                  .read<WizardBloc>()
                  .add(WizardEventActionRequirementsChanged(funcName, content)),
              onValidate: (content) => _requestValidation(
                context,
                state,
                DeployerArtifactType.eventAction,
                content,
                entityId: funcName,
              ),
              constraints: Step3Constraints.getFunctionConstraints(
                state.layer2Provider,
              ),
              exampleContent: Step3Constraints.getProcessorExample(
                state.layer2Provider,
              ),
              initiallyExpanded:
                  !(state.eventActionValidated[funcName] ?? false),
              forceCollapsed: state.forceCollapseSections,
            ),
          );
          widgets.add(const SizedBox(height: 16));
        }
      }
    }

    // === STATE MACHINE ===
    if (state.shouldShowStateMachine) {
      final filename = state.stateMachineFilename ?? 'state_machine.json';
      widgets.add(
        CollapsibleBlockWrapper(
          title: filename,
          subtitle: 'Workflow / state machine definition',
          icon: Icons.account_tree,
          isValid: state.stateMachineValidated ? true : null,
          showEditBadge: true,
          initiallyExpanded: !state.stateMachineValidated,
          forceCollapsed: state.forceCollapseSections,
          child: FileEditorBlock(
            showHeader: false,
            filename: filename,
            description: 'Workflow / state machine definition',
            icon: Icons.account_tree,
            isHighlighted: true,
            constraints: Step3Constraints.getStateMachineConstraints(
              state.layer2Provider,
            ),
            exampleContent: Step3Constraints.getStateMachineExample(
              state.layer2Provider,
            ),
            initialContent: state.stateMachineContent ?? '',
            isValidated: state.stateMachineValidated,
            isValidating: state.isArtifactValidating('state-machine'),
            validationFeedback: state.artifactFeedback('state-machine'),
            onContentChanged: (content) => context.read<WizardBloc>().add(
              WizardStateMachineContentChanged(content),
            ),
            onValidate: (content) => _requestValidation(
              context,
              state,
              DeployerArtifactType.stateMachine,
              content,
            ),
            autoValidateOnUpload: true,
          ),
        ),
      );
    }

    // If nothing to show (all conditions false), show info
    if (widgets.isEmpty) {
      widgets.add(
        Step3InfoCards.emptyState(
          context,
          'Enable triggerNotificationWorkflow or returnFeedbackToDevice in Step 2 for L2 inputs.',
        ),
      );
    }

    return widgets;
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<WizardBloc, WizardState>(
      builder: (context, state) {
        // Create layer builder from BLoC state
        _layerBuilder = ArchitectureLayerBuilder(
          calcResult: state.calcResult,
          calcParams: state.calcParams,
        );

        return Column(
          children: [
            Expanded(
              child: state.calcResult == null
                  ? const Step3NoResultMessage()
                  : _buildLayerAlignedLayout(context, state),
            ),
          ],
        );
      },
    );
  }

  Widget _buildLayerAlignedLayout(BuildContext context, WizardState state) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final showFlowchart = constraints.maxWidth >= _flowchartBreakpoint;

        return SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ============================================================
              // QUICK UPLOAD AREA (Always visible, not collapsible)
              // ============================================================
              const Step3QuickUploadSection(),

              const SizedBox(height: 32),

              // Separator with "Or configure manually" text
              const Step3ManualSeparator(),

              const SizedBox(height: 24),

              // ============================================================
              // SECTION 1: Configuration Files (was Section 2)
              // ============================================================
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 800),
                  child: CollapsibleSection(
                    sectionNumber: 1,
                    title: 'Configuration Files',
                    description:
                        'Core deployment settings and device definitions',
                    icon: Icons.settings,
                    // Auto-collapse if all configs are valid (on edit)
                    initiallyExpanded:
                        state.mode == WizardMode.edit && !state.isSection2Valid,
                    isValid:
                        state.isSection2Valid, // Show check icon when complete
                    forceCollapsed: state.forceCollapseSections,
                    child: _buildConfigSection(context, state),
                  ),
                ),
              ),

              // ============================================================
              // SECTION 2: User Functions & Assets (was Section 3)
              // ============================================================
              Center(
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    maxWidth: showFlowchart
                        ? _flowchartWidth + 32 + 800 + 32
                        : 800,
                  ),
                  child: CollapsibleSection(
                    sectionNumber: 2,
                    title: 'User Functions & Assets',
                    description:
                        'Custom processors, workflows, and visualization config',
                    icon: Icons.code,
                    // Auto-collapse if all configs are valid (on edit)
                    initiallyExpanded:
                        state.mode == WizardMode.edit && !state.isSection3Valid,
                    collapsedMaxWidth: 800,
                    isValid:
                        state.isSection3Valid, // Show check icon when complete
                    forceCollapsed: state.forceCollapseSections,
                    // Info message about dependency (non-blocking)
                    infoHint:
                        'Inputs here depend on Section 1 configuration files (config_events.json, config_iot_devices.json)',
                    child: _buildDataFlowSection(context, state, showFlowchart),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildConfigSection(BuildContext context, WizardState state) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // config.json - editable with auto values
        CollapsibleBlockWrapper(
          title: 'config.json',
          subtitle: 'Core deployment configuration',
          icon: Icons.settings,
          isValid: state.configJsonValidated ? true : null,
          showEditBadge: true,
          autoBadge: 'From Step 1 & 2',
          initiallyExpanded: !state.configJsonValidated,
          forceCollapsed: state.forceCollapseSections,
          child: ConfigJsonVisualizationBlock(
            showHeader: false,
            twinName: state.deployerDigitalTwinName,
            mode: state.debugMode == true ? 'debug' : 'production',
            hotStorageDays:
                (state.calcParams?.hotStorageDurationInMonths ?? 1) * 30,
            coldStorageDays:
                (state.calcParams?.coolStorageDurationInMonths ?? 3) * 30,
            isValidated: state.configJsonValidated,
            isValidating: state.isArtifactValidating('config:core'),
            validationFeedback: state.artifactFeedback('config:core'),
            onTwinNameChanged: (name) {
              context.read<WizardBloc>().add(
                WizardDeployerTwinNameChanged(name),
              );
            },
            onValidate: (config) {
              final content = const JsonEncoder.withIndent(
                '  ',
              ).convert(config);
              _requestValidation(
                context,
                state,
                DeployerArtifactType.config,
                content,
              );
            },
          ),
        ),
        const SizedBox(height: 16),

        // config_events.json - editable
        CollapsibleBlockWrapper(
          title: 'config_events.json',
          subtitle: 'Event-driven automation rules',
          icon: Icons.bolt,
          isValid: state.configEventsValidated ? true : null,
          showEditBadge: true,
          initiallyExpanded: !state.configEventsValidated,
          forceCollapsed: state.forceCollapseSections,
          child: FileEditorBlock(
            showHeader: false,
            filename: 'config_events.json',
            description: 'Event-driven automation rules',
            icon: Icons.bolt,
            isHighlighted: true,
            constraints:
                '• JSON array of event conditions\n• Define actions for each condition',
            exampleContent: Step3Examples.configEvents,
            initialContent: state.configEventsJson ?? '',
            isValidated: state.configEventsValidated,
            isValidating: state.isArtifactValidating('config:events'),
            validationFeedback: state.artifactFeedback('config:events'),
            onContentChanged: (content) {
              context.read<WizardBloc>().add(
                WizardConfigEventsChanged(content),
              );
            },
            onValidate: (content) {
              _requestValidation(
                context,
                state,
                DeployerArtifactType.events,
                content,
              );
            },
            autoValidateOnUpload: true,
          ),
        ),
        const SizedBox(height: 16),

        // config_iot_devices.json - editable
        CollapsibleBlockWrapper(
          title: 'config_iot_devices.json',
          subtitle: 'IoT device definitions',
          icon: Icons.sensors,
          isValid: state.configIotDevicesValidated ? true : null,
          showEditBadge: true,
          initiallyExpanded: !state.configIotDevicesValidated,
          forceCollapsed: state.forceCollapseSections,
          child: FileEditorBlock(
            showHeader: false,
            filename: 'config_iot_devices.json',
            description: 'IoT device definitions',
            icon: Icons.sensors,
            isHighlighted: true,
            constraints:
                '• JSON array of device configs\n• Define properties per device',
            exampleContent: Step3Examples.configIotDevices,
            initialContent: state.configIotDevicesJson ?? '',
            isValidated: state.configIotDevicesValidated,
            isValidating: state.isArtifactValidating('config:iot-devices'),
            validationFeedback: state.artifactFeedback('config:iot-devices'),
            onContentChanged: (content) {
              context.read<WizardBloc>().add(
                WizardConfigIotDevicesChanged(content),
              );
            },
            onValidate: (content) => _requestValidation(
              context,
              state,
              DeployerArtifactType.iotDevices,
              content,
            ),
            autoValidateOnUpload: true,
          ),
        ),
        const SizedBox(height: 16),

        // L4 Hierarchy JSON - only shown when L4 provider is AWS or Azure
        if (state.layer4Provider?.toUpperCase() == 'AWS' ||
            state.layer4Provider?.toUpperCase() == 'AZURE') ...[
          Builder(
            builder: (context) {
              final l4Provider = state.layer4Provider!.toLowerCase();
              final isAws = l4Provider == 'aws';
              final filename = isAws
                  ? 'aws_hierarchy.json'
                  : 'azure_hierarchy.json';
              final description = isAws
                  ? 'TwinMaker entity hierarchy'
                  : 'Azure Digital Twins hierarchy';
              final constraints = isAws
                  ? '• Define entities with components\\n• Match entity IDs to scene config'
                  : '• Define twins with DTDL model\\n• Match twin IDs to scene config';

              return CollapsibleBlockWrapper(
                title: filename,
                subtitle: description,
                icon: Icons.account_tree,
                initiallyExpanded: !state.hierarchyValidated,
                forceCollapsed: state.forceCollapseSections,
                copyContent: state.hierarchyContent,
                child: FileEditorBlock(
                  showHeader: false,
                  filename: filename,
                  description: description,
                  icon: Icons.account_tree,
                  isHighlighted: true,
                  constraints: constraints,
                  exampleContent: isAws
                      ? Step3Examples.awsHierarchy
                      : Step3Examples.azureHierarchy,
                  initialContent: state.hierarchyContent ?? '',
                  isValidated: state.hierarchyValidated,
                  isValidating: state.isArtifactValidating('hierarchy'),
                  validationFeedback: state.artifactFeedback('hierarchy'),
                  onContentChanged: (content) {
                    context.read<WizardBloc>().add(
                      WizardHierarchyContentChanged(content),
                    );
                  },
                  onValidate: (content) {
                    _requestValidation(
                      context,
                      state,
                      DeployerArtifactType.hierarchy,
                      content,
                    );
                  },
                  autoValidateOnUpload: true,
                ),
              );
            },
          ),
          const SizedBox(height: 16),
        ],

        // config_optimization.json - read-only
        CollapsibleBlockWrapper(
          title: 'config_optimization.json',
          subtitle: 'Optimizer calculation results',
          icon: Icons.calculate,
          autoBadge: 'From Step 2',
          copyContent: _buildConfigOptimizationJson(state),
          child: ConfigVisualizationBlock(
            showHeader: false,
            filename: 'config_optimization.json',
            description: 'Optimizer calculation results',
            icon: Icons.calculate,
            sourceLabel: 'From Step 2',
            jsonContent: _buildConfigOptimizationJson(state),
            visualContent: ConfigVisualizationBlock.buildOptimizationVisual(
              inputParams: {
                'useEventChecking': state.calcParams?.useEventChecking ?? false,
                'triggerNotificationWorkflow':
                    state.calcParams?.triggerNotificationWorkflow ?? false,
                'returnFeedbackToDevice':
                    state.calcParams?.returnFeedbackToDevice ?? false,
                'needs3DModel': state.calcParams?.needs3DModel ?? false,
              },
            ),
          ),
        ),
        const SizedBox(height: 16),

        // config_providers.json - read-only
        CollapsibleBlockWrapper(
          title: 'config_providers.json',
          subtitle: 'Provider assignments per layer',
          icon: Icons.cloud,
          autoBadge: 'From Step 2',
          copyContent: _buildConfigProvidersJson(state),
          child: ConfigVisualizationBlock(
            showHeader: false,
            filename: 'config_providers.json',
            description: 'Provider assignments per layer',
            icon: Icons.cloud,
            sourceLabel: 'From Step 2',
            jsonContent: _buildConfigProvidersJson(state),
            visualContent: ConfigVisualizationBlock.buildProvidersVisual(
              _buildProviderMap(),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDataFlowSection(
    BuildContext context,
    WizardState state,
    bool showFlowchart,
  ) {
    final layerBuilder = _layerBuilder!;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Step3FlowHeader(
          showFlowchart: showFlowchart,
          flowchartWidth: _flowchartWidth,
        ),
        const SizedBox(height: 24),

        // L1 Row
        Step3LayerRow(
          showFlowchart: showFlowchart,
          flowchartWidth: _flowchartWidth,
          flowchart: layerBuilder.buildL1Layer(context),
          editors: [
            CollapsibleBlockWrapper(
              title: 'payloads.json',
              subtitle: 'IoT device payload schemas',
              icon: Icons.data_object,
              isValid: state.payloadsValidated ? true : null,
              showEditBadge: true,
              initiallyExpanded: !state.payloadsValidated,
              forceCollapsed: state.forceCollapseSections,
              child: FileEditorBlock(
                showHeader: false,
                filename: 'payloads.json',
                description: 'IoT device payload schemas',
                icon: Icons.data_object,
                isHighlighted: true,
                constraints:
                    '• Must be valid JSON\n• Define device ID and payload structure',
                exampleContent: Step3Examples.payloads,
                initialContent: state.payloadsJson ?? '',
                isValidated: state.payloadsValidated,
                isValidating: state.isArtifactValidating('payloads'),
                validationFeedback: state.artifactFeedback('payloads'),
                onContentChanged: (content) => context.read<WizardBloc>().add(
                  WizardPayloadsChanged(content),
                ),
                onValidate: (content) => _requestValidation(
                  context,
                  state,
                  DeployerArtifactType.payloads,
                  content,
                ),
                autoValidateOnUpload: true,
              ),
            ),
          ],
        ),

        if (showFlowchart) const Step3ArrowRow(flowchartWidth: _flowchartWidth),

        // L2 Row (Dynamic)
        Step3LayerRow(
          showFlowchart: showFlowchart,
          flowchartWidth: _flowchartWidth,
          flowchart: layerBuilder.buildL2Layer(context),
          editors: _buildL2DynamicInputs(context, state),
        ),

        if (showFlowchart) const Step3ArrowRow(flowchartWidth: _flowchartWidth),

        // L3 Row
        Step3LayerRow(
          showFlowchart: showFlowchart,
          flowchartWidth: _flowchartWidth,
          flowchart: layerBuilder.buildL3Layer(context),
          editors: [Step3InfoCards.autoConfigured(context)],
        ),

        if (showFlowchart) const Step3ArrowRow(flowchartWidth: _flowchartWidth),

        // L4 Row - Scene Config (only when needs3DModel && L4 provider is AWS/Azure && hierarchy validated)
        if (state.calcParams?.needs3DModel == true &&
            state.hierarchyValidated &&
            (state.layer4Provider?.toUpperCase() == 'AWS' ||
                state.layer4Provider?.toUpperCase() == 'AZURE')) ...[
          Step3LayerRow(
            showFlowchart: showFlowchart,
            flowchartWidth: _flowchartWidth,
            flowchart: layerBuilder.buildL4Layer(context),
            editors: [
              Builder(
                builder: (context) {
                  final l4Provider = state.layer4Provider!.toLowerCase();
                  final isAws = l4Provider == 'aws';
                  final filename = isAws
                      ? 'scene.json'
                      : '3DScenesConfiguration.json';
                  final description = isAws
                      ? 'TwinMaker scene configuration'
                      : 'Azure 3D Scenes Studio config';
                  final constraints = isAws
                      ? '• References entities from hierarchy\\n• GLB model URIs'
                      : '• primaryTwinID must exist in hierarchy\\n• {{STORAGE_URL}} for asset URLs';

                  return Column(
                    children: [
                      // Scene Config JSON
                      CollapsibleBlockWrapper(
                        title: filename,
                        subtitle: description,
                        icon: Icons.view_in_ar,
                        isValid: state.sceneConfigValidated ? true : null,
                        showEditBadge: true,
                        initiallyExpanded: !state.sceneConfigValidated,
                        forceCollapsed: state.forceCollapseSections,
                        copyContent: state.sceneConfigContent,
                        child: FileEditorBlock(
                          showHeader: false,
                          filename: filename,
                          description: description,
                          icon: Icons.view_in_ar,
                          isHighlighted: true,
                          constraints: constraints,
                          exampleContent: isAws
                              ? Step3Examples.awsSceneConfig
                              : Step3Examples.azureSceneConfig,
                          initialContent: state.sceneConfigContent ?? '',
                          isValidated: state.sceneConfigValidated,
                          isValidating: state.isArtifactValidating(
                            'scene-config',
                          ),
                          validationFeedback: state.artifactFeedback(
                            'scene-config',
                          ),
                          onContentChanged: (content) {
                            context.read<WizardBloc>().add(
                              WizardSceneConfigContentChanged(content),
                            );
                          },
                          onValidate: (content) {
                            _requestValidation(
                              context,
                              state,
                              DeployerArtifactType.sceneConfig,
                              content,
                            );
                          },
                          autoValidateOnUpload: true,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Step3GlbUploadCard(
                        isUploaded: state.sceneGlbUploaded,
                        onDelete: () => _deleteSceneGlb(context, state),
                        onUpload: () => _pickAndUploadSceneGlb(context, state),
                      ),
                    ],
                  );
                },
              ),
            ],
          ),
          if (showFlowchart)
            const Step3ArrowRow(flowchartWidth: _flowchartWidth),
        ] else ...[
          // No L4 Scene needed - show info card
          Step3LayerRow(
            showFlowchart: showFlowchart,
            flowchartWidth: _flowchartWidth,
            flowchart: layerBuilder.buildL4Layer(context),
            editors: [
              Step3InfoCards.l4Info(
                context,
                needs3DModel: state.calcParams?.needs3DModel ?? false,
                l4Provider: state.layer4Provider,
              ),
            ],
          ),
          if (showFlowchart)
            const Step3ArrowRow(flowchartWidth: _flowchartWidth),
        ],

        // L5 Row - User Config (AWS/Azure only)
        Step3LayerRow(
          showFlowchart: showFlowchart,
          flowchartWidth: _flowchartWidth,
          flowchart: layerBuilder.buildL5Layer(context),
          editors: [
            if (state.layer5Provider?.toUpperCase() == 'AWS' ||
                state.layer5Provider?.toUpperCase() == 'AZURE') ...[
              Builder(
                builder: (context) {
                  // Provider already checked above, proceed with config
                  return CollapsibleBlockWrapper(
                    title: 'config_user.json',
                    subtitle: 'Grafana dashboard configuration',
                    icon: Icons.dashboard,
                    isValid: state.userConfigValidated ? true : null,
                    showEditBadge: true,
                    initiallyExpanded: !state.userConfigValidated,
                    forceCollapsed: state.forceCollapseSections,
                    copyContent: state.userConfigContent,
                    child: FileEditorBlock(
                      showHeader: false,
                      filename: 'config_user.json',
                      description: 'Grafana dashboard user configuration',
                      icon: Icons.dashboard,
                      isHighlighted: true,
                      constraints:
                          '• Dashboard panels and queries\\n• Data source configuration',
                      exampleContent: Step3Examples.userConfig,
                      initialContent: state.userConfigContent ?? '',
                      isValidated: state.userConfigValidated,
                      isValidating: state.isArtifactValidating('user-config'),
                      validationFeedback: state.artifactFeedback('user-config'),
                      onContentChanged: (content) {
                        context.read<WizardBloc>().add(
                          WizardUserConfigContentChanged(content),
                        );
                      },
                      onValidate: (content) {
                        // User config is L5 - use layer5Provider instead of layer4Provider
                        _requestValidation(
                          context,
                          state,
                          DeployerArtifactType.userConfig,
                          content,
                          providerOverride: state.layer5Provider,
                        );
                      },
                      autoValidateOnUpload: true,
                    ),
                  );
                },
              ),
            ] else ...[
              Step3InfoCards.l5Info(context, l5Provider: state.layer5Provider),
            ],
          ],
        ),

        const SizedBox(height: 24),
        Step3FlowFooter(
          showFlowchart: showFlowchart,
          flowchartWidth: _flowchartWidth,
          legend: _layerBuilder!.buildLegend(context),
        ),
      ],
    );
  }

  String _buildConfigOptimizationJson(WizardState state) {
    if (state.calcResult == null) return '// No calculation result';
    return const JsonEncoder.withIndent('  ').convert({
      'result': {
        'inputParamsUsed': {
          'useEventChecking': state.calcParams?.useEventChecking ?? false,
          'triggerNotificationWorkflow':
              state.calcParams?.triggerNotificationWorkflow ?? false,
          'returnFeedbackToDevice':
              state.calcParams?.returnFeedbackToDevice ?? false,
          'needs3DModel': state.calcParams?.needs3DModel ?? false,
        },
      },
    });
  }

  String _buildConfigProvidersJson(WizardState state) {
    if (state.calcResult == null || _layerBuilder == null) {
      return '// No calculation result';
    }
    final layers = _layerBuilder!.layerProviders;
    String? toJson(String? p) => p == null
        ? null
        : (p.toUpperCase() == 'GCP' ? 'google' : p.toLowerCase());
    return const JsonEncoder.withIndent('  ').convert({
      'layer_1_provider': toJson(layers['L1']),
      'layer_2_provider': toJson(layers['L2']),
      'layer_3_hot_provider': toJson(layers['L3_hot']),
      'layer_3_cold_provider': toJson(layers['L3_cold']),
      'layer_3_archive_provider': toJson(layers['L3_archive']),
      'layer_4_provider': toJson(layers['L4']),
      'layer_5_provider': toJson(layers['L5']),
    });
  }

  Map<String, String> _buildProviderMap() {
    if (_layerBuilder == null) return {};
    final layers = _layerBuilder!.layerProviders;
    String get(String key) => layers[key]?.toUpperCase() ?? 'N/A';
    return {
      'layer_1_provider': get('L1'),
      'layer_2_provider': get('L2'),
      'layer_3_hot_provider': get('L3_hot'),
      'layer_3_cold_provider': get('L3_cold'),
      'layer_3_archive_provider': get('L3_archive'),
      'layer_4_provider': get('L4'),
      'layer_5_provider': get('L5'),
    };
  }

  Future<void> _deleteSceneGlb(BuildContext context, WizardState state) async {
    final twinId = state.twinId;
    if (twinId == null) return;

    final container = ProviderScope.containerOf(context);
    final api = container.read(apiServiceProvider);
    final bloc = context.read<WizardBloc>();
    final messenger = ScaffoldMessenger.of(context);

    try {
      await api.deleteSceneGlb(twinId);
      bloc.add(const WizardSceneGlbUploadStatusChanged(false));
    } catch (e) {
      messenger.showSnackBar(
        SnackBar(
          content: Text('Delete failed: ${ApiErrorHandler.extractMessage(e)}'),
        ),
      );
    }
  }

  Future<void> _pickAndUploadSceneGlb(
    BuildContext context,
    WizardState state,
  ) async {
    final twinId = state.twinId;
    final messenger = ScaffoldMessenger.of(context);
    final container = ProviderScope.containerOf(context);
    final api = container.read(apiServiceProvider);
    final bloc = context.read<WizardBloc>();

    if (twinId == null) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Save draft first before uploading GLB')),
      );
      return;
    }

    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['glb'],
      withData: true,
    );

    if (result == null || result.files.isEmpty) return;

    final file = result.files.first;
    final bytes = file.bytes;

    if (bytes == null) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Failed to read file')),
      );
      return;
    }

    final sizeMb = bytes.length / (1024 * 1024);
    if (sizeMb > 100) {
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            'File too large: ${sizeMb.toStringAsFixed(1)}MB (max 100MB)',
          ),
        ),
      );
      return;
    }

    try {
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            'Uploading ${file.name} (${sizeMb.toStringAsFixed(1)}MB)...',
          ),
        ),
      );

      await api.uploadSceneGlb(twinId, bytes, file.name);
      bloc.add(const WizardSceneGlbUploadStatusChanged(true));

      messenger.showSnackBar(
        const SnackBar(content: Text('GLB uploaded successfully')),
      );
    } catch (e) {
      messenger.showSnackBar(
        SnackBar(
          content: Text('Upload failed: ${ApiErrorHandler.extractMessage(e)}'),
        ),
      );
    }
  }
}
