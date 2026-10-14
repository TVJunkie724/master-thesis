import 'package:equatable/equatable.dart';

import '../../models/cloud_connection.dart';

class CloudAccessState extends Equatable {
  final List<CloudConnection> connections;
  final bool isLoading;
  final String? loadError;
  final Set<String> busyConnectionIds;
  final bool isCreating;
  final bool isImporting;
  final CloudAccessFeedback? feedback;

  const CloudAccessState({
    this.connections = const [],
    this.isLoading = false,
    this.loadError,
    this.busyConnectionIds = const {},
    this.isCreating = false,
    this.isImporting = false,
    this.feedback,
  });

  CloudAccessState copyWith({
    List<CloudConnection>? connections,
    bool? isLoading,
    String? loadError,
    bool clearLoadError = false,
    Set<String>? busyConnectionIds,
    bool? isCreating,
    bool? isImporting,
    CloudAccessFeedback? feedback,
    bool clearFeedback = false,
  }) {
    return CloudAccessState(
      connections: connections ?? this.connections,
      isLoading: isLoading ?? this.isLoading,
      loadError: clearLoadError ? null : loadError ?? this.loadError,
      busyConnectionIds: busyConnectionIds ?? this.busyConnectionIds,
      isCreating: isCreating ?? this.isCreating,
      isImporting: isImporting ?? this.isImporting,
      feedback: clearFeedback ? null : feedback ?? this.feedback,
    );
  }

  @override
  List<Object?> get props => [
    connections,
    isLoading,
    loadError,
    busyConnectionIds,
    isCreating,
    isImporting,
    feedback,
  ];
}

class CloudAccessFeedback extends Equatable {
  final String message;
  final bool isError;

  const CloudAccessFeedback._(this.message, {required this.isError});

  factory CloudAccessFeedback.success(String message) {
    return CloudAccessFeedback._(message, isError: false);
  }

  factory CloudAccessFeedback.error(String message) {
    return CloudAccessFeedback._(message, isError: true);
  }

  @override
  List<Object?> get props => [message, isError];
}
