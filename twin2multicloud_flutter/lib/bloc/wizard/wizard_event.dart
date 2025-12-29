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
