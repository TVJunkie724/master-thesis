import 'dart:convert';

import 'package:flutter/material.dart';

import '../../../../bloc/wizard/wizard.dart';
import '../../../../config/step3_examples.dart';
import '../../../../models/deployer_artifact_validation.dart';
import '../../../../theme/spacing.dart';
import '../../../../widgets/architecture_layer_builder.dart';
import '../../../../widgets/file_inputs/collapsible_block_wrapper.dart';
import '../../../../widgets/file_inputs/config_json_visualization_block.dart';
import '../../../../widgets/file_inputs/config_visualization_block.dart';
import '../../../../widgets/file_inputs/file_editor_block.dart';
import 'deployment_contracts.dart';

class DeploymentConfigSection extends StatelessWidget {
  final WizardState state;
  final ArchitectureLayerBuilder layerBuilder;
  final WizardEventSink onEvent;
  final bool showCore;
  final bool showHierarchy;
  final bool showGenerated;

  const DeploymentConfigSection({
    super.key,
    required this.state,
    required this.layerBuilder,
    required this.onEvent,
    this.showCore = true,
    this.showHierarchy = true,
    this.showGenerated = true,
  });

  void _validate(
    DeployerArtifactType type,
    String content, {
    String? providerOverride,
  }) {
    onEvent(
      WizardArtifactValidationRequested(
        buildDeploymentValidationRequest(
          state: state,
          type: type,
          content: content,
          providerOverride: providerOverride,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const ValueKey('deployment-config-section'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (showCore) ...[
          CollapsibleBlockWrapper(
            title: 'config.json',
            subtitle: 'Core deployment configuration',
            icon: Icons.settings,
            isValid: state.configJsonValidated ? true : null,
            showEditBadge: true,
            autoBadge: 'Generated',
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
                onEvent(WizardDeployerTwinNameChanged(name));
              },
              onValidate: (config) {
                _validate(
                  DeployerArtifactType.config,
                  const JsonEncoder.withIndent('  ').convert(config),
                );
              },
            ),
          ),
          const SizedBox(height: AppSpacing.md),
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
                onEvent(WizardConfigEventsChanged(content));
              },
              onValidate: (content) {
                _validate(DeployerArtifactType.events, content);
              },
              autoValidateOnUpload: true,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
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
                onEvent(WizardConfigIotDevicesChanged(content));
              },
              onValidate: (content) {
                _validate(DeployerArtifactType.iotDevices, content);
              },
              autoValidateOnUpload: true,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
        ],
        if (showHierarchy && _supportsTwinAssets(state.layer4Provider)) ...[
          _HierarchyEditor(state: state, onEvent: onEvent),
          const SizedBox(height: AppSpacing.md),
        ],
        if (showGenerated) ...[
          _GeneratedOptimizationConfig(state: state),
          const SizedBox(height: AppSpacing.md),
          _GeneratedProviderConfig(state: state, layerBuilder: layerBuilder),
        ],
      ],
    );
  }
}

class _HierarchyEditor extends StatelessWidget {
  final WizardState state;
  final WizardEventSink onEvent;

  const _HierarchyEditor({required this.state, required this.onEvent});

  @override
  Widget build(BuildContext context) {
    final isAws = state.layer4Provider!.toLowerCase() == 'aws';
    final filename = isAws ? 'aws_hierarchy.json' : 'azure_hierarchy.json';
    final description = isAws
        ? 'TwinMaker entity hierarchy'
        : 'Azure Digital Twins hierarchy';
    final constraints = isAws
        ? '• Define entities with components\n• Match entity IDs to scene config'
        : '• Define twins with DTDL model\n• Match twin IDs to scene config';

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
          onEvent(WizardHierarchyContentChanged(content));
        },
        onValidate: (content) {
          onEvent(
            WizardArtifactValidationRequested(
              buildDeploymentValidationRequest(
                state: state,
                type: DeployerArtifactType.hierarchy,
                content: content,
              ),
            ),
          );
        },
        autoValidateOnUpload: true,
      ),
    );
  }
}

class _GeneratedOptimizationConfig extends StatelessWidget {
  final WizardState state;

  const _GeneratedOptimizationConfig({required this.state});

  @override
  Widget build(BuildContext context) {
    final content = _buildConfigOptimizationJson(state);
    return CollapsibleBlockWrapper(
      title: 'config_optimization.json',
      subtitle: 'Optimizer calculation results',
      icon: Icons.calculate,
      autoBadge: 'Generated',
      copyContent: content,
      child: ConfigVisualizationBlock(
        showHeader: false,
        filename: 'config_optimization.json',
        description: 'Optimizer calculation results',
        icon: Icons.calculate,
        sourceLabel: 'Architecture decision',
        jsonContent: content,
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
    );
  }
}

class _GeneratedProviderConfig extends StatelessWidget {
  final WizardState state;
  final ArchitectureLayerBuilder layerBuilder;

  const _GeneratedProviderConfig({
    required this.state,
    required this.layerBuilder,
  });

  @override
  Widget build(BuildContext context) {
    final content = _buildConfigProvidersJson(state, layerBuilder);
    return CollapsibleBlockWrapper(
      title: 'config_providers.json',
      subtitle: 'Provider assignments per layer',
      icon: Icons.cloud,
      autoBadge: 'Generated',
      copyContent: content,
      child: ConfigVisualizationBlock(
        showHeader: false,
        filename: 'config_providers.json',
        description: 'Provider assignments per layer',
        icon: Icons.cloud,
        sourceLabel: 'Architecture decision',
        jsonContent: content,
        visualContent: ConfigVisualizationBlock.buildProvidersVisual(
          _buildProviderMap(layerBuilder),
        ),
      ),
    );
  }
}

bool _supportsTwinAssets(String? provider) {
  final normalized = provider?.toUpperCase();
  return normalized == 'AWS' || normalized == 'AZURE';
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

String _buildConfigProvidersJson(
  WizardState state,
  ArchitectureLayerBuilder layerBuilder,
) {
  if (state.calcResult == null) return '// No calculation result';
  final layers = layerBuilder.layerProviders;
  String? toJson(String? provider) => provider == null
      ? null
      : (provider.toUpperCase() == 'GCP' ? 'google' : provider.toLowerCase());
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

Map<String, String> _buildProviderMap(ArchitectureLayerBuilder layerBuilder) {
  final layers = layerBuilder.layerProviders;
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
