import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../bloc/wizard/wizard.dart';
import '../../config/step3_examples.dart';
import '../../providers/twins_provider.dart';
import '../../utils/api_error_handler.dart';
import '../../widgets/architecture_layer_builder.dart';
import '../../widgets/file_inputs/file_editor_block.dart';
import '../../widgets/file_inputs/collapsible_section.dart';
import '../../widgets/file_inputs/zip_upload_block.dart';
import '../../widgets/file_inputs/config_json_visualization_block.dart';
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
  ArchitectureLayerBuilder? _layerBuilder;
  
  // Breakpoint for showing flowchart column
  static const double _flowchartBreakpoint = 900;
  static const double _flowchartWidth = 450;

  /// Validate config file via API (direct call, not via BLoC)
  /// This matches the CredentialSection pattern for inline validation feedback
  Future<Map<String, dynamic>> _validateConfigFile(
    String configType,
    String content,
    WizardState state,
  ) async {
    final twinId = state.twinId;
    if (twinId == null) {
      return {'valid': false, 'message': 'Save draft first to enable validation'};
    }

    if (content.trim().isEmpty) {
      return {'valid': false, 'message': 'No content to validate'};
    }

    try {
      // Direct API call for immediate feedback
      final container = ProviderScope.containerOf(context);
      final api = container.read(apiServiceProvider);
      final result = await api.validateDeployerConfig(twinId, configType, content);
      
      final valid = result['valid'] == true;
      final message = result['message']?.toString() ?? (valid ? 'Valid ✓' : 'Validation failed');
      
      // Update BLoC state for persistence via event (not emit which is protected)
      // Guard with mounted check since we crossed an async gap
      if (mounted) {
        context.read<WizardBloc>().add(WizardConfigValidationCompleted(configType, valid));
      }
      
      return {'valid': valid, 'message': message};
    } catch (e) {
      return {'valid': false, 'message': 'Validation failed: ${ApiErrorHandler.extractMessage(e)}'};
    }
  }

  /// Build amber info box for unmet dependencies
  Widget _buildDependencyInfoBox(String message) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.amber.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.amber.shade200),
      ),
      child: Row(
        children: [
          Icon(Icons.info_outline, color: Colors.amber.shade700, size: 24),
          const SizedBox(width: 16),
          Expanded(child: Text(message, style: TextStyle(color: Colors.amber.shade900, fontSize: 13))),
        ],
      ),
    );
  }

  /// Build grey info box for empty state
  Widget _buildEmptyStateBox(String message) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Row(
        children: [
          Icon(Icons.info_outline, color: Colors.grey.shade500, size: 24),
          const SizedBox(width: 16),
          Expanded(child: Text(message, style: TextStyle(color: Colors.grey.shade600, fontSize: 13))),
        ],
      ),
    );
  }

  /// Build dynamic L2 inputs based on Section 2 validation state
  List<Widget> _buildL2DynamicInputs(BuildContext context, WizardState state) {
    final widgets = <Widget>[];
    
    // === PROCESSORS ===
    // Show one processor input per device from validated config_iot_devices.json
    if (!state.configIotDevicesValidated) {
      widgets.add(_buildDependencyInfoBox(
        'Validate config_iot_devices.json first to enable processor function inputs.'
      ));
    } else if (state.deviceIds.isEmpty) {
      widgets.add(_buildEmptyStateBox('No devices found in config_iot_devices.json'));
    } else {
      for (final deviceId in state.deviceIds) {
        widgets.add(FileEditorBlock(
          filename: 'processors/$deviceId/lambda_function.py',
          description: 'Processor Lambda for $deviceId',
          icon: Icons.code,
          isHighlighted: true,
          constraints: '• AWS Lambda handler with lambda_handler()\n• Processes incoming IoT events',
          exampleContent: Step3Examples.processors,
          initialContent: state.processorContents[deviceId] ?? '',
          isValidated: state.processorValidated[deviceId] ?? false,
          onContentChanged: (content) => context.read<WizardBloc>().add(
            WizardProcessorContentChanged(deviceId, content),
          ),
          onValidate: (content) async => {'valid': true, 'message': 'Python syntax check pending'},
        ));
        widgets.add(const SizedBox(height: 16));
      }
    }
    
    // === FEEDBACK FUNCTION ===
    if (state.shouldShowFeedbackFunction) {
      widgets.add(FileEditorBlock(
        filename: 'event-feedback/lambda_function.py',
        description: 'Event feedback Lambda',
        icon: Icons.feedback,
        isHighlighted: true,
        constraints: '• AWS Lambda with MQTT feedback capability\n• Sends feedback to IoT devices',
        exampleContent: Step3Examples.processors,
        initialContent: state.eventFeedbackContent ?? '',
        isValidated: state.eventFeedbackValidated,
        onContentChanged: (content) => context.read<WizardBloc>().add(
          WizardEventFeedbackContentChanged(content),
        ),
        onValidate: (content) async => {'valid': true, 'message': 'Python syntax check pending'},
      ));
      widgets.add(const SizedBox(height: 16));
    }
    
    // === EVENT ACTION FUNCTIONS ===
    if (state.calcParams?.useEventChecking == true) {
      if (!state.configEventsValidated) {
        widgets.add(_buildDependencyInfoBox(
          'Validate config_events.json first to enable event action function inputs.'
        ));
      } else if (state.eventActionFunctionNames.isEmpty) {
        widgets.add(_buildEmptyStateBox('No event actions with functionName defined.'));
      } else {
        for (final funcName in state.eventActionFunctionNames) {
          widgets.add(FileEditorBlock(
            filename: 'event_actions/$funcName/lambda_function.py',
            description: 'Event action: $funcName',
            icon: Icons.bolt,
            isHighlighted: true,
            constraints: '• AWS Lambda triggered by EventBridge rules\n• Handles $funcName events',
            exampleContent: Step3Examples.processors,
            initialContent: state.eventActionContents[funcName] ?? '',
            isValidated: state.eventActionValidated[funcName] ?? false,
            onContentChanged: (content) => context.read<WizardBloc>().add(
              WizardEventActionContentChanged(funcName, content),
            ),
            onValidate: (content) async => {'valid': true, 'message': 'Python syntax check pending'},
          ));
          widgets.add(const SizedBox(height: 16));
        }
      }
    }
    
    // === STATE MACHINE ===
    if (state.shouldShowStateMachine) {
      final filename = state.stateMachineFilename ?? 'state_machine.json';
      widgets.add(FileEditorBlock(
        filename: filename,
        description: 'Workflow / state machine definition',
        icon: Icons.account_tree,
        isHighlighted: true,
        constraints: _getStateMachineConstraints(state.layer2Provider),
        exampleContent: _getStateMachineExample(state.layer2Provider),
        initialContent: state.stateMachineContent ?? '',
        isValidated: state.stateMachineValidated,
        onContentChanged: (content) => context.read<WizardBloc>().add(
          WizardStateMachineContentChanged(content),
        ),
        onValidate: (content) async => {'valid': true, 'message': 'Schema validation pending'},
      ));
    }
    
    // If nothing to show (all conditions false), show info
    if (widgets.isEmpty) {
      widgets.add(_buildEmptyStateBox(
        'Enable triggerNotificationWorkflow or returnFeedbackToDevice in Step 2 for L2 inputs.'
      ));
    }
    
    return widgets;
  }
  
  String _getStateMachineConstraints(String? provider) {
    switch (provider?.toLowerCase()) {
      case 'aws':
        return '• AWS Step Functions JSON\n• Amazon States Language';
      case 'azure':
        return '• Azure Logic App JSON\n• Workflow definition';
      case 'gcp':
        return '• Google Workflows YAML\n• Workflow syntax';
      default:
        return '• Provider-specific workflow definition';
    }
  }
  
  String _getStateMachineExample(String? provider) {
    switch (provider?.toLowerCase()) {
      case 'aws': return Step3Examples.awsStateMachine;
      case 'azure': return Step3Examples.azureStateMachine;
      case 'gcp': return Step3Examples.gcpStateMachine;
      default: return Step3Examples.stateMachine;
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
              // For new twins, expand this section to guide users to upload a zip first
              // For existing twins, keep collapsed since they likely have config already
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 800),
                  child: CollapsibleSection(
                    sectionNumber: 1,
                    title: 'Quick Upload',
                    description: 'Upload a complete project zip to auto-fill all fields',
                    icon: Icons.folder_zip,
                    initiallyExpanded: state.mode == WizardMode.create,
                    child: ZipUploadBlock(
                      onZipSelected: (path) {
                        // ZIP upload functionality - TODO: implement extraction
                      },
                    ),
                  ),
                ),
              ),
              
              // Section 2: Configuration Files
              // For new twins, keep collapsed until they upload or choose manual entry
              // For existing twins with all valid configs, collapse to reduce noise
              // For existing twins with missing/invalid configs, expand to show what needs work
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 800),
                  child: CollapsibleSection(
                    sectionNumber: 2,
                    title: 'Configuration Files',
                    description: 'Core deployment settings and device definitions',
                    icon: Icons.settings,
                    // Auto-collapse if all Section 2 configs are valid (on edit)
                    initiallyExpanded: state.mode == WizardMode.edit && !state.isSection2Valid,
                    isValid: state.isSection2Valid,  // Show check icon when complete
                    child: _buildConfigSection(context, state),
                  ),
                ),
              ),
              
              // Section 3: User Functions & Assets
              // No longer locked - validation will handle dependencies
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
                    initiallyExpanded: state.mode == WizardMode.edit,
                    collapsedMaxWidth: 800,
                    // Info message about dependency (non-blocking)
                    infoHint: 'Inputs here depend on Section 2 configuration files (config_events.json, config_iot_devices.json)',
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
        ConfigJsonVisualizationBlock(
          twinName: state.deployerDigitalTwinName,  // Separate from Step 1 project name
          mode: state.debugMode == true ? 'debug' : 'production',
          // Convert months to days for display (CalcParams uses months)
          hotStorageDays: (state.calcParams?.hotStorageDurationInMonths ?? 1) * 30,
          coldStorageDays: (state.calcParams?.coolStorageDurationInMonths ?? 3) * 30,
          isValidated: state.configJsonValidated,  // Persist validation across navigation
          onTwinNameChanged: (name) {
            // Update deployer digital twin name in BLoC state (separate from Step 1 project name)
            context.read<WizardBloc>().add(WizardDeployerTwinNameChanged(name));
          },
          onValidate: (config) async {
            // Convert config map to JSON string for API validation
            final content = const JsonEncoder.withIndent('  ').convert(config);
            return await _validateConfigFile('config', content, state);
          },
          onValidationSuccess: () {
            // Persist validation success to BLoC state (gates save)
            context.read<WizardBloc>().add(const WizardConfigValidationCompleted('config', true));
          },
        ),
        const SizedBox(height: 16),
        
        FileEditorBlock(
          filename: 'config_events.json',
          description: 'Event-driven automation rules',
          icon: Icons.bolt,
          isHighlighted: true,
          constraints: '• JSON array of event conditions\n• Define actions for each condition',
          exampleContent: Step3Examples.configEvents,
          initialContent: state.configEventsJson ?? '',
          isValidated: state.configEventsValidated,  // Persist validation across navigation
          onContentChanged: (content) {
            // State is managed by BLoC
            context.read<WizardBloc>().add(WizardConfigEventsChanged(content));
          },
          onValidate: (content) async {
            // Direct API call - do NOT use BLoC for validation UI
            // BLoC is only for content persistence
            return await _validateConfigFile('events', content, state);
          },
          autoValidateOnUpload: true,
        ),
        const SizedBox(height: 16),
        
        FileEditorBlock(
          filename: 'config_iot_devices.json',
          description: 'IoT device definitions',
          icon: Icons.sensors,
          isHighlighted: true,
          constraints: '• JSON array of device configs\n• Define properties per device',
          exampleContent: Step3Examples.configIotDevices,
          initialContent: state.configIotDevicesJson ?? '',
          isValidated: state.configIotDevicesValidated,  // Persist validation across navigation
          onContentChanged: (content) {
            // State is managed by BLoC
            context.read<WizardBloc>().add(WizardConfigIotDevicesChanged(content));
          },
          onValidate: (content) async {
            // Direct API call - do NOT use BLoC for validation UI
            return await _validateConfigFile('iot', content, state);
          },
          autoValidateOnUpload: true,
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
            initialContent: state.payloadsJson ?? '',
            isValidated: state.payloadsValidated,
            onContentChanged: (content) => context.read<WizardBloc>().add(WizardPayloadsChanged(content)),
            onValidate: (content) => _validateConfigFile('payloads', content, state),
            autoValidateOnUpload: true,
          ),
        ]),
        
        if (showFlowchart) _buildArrowRow(),

        // L2 Row (Dynamic)
        _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL2Layer(context), editors: 
          _buildL2DynamicInputs(context, state),
        ),
        
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
            initialContent: '',  // TODO: Migrate to BLoC
            onContentChanged: (_) {},  // TODO: Migrate to BLoC
            onValidate: (content) => _validateFile('scene_assets', content),
          ),
        ]),
        
        if (showFlowchart) _buildArrowRow(),

        // L5 Row
        _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL5Layer(context), editors: [
          FileEditorBlock(
            filename: 'config_user.json',
            description: 'Platform user configuration',
            icon: Icons.dashboard,
            isHighlighted: true,
            constraints: '• Dashboard layout and panels',
            exampleContent: Step3Examples.userConfig,
            initialContent: '',  // TODO: Migrate to BLoC
            onContentChanged: (_) {},  // TODO: Migrate to BLoC
            onValidate: (content) => _validateFile('user_config', content),
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
            Icon(Icons.edit_document, size: 24, color: Colors.grey.shade500),
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
