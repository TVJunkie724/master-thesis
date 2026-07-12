import 'package:equatable/equatable.dart';

import '../../models/cloud_access_inventory.dart';

class CloudAccessState extends Equatable {
  final CloudAccessInventory? inventory;
  final bool isLoading;
  final String? loadError;
  final Set<String> busyConnectionIds;
  final bool isCreating;
  final CloudAccessFeedback? feedback;

  const CloudAccessState({
    this.inventory,
    this.isLoading = false,
    this.loadError,
    this.busyConnectionIds = const {},
    this.isCreating = false,
    this.feedback,
  });

  CloudAccessState copyWith({
    CloudAccessInventory? inventory,
    bool? isLoading,
    String? loadError,
    bool clearLoadError = false,
    Set<String>? busyConnectionIds,
    bool? isCreating,
    CloudAccessFeedback? feedback,
    bool clearFeedback = false,
  }) {
    return CloudAccessState(
      inventory: inventory ?? this.inventory,
      isLoading: isLoading ?? this.isLoading,
      loadError: clearLoadError ? null : loadError ?? this.loadError,
      busyConnectionIds: busyConnectionIds ?? this.busyConnectionIds,
      isCreating: isCreating ?? this.isCreating,
      feedback: clearFeedback ? null : feedback ?? this.feedback,
    );
  }

  @override
  List<Object?> get props => [
    inventory,
    isLoading,
    loadError,
    busyConnectionIds,
    isCreating,
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
