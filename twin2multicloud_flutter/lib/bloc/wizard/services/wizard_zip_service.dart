// lib/bloc/wizard/services/wizard_zip_service.dart
// Handles zip file upload processing for wizard Step 3
// STATELESS SERVICE: receives data, returns state (no API calls)

import 'dart:convert';
import 'package:flutter/foundation.dart';
import '../wizard_state.dart';

/// Result of processing a zip upload.
/// Consistent with WizardInitResult pattern.
class ZipProcessingResult {
  final WizardState state;
  final bool success;
  final bool shouldTriggerCollapse;

  const ZipProcessingResult({
    required this.state,
    required this.success,
    this.shouldTriggerCollapse = false,
  });

  /// Factory for successful result
  factory ZipProcessingResult.ok(
    WizardState state, {
    bool shouldTriggerCollapse = false,
  }) => ZipProcessingResult(
    state: state,
    success: true,
    shouldTriggerCollapse: shouldTriggerCollapse,
  );

  /// Factory for error result
  factory ZipProcessingResult.error(WizardState state, String message) =>
      ZipProcessingResult(
        state: state.copyWith(
          zipUploadInProgress: false,
          errorMessage: message,
        ),
        success: false,
      );
}

/// Data class for extracted content from zip.
/// Public for testing.
class ExtractedContent {
  final String? digitalTwinName;
  final String? configEvents;
  final String? configIotDevices;
  final String? payloads;
  final String? hierarchy;
  final String? sceneConfig;
  final String? userConfig;
  final String? stateMachine;
  final String? eventFeedback;
  final Map<String, String> processors;
  final Map<String, String> eventActions;
  final bool glbUploaded;

  const ExtractedContent({
    this.digitalTwinName,
    this.configEvents,
    this.configIotDevices,
    this.payloads,
    this.hierarchy,
    this.sceneConfig,
    this.userConfig,
    this.stateMachine,
    this.eventFeedback,
    this.processors = const {},
    this.eventActions = const {},
    this.glbUploaded = false,
  });
}

/// Data class for validation results from zip.
/// Public for testing.
class ZipValidationResult {
  final bool configJsonValid;
  final bool eventsValid;
  final bool iotDevicesValid;
  final bool payloadsValid;
  final bool hierarchyValid;
  final bool sceneConfigValid;
  final bool userConfigValid;
  final bool stateMachineValid;
  final bool eventFeedbackValid;
  final Map<String, bool> processorValidation;
  final Map<String, bool> eventActionValidation;

  const ZipValidationResult({
    this.configJsonValid = false,
    this.eventsValid = false,
    this.iotDevicesValid = false,
    this.payloadsValid = false,
    this.hierarchyValid = false,
    this.sceneConfigValid = false,
    this.userConfigValid = false,
    this.stateMachineValid = false,
    this.eventFeedbackValid = false,
    this.processorValidation = const {},
    this.eventActionValidation = const {},
  });
}

