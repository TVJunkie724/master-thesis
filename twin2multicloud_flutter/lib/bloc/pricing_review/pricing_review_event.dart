import 'package:equatable/equatable.dart';

sealed class PricingReviewEvent extends Equatable {
  const PricingReviewEvent();

  @override
  List<Object?> get props => [];
}

class PricingReviewStarted extends PricingReviewEvent {
  const PricingReviewStarted();
}

class PricingReviewReloadRequested extends PricingReviewEvent {
  const PricingReviewReloadRequested();
}

class PricingReviewProviderSelected extends PricingReviewEvent {
  final String provider;

  const PricingReviewProviderSelected(this.provider);

  @override
  List<Object?> get props => [provider];
}

class PricingReviewProviderRefreshRequested extends PricingReviewEvent {
  final String provider;
  final String? connectionId;

  const PricingReviewProviderRefreshRequested(
    this.provider, {
    this.connectionId,
  });

  @override
  List<Object?> get props => [provider, connectionId];
}

class PricingReviewReportsReloadRequested extends PricingReviewEvent {
  final String provider;

  const PricingReviewReportsReloadRequested(this.provider);

  @override
  List<Object?> get props => [provider];
}

class PricingReviewCandidateSelected extends PricingReviewEvent {
  final String reportId;
  final String candidateId;

  const PricingReviewCandidateSelected(this.reportId, this.candidateId);

  @override
  List<Object?> get props => [reportId, candidateId];
}

class PricingReviewReportExpanded extends PricingReviewEvent {
  final String reportId;

  const PricingReviewReportExpanded(this.reportId);

  @override
  List<Object?> get props => [reportId];
}

class PricingReviewDecisionRequested extends PricingReviewEvent {
  final String reportId;
  final String decision;
  final String? rationale;

  const PricingReviewDecisionRequested({
    required this.reportId,
    required this.decision,
    this.rationale,
  });

  @override
  List<Object?> get props => [reportId, decision, rationale];
}

class PricingReviewFeedbackCleared extends PricingReviewEvent {
  const PricingReviewFeedbackCleared();
}
