// lib/bloc/wizard/wizard_event.dart
// Events for the Wizard BLoC state machine

import 'dart:typed_data';
import 'package:equatable/equatable.dart';
import '../../models/calc_params.dart';
import '../../models/cloud_connection.dart';

/// Base class for all wizard events
abstract class WizardEvent extends Equatable {
  const WizardEvent();
  @override
  List<Object?> get props => [];
}

// ============================================================
// INITIALIZATION EVENTS
// ============================================================

/// Initialize wizard for creating a new twin
class WizardInitCreate extends WizardEvent {
  const WizardInitCreate();
}

/// Initialize wizard for editing an existing twin
class WizardInitEdit extends WizardEvent {
  final String twinId;
  const WizardInitEdit(this.twinId);
  @override
  List<Object?> get props => [twinId];
}

// ============================================================
// NAVIGATION EVENTS
// ============================================================

/// Move to the next step (validates current step first)
class WizardNextStep extends WizardEvent {
  const WizardNextStep();
}

/// Move to the previous step
class WizardPreviousStep extends WizardEvent {
  const WizardPreviousStep();
}

/// Jump to a specific step (only allowed for reached steps)
class WizardGoToStep extends WizardEvent {
  final int step;
  const WizardGoToStep(this.step);
  @override
  List<Object?> get props => [step];
}

// ============================================================
// STEP 1: CONFIGURATION EVENTS
// ============================================================

/// Twin name was changed
class WizardTwinNameChanged extends WizardEvent {
  final String name;
  const WizardTwinNameChanged(this.name);
  @override
  List<Object?> get props => [name];
}

/// Debug mode toggle changed
class WizardDebugModeChanged extends WizardEvent {
  final bool debugMode;
  const WizardDebugModeChanged(this.debugMode);
  @override
  List<Object?> get props => [debugMode];
}

/// Credentials were updated for a provider
class WizardCredentialsChanged extends WizardEvent {
  final String provider; // 'aws', 'azure', 'gcp'
  final Map<String, String> credentials;
  const WizardCredentialsChanged(this.provider, this.credentials);
  @override
  List<Object?> get props => [provider, credentials];
}

/// Credentials were validated for a provider
class WizardCredentialsValidated extends WizardEvent {
  final String provider;
  final bool isValid;
  const WizardCredentialsValidated(this.provider, this.isValid);
  @override
  List<Object?> get props => [provider, isValid];
}

/// Credentials were cleared for a provider (triggers deletion on save)
class WizardCredentialsCleared extends WizardEvent {
  final String provider; // 'aws', 'azure', 'gcp'
  const WizardCredentialsCleared(this.provider);
  @override
  List<Object?> get props => [provider];
}

/// Load reusable Cloud Connections for all providers
class WizardCloudConnectionsLoadRequested extends WizardEvent {
  const WizardCloudConnectionsLoadRequested();
}

/// A provider was bound to an existing Cloud Connection
class WizardCloudConnectionSelected extends WizardEvent {
  final CloudProvider provider;
  final String? connectionId;

  const WizardCloudConnectionSelected(this.provider, this.connectionId);

  @override
  List<Object?> get props => [provider, connectionId];
}

/// User submitted a new Cloud Connection for creation
class WizardCloudConnectionCreateRequested extends WizardEvent {
  final CloudProvider provider;
  final CloudConnectionCreateRequest request;

  const WizardCloudConnectionCreateRequested(this.provider, this.request);

  @override
  List<Object?> get props => [provider, request];
}

/// Validate a selected stored Cloud Connection
class WizardCloudConnectionValidateRequested extends WizardEvent {
  final CloudProvider provider;
  final String connectionId;

  const WizardCloudConnectionValidateRequested(
    this.provider,
    this.connectionId,
  );

  @override
  List<Object?> get props => [provider, connectionId];
}

/// Unbind a provider from the current twin
class WizardCloudConnectionUnbound extends WizardEvent {
  final CloudProvider provider;

  const WizardCloudConnectionUnbound(this.provider);

  @override
  List<Object?> get props => [provider];
}

/// Delete a reusable Cloud Connection
class WizardCloudConnectionDeleteRequested extends WizardEvent {
  final CloudProvider provider;
  final String connectionId;

  const WizardCloudConnectionDeleteRequested(this.provider, this.connectionId);

  @override
  List<Object?> get props => [provider, connectionId];
}

// ============================================================
// STEP 2: OPTIMIZER EVENTS
// ============================================================

/// Calculation parameters were changed
class WizardCalcParamsChanged extends WizardEvent {
  final CalcParams params;
  const WizardCalcParamsChanged(this.params);
  @override
  List<Object?> get props => [params];
}

/// Calculation form validity changed
class WizardCalcFormValidChanged extends WizardEvent {
  final bool isValid;
  const WizardCalcFormValidChanged(this.isValid);
  @override
  List<Object?> get props => [isValid];
}

/// User requested calculation
class WizardCalculateRequested extends WizardEvent {
  const WizardCalculateRequested();
}

