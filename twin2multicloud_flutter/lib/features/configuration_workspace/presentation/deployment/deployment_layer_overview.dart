import 'package:flutter/material.dart';

import '../../../../bloc/wizard/wizard.dart';
import '../../../../config/step3_examples.dart';
import '../../../../models/deployer_artifact_validation.dart';
import '../../../../theme/spacing.dart';
import '../../../../widgets/architecture_layer_builder.dart';
import '../../../../widgets/file_inputs/collapsible_block_wrapper.dart';
import '../../../../widgets/file_inputs/file_editor_block.dart';
import '../../../../widgets/step3/info_cards.dart';
import '../../../../widgets/step3/provider_capability_status_card.dart';
import '../../../../widgets/step3/step3_glb_upload_card.dart';
import '../../../../widgets/step3/step3_layout_widgets.dart';
import 'deployment_contracts.dart';
import 'deployment_user_logic_section.dart';

class DeploymentLayerOverview extends StatelessWidget {
  final WizardState state;
  final ArchitectureLayerBuilder layerBuilder;
  final DeploymentTaskFocus focus;
  final bool showFlowchart;
  final double flowchartWidth;
  final WizardEventSink onEvent;
  final VoidCallback onUploadGlb;
  final VoidCallback onDeleteGlb;

  const DeploymentLayerOverview({
    super.key,
    required this.state,
    required this.layerBuilder,
    required this.focus,
    required this.showFlowchart,
    required this.flowchartWidth,
    required this.onEvent,
    required this.onUploadGlb,
    required this.onDeleteGlb,
  });

  bool get _showDataContracts =>
      focus == DeploymentTaskFocus.all ||
      focus == DeploymentTaskFocus.dataContracts;

  bool get _showUserLogic =>
      focus == DeploymentTaskFocus.all ||
      focus == DeploymentTaskFocus.userLogic;

