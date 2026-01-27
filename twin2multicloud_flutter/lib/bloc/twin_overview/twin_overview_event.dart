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

/// SSE log event received
class TwinOverviewLogReceived extends TwinOverviewEvent {
  final String log;
  final String? timestamp;

  const TwinOverviewLogReceived(this.log, {this.timestamp});

  @override
  List<Object?> get props => [log, timestamp];
}

/// SSE deployment complete
class TwinOverviewDeploymentComplete extends TwinOverviewEvent {
  final bool success;
  final String? newState;
  final String? message;
  final Map<String, dynamic>? outputs; // Terraform outputs

  const TwinOverviewDeploymentComplete({
    required this.success,
    this.newState,
    this.message,
    this.outputs,
  });

  @override
  List<Object?> get props => [success, newState, message, outputs];
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