// ============================================================
// PERSISTENCE EVENTS
// ============================================================

/// Save current state as draft
class WizardSaveDraft extends WizardEvent {
  const WizardSaveDraft();
}

/// Finish wizard and save final state
class WizardFinish extends WizardEvent {
  const WizardFinish();
}

// ============================================================
// UI FEEDBACK EVENTS
// ============================================================

/// Clear all transient notifications (error, success, warning)
class WizardClearNotifications extends WizardEvent {
  const WizardClearNotifications();
}

/// Dismiss the current error message
class WizardDismissError extends WizardEvent {
  const WizardDismissError();
}

// ============================================================
// STEP 3 INVALIDATION EVENTS
// ============================================================

/// User confirmed to proceed with new calculation results (clears Section 3)
class WizardProceedWithNewResults extends WizardEvent {
  const WizardProceedWithNewResults();
}

/// User chose to restore old calculation results (discard unsaved calc)
class WizardRestoreOldResults extends WizardEvent {
  const WizardRestoreOldResults();
}

/// Combined: Proceed with new results AND save draft (atomic operation)
class WizardProceedAndSave extends WizardEvent {
  const WizardProceedAndSave();
}

/// Combined: Proceed with new results AND go to next step (atomic operation)
class WizardProceedAndNext extends WizardEvent {
  const WizardProceedAndNext();
}

/// Clear step3 invalidation flag (user chose to proceed)
class WizardClearInvalidation extends WizardEvent {
  const WizardClearInvalidation();
}

// ============================================================
// STEP 3 SECTION 2: CONFIG FILE EVENTS
// ============================================================

/// config_events.json content changed
class WizardConfigEventsChanged extends WizardEvent {
  final String content;
  const WizardConfigEventsChanged(this.content);
  @override
  List<Object?> get props => [content];
}

/// config.json digital_twin_name changed (separate from Step 1 project name)
class WizardDeployerTwinNameChanged extends WizardEvent {
  final String name;
  const WizardDeployerTwinNameChanged(this.name);
  @override
  List<Object?> get props => [name];
}

/// config_iot_devices.json content changed
class WizardConfigIotDevicesChanged extends WizardEvent {
  final String content;
  const WizardConfigIotDevicesChanged(this.content);
  @override
  List<Object?> get props => [content];
}

/// payloads.json content changed (L1)
class WizardPayloadsChanged extends WizardEvent {
  final String content;
  const WizardPayloadsChanged(this.content);
  @override
  List<Object?> get props => [content];
}

/// Request validation of a deployer config file
class WizardValidateDeployerConfig extends WizardEvent {
  final String configType; // 'events' or 'iot'
  const WizardValidateDeployerConfig(this.configType);
  @override
  List<Object?> get props => [configType];
}

/// Validation completed (called from widget after direct API call)
class WizardConfigValidationCompleted extends WizardEvent {
  final String configType; // 'events' or 'iot'
  final bool valid;
  const WizardConfigValidationCompleted(this.configType, this.valid);
  @override
  List<Object?> get props => [configType, valid];
}

// ============================================================
// STEP 3 SECTION 3: L2 USER FUNCTION EVENTS
// ============================================================

/// Processor content changed for a specific device
class WizardProcessorContentChanged extends WizardEvent {
  final String deviceId;
  final String content;
  const WizardProcessorContentChanged(this.deviceId, this.content);
  @override
  List<Object?> get props => [deviceId, content];
}

/// Event feedback function content changed
class WizardEventFeedbackContentChanged extends WizardEvent {
  final String content;
  const WizardEventFeedbackContentChanged(this.content);
  @override
  List<Object?> get props => [content];
}

/// Event action function content changed
class WizardEventActionContentChanged extends WizardEvent {
  final String functionName;
  final String content;
  const WizardEventActionContentChanged(this.functionName, this.content);
  @override
  List<Object?> get props => [functionName, content];
}

/// State machine content changed
class WizardStateMachineContentChanged extends WizardEvent {
  final String content;
  const WizardStateMachineContentChanged(this.content);
  @override
  List<Object?> get props => [content];
}

// ============================================================
// STEP 3 SECTION 3: L2 REQUIREMENTS.TXT EVENTS
// ============================================================

/// Processor requirements.txt changed for a specific device
/// Pass null to remove requirements (will be deleted on save)
class WizardProcessorRequirementsChanged extends WizardEvent {
  final String deviceId;
  final String? content; // null = remove
  const WizardProcessorRequirementsChanged(this.deviceId, this.content);
  @override
  List<Object?> get props => [deviceId, content];
}

/// Event feedback requirements.txt changed
class WizardEventFeedbackRequirementsChanged extends WizardEvent {
  final String? content; // null = remove
  const WizardEventFeedbackRequirementsChanged(this.content);
  @override
  List<Object?> get props => [content];
}