/// STATELESS service for processing zip uploads in the wizard.
/// Receives data, returns state (no API calls).
class WizardZipService {
  /// Process the actual zip upload and populate fields
  ///
  /// Returns [ZipProcessingResult] containing the new state and whether
  /// to trigger section collapse (when all validations pass).
  ZipProcessingResult processZipUpload({
    required WizardState state,
    required Map<String, dynamic> apiResult,
  }) {
    final success = apiResult['success'] as bool? ?? false;
    final errors = List<String>.from(apiResult['validation_errors'] ?? []);
    final warnings = List<String>.from(apiResult['warnings'] ?? []);
    // Safe cast from potentially dynamic maps
    final files = Map<String, dynamic>.from(apiResult['files'] ?? {});
    final functions = Map<String, dynamic>.from(apiResult['functions'] ?? {});
    final assets = Map<String, dynamic>.from(apiResult['assets'] ?? {});

    // Handle validation errors
    if (!success && errors.isNotEmpty) {
      return ZipProcessingResult(
        success: false,
        state: state.copyWith(
          zipUploadInProgress: false,
          errorMessage: 'Validation errors:\n${errors.join('\n')}',
          warningMessage: warnings.isNotEmpty ? warnings.join('\n') : null,
        ),
      );
    }

    // Extract content from files
    final extracted = extractContent(files, functions, assets);

    // Build validation maps from backend validation status
    final validation = buildValidationMaps(files, functions);

    // Create new state with extracted content and validation status
    final newState = state.copyWith(
      zipUploadInProgress: false,
      deployerDigitalTwinName: extracted.digitalTwinName,
      configEventsJson: extracted.configEvents,
      configIotDevicesJson: extracted.configIotDevices,
      payloadsJson: extracted.payloads,
      hierarchyContent: extracted.hierarchy,
      sceneConfigContent: extracted.sceneConfig,
      userConfigContent: extracted.userConfig,
      stateMachineContent: extracted.stateMachine,
      processorContents: extracted.processors.isNotEmpty
          ? extracted.processors
          : state.processorContents,
      eventActionContents: extracted.eventActions.isNotEmpty
          ? extracted.eventActions
          : state.eventActionContents,
      eventFeedbackContent: extracted.eventFeedback,
      sceneGlbUploaded: extracted.glbUploaded,
      hasUnsavedChanges: true,
      successMessage:
          'Zip extracted! ${countExtracted(files, functions, assets)} items populated.',
      warningMessage: warnings.isNotEmpty ? warnings.join('\n') : null,
      // Set validation based on backend validation status
      configJsonValidated: validation.configJsonValid,
      configEventsValidated: validation.eventsValid,
      configIotDevicesValidated: validation.iotDevicesValid,
      payloadsValidated: validation.payloadsValid,
      hierarchyValidated: validation.hierarchyValid,
      sceneConfigValidated: validation.sceneConfigValid,
      userConfigValidated: validation.userConfigValid,
      stateMachineValidated: validation.stateMachineValid,
      processorValidated: validation.processorValidation.isNotEmpty
          ? validation.processorValidation
          : state.processorValidated,
      eventActionValidated: validation.eventActionValidation.isNotEmpty
          ? validation.eventActionValidation
          : state.eventActionValidated,
      eventFeedbackValidated: validation.eventFeedbackValid,
    );

    // Check if all sections are valid for auto-collapse
    final allSectionsValid =
        newState.isSection2Valid && newState.isSection3Valid;

    // Log validation state (only in debug mode)
    if (kDebugMode) {
      _logValidationState(newState, allSectionsValid);
    }

    return ZipProcessingResult.ok(
      newState,
      shouldTriggerCollapse: allSectionsValid,
    );
  }

  /// Check if a file result has extractable content.
  /// Public for testing.
  bool fileHasContent(dynamic file) {
    if (file == null) return false;
    if (file is! Map<String, dynamic>) return false;
    return file['exists'] == true && file['content'] != null;
  }

  /// Check if a file is valid (exists, has content, no validation error).
  /// Public for testing.
  bool isFileValid(dynamic file) {
    if (file == null) return false;
    if (file is! Map<String, dynamic>) return false;
    return file['exists'] == true &&
        file['content'] != null &&
        file['validation_error'] == null;
  }

