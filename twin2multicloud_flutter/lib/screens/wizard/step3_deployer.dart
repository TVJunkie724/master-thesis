import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../bloc/wizard/wizard.dart';
import '../../config/step3_examples.dart';
import '../../providers/twins_provider.dart';
import '../../utils/api_error_handler.dart';
import '../../services/api_service.dart';
import '../../widgets/architecture_layer_builder.dart';
import '../../widgets/file_inputs/file_editor_block.dart';
import '../../widgets/file_inputs/function_package_block.dart';
import '../../widgets/file_inputs/collapsible_section.dart';
import '../../widgets/file_inputs/collapsible_block_wrapper.dart';
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

  /// Validate L2 content (function-code or state-machine) and dispatch BLoC event
  Future<Map<String, dynamic>> _validateL2Content(
    String type,
    String content,
    WizardState state, {
    String? entityId,  // deviceId or functionName for Map-based validation
  }) async {
    final twinId = state.twinId;
    final provider = state.layer2Provider;
    
    if (twinId == null) return {'valid': false, 'message': 'Save draft first'};
    if (provider == null) return {'valid': false, 'message': 'Complete Step 2 first'};
    if (content.trim().isEmpty) return {'valid': false, 'message': 'No content'};

    try {
      final container = ProviderScope.containerOf(context);
      final api = container.read(apiServiceProvider);
      final result = await api.validateL2Content(twinId, type, content, provider);
      final valid = result['valid'] == true;
      final message = result['message']?.toString() ?? (valid ? 'Valid ✓' : 'Failed');
      
      // Dispatch BLoC event to persist validation state
      if (mounted && valid) {
        _dispatchL2ValidationEvent(type, entityId, valid);
      }
      
      return {'valid': valid, 'message': message};
    } catch (e) {
      return {'valid': false, 'message': ApiErrorHandler.extractMessage(e)};
    }
  }

  void _dispatchL2ValidationEvent(String type, String? entityId, bool valid) {
    final bloc = context.read<WizardBloc>();
    if (type == 'function-code') {
      // Determine which L2 function type based on entityId pattern
      if (entityId != null && entityId.startsWith('processor:')) {
        bloc.add(WizardProcessorValidationCompleted(entityId.substring(10), valid));
      } else if (entityId != null && entityId.startsWith('event-action:')) {
        bloc.add(WizardEventActionValidationCompleted(entityId.substring(13), valid));
      } else if (entityId == 'feedback') {
        bloc.add(WizardEventFeedbackValidationCompleted(valid));
      }
    } else if (type == 'state-machine') {
      bloc.add(WizardStateMachineValidationCompleted(valid));
    }
  }

  /// Validate L4/L5 content and dispatch BLoC event
  /// [providerOverride] - Use specific provider (for L5 user-config which uses layer5Provider)
  Future<Map<String, dynamic>> _validateL4Content(
    String type,  // 'hierarchy', 'scene-config', 'user-config'
    String content,
    WizardState state, {
    String? providerOverride,
  }) async {
    final twinId = state.twinId;
    if (twinId == null) {
      return {'valid': false, 'message': 'Save draft first'};
    }
    
    // Use override if provided, otherwise default to L4 provider
    final provider = (providerOverride ?? state.layer4Provider)?.toLowerCase();
    if (provider == null) {
      final layer = type == 'user-config' ? 'L5' : 'L4';
      return {'valid': false, 'message': 'No $layer provider selected (Step 2)'};
    }
    
    try {
      final container = ProviderScope.containerOf(context); final api = container.read(apiServiceProvider);
      final bloc = context.read<WizardBloc>();  // Capture before await
      final result = await api.validateL4Content(twinId, type, content, provider);
      
      final valid = result['valid'] == true;
      final message = result['message']?.toString() ?? (valid ? 'Valid' : 'Validation failed');
      
      // Dispatch appropriate BLoC event
      switch (type) {
        case 'hierarchy':
          bloc.add(WizardHierarchyValidationCompleted(valid));
          break;
        case 'scene-config':
          bloc.add(WizardSceneConfigValidationCompleted(valid));
          break;
        case 'user-config':
          bloc.add(WizardUserConfigValidationCompleted(valid));
          break;
      }
      
      return {'valid': valid, 'message': message};
    } catch (e) {
      return {'valid': false, 'message': ApiErrorHandler.extractMessage(e)};
    }
  }

  /// Get provider-specific function constraints for UI
  String _getFunctionConstraints(String? provider) {
    switch (provider?.toLowerCase()) {
      case 'aws':
        return '• AWS Lambda with lambda_handler(event, context)\n• Returns dict with statusCode';
      case 'azure':
        return '• Azure Function with main(req)\n• Returns HttpResponse';
      case 'gcp':
      case 'google':
        return '• Cloud Function with any entry point\n• HTTP request handler';
      default:
        return '• Provider-specific function entry point';
    }
  }

  /// Get provider-specific processor example
  String _getProcessorExample(String? provider) {
    switch (provider?.toLowerCase()) {
      case 'aws': return Step3Examples.processors;
      case 'azure': return Step3Examples.azureProcessors;
      case 'gcp':
      case 'google': return Step3Examples.gcpProcessors;
      default: return Step3Examples.processors;
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
        widgets.add(FunctionPackageBlock(
          codeFilename: 'processors/$deviceId/lambda_function.py',
          description: 'Processor Lambda for $deviceId',
          codeContent: state.processorContents[deviceId] ?? '',
          isCodeValidated: state.processorValidated[deviceId] ?? false,
          onCodeChanged: (content) => context.read<WizardBloc>().add(
            WizardProcessorContentChanged(deviceId, content),
          ),
          requirementsContent: state.processorRequirements[deviceId],
          onRequirementsChanged: (content) => context.read<WizardBloc>().add(
            WizardProcessorRequirementsChanged(deviceId, content),
          ),
          onValidate: (content) => _validateL2Content('function-code', content, state, entityId: 'processor:$deviceId'),
          constraints: _getFunctionConstraints(state.layer2Provider),
          exampleContent: _getProcessorExample(state.layer2Provider),
          initiallyExpanded: !(state.processorValidated[deviceId] ?? false),
        ));
        widgets.add(const SizedBox(height: 16));
      }
    }
    
    // === FEEDBACK FUNCTION ===
    if (state.shouldShowFeedbackFunction) {
      widgets.add(FunctionPackageBlock(
        codeFilename: 'event-feedback/lambda_function.py',
        description: 'Event feedback Lambda',
        codeContent: state.eventFeedbackContent ?? '',
        isCodeValidated: state.eventFeedbackValidated,
        onCodeChanged: (content) => context.read<WizardBloc>().add(
          WizardEventFeedbackContentChanged(content),
        ),
        requirementsContent: state.eventFeedbackRequirements,
        onRequirementsChanged: (content) => context.read<WizardBloc>().add(
          WizardEventFeedbackRequirementsChanged(content),
        ),
        onValidate: (content) => _validateL2Content('function-code', content, state, entityId: 'feedback'),
        constraints: _getFunctionConstraints(state.layer2Provider),
        exampleContent: _getProcessorExample(state.layer2Provider),
        initiallyExpanded: !state.eventFeedbackValidated,
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
          widgets.add(FunctionPackageBlock(
            codeFilename: 'event_actions/$funcName/lambda_function.py',
            description: 'Event action: $funcName',
            codeContent: state.eventActionContents[funcName] ?? '',
            isCodeValidated: state.eventActionValidated[funcName] ?? false,
            onCodeChanged: (content) => context.read<WizardBloc>().add(
              WizardEventActionContentChanged(funcName, content),
            ),
            requirementsContent: state.eventActionRequirements[funcName],
            onRequirementsChanged: (content) => context.read<WizardBloc>().add(
              WizardEventActionRequirementsChanged(funcName, content),
            ),
            onValidate: (content) => _validateL2Content('function-code', content, state, entityId: 'event-action:$funcName'),
            constraints: _getFunctionConstraints(state.layer2Provider),
            exampleContent: _getProcessorExample(state.layer2Provider),
            initiallyExpanded: !(state.eventActionValidated[funcName] ?? false),
          ));
          widgets.add(const SizedBox(height: 16));
        }
      }
    }
    
    // === STATE MACHINE ===
    if (state.shouldShowStateMachine) {
      final filename = state.stateMachineFilename ?? 'state_machine.json';
      widgets.add(CollapsibleBlockWrapper(
        title: filename,
        subtitle: 'Workflow / state machine definition',
        icon: Icons.account_tree,
        isValid: state.stateMachineValidated ? true : null,
        showEditBadge: true,
        initiallyExpanded: !state.stateMachineValidated,
        child: FileEditorBlock(
          showHeader: false,
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
          onValidate: (content) => _validateL2Content('state-machine', content, state),
          autoValidateOnUpload: true,
        ),
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
        // config.json - editable with auto values
        CollapsibleBlockWrapper(
          title: 'config.json',
          subtitle: 'Core deployment configuration',
          icon: Icons.settings,
          isValid: state.configJsonValidated ? true : null,
          showEditBadge: true,
          autoBadge: 'From Step 1 & 2',
          initiallyExpanded: !state.configJsonValidated,
          child: ConfigJsonVisualizationBlock(
            showHeader: false,
            twinName: state.deployerDigitalTwinName,
            mode: state.debugMode == true ? 'debug' : 'production',
            hotStorageDays: (state.calcParams?.hotStorageDurationInMonths ?? 1) * 30,
            coldStorageDays: (state.calcParams?.coolStorageDurationInMonths ?? 3) * 30,
            isValidated: state.configJsonValidated,
            onTwinNameChanged: (name) {
              context.read<WizardBloc>().add(WizardDeployerTwinNameChanged(name));
            },
            onValidate: (config) async {
              final content = const JsonEncoder.withIndent('  ').convert(config);
              return await _validateConfigFile('config', content, state);
            },
            onValidationSuccess: () {
              context.read<WizardBloc>().add(const WizardConfigValidationCompleted('config', true));
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
          child: FileEditorBlock(
            showHeader: false,
            filename: 'config_events.json',
            description: 'Event-driven automation rules',
            icon: Icons.bolt,
            isHighlighted: true,
            constraints: '• JSON array of event conditions\n• Define actions for each condition',
            exampleContent: Step3Examples.configEvents,
            initialContent: state.configEventsJson ?? '',
            isValidated: state.configEventsValidated,
            onContentChanged: (content) {
              context.read<WizardBloc>().add(WizardConfigEventsChanged(content));
            },
            onValidate: (content) async {
              return await _validateConfigFile('events', content, state);
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
          child: FileEditorBlock(
            showHeader: false,
            filename: 'config_iot_devices.json',
            description: 'IoT device definitions',
            icon: Icons.sensors,
            isHighlighted: true,
            constraints: '• JSON array of device configs\n• Define properties per device',
            exampleContent: Step3Examples.configIotDevices,
            initialContent: state.configIotDevicesJson ?? '',
            isValidated: state.configIotDevicesValidated,
            onContentChanged: (content) {
              context.read<WizardBloc>().add(WizardConfigIotDevicesChanged(content));
            },
            onValidate: (content) async {
              return await _validateConfigFile('iot', content, state);
            },
            autoValidateOnUpload: true,
          ),
        ),
        const SizedBox(height: 16),
        
        // L4 Hierarchy JSON - only shown when L4 provider is AWS or Azure
        if (state.layer4Provider?.toUpperCase() == 'AWS' || 
            state.layer4Provider?.toUpperCase() == 'AZURE') ...[
          Builder(builder: (context) {
            final l4Provider = state.layer4Provider!.toLowerCase();
            final isAws = l4Provider == 'aws';
            final filename = isAws ? 'aws_hierarchy.json' : 'azure_hierarchy.json';
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
                onContentChanged: (content) {
                  context.read<WizardBloc>().add(WizardHierarchyContentChanged(content));
                },
                onValidate: (content) async {
                  return await _validateL4Content('hierarchy', content, state);
                },
                autoValidateOnUpload: true,
              ),
            );
          }),
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
                'triggerNotificationWorkflow': state.calcParams?.triggerNotificationWorkflow ?? false,
                'returnFeedbackToDevice': state.calcParams?.returnFeedbackToDevice ?? false,
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
            visualContent: ConfigVisualizationBlock.buildProvidersVisual(_buildProviderMap()),
          ),
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
          CollapsibleBlockWrapper(
            title: 'payloads.json',
            subtitle: 'IoT device payload schemas',
            icon: Icons.data_object,
            isValid: state.payloadsValidated ? true : null,
            showEditBadge: true,
            initiallyExpanded: !state.payloadsValidated,
            child: FileEditorBlock(
              showHeader: false,
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

        // L4 Row - Scene Config (only when needs3DModel && L4 provider is AWS/Azure && hierarchy validated)
        if (state.calcParams?.needs3DModel == true && 
            state.hierarchyValidated &&
            (state.layer4Provider?.toUpperCase() == 'AWS' || 
             state.layer4Provider?.toUpperCase() == 'AZURE')) ...[
          _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL4Layer(context), editors: [
            Builder(builder: (context) {
              final l4Provider = state.layer4Provider!.toLowerCase();
              final isAws = l4Provider == 'aws';
              final filename = isAws ? 'scene.json' : '3DScenesConfiguration.json';
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
                    showEditBadge: true,
                    initiallyExpanded: !state.sceneConfigValidated,
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
                      onContentChanged: (content) {
                        context.read<WizardBloc>().add(WizardSceneConfigContentChanged(content));
                      },
                      onValidate: (content) async {
                        return await _validateL4Content('scene-config', content, state);
                      },
                      autoValidateOnUpload: true,
                    ),
                  ),
                  const SizedBox(height: 12),
                  // GLB Upload Status Card
                  _buildGlbUploadCard(context, state),
                ],
              );
            }),
          ]),
          if (showFlowchart) _buildArrowRow(),
        ] else ...[
          // No L4 Scene needed - show info card
          _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL4Layer(context), editors: [
            _buildL4InfoCard(context, state),
          ]),
          if (showFlowchart) _buildArrowRow(),
        ],

        // L5 Row - User Config (AWS/Azure only)
        _buildLayerRow(context, showFlowchart: showFlowchart, flowchart: layerBuilder.buildL5Layer(context), editors: [
          if (state.layer5Provider?.toUpperCase() == 'AWS' || 
              state.layer5Provider?.toUpperCase() == 'AZURE') ...[
            Builder(builder: (context) {
              // Provider already checked above, proceed with config
              return CollapsibleBlockWrapper(
                title: 'config_user.json',
                subtitle: 'Grafana dashboard configuration',
                icon: Icons.dashboard,
                showEditBadge: true,
                initiallyExpanded: !state.userConfigValidated,
                copyContent: state.userConfigContent,
                child: FileEditorBlock(
                  showHeader: false,
                  filename: 'config_user.json',
                  description: 'Grafana dashboard user configuration',
                  icon: Icons.dashboard,
                  isHighlighted: true,
                  constraints: '• Dashboard panels and queries\\n• Data source configuration',
                  exampleContent: Step3Examples.userConfig,
                  initialContent: state.userConfigContent ?? '',
                  isValidated: state.userConfigValidated,
                  onContentChanged: (content) {
                    context.read<WizardBloc>().add(WizardUserConfigContentChanged(content));
                  },
                  onValidate: (content) async {
                    // User config is L5 - use layer5Provider instead of layer4Provider
                    return await _validateL4Content(
                      'user-config', content, state,
                      providerOverride: state.layer5Provider,
                    );
                  },
                  autoValidateOnUpload: true,
                ),
              );
            }),
          ] else ...[
            _buildL5InfoCard(context, state),
          ],
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

  // ============================================================
  // L4/L5 HELPER WIDGETS
  // ============================================================

  /// GLB file upload card - shows upload button or uploaded status
  Widget _buildGlbUploadCard(BuildContext context, WizardState state) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isUploaded = state.sceneGlbUploaded;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isUploaded 
              ? Colors.green.shade300 
              : (isDark ? Colors.grey.shade700 : Colors.grey.shade300),
        ),
      ),
      child: Row(
        children: [
          Icon(
            isUploaded ? Icons.check_circle : Icons.view_in_ar,
            color: isUploaded ? Colors.green : Colors.grey.shade600,
            size: 32,
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'scene.glb',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  isUploaded 
                      ? '3D model uploaded ✓' 
                      : 'Upload 3D model for visualization',
                  style: TextStyle(
                    fontSize: 12,
                    color: isUploaded ? Colors.green : Colors.grey.shade600,
                  ),
                ),
              ],
            ),
          ),
          if (isUploaded) ...[
            IconButton(
              icon: const Icon(Icons.delete_outline, color: Colors.red),
              tooltip: 'Delete GLB',
              onPressed: () async {
                final twinId = state.twinId;
                if (twinId == null) return;
                final container = ProviderScope.containerOf(context); final api = container.read(apiServiceProvider);
                final bloc = context.read<WizardBloc>();
                final messenger = ScaffoldMessenger.of(context);
                try {
                  await api.deleteSceneGlb(twinId);
                  bloc.add(const WizardSceneGlbUploadStatusChanged(false));
                } catch (e) {
                  messenger.showSnackBar(
                    SnackBar(content: Text('Delete failed: ${ApiErrorHandler.extractMessage(e)}')),
                  );
                }
              },
            ),
          ] else ...[
            ElevatedButton.icon(
              icon: const Icon(Icons.upload_file, size: 18),
              label: const Text('Upload GLB'),
              onPressed: () async {
                final twinId = state.twinId;
                // Capture references before any async operations
                final messenger = ScaffoldMessenger.of(context);
                final container = ProviderScope.containerOf(context); final api = container.read(apiServiceProvider);
                final bloc = context.read<WizardBloc>();
                
                if (twinId == null) {
                  messenger.showSnackBar(
                    const SnackBar(content: Text('Save draft first before uploading GLB')),
                  );
                  return;
                }
                
                // Pick GLB file
                final result = await FilePicker.platform.pickFiles(
                  type: FileType.custom,
                  allowedExtensions: ['glb'],
                  withData: true,  // Required for web support
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
                
                // Size check (100MB limit)
                final sizeMb = bytes.length / (1024 * 1024);
                if (sizeMb > 100) {
                  messenger.showSnackBar(
                    SnackBar(content: Text('File too large: ${sizeMb.toStringAsFixed(1)}MB (max 100MB)')),
                  );
                  return;
                }
                
                // Upload to server
                try {
                  messenger.showSnackBar(
                    SnackBar(content: Text('Uploading ${file.name} (${sizeMb.toStringAsFixed(1)}MB)...')),
                  );
                  
                  await api.uploadSceneGlb(
                    twinId,
                    bytes,
                    file.name,
                  );
                  
                  bloc.add(const WizardSceneGlbUploadStatusChanged(true));
                  
                  messenger.showSnackBar(
                    const SnackBar(content: Text('GLB uploaded successfully ✓')),
                  );
                } catch (e) {
                  messenger.showSnackBar(
                    SnackBar(content: Text('Upload failed: ${ApiErrorHandler.extractMessage(e)}')),
                  );
                }
              },
            ),
          ],
        ],
      ),
    );
  }

  /// L4 info card when needs3DModel is false or L4 provider is not AWS/Azure
  Widget _buildL4InfoCard(BuildContext context, WizardState state) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final needs3D = state.calcParams?.needs3DModel == true;
    final l4Provider = state.layer4Provider?.toUpperCase();
    
    String message;
    IconData icon;
    Color color;
    
    if (!needs3D) {
      message = 'L4 visualization not needed (needs3DModel = false in Step 2)';
      icon = Icons.info_outline;
      color = Colors.blue;
    } else if (l4Provider == 'GCP') {
      message = 'GCP does not support 3D visualization in this thesis scope';
      icon = Icons.block;
      color = Colors.orange;
    } else if (l4Provider == null) {
      message = 'No L4 provider selected in Step 2';
      icon = Icons.warning_amber;
      color = Colors.amber;
    } else {
      message = 'L4 configuration not required';
      icon = Icons.check_circle_outline;
      color = Colors.green;
    }
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: isDark ? Colors.grey.shade700 : Colors.grey.shade300),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 28),
          const SizedBox(width: 16),
          Expanded(
            child: Text(message, style: TextStyle(color: Colors.grey.shade600)),
          ),
        ],
      ),
    );
  }

  /// L5 info card when L5 provider is not AWS/Azure
  Widget _buildL5InfoCard(BuildContext context, WizardState state) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final l5Provider = state.layer5Provider?.toUpperCase();
    
    String message;
    if (l5Provider == 'GCP') {
      message = 'GCP Grafana configuration not supported in this thesis scope';
    } else if (l5Provider == null) {
      message = 'No L5 provider selected in Step 2';
    } else {
      message = 'L5 config not required for $l5Provider';
    }
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: isDark ? Colors.grey.shade700 : Colors.grey.shade300),
      ),
      child: Row(
        children: [
          Icon(Icons.info_outline, color: Colors.blue, size: 28),
          const SizedBox(width: 16),
          Expanded(
            child: Text(message, style: TextStyle(color: Colors.grey.shade600)),
          ),
        ],
      ),
    );
  }
}