/// Event action requirements.txt changed
class WizardEventActionRequirementsChanged extends WizardEvent {
  final String functionName;
  final String? content; // null = remove
  const WizardEventActionRequirementsChanged(this.functionName, this.content);
  @override
  List<Object?> get props => [functionName, content];
}

// ============================================================
// STEP 3 SECTION 3: L2 VALIDATION COMPLETED EVENTS
// ============================================================

/// Processor validation completed
class WizardProcessorValidationCompleted extends WizardEvent {
  final String deviceId;
  final bool valid;
  const WizardProcessorValidationCompleted(this.deviceId, this.valid);
  @override
  List<Object?> get props => [deviceId, valid];
}

/// Event feedback validation completed
class WizardEventFeedbackValidationCompleted extends WizardEvent {
  final bool valid;
  const WizardEventFeedbackValidationCompleted(this.valid);
  @override
  List<Object?> get props => [valid];
}

/// Event action validation completed
class WizardEventActionValidationCompleted extends WizardEvent {
  final String functionName;
  final bool valid;
  const WizardEventActionValidationCompleted(this.functionName, this.valid);
  @override
  List<Object?> get props => [functionName, valid];
}

/// State machine validation completed
class WizardStateMachineValidationCompleted extends WizardEvent {
  final bool valid;
  const WizardStateMachineValidationCompleted(this.valid);
  @override
  List<Object?> get props => [valid];
}

// ============================================================
// STEP 3 SECTION 2: L4 HIERARCHY EVENTS
// ============================================================

/// Hierarchy JSON content changed
class WizardHierarchyContentChanged extends WizardEvent {
  final String content;
  const WizardHierarchyContentChanged(this.content);
  @override
  List<Object?> get props => [content];
}

/// Hierarchy validation completed
class WizardHierarchyValidationCompleted extends WizardEvent {
  final bool valid;
  const WizardHierarchyValidationCompleted(this.valid);
  @override
  List<Object?> get props => [valid];
}

// ============================================================
// STEP 3 SECTION 3: L4 SCENE EVENTS
// ============================================================

/// Scene config JSON content changed
class WizardSceneConfigContentChanged extends WizardEvent {
  final String content;
  const WizardSceneConfigContentChanged(this.content);
  @override
  List<Object?> get props => [content];
}

/// Scene config validation completed
class WizardSceneConfigValidationCompleted extends WizardEvent {
  final bool valid;
  const WizardSceneConfigValidationCompleted(this.valid);
  @override
  List<Object?> get props => [valid];
}

/// GLB file upload status changed
class WizardSceneGlbUploadStatusChanged extends WizardEvent {
  final bool uploaded;
  const WizardSceneGlbUploadStatusChanged(this.uploaded);
  @override
  List<Object?> get props => [uploaded];
}

// ============================================================
// STEP 3 SECTION 3: L4/L5 USER CONFIG EVENTS
// ============================================================

/// User config JSON content changed
class WizardUserConfigContentChanged extends WizardEvent {
  final String content;
  const WizardUserConfigContentChanged(this.content);
  @override
  List<Object?> get props => [content];
}

/// User config validation completed
class WizardUserConfigValidationCompleted extends WizardEvent {
  final bool valid;
  const WizardUserConfigValidationCompleted(this.valid);
  @override
  List<Object?> get props => [valid];
}

// ============================================================
// STEP 3: L4 CLEANUP EVENT
// ============================================================

/// Request cleanup of L4 assets when L4 provider changes
/// This triggers async GLB deletion on the server
class WizardL4CleanupRequested extends WizardEvent {
  const WizardL4CleanupRequested();
  @override
  List<Object?> get props => [];
}

// ============================================================
// STEP 3: ZIP UPLOAD EVENTS
// ============================================================

/// User requested zip upload for auto-population
/// Triggers confirmation dialog if Step 3 already has data
class WizardZipUploadRequested extends WizardEvent {
  final String filePath;
  final Uint8List fileBytes;
  final String fileName;
  const WizardZipUploadRequested({
    required this.filePath,
    required this.fileBytes,
    required this.fileName,
  });
  @override
  List<Object?> get props => [filePath, fileName];
}

/// User confirmed to replace existing Step 3 data with zip contents
class WizardZipUploadConfirmed extends WizardEvent {
  final String filePath;
  final Uint8List fileBytes;
  final String fileName;
  const WizardZipUploadConfirmed({
    required this.filePath,
    required this.fileBytes,
    required this.fileName,
  });
  @override
  List<Object?> get props => [filePath, fileName];
}

/// Zip upload and extraction completed successfully
class WizardZipUploadSuccess extends WizardEvent {
  final Map<String, dynamic> extractionResult;
  const WizardZipUploadSuccess(this.extractionResult);
  @override
  List<Object?> get props => [extractionResult];
}

/// Zip upload failed with validation errors
class WizardZipUploadFailure extends WizardEvent {
  final List<String> errors;
  final List<String> warnings;
  const WizardZipUploadFailure({
    required this.errors,
    this.warnings = const [],
  });
  @override
  List<Object?> get props => [errors, warnings];
}
