import 'package:equatable/equatable.dart';

class PricingReviewState extends Equatable {
  final String? selectedTwinId;
  final String? refreshingProvider;
  final PricingReviewFeedback? feedback;
  final int refreshRevision;
  final String? lastRefreshedTwinId;

  const PricingReviewState({
    this.selectedTwinId,
    this.refreshingProvider,
    this.feedback,
    this.refreshRevision = 0,
    this.lastRefreshedTwinId,
  });

  bool get canRefreshProvider =>
      selectedTwinId != null && refreshingProvider == null;

  PricingReviewState copyWith({
    String? selectedTwinId,
    bool clearSelectedTwinId = false,
    String? refreshingProvider,
    bool clearRefreshingProvider = false,
    PricingReviewFeedback? feedback,
    bool clearFeedback = false,
    int? refreshRevision,
    String? lastRefreshedTwinId,
    bool clearLastRefreshedTwinId = false,
  }) {
    return PricingReviewState(
      selectedTwinId: clearSelectedTwinId
          ? null
          : selectedTwinId ?? this.selectedTwinId,
      refreshingProvider: clearRefreshingProvider
          ? null
          : refreshingProvider ?? this.refreshingProvider,
      feedback: clearFeedback ? null : feedback ?? this.feedback,
      refreshRevision: refreshRevision ?? this.refreshRevision,
      lastRefreshedTwinId: clearLastRefreshedTwinId
          ? null
          : lastRefreshedTwinId ?? this.lastRefreshedTwinId,
    );
  }

  @override
  List<Object?> get props => [
    selectedTwinId,
    refreshingProvider,
    feedback,
    refreshRevision,
    lastRefreshedTwinId,
  ];
}

class PricingReviewFeedback extends Equatable {
  final String message;
  final bool isError;

  const PricingReviewFeedback._(this.message, {required this.isError});

  factory PricingReviewFeedback.success(String message) {
    return PricingReviewFeedback._(message, isError: false);
  }

  factory PricingReviewFeedback.error(String message) {
    return PricingReviewFeedback._(message, isError: true);
  }

  @override
  List<Object?> get props => [message, isError];
}
