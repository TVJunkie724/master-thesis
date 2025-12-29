import 'dart:convert';
import 'package:flutter/material.dart';
import '../../models/wizard_cache.dart';
import '../../models/calc_result.dart';
import '../../config/step3_examples.dart';
import '../../widgets/architecture_layer_builder.dart';
import '../../widgets/file_inputs/file_editor_block.dart';
import '../../widgets/file_inputs/collapsible_section.dart';
import '../../widgets/file_inputs/zip_upload_block.dart';
import '../../widgets/file_inputs/config_form_block.dart';
import '../../widgets/file_inputs/config_visualization_block.dart';

/// Step 3: Deployer Configuration
/// 
/// Three collapsible sections:
/// 1. Quick Upload - Project zip file
/// 2. Configuration Files - Core deployment config
/// 3. User Functions & Assets - Layer-aligned file editors
class Step3Deployer extends StatefulWidget {
  final String? twinId;
  final WizardCache cache;
  final VoidCallback onCacheChanged;

  const Step3Deployer({
    super.key,
    required this.twinId,
    required this.cache,
    required this.onCacheChanged,
  });

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

  CalcResult? get _result => widget.cache.calcResult;
  
  ArchitectureLayerBuilder? _layerBuilder;
  
  ArchitectureLayerBuilder get layerBuilder {
    _layerBuilder ??= ArchitectureLayerBuilder(
      calcResult: widget.cache.calcResult,
      calcParams: widget.cache.calcParams,
    );
    return _layerBuilder!;
  }
  
