import 'package:equatable/equatable.dart';

import '../../services/sse_service.dart';

abstract class DeploymentVerificationEvent extends Equatable {
  const DeploymentVerificationEvent();

  @override
  List<Object?> get props => [];
}

class DeploymentVerificationInfrastructureRequested
    extends DeploymentVerificationEvent {
  const DeploymentVerificationInfrastructureRequested();
}

class DeploymentVerificationDataFlowRequested
    extends DeploymentVerificationEvent {
  final String payloadText;

  const DeploymentVerificationDataFlowRequested(this.payloadText);

  @override
  List<Object?> get props => [payloadText];
}

class DeploymentVerificationSseReceived extends DeploymentVerificationEvent {
  final SseLogEvent event;

  const DeploymentVerificationSseReceived(this.event);

  @override
  List<Object?> get props => [event];
}

class DeploymentVerificationSseFailed extends DeploymentVerificationEvent {
  final Object error;

  const DeploymentVerificationSseFailed(this.error);

  @override
  List<Object?> get props => [error];
}
