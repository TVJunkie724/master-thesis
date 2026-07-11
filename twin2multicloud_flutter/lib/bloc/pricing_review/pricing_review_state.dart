import 'package:equatable/equatable.dart';

import '../../models/cloud_access_inventory.dart';
import '../../models/pricing_candidate_review.dart';
import '../../models/pricing_health.dart';
import '../../models/pricing_refresh_run.dart';

class PricingReviewState extends Equatable {
  final String selectedProvider;
  final PricingHealthResponse? pricingHealth;
  final CloudAccessInventory? cloudAccess;
  final bool isLoadingPricingHealth;
  final bool isLoadingCloudAccess;
  final String? pricingHealthError;
  final String? cloudAccessError;
  final String? refreshingProvider;
  final Map<String, PricingRefreshRun> latestRuns;
  final Map<String, List<PricingCandidateReport>> reportsByProvider;
  final Map<String, String> reportErrorsByProvider;
  final Map<String, String> selectedCandidateIds;
  final Set<String> loadingTraceReportIds;
  final Map<String, PricingTrace> tracesByReportId;
  final Map<String, String> traceErrorsByReportId;
  final Set<String> savingDecisionReportIds;
  final Map<String, PricingReviewDecision> decisionsByReportId;
  final PricingReviewFeedback? feedback;

  const PricingReviewState({
    this.selectedProvider = 'aws',
    this.pricingHealth,
    this.cloudAccess,
    this.isLoadingPricingHealth = false,
    this.isLoadingCloudAccess = false,
    this.pricingHealthError,
    this.cloudAccessError,
    this.refreshingProvider,
    this.latestRuns = const {},
    this.reportsByProvider = const {},
    this.reportErrorsByProvider = const {},
    this.selectedCandidateIds = const {},
    this.loadingTraceReportIds = const {},
    this.tracesByReportId = const {},
    this.traceErrorsByReportId = const {},
    this.savingDecisionReportIds = const {},
    this.decisionsByReportId = const {},
    this.feedback,
  });

  CloudAccessEntry? accessFor(String provider) =>
      cloudAccess?.pricingFor(provider);

  bool canRefresh(String provider) {
    return refreshingProvider == null &&
        accessFor(provider)?.canRefreshPricing == true;
  }

  PricingReviewState copyWith({
    String? selectedProvider,
    PricingHealthResponse? pricingHealth,
    CloudAccessInventory? cloudAccess,
    bool? isLoadingPricingHealth,
    bool? isLoadingCloudAccess,
    String? pricingHealthError,
    bool clearPricingHealthError = false,
    String? cloudAccessError,
    bool clearCloudAccessError = false,
    String? refreshingProvider,
    bool clearRefreshingProvider = false,
    Map<String, PricingRefreshRun>? latestRuns,
    Map<String, List<PricingCandidateReport>>? reportsByProvider,
    Map<String, String>? reportErrorsByProvider,
    Map<String, String>? selectedCandidateIds,
    Set<String>? loadingTraceReportIds,
    Map<String, PricingTrace>? tracesByReportId,
    Map<String, String>? traceErrorsByReportId,
    Set<String>? savingDecisionReportIds,
    Map<String, PricingReviewDecision>? decisionsByReportId,
    PricingReviewFeedback? feedback,
    bool clearFeedback = false,
  }) {
    return PricingReviewState(
      selectedProvider: selectedProvider ?? this.selectedProvider,
      pricingHealth: pricingHealth ?? this.pricingHealth,
      cloudAccess: cloudAccess ?? this.cloudAccess,
      isLoadingPricingHealth:
          isLoadingPricingHealth ?? this.isLoadingPricingHealth,
      isLoadingCloudAccess: isLoadingCloudAccess ?? this.isLoadingCloudAccess,
      pricingHealthError: clearPricingHealthError
          ? null
          : pricingHealthError ?? this.pricingHealthError,
      cloudAccessError: clearCloudAccessError
          ? null
          : cloudAccessError ?? this.cloudAccessError,
      refreshingProvider: clearRefreshingProvider
          ? null
          : refreshingProvider ?? this.refreshingProvider,
      latestRuns: latestRuns ?? this.latestRuns,
      reportsByProvider: reportsByProvider ?? this.reportsByProvider,
      reportErrorsByProvider:
          reportErrorsByProvider ?? this.reportErrorsByProvider,
      selectedCandidateIds: selectedCandidateIds ?? this.selectedCandidateIds,
      loadingTraceReportIds:
          loadingTraceReportIds ?? this.loadingTraceReportIds,
      tracesByReportId: tracesByReportId ?? this.tracesByReportId,
      traceErrorsByReportId:
          traceErrorsByReportId ?? this.traceErrorsByReportId,
      savingDecisionReportIds:
          savingDecisionReportIds ?? this.savingDecisionReportIds,
      decisionsByReportId: decisionsByReportId ?? this.decisionsByReportId,
      feedback: clearFeedback ? null : feedback ?? this.feedback,
    );
  }

  @override
  List<Object?> get props => [
    selectedProvider,
    pricingHealth,
    cloudAccess,
    isLoadingPricingHealth,
    isLoadingCloudAccess,
    pricingHealthError,
    cloudAccessError,
    refreshingProvider,
    latestRuns,
    reportsByProvider,
    reportErrorsByProvider,
    selectedCandidateIds,
    loadingTraceReportIds,
    tracesByReportId,
    traceErrorsByReportId,
    savingDecisionReportIds,
    decisionsByReportId,
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