  /// Extract all content from zip result.
  /// Public for testing.
  ExtractedContent extractContent(
    Map<String, dynamic> files,
    Map<String, dynamic> functions,
    Map<String, dynamic> assets,
  ) {
    String? digitalTwinName;
    String? configEvents;
    String? configIotDevices;
    String? payloads;
    String? hierarchy;
    String? sceneConfig;
    String? userConfig;
    String? stateMachine;
    String? eventFeedback;
    Map<String, String> processors = {};
    Map<String, String> eventActions = {};
    bool glbUploaded = false;

    // Extract digital_twin_name from config.json
    if (fileHasContent(files['config.json'])) {
      try {
        final configJson = jsonDecode(
          files['config.json']['content'] as String,
        );
        if (configJson is Map<String, dynamic>) {
          digitalTwinName = configJson['digital_twin_name'] as String?;
        }
      } catch (e) {
        // Ignore parse errors - validation will catch them
      }
    }

    // Config files
    if (fileHasContent(files['config_events.json'])) {
      configEvents = files['config_events.json']['content'];
    }
    if (fileHasContent(files['config_iot_devices.json'])) {
      configIotDevices = files['config_iot_devices.json']['content'];
    }
    if (fileHasContent(files['iot_device_simulator/payloads.json'])) {
      payloads = files['iot_device_simulator/payloads.json']['content'];
    }

    // Hierarchy (check both AWS and Azure format)
    if (fileHasContent(files['twin_hierarchy/aws_hierarchy.json'])) {
      hierarchy = files['twin_hierarchy/aws_hierarchy.json']['content'];
    } else if (fileHasContent(files['twin_hierarchy/azure_hierarchy.json'])) {
      hierarchy = files['twin_hierarchy/azure_hierarchy.json']['content'];
    }

    // Scene config (provider-specific subdirectories)
    if (fileHasContent(files['scene_assets/aws/scene.json'])) {
      sceneConfig = files['scene_assets/aws/scene.json']['content'];
    } else if (fileHasContent(
      files['scene_assets/azure/3DScenesConfiguration.json'],
    )) {
      sceneConfig =
          files['scene_assets/azure/3DScenesConfiguration.json']['content'];
    }

    // User config
    if (fileHasContent(files['config_user.json'])) {
      userConfig = files['config_user.json']['content'];
    }

    // Processors
    final processorMap = functions['processors'] as Map<String, dynamic>? ?? {};
    for (final entry in processorMap.entries) {
      if (fileHasContent(entry.value)) {
        processors[entry.key] = entry.value['content'];
      }
    }

    // Event actions
    final actionMap = functions['event_actions'] as Map<String, dynamic>? ?? {};
    for (final entry in actionMap.entries) {
      if (fileHasContent(entry.value)) {
        eventActions[entry.key] = entry.value['content'];
      }
    }

    // Event feedback
    if (fileHasContent(functions['event_feedback'])) {
      eventFeedback = functions['event_feedback']['content'];
    }

    // State machine (check all provider formats)
    if (fileHasContent(files['state_machines/aws_step_function.json'])) {
      stateMachine = files['state_machines/aws_step_function.json']['content'];
    } else if (fileHasContent(files['state_machines/azure_logic_app.json'])) {
      stateMachine = files['state_machines/azure_logic_app.json']['content'];
    } else if (fileHasContent(
      files['state_machines/google_cloud_workflow.yaml'],
    )) {
      stateMachine =
          files['state_machines/google_cloud_workflow.yaml']['content'];
    }

    // GLB (already saved by Management API)
    if (assets['scene_glb'] != null) {
      final glbData = assets['scene_glb'] as Map<String, dynamic>;
      glbUploaded = glbData['exists'] == true && glbData['saved'] == true;
    }

    return ExtractedContent(
      digitalTwinName: digitalTwinName,
      configEvents: configEvents,
      configIotDevices: configIotDevices,
      payloads: payloads,
      hierarchy: hierarchy,
      sceneConfig: sceneConfig,
      userConfig: userConfig,
      stateMachine: stateMachine,
      eventFeedback: eventFeedback,
      processors: processors,
      eventActions: eventActions,
      glbUploaded: glbUploaded,
    );
  }