  @override
  void didUpdateWidget(Step3Deployer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.cache.calcResult != oldWidget.cache.calcResult ||
        widget.cache.calcParams != oldWidget.cache.calcParams) {
      _layerBuilder = ArchitectureLayerBuilder(
        calcResult: widget.cache.calcResult,
        calcParams: widget.cache.calcParams,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: _result == null
              ? _buildNoResultMessage()
              : _buildLayerAlignedLayout(),
        ),
      ],
    );
  }

  // Breakpoint for showing flowchart column
  static const double _flowchartBreakpoint = 900;
  static const double _flowchartWidth = 450;

  Widget _buildLayerAlignedLayout() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final showFlowchart = constraints.maxWidth >= _flowchartBreakpoint;
        
        return SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ===== SECTION 1: Quick Upload =====
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
              
              // ===== SECTION 2: Configuration Files =====
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 800),
                  child: CollapsibleSection(
                    sectionNumber: 2,
                    title: 'Configuration Files',
                    description: 'Core deployment settings and device definitions',
                    icon: Icons.settings,
                    initiallyExpanded: true,
                    child: _buildConfigSection(),
                  ),
                ),
              ),
              
              // ===== SECTION 3: User Functions & Assets =====
              // Max width = flowchart (450) + gap (32) + editors (800) + padding (32*2)
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
                    child: _buildDataFlowSection(showFlowchart),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
  
  /// Section 2: Configuration files section
  Widget _buildConfigSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // config.json - Form inputs
        ConfigFormBlock(
          onConfigChanged: (config) {
            // TODO: Store config in cache
          },
        ),
        
        const SizedBox(height: 16),
        
        // config_events.json - Editable
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
        
        // config_iot_devices.json - Editable
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
        
        // config_optimization.json - Read-only with visual summary
        ConfigVisualizationBlock(
          filename: 'config_optimization.json',
          description: 'Optimizer calculation results',
          icon: Icons.calculate,
          sourceLabel: 'From Step 2',
          jsonContent: _buildConfigOptimizationJson(),
          visualContent: ConfigVisualizationBlock.buildOptimizationVisual(
            inputParams: {
              'useEventChecking': widget.cache.calcParams?.useEventChecking ?? false,
              'triggerNotificationWorkflow': widget.cache.calcParams?.triggerNotificationWorkflow ?? false,
              'returnFeedbackToDevice': widget.cache.calcParams?.returnFeedbackToDevice ?? false,
              // 'integrateErrorHandling': widget.cache.calcParams?.integrateErrorHandling ?? false,
              'needs3DModel': widget.cache.calcParams?.needs3DModel ?? false,
            },
          ),
        ),
        
        const SizedBox(height: 16),
        
        // config_providers.json - Read-only with visual summary
        ConfigVisualizationBlock(
          filename: 'config_providers.json',
          description: 'Provider assignments per layer',
          icon: Icons.cloud,
          sourceLabel: 'From Step 2',
          jsonContent: _buildConfigProvidersJson(),
          visualContent: ConfigVisualizationBlock.buildProvidersVisual(
            _buildProviderMap(),
          ),
        ),
      ],
    );
  }
  
  /// Section 3: Data flow with layer-aligned file editors
  Widget _buildDataFlowSection(bool showFlowchart) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        _buildHeader(context, showFlowchart),
        const SizedBox(height: 24),

        // L1 Row
        _buildLayerRow(
          context,
          showFlowchart: showFlowchart,
          flowchart: layerBuilder.buildL1Layer(context),
          editors: [
            FileEditorBlock(
              filename: 'payloads.json',
              description: 'IoT device payload schemas',
              icon: Icons.data_object,
              isHighlighted: true,
              constraints: '• Must be valid JSON\n• Define device ID and payload structure',
              exampleContent: Step3Examples.payloads,
              initialContent: _payloadsContent,
              onContentChanged: (content) => setState(() => _payloadsContent = content),
              onValidate: (content) => _validateFile('payloads', content),
            ),
          ],
        ),
        
        if (showFlowchart) _buildArrowRow(),

        // L2 Row
        _buildLayerRow(
          context,
          showFlowchart: showFlowchart,
          flowchart: layerBuilder.buildL2Layer(context),
          editors: [
            FileEditorBlock(
              filename: 'processors/',
              description: 'User processor functions',
              icon: Icons.code,
              isHighlighted: true,
              constraints: '• Python files with process() function\n• One file per device type',
              exampleContent: Step3Examples.processors,
              initialContent: _processorsContent,
              onContentChanged: (content) => setState(() => _processorsContent = content),
              onValidate: (content) => _validateFile('processors', content),
            ),
            const SizedBox(height: 16),
            FileEditorBlock(
              filename: 'state_machine.json',
              description: 'State machine definition (for event workflows)',
              icon: Icons.account_tree,
              isHighlighted: true,
              constraints: '• AWS Step Functions / Azure Logic App / GCP Workflow format',
              exampleContent: Step3Examples.stateMachine,
              initialContent: _stateMachineContent,
              onContentChanged: (content) => setState(() => _stateMachineContent = content),
              onValidate: (content) => _validateFile('state_machine', content),
            ),
          ],
        ),
        
        if (showFlowchart) _buildArrowRow(),

        // L3 Row
        _buildLayerRow(
          context,
          showFlowchart: showFlowchart,
          flowchart: layerBuilder.buildL3Layer(context),
          editors: [
            Builder(
              builder: (context) {
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
                            Text(
                              'Auto-configured',
                              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14, color: isDark ? Colors.white : Colors.black87),
                            ),
                            Text(
                              'Storage tiers are automatically provisioned based on the selected providers.',
                              style: TextStyle(color: isDark ? Colors.grey.shade400 : Colors.grey.shade600, fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ],
        ),
        
        if (showFlowchart) _buildArrowRow(),

        // L4 Row
        _buildLayerRow(
          context,
          showFlowchart: showFlowchart,
          flowchart: layerBuilder.buildL4Layer(context),
          editors: [
            FileEditorBlock(
              filename: 'scene_assets/',
              description: '3D scene configuration files',
              icon: Icons.view_in_ar,
              isHighlighted: true,
              constraints: '• 3DScenesConfiguration.json for Azure ADT\n• Scene definitions and models',
              exampleContent: Step3Examples.sceneAssets,
              initialContent: _sceneAssetsContent,
              onContentChanged: (content) => setState(() => _sceneAssetsContent = content),
              onValidate: (content) => _validateFile('scene_assets', content),
            ),
          ],
        ),
        
        if (showFlowchart) _buildArrowRow(),

        // L5 Row
        _buildLayerRow(
          context,
          showFlowchart: showFlowchart,
          flowchart: layerBuilder.buildL5Layer(context),
          editors: [
            FileEditorBlock(
              filename: 'config_grafana.json',
              description: 'Grafana dashboard configuration',
              icon: Icons.dashboard,
              isHighlighted: true,
              constraints: '• Dashboard layout and panels\n• Data source connections',
              exampleContent: Step3Examples.grafanaConfig,
              initialContent: _grafanaConfigContent,
              onContentChanged: (content) => setState(() => _grafanaConfigContent = content),
              onValidate: (content) => _validateFile('grafana_config', content),
            ),
          ],
        ),

        const SizedBox(height: 24),

        // Footer
        _buildFooter(context, showFlowchart),
      ],
    );
  }
  
  /// Generate config_optimization.json from Step 2 CalcResult
  String _buildConfigOptimizationJson() {
    final result = _result;
    if (result == null) return '// No calculation result';
    
    final params = widget.cache.calcParams;
    final layers = layerBuilder.layerProviders;
    
    return const JsonEncoder.withIndent('  ').convert({
      'result': {
        // 'calculationResult': {
        //   'L1': layers['L1'],
        //   'L2': {
        //     'Hot': layers['L2'],
        //     'Cool': layers['L3_cold'],
        //     'Archive': layers['L3_archive'],
        //   },
        //   'L3': layers['L3_hot'],
        //   'L4': layers['L4'],
        //   'L5': layers['L5'],
        // },
        'inputParamsUsed': {
          'useEventChecking': params?.useEventChecking ?? false,
          'triggerNotificationWorkflow': params?.triggerNotificationWorkflow ?? false,
          'returnFeedbackToDevice': params?.returnFeedbackToDevice ?? false,
          // 'integrateErrorHandling': params?.integrateErrorHandling ?? false,
          'needs3DModel': params?.needs3DModel ?? false,
        },
      },
    });
  }
  
  /// Generate config_providers.json from Step 2 CalcResult
  String _buildConfigProvidersJson() {
    final result = _result;
    if (result == null) return '// No calculation result';
    
    final layers = layerBuilder.layerProviders;
    
    String? providerToString(String? p) {
      if (p == null) return null;  // Will be serialized as null in JSON
      switch (p.toUpperCase()) {
        case 'AWS': return 'aws';
        case 'AZURE': return 'azure';
        case 'GCP': return 'google';
        default: return p.toLowerCase();
      }
    }
    
    // Always include all layers - null for unconfigured
    return const JsonEncoder.withIndent('  ').convert({
      'layer_1_provider': providerToString(layers['L1']),
      'layer_2_provider': providerToString(layers['L2']),
      'layer_3_hot_provider': providerToString(layers['L3_hot']),
      'layer_3_cold_provider': providerToString(layers['L3_cold']),
      'layer_3_archive_provider': providerToString(layers['L3_archive']),
      'layer_4_provider': providerToString(layers['L4']),
      'layer_5_provider': providerToString(layers['L5']),
    });
  }

  /// Build provider map for visualization widget
  Map<String, String> _buildProviderMap() {
    final layers = layerBuilder.layerProviders;
    
    String getProvider(String key) {
      final value = layers[key];
      return value?.toUpperCase() ?? 'N/A';
    }
    
    return {
      'layer_1_provider': getProvider('L1'),
      'layer_2_provider': getProvider('L2'),
      'layer_3_hot_provider': getProvider('L3_hot'),
      'layer_3_cold_provider': getProvider('L3_cold'),
      'layer_3_archive_provider': getProvider('L3_archive'),
      'layer_4_provider': getProvider('L4'),
      'layer_5_provider': getProvider('L5'),
    };
  }

  Widget _buildHeader(BuildContext context, bool showFlowchart) {
    if (!showFlowchart) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.edit_document, size: 24, color: Theme.of(context).primaryColor),
              const SizedBox(width: 12),
              Text(
                'Configuration Files',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Upload or edit configuration files for your deployment',
            style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
          ),
        ],
      );
    }
    
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: _flowchartWidth,
          child: Column(
            children: [
              Text('Data Flow', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text('Component architecture', style: TextStyle(fontSize: 12, color: Colors.grey.shade500)),
            ],
          ),
        ),
        const SizedBox(width: 32),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.edit_document, size: 24, color: Theme.of(context).primaryColor),
                  const SizedBox(width: 12),
                  Text(
                    'Configuration Files',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'Upload or edit configuration files for your deployment',
                style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
              ),
            ],
          ),
        ),
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
          Expanded(
            child: Text(
              'Files will be validated and bundled during deployment. Click "Finish Configuration" when ready.',
              style: TextStyle(color: Colors.blue.shade800, fontSize: 13),
            ),
          ),
        ],
      ),
    );
    
    if (!showFlowchart) {
      return infoBox;
    }
    
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: _flowchartWidth,
          child: layerBuilder.buildLegend(context),
        ),
        const SizedBox(width: 32),
        Expanded(child: infoBox),
      ],
    );
  }

  /// Builds a layer row with flowchart on left and editors on right
  Widget _buildLayerRow(BuildContext context, {required bool showFlowchart, required Widget flowchart, required List<Widget> editors}) {
    // Editors column with max width constraint
    // Editors column with max width constraint
    final editorsColumn = ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 800),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: editors,
      ),
    );
    
    // Without flowchart: just editors in a column, centered
    if (!showFlowchart) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 24),
        child: Center(child: editorsColumn),
      );
    }
    
    // With flowchart: row layout - use Flexible instead of Expanded to respect maxWidth
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Left: Flowchart layer (natural height, top-aligned)
        SizedBox(
          width: _flowchartWidth,
          child: flowchart,
        ),
        const SizedBox(width: 32),
        // Right: File editors with max width, aligned to start of remaining space
        Flexible(
          child: Align(
            alignment: Alignment.topLeft,
            child: editorsColumn,
          ),
        ),
      ],
    );
  }

  /// Arrow between layer rows (only shown when flowchart is visible)
  Widget _buildArrowRow() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          SizedBox(
            width: _flowchartWidth,
            child: Center(
              child: Icon(Icons.arrow_downward, size: 24, color: Colors.grey.shade500),
            ),
          ),
          const SizedBox(width: 32),
          const Expanded(child: SizedBox.shrink()),
        ],
      ),
    );
  }

  Future<Map<String, dynamic>> _validateFile(String fileType, String content) async {
    try {
      if (content.trim().isEmpty) {
        return {'valid': false, 'message': 'File is empty'};
      }
      return {'valid': true, 'message': 'Content looks valid ✓'};
    } catch (e) {
      return {'valid': false, 'message': 'Validation error: $e'};
    }
  }

  Widget _buildNoResultMessage() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.warning_amber_rounded, size: 64, color: Colors.orange.shade400),
          const SizedBox(height: 16),
          Text('No Optimization Result', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text('Please complete Step 2 (Optimizer) first.', style: TextStyle(color: Colors.grey.shade600)),
          const SizedBox(height: 16),
          Text('Use the Back button above to return.', style: TextStyle(color: Colors.grey.shade500, fontSize: 12)),
        ],
      ),
    );
  }
}
