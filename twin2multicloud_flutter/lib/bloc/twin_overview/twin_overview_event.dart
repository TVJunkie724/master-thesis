// lib/bloc/twin_overview/twin_overview_event.dart
// Events for the twin overview BLoC

import 'package:equatable/equatable.dart';

abstract class TwinOverviewEvent extends Equatable {
  const TwinOverviewEvent();

  @override
  List<Object?> get props => [];
}

/// Load twin data for overview display
class TwinOverviewLoad extends TwinOverviewEvent {
  final String twinId;

  const TwinOverviewLoad(this.twinId);

  @override
  List<Object?> get props => [twinId];
}

/// Refresh twin data (e.g., after state change)
class TwinOverviewRefresh extends TwinOverviewEvent {
  const TwinOverviewRefresh();
}

/// Explicitly validate the currently required deployment provider access.
class TwinOverviewRunDeploymentPreflight extends TwinOverviewEvent {
  const TwinOverviewRunDeploymentPreflight();
}

/// Trigger deployment
class TwinOverviewDeploy extends TwinOverviewEvent {
  const TwinOverviewDeploy();
}

/// Trigger destroy
class TwinOverviewDestroy extends TwinOverviewEvent {
  const TwinOverviewDestroy();
}

/// Delete the twin
class TwinOverviewDelete extends TwinOverviewEvent {
  const TwinOverviewDelete();
}

/// SSE deployment complete
class TwinOverviewDeploymentComplete extends TwinOverviewEvent {
  final bool success;
  final String? newState;
  final String? message;
  final Map<String, dynamic>? outputs; // Terraform outputs
  final int? eventId;

  const TwinOverviewDeploymentComplete({
    required this.success,
    this.newState,
    this.message,
    this.outputs,
    this.eventId,
  });

  @override
  List<Object?> get props => [success, newState, message, outputs, eventId];
}

/// Clear success/error messages
class TwinOverviewClearMessages extends TwinOverviewEvent {
  const TwinOverviewClearMessages();
}

/// Message type for alert banners
enum MessageType { info, success, error }

/// Show a message in the alert banner
class TwinOverviewShowMessage extends TwinOverviewEvent {
  final String message;
  final MessageType type;

  const TwinOverviewShowMessage(this.message, this.type);

  @override
  List<Object?> get props => [message, type];
}

/// Close the deployment terminal panel
class TwinOverviewCloseTerminal extends TwinOverviewEvent {
  const TwinOverviewCloseTerminal();
}

/// Start a log trace test
class TwinOverviewStartLogTrace extends TwinOverviewEvent {
  const TwinOverviewStartLogTrace();
}

/// Log trace log received (from SSE stream)
class TwinOverviewLogTraceUpdate extends TwinOverviewEvent {
  final String logLine;
  final String? layer;
  final String? provider;
  final String? traceId;

  const TwinOverviewLogTraceUpdate(
    this.logLine, {
    this.layer,
    this.provider,
    this.traceId,
  });

  @override
  List<Object?> get props => [logLine, layer, provider, traceId];
}

/// Log trace completed
class TwinOverviewLogTraceComplete extends TwinOverviewEvent {
  final int? totalLogs;
  final String? traceId;

  const TwinOverviewLogTraceComplete({this.totalLogs, this.traceId});

  @override
  List<Object?> get props => [totalLogs, traceId];
}

/// Log trace error occurred
class TwinOverviewLogTraceError extends TwinOverviewEvent {
  final String message;
  final String? traceId;

  const TwinOverviewLogTraceError(this.message, {this.traceId});

  @override
  List<Object?> get props => [message, traceId];
}

/// Cancel the active log trace stream without affecting deployment logs.
class TwinOverviewCancelLogTrace extends TwinOverviewEvent {
  const TwinOverviewCancelLogTrace();
}

/// Download simulator package
class TwinOverviewDownloadSimulator extends TwinOverviewEvent {
  final bool acknowledgedSensitiveCredentials;

  const TwinOverviewDownloadSimulator({
    required this.acknowledgedSensitiveCredentials,
  });

  @override
  List<Object?> get props => [acknowledgedSensitiveCredentials];
}

class TwinOverviewSimulatorSaveStarted extends TwinOverviewEvent {
  const TwinOverviewSimulatorSaveStarted();
}

class TwinOverviewSimulatorSaveCompleted extends TwinOverviewEvent {
  final String message;

  const TwinOverviewSimulatorSaveCompleted(this.message);

  @override
  List<Object?> get props => [message];
}

class TwinOverviewSimulatorSaveCancelled extends TwinOverviewEvent {
  const TwinOverviewSimulatorSaveCancelled();
}

class TwinOverviewSimulatorSaveFailed extends TwinOverviewEvent {
  final String message;

  const TwinOverviewSimulatorSaveFailed(this.message);

  @override
  List<Object?> get props => [message];
}