  bool get _showTwinAssets =>
      focus == DeploymentTaskFocus.all ||
      focus == DeploymentTaskFocus.twinAssets;

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
      key: const ValueKey('deployment-layer-overview'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (focus == DeploymentTaskFocus.all)
          Step3FlowHeader(
            showFlowchart: showFlowchart,
            flowchartWidth: flowchartWidth,
          ),
        if (focus == DeploymentTaskFocus.all)
          const SizedBox(height: AppSpacing.lg),
        if (_showDataContracts) _buildPayloadsRow(context),
        if (showFlowchart && focus == DeploymentTaskFocus.all)
          Step3ArrowRow(flowchartWidth: flowchartWidth),
        if (_showUserLogic) _buildUserLogicRow(context),
        if (showFlowchart) Step3ArrowRow(flowchartWidth: flowchartWidth),
        if (focus == DeploymentTaskFocus.all) _buildStorageRow(context),
        if (showFlowchart) Step3ArrowRow(flowchartWidth: flowchartWidth),
        if (_showTwinAssets) ..._buildSceneRows(context),
        if (_showTwinAssets) _buildUserConfigRow(context),
        const SizedBox(height: AppSpacing.lg),
        if (focus == DeploymentTaskFocus.all)
          Step3FlowFooter(
            showFlowchart: showFlowchart,
            flowchartWidth: flowchartWidth,
            legend: layerBuilder.buildLegend(context),
          ),
      ],
    );
  }

  Widget _buildPayloadsRow(BuildContext context) {
    return Step3LayerRow(
      showFlowchart: showFlowchart,
      flowchartWidth: flowchartWidth,
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
            onContentChanged: (content) {
              onEvent(WizardPayloadsChanged(content));
            },
            onValidate: (content) {
              _validate(DeployerArtifactType.payloads, content);
            },
            autoValidateOnUpload: true,
          ),
        ),
      ],
    );
  }

  Widget _buildUserLogicRow(BuildContext context) {
    return Step3LayerRow(
      showFlowchart: showFlowchart,
      flowchartWidth: flowchartWidth,
      flowchart: layerBuilder.buildL2Layer(context),
      editors: [DeploymentUserLogicSection(state: state, onEvent: onEvent)],
    );
  }

  Widget _buildStorageRow(BuildContext context) {
    return Step3LayerRow(
      showFlowchart: showFlowchart,
      flowchartWidth: flowchartWidth,
      flowchart: layerBuilder.buildL3Layer(context),
      editors: [Step3InfoCards.autoConfigured(context)],
    );
  }

  List<Widget> _buildSceneRows(BuildContext context) {
    final provider = state.layer4Provider;
    final capability = state.providerCapability(provider, 'l4');
    final supportsAssets = state.isLayerSelectable(provider, 'l4');
    final hasEditableScene =
        state.calcParams?.needs3DModel == true &&
        state.hierarchyValidated &&
        supportsAssets;

    final rows = <Widget>[
      Step3LayerRow(
        showFlowchart: showFlowchart,
        flowchartWidth: flowchartWidth,
        flowchart: layerBuilder.buildL4Layer(context),
        editors: [
          if (hasEditableScene)
            _SceneEditor(
              state: state,
              onEvent: onEvent,
              onValidate: (content) {
                _validate(DeployerArtifactType.sceneConfig, content);
              },
              onUploadGlb: onUploadGlb,
              onDeleteGlb: onDeleteGlb,
            )
          else if (state.calcParams?.needs3DModel != true || provider == null)
            Step3InfoCards.l4Info(
              context,
              needs3DModel: state.calcParams?.needs3DModel ?? false,
              l4Provider: provider,
            ),
          if (state.calcParams?.needs3DModel == true &&
              provider != null &&
              !supportsAssets)
            ProviderCapabilityStatusCard(
              layer: 'l4',
              provider: provider,
              capability: capability,
              isLoading: state.providerCapabilitiesLoading,
              loadError: state.providerCapabilitiesError,
              onRetry: () =>
                  onEvent(const WizardProviderCapabilitiesLoadRequested()),
            ),
        ],
      ),
    ];
    if (showFlowchart) {
      rows.add(Step3ArrowRow(flowchartWidth: flowchartWidth));
    }
    return rows;
  }

  Widget _buildUserConfigRow(BuildContext context) {
    final provider = state.layer5Provider;
    final capability = state.providerCapability(provider, 'l5');
    final selectable = state.isLayerSelectable(provider, 'l5');
    return Step3LayerRow(
      showFlowchart: showFlowchart,
      flowchartWidth: flowchartWidth,
      flowchart: layerBuilder.buildL5Layer(context),
      editors: [
        if (selectable)
          CollapsibleBlockWrapper(
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
                  '• Dashboard panels and queries\n• Data source configuration',
              exampleContent: Step3Examples.userConfig,
              initialContent: state.userConfigContent ?? '',
              isValidated: state.userConfigValidated,
              isValidating: state.isArtifactValidating('user-config'),
              validationFeedback: state.artifactFeedback('user-config'),
              onContentChanged: (content) {
                onEvent(WizardUserConfigContentChanged(content));
              },
              onValidate: (content) {
                _validate(
                  DeployerArtifactType.userConfig,
                  content,
                  providerOverride: state.layer5Provider,
                );
              },
              autoValidateOnUpload: true,
            ),
          )
        else if (provider == null)
          Step3InfoCards.l5Info(context, l5Provider: provider)
        else
          ProviderCapabilityStatusCard(
            layer: 'l5',
            provider: provider,
            capability: capability,
            isLoading: state.providerCapabilitiesLoading,
            loadError: state.providerCapabilitiesError,
            onRetry: () =>
                onEvent(const WizardProviderCapabilitiesLoadRequested()),
          ),
      ],
    );
  }
}

class _SceneEditor extends StatelessWidget {
  final WizardState state;
  final WizardEventSink onEvent;
  final ValueChanged<String> onValidate;
  final VoidCallback onUploadGlb;
  final VoidCallback onDeleteGlb;

  const _SceneEditor({
    required this.state,
    required this.onEvent,
    required this.onValidate,
    required this.onUploadGlb,
    required this.onDeleteGlb,
  });

  @override
  Widget build(BuildContext context) {
    final isAws = state.layer4Provider!.toLowerCase() == 'aws';
    final filename = isAws ? 'scene.json' : '3DScenesConfiguration.json';
    final description = isAws
        ? 'TwinMaker scene configuration'
        : 'Azure 3D Scenes Studio config';
    final constraints = isAws
        ? '• References entities from hierarchy\n• GLB model URIs'
        : '• primaryTwinID must exist in hierarchy\n• {{STORAGE_URL}} for asset URLs';

    return Column(
      children: [
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
            isValidating: state.isArtifactValidating('scene-config'),
            validationFeedback: state.artifactFeedback('scene-config'),
            onContentChanged: (content) {
              onEvent(WizardSceneConfigContentChanged(content));
            },
            onValidate: onValidate,
            autoValidateOnUpload: true,
          ),
        ),
        const SizedBox(height: AppSpacing.md - AppSpacing.xs),
        Step3GlbUploadCard(
          isUploaded: state.sceneGlbUploaded,
          isBusy: state.sceneGlbCommand.isBusy,
          onDelete: onDeleteGlb,
          onUpload: onUploadGlb,
        ),
      ],
    );
  }
}
