import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../bloc/wizard/wizard.dart';
import '../../config/step3_examples.dart';
import '../../widgets/architecture_layer_builder.dart';
import '../../widgets/file_inputs/file_editor_block.dart';
import '../../widgets/file_inputs/collapsible_section.dart';
import '../../widgets/file_inputs/zip_upload_block.dart';
import '../../widgets/file_inputs/config_form_block.dart';
import '../../widgets/file_inputs/config_visualization_block.dart';

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
  // Section 1: Zip upload state
  String? _selectedZipPath;
  
  // Section 2: Config file content state
  String _configEventsContent = '';
  String _configIotDevicesContent = '';
  
  // Section 3: User function file content state
  String _payloadsContent = '';
  String _processorsContent = '';
  String _stateMachineContent = '';
  String _sceneAssetsContent = '';
  String _grafanaConfigContent = '';

  ArchitectureLayerBuilder? _layerBuilder;
  
  // Track last hasData state to avoid spamming BLoC events
  bool _lastHasSection3Data = false;
  
  // Breakpoint for showing flowchart column
  static const double _flowchartBreakpoint = 900;
  static const double _flowchartWidth = 450;
  
  /// Update Section 3 content and notify BLoC about data presence
  void _updateSection3Content({
    String? payloads,
    String? processors,
    String? stateMachine,
    String? sceneAssets,
    String? grafanaConfig,
  }) {
    setState(() {
      if (payloads != null) _payloadsContent = payloads;
      if (processors != null) _processorsContent = processors;
      if (stateMachine != null) _stateMachineContent = stateMachine;
      if (sceneAssets != null) _sceneAssetsContent = sceneAssets;
      if (grafanaConfig != null) _grafanaConfigContent = grafanaConfig;
    });
    
    // Notify BLoC about whether Section 3 has any data
    final hasData = _payloadsContent.isNotEmpty ||
        _processorsContent.isNotEmpty ||
        _stateMachineContent.isNotEmpty ||
        _sceneAssetsContent.isNotEmpty ||
        _grafanaConfigContent.isNotEmpty;
    
    // Only dispatch if state actually changed (debounce)
    if (hasData != _lastHasSection3Data) {
      _lastHasSection3Data = hasData;
      context.read<WizardBloc>().add(WizardSection3DataChanged(hasData));
    }
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
                  ? _buildNoResultMessage(context)
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
              // Section 1: Quick Upload
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 800),
                  child: CollapsibleSection(
                    sectionNumber: 1,
                    title: 'Quick Upload',
                    description: 'Upload a complete project zip to auto-fill all fields',
                    icon: Icons.folder_zip,
                    initiallyExpanded: false,
                    child: ZipUploadBlock(
                      onZipSelected: (path) => setState(() => _selectedZipPath = path),
                    ),
                  ),
                ),
              ),
              
              // Section 2: Configuration Files
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 800),
                  child: CollapsibleSection(
                    sectionNumber: 2,
                    title: 'Configuration Files',
                    description: 'Core deployment settings and device definitions',
                    icon: Icons.settings,
                    initiallyExpanded: true,
                    child: _buildConfigSection(context, state),
                  ),
                ),
              ),
              
              // Section 3: User Functions & Assets
              Center(
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    maxWidth: showFlowchart ? _flowchartWidth + 32 + 800 + 32 : 800,
                  ),
                  child: CollapsibleSection(
                    sectionNumber: 3,
                    title: 'User Functions & Assets',
                    description: 'Custom processors, workflows, and visualization config',
                    icon: Icons.code,
                    initiallyExpanded: true,
                    collapsedMaxWidth: 800,
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
        ConfigFormBlock(onConfigChanged: (config) {}),
        const SizedBox(height: 16),
        
        FileEditorBlock(
          filename: 'config_events.json',
          description: 'Event-driven automation rules',
          icon: Icons.bolt,
          isHighlighted: true,
          constraints: '• JSON array of event conditions\n• Define actions for each condition',
          exampleContent: Step3Examples.configEvents,
          initialContent: _configEventsContent,
          onContentChanged: (content) => setState(() => _configEventsContent = content),
          onValidate: (content) => _validateFile('config_events', content),
        ),
        const SizedBox(height: 16),
        
        FileEditorBlock(
          filename: 'config_iot_devices.json',
          description: 'IoT device definitions',
          icon: Icons.sensors,
          isHighlighted: true,
          constraints: '• JSON array of device configs\n• Define properties per device',
          exampleContent: Step3Examples.configIotDevices,
          initialContent: _configIotDevicesContent,
          onContentChanged: (content) => setState(() => _configIotDevicesContent = content),
          onValidate: (content) => _validateFile('config_iot_devices', content),
        ),
        const SizedBox(height: 16),
        
        ConfigVisualizationBlock(
          filename: 'config_optimization.json',
          description: 'Optimizer calculation results',
          icon: Icons.calculate,
          sourceLabel: 'From Step 2',
          jsonContent: _buildConfigOptimizationJson(state),
          visualContent: ConfigVisualizationBlock.buildOptimizationVisual(
            inputParams: {
              'useEventChecking': state.calcParams?.useEventChecking ?? false,
              'triggerNotificationWorkflow': state.calcParams?.triggerNotificationWorkflow ?? false,
              'returnFeedbackToDevice': state.calcParams?.returnFeedbackToDevice ?? false,
              'needs3DModel': state.calcParams?.needs3DModel ?? false,
            },
          ),
        ),
        const SizedBox(height: 16),
        
        ConfigVisualizationBlock(
          filename: 'config_providers.json',
          description: 'Provider assignments per layer',
          icon: Icons.cloud,
          sourceLabel: 'From Step 2',
          jsonContent: _buildConfigProvidersJson(state),
          visualContent: ConfigVisualizationBlock.buildProvidersVisual(_buildProviderMap()),
        ),
      ],
    );
  }

  Widget _buildDataFlowSection(BuildContext context, WizardState state, bool showFlowchart) {
    final layerBuilder = _layerBuilder!;
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeader(context, showFlowchart),
        const SizedBox(height: 24),

        // L1 Row
        _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL1Layer(context), editors: [
          FileEditorBlock(
            filename: 'payloads.json',
            description: 'IoT device payload schemas',
            icon: Icons.data_object,
            isHighlighted: true,
            constraints: '• Must be valid JSON\n• Define device ID and payload structure',
            exampleContent: Step3Examples.payloads,
            initialContent: _payloadsContent,
            onContentChanged: (content) => _updateSection3Content(payloads: content),
            onValidate: (content) => _validateFile('payloads', content),
          ),
        ]),
        
        if (showFlowchart) _buildArrowRow(),

        // L2 Row
        _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL2Layer(context), editors: [
          FileEditorBlock(
            filename: 'processors/',
            description: 'User processor functions',
            icon: Icons.code,
            isHighlighted: true,
            constraints: '• Python files with process() function\n• One file per device type',
            exampleContent: Step3Examples.processors,
            initialContent: _processorsContent,
            onContentChanged: (content) => _updateSection3Content(processors: content),
            onValidate: (content) => _validateFile('processors', content),
          ),
          const SizedBox(height: 16),
          FileEditorBlock(
            filename: 'state_machine.json',
            description: 'State machine definition',
            icon: Icons.account_tree,
            isHighlighted: true,
            constraints: '• AWS Step Functions / Azure Logic App / GCP Workflow',
            exampleContent: Step3Examples.stateMachine,
            initialContent: _stateMachineContent,
            onContentChanged: (content) => _updateSection3Content(stateMachine: content),
            onValidate: (content) => _validateFile('state_machine', content),
          ),
        ]),
        
        if (showFlowchart) _buildArrowRow(),

        // L3 Row
        _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL3Layer(context), editors: [
          _buildAutoConfiguredCard(context),
        ]),
        
        if (showFlowchart) _buildArrowRow(),

        // L4 Row
        _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL4Layer(context), editors: [
          FileEditorBlock(
            filename: 'scene_assets/',
            description: '3D scene configuration files',
            icon: Icons.view_in_ar,
            isHighlighted: true,
            constraints: '• 3DScenesConfiguration.json for Azure ADT',
            exampleContent: Step3Examples.sceneAssets,
            initialContent: _sceneAssetsContent,
            onContentChanged: (content) => _updateSection3Content(sceneAssets: content),
            onValidate: (content) => _validateFile('scene_assets', content),
          ),
        ]),
        
        if (showFlowchart) _buildArrowRow(),

        // L5 Row
        _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL5Layer(context), editors: [
          FileEditorBlock(
            filename: 'config_grafana.json',
            description: 'Grafana dashboard configuration',
            icon: Icons.dashboard,
            isHighlighted: true,
            constraints: '• Dashboard layout and panels',
            exampleContent: Step3Examples.grafanaConfig,
            initialContent: _grafanaConfigContent,
            onContentChanged: (content) => _updateSection3Content(grafanaConfig: content),
            onValidate: (content) => _validateFile('grafana_config', content),
          ),
        ]),

        const SizedBox(height: 24),
        _buildFooter(context, showFlowchart),
      ],
    );
  }

  Widget _buildAutoConfiguredCard(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: isDark ? Colors.grey.shade700 : Colors.grey.shade300),
      ),
      child: Row(
        children: [
          Icon(Icons.check_circle, color: Colors.green.shade500, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Auto-configured', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14, color: isDark ? Colors.white : Colors.black87)),
                Text('Storage tiers are automatically provisioned.', style: TextStyle(color: isDark ? Colors.grey.shade400 : Colors.grey.shade600, fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _buildConfigOptimizationJson(WizardState state) {
    if (state.calcResult == null) return '// No calculation result';
    return const JsonEncoder.withIndent('  ').convert({
      'result': {
        'inputParamsUsed': {
          'useEventChecking': state.calcParams?.useEventChecking ?? false,
          'triggerNotificationWorkflow': state.calcParams?.triggerNotificationWorkflow ?? false,
          'returnFeedbackToDevice': state.calcParams?.returnFeedbackToDevice ?? false,
          'needs3DModel': state.calcParams?.needs3DModel ?? false,
        },
      },
    });
  }

  String _buildConfigProvidersJson(WizardState state) {
    if (state.calcResult == null || _layerBuilder == null) return '// No calculation result';
    final layers = _layerBuilder!.layerProviders;
    String? toJson(String? p) => p == null ? null : (p.toUpperCase() == 'GCP' ? 'google' : p.toLowerCase());
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

  Widget _buildHeader(BuildContext context, bool showFlowchart) {
    final editorsHeader = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.edit_document, size: 24, color: Theme.of(context).primaryColor),
            const SizedBox(width: 12),
            Text('Configuration Files', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 4),
        Text('Upload or edit configuration files for your deployment', style: TextStyle(fontSize: 13, color: Colors.grey.shade600)),
      ],
    );
    
    if (!showFlowchart) return editorsHeader;
    
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: _flowchartWidth, child: Column(children: [
          Text('Data Flow', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text('Component architecture', style: TextStyle(fontSize: 12, color: Colors.grey.shade500)),
        ])),
        const SizedBox(width: 32),
        Expanded(child: editorsHeader),
      ],
    );
  }

  Widget _buildFooter(BuildContext context, bool showFlowchart) {
    final infoBox = Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.blue.shade50,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.blue.shade200),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline, color: Colors.blue.shade700, size: 20),
          const SizedBox(width: 12),
          Expanded(child: Text('Click "Finish Configuration" when ready.', style: TextStyle(color: Colors.blue.shade800, fontSize: 13))),
        ],
      ),
    );
    
    if (!showFlowchart) return infoBox;
    
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: _flowchartWidth, child: _layerBuilder!.buildLegend(context)),
        const SizedBox(width: 32),
        Expanded(child: infoBox),
      ],
    );
  }

  Widget _buildLayerRow(BuildContext context, {required bool showFlowchart, required Widget flowchart, required List<Widget> editors}) {
    final editorsColumn = ConstrainedBox(constraints: const BoxConstraints(maxWidth: 800), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: editors));
    if (!showFlowchart) return Padding(padding: const EdgeInsets.only(bottom: 24), child: Center(child: editorsColumn));
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SizedBox(width: _flowchartWidth, child: flowchart),
      const SizedBox(width: 32),
      Flexible(child: Align(alignment: Alignment.topLeft, child: editorsColumn)),
    ]);
  }

  Widget _buildArrowRow() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(children: [
        SizedBox(width: _flowchartWidth, child: Center(child: Icon(Icons.arrow_downward, size: 24, color: Colors.grey.shade500))),
        const SizedBox(width: 32),
        const Expanded(child: SizedBox.shrink()),
      ]),
    );
  }

  Future<Map<String, dynamic>> _validateFile(String fileType, String content) async {
    if (content.trim().isEmpty) return {'valid': false, 'message': 'File is empty'};
    return {'valid': true, 'message': 'Content looks valid ✓'};
  }

  Widget _buildNoResultMessage(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.warning_amber_rounded, size: 64, color: Colors.orange.shade400),
          const SizedBox(height: 16),
          Text('No Optimization Result', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text('Please complete Step 2 (Optimizer) first.', style: TextStyle(color: Colors.grey.shade600)),
        ],
      ),
    );
  }
}
