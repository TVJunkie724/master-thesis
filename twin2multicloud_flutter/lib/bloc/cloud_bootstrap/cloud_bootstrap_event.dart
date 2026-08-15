import 'package:equatable/equatable.dart';

import '../../models/cloud_bootstrap.dart';

sealed class CloudBootstrapEvent extends Equatable {
  const CloudBootstrapEvent();
}

final class CloudBootstrapOpened extends CloudBootstrapEvent {
  final CloudBootstrapTarget? initialTarget;

  const CloudBootstrapOpened({this.initialTarget});

  @override
  List<Object?> get props => [initialTarget];
}

final class CloudBootstrapGuideRequested extends CloudBootstrapEvent {
  final CloudBootstrapTarget target;

  const CloudBootstrapGuideRequested(this.target);

  @override
  List<Object?> get props => [target];
}

final class CloudBootstrapSessionStarted extends CloudBootstrapEvent {
  final String displayName;

  const CloudBootstrapSessionStarted(this.displayName);

  @override
  List<Object?> get props => [displayName];
}

final class CloudBootstrapExecuteSubmitted extends CloudBootstrapEvent {
  final CloudBootstrapExecuteRequest request;

  const CloudBootstrapExecuteSubmitted(this.request);

  @override
  List<Object?> get props => [request];
}

final class CloudBootstrapSessionRechecked extends CloudBootstrapEvent {
  const CloudBootstrapSessionRechecked();

  @override
  List<Object?> get props => const [];
}

final class CloudBootstrapCredentialReentryRequested
    extends CloudBootstrapEvent {
  const CloudBootstrapCredentialReentryRequested();

  @override
  List<Object?> get props => const [];
}

final class CloudBootstrapManualRevocationAcknowledged
    extends CloudBootstrapEvent {
  const CloudBootstrapManualRevocationAcknowledged();

  @override
  List<Object?> get props => const [];
}

final class CloudBootstrapCancelled extends CloudBootstrapEvent {
  const CloudBootstrapCancelled();

  @override
  List<Object?> get props => const [];
}

final class CloudBootstrapStartNewRequested extends CloudBootstrapEvent {
  const CloudBootstrapStartNewRequested();

  @override
  List<Object?> get props => const [];
}

final class CloudBootstrapClosed extends CloudBootstrapEvent {
  const CloudBootstrapClosed();

  @override
  List<Object?> get props => const [];
}
