import 'package:equatable/equatable.dart';

import '../../models/pricing_review_state.dart';
import '../../models/twin.dart';

class PricingReviewState extends Equatable {
  final String? selectedTwinId;
  final List<Twin> twins;
  final bool isLoadingTwins;
  final String? twinsError;
  final PricingReviewStateResponse? reviewState;
  final bool isLoadingReviewState;
  final String? reviewStateError;
  final String? refreshingProvider;
  final PricingReviewFeedback? feedback;

  const PricingReviewState({
    this.selectedTwinId,
    this.twins = const [],
    this.isLoadingTwins = false,
    this.twinsError,
    this.reviewState,
    this.isLoadingReviewState = false,
    this.reviewStateError,
    this.refreshingProvider,
    this.feedback,
  });

  bool get canRefreshProvider =>
      selectedTwinId != null && refreshingProvider == null;

  bool get hasTwins => twins.isNotEmpty;

  PricingReviewState copyWith({
    String? selectedTwinId,
    bool clearSelectedTwinId = false,
    List<Twin>? twins,
    bool? isLoadingTwins,
    String? twinsError,
    bool clearTwinsError = false,
    PricingReviewStateResponse? reviewState,
    bool clearReviewState = false,
    bool? isLoadingReviewState,
    String? reviewStateError,
    bool clearReviewStateError = false,
    String? refreshingProvider,
    bool clearRefreshingProvider = false,
    PricingReviewFeedback? feedback,
    bool clearFeedback = false,
  }) {
    return PricingReviewState(
      selectedTwinId: clearSelectedTwinId
          ? null
          : selectedTwinId ?? this.selectedTwinId,
      twins: twins ?? this.twins,
      isLoadingTwins: isLoadingTwins ?? this.isLoadingTwins,
      twinsError: clearTwinsError ? null : twinsError ?? this.twinsError,
      reviewState: clearReviewState ? null : reviewState ?? this.reviewState,
      isLoadingReviewState: isLoadingReviewState ?? this.isLoadingReviewState,
      reviewStateError: clearReviewStateError
          ? null
          : reviewStateError ?? this.reviewStateError,
      refreshingProvider: clearRefreshingProvider
          ? null
          : refreshingProvider ?? this.refreshingProvider,
      feedback: clearFeedback ? null : feedback ?? this.feedback,
    );
  }

  @override
  List<Object?> get props => [
    selectedTwinId,
    twins,
    isLoadingTwins,
    twinsError,
    reviewState,
    isLoadingReviewState,
    reviewStateError,
    refreshingProvider,
    feedback,
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
