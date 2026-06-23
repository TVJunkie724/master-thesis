import 'package:equatable/equatable.dart';

sealed class PricingReviewEvent extends Equatable {
  const PricingReviewEvent();

  @override
  List<Object?> get props => [];
}

class PricingReviewTwinSelected extends PricingReviewEvent {
  final String? twinId;

  const PricingReviewTwinSelected(this.twinId);

  @override
  List<Object?> get props => [twinId];
}

class PricingReviewStarted extends PricingReviewEvent {
  const PricingReviewStarted();
}

class PricingReviewReloadRequested extends PricingReviewEvent {
  const PricingReviewReloadRequested();
}

class PricingReviewProviderRefreshRequested extends PricingReviewEvent {
  final String provider;

  const PricingReviewProviderRefreshRequested(this.provider);

  @override
  List<Object?> get props => [provider];
}

class PricingReviewFeedbackCleared extends PricingReviewEvent {
  const PricingReviewFeedbackCleared();
}