  /// Build validation maps from file results.
  /// Public for testing.
  ZipValidationResult buildValidationMaps(
    Map<String, dynamic> files,
    Map<String, dynamic> functions,
  ) {
    final processorMap = functions['processors'] as Map<String, dynamic>? ?? {};
    final actionMap = functions['event_actions'] as Map<String, dynamic>? ?? {};

    // Build processor validation map
    Map<String, bool> processorValidation = {};
    for (final entry in processorMap.entries) {
      processorValidation[entry.key] = isFileValid(entry.value);
    }

    // Build event action validation map
    Map<String, bool> eventActionValidation = {};
    for (final entry in actionMap.entries) {
      eventActionValidation[entry.key] = isFileValid(entry.value);
    }

    return ZipValidationResult(
      configJsonValid: isFileValid(files['config.json']),
      eventsValid: isFileValid(files['config_events.json']),
      iotDevicesValid: isFileValid(files['config_iot_devices.json']),
      payloadsValid: isFileValid(files['iot_device_simulator/payloads.json']),
      hierarchyValid:
          isFileValid(files['twin_hierarchy/aws_hierarchy.json']) ||
          isFileValid(files['twin_hierarchy/azure_hierarchy.json']),
      sceneConfigValid:
          isFileValid(files['scene_assets/aws/scene.json']) ||
          isFileValid(files['scene_assets/azure/3DScenesConfiguration.json']),
      userConfigValid: isFileValid(files['config_user.json']),
      stateMachineValid:
          isFileValid(files['state_machines/aws_step_function.json']) ||
          isFileValid(files['state_machines/azure_logic_app.json']) ||
          isFileValid(files['state_machines/google_cloud_workflow.yaml']),
      eventFeedbackValid: isFileValid(functions['event_feedback']),
      processorValidation: processorValidation,
      eventActionValidation: eventActionValidation,
    );
  }

  /// Count how many items were extracted for success message.
  /// Public for testing.
  int countExtracted(
    Map<String, dynamic> files,
    Map<String, dynamic> functions,
    Map<String, dynamic> assets,
  ) {
    int count = 0;
    files.forEach((k, v) {
      if (fileHasContent(v)) count++;
    });
    (functions['processors'] as Map<String, dynamic>?)?.forEach((k, v) {
      if (fileHasContent(v)) count++;
    });
    (functions['event_actions'] as Map<String, dynamic>?)?.forEach((k, v) {
      if (fileHasContent(v)) count++;
    });
    if (fileHasContent(functions['event_feedback'])) count++;
    if (assets['scene_glb']?['saved'] == true) count++;
    return count;
  }

  /// Log validation state for debugging (only called in debug mode)
  void _logValidationState(WizardState state, bool allSectionsValid) {
    debugPrint('=== ZIP UPLOAD VALIDATION DEBUG ===');
    debugPrint('Section 2 Valid: ${state.isSection2Valid}');
    debugPrint('  - configJsonValidated: ${state.configJsonValidated}');
    debugPrint('  - configEventsValidated: ${state.configEventsValidated}');
    debugPrint(
      '  - configIotDevicesValidated: ${state.configIotDevicesValidated}',
    );
    debugPrint('  - hierarchyValidated: ${state.hierarchyValidated}');
    debugPrint('  - L4 provider: ${state.layer4Provider}');
    debugPrint('Section 3 Valid: ${state.isSection3Valid}');
    debugPrint('  - payloadsValidated: ${state.payloadsValidated}');
    debugPrint('  - processorValidated: ${state.processorValidated}');
    debugPrint('  - deviceIds: ${state.deviceIds}');
    debugPrint(
      '  - calcParams.returnFeedbackToDevice: ${state.calcParams?.returnFeedbackToDevice}',
    );
    debugPrint('  - eventFeedbackValidated: ${state.eventFeedbackValidated}');
    debugPrint(
      '  - calcParams.useEventChecking: ${state.calcParams?.useEventChecking}',
    );
    debugPrint('  - eventActionValidated: ${state.eventActionValidated}');
    debugPrint(
      '  - calcParams.triggerNotificationWorkflow: ${state.calcParams?.triggerNotificationWorkflow}',
    );
    debugPrint('  - stateMachineValidated: ${state.stateMachineValidated}');
    debugPrint(
      '  - calcParams.needs3DModel: ${state.calcParams?.needs3DModel}',
    );
    debugPrint('  - sceneConfigValidated: ${state.sceneConfigValidated}');
    debugPrint('  - L5 provider: ${state.layer5Provider}');
    debugPrint('  - userConfigValidated: ${state.userConfigValidated}');
    debugPrint('All sections valid: $allSectionsValid');
    debugPrint('===================================');
  }
}
