// lib/bloc/wizard/wizard_event.dart
// Events for the Wizard BLoC state machine

import 'package:equatable/equatable.dart';
import '../../models/calc_params.dart';

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

/// Section 3 data status changed (any field has content)
class WizardSection3DataChanged extends WizardEvent {
  final bool hasData;
  const WizardSection3DataChanged(this.hasData);
  @override
  List<Object?> get props => [hasData];
}

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
