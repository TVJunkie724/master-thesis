import 'package:equatable/equatable.dart';

import '../../models/cloud_connection.dart';

sealed class CloudAccessEvent extends Equatable {
  const CloudAccessEvent();

  @override
  List<Object?> get props => [];
}

class CloudAccessStarted extends CloudAccessEvent {
  const CloudAccessStarted();
}

class CloudAccessReloadRequested extends CloudAccessEvent {
  const CloudAccessReloadRequested();
}

class CloudAccessCreateRequested extends CloudAccessEvent {
  final CloudConnectionCreateRequest request;

  const CloudAccessCreateRequested(this.request);

  @override
  List<Object?> get props => [request];
}

class CloudAccessValidateRequested extends CloudAccessEvent {
  final String connectionId;

  const CloudAccessValidateRequested(this.connectionId);

  @override
  List<Object?> get props => [connectionId];
}

class CloudAccessDefaultRequested extends CloudAccessEvent {
  final String connectionId;

  const CloudAccessDefaultRequested(this.connectionId);

  @override
  List<Object?> get props => [connectionId];
}

class CloudAccessDeleteRequested extends CloudAccessEvent {
  final String connectionId;

  const CloudAccessDeleteRequested(this.connectionId);

  @override
  List<Object?> get props => [connectionId];
}

class CloudAccessFeedbackCleared extends CloudAccessEvent {
  const CloudAccessFeedbackCleared();
}
