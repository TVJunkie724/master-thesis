import 'package:flutter_bloc/flutter_bloc.dart';

import '../../models/pricing_candidate_review.dart';
import '../../services/api_service.dart';
import '../../utils/api_error_handler.dart';
import '../../widgets/pricing/pricing_review_strings.dart';
import 'pricing_review_event.dart';
import 'pricing_review_state.dart';

class PricingReviewBloc extends Bloc<PricingReviewEvent, PricingReviewState> {
  final ApiService _api;
  final Set<String> _refreshInFlight = {};

  PricingReviewBloc({required ApiService api})
    : _api = api,
      super(const PricingReviewState()) {
    on<PricingReviewStarted>(_onStarted);
    on<PricingReviewReloadRequested>(_onReloadRequested);
    on<PricingReviewProviderSelected>(_onProviderSelected);
    on<PricingReviewProviderRefreshRequested>(_onProviderRefreshRequested);
    on<PricingReviewReportsReloadRequested>(_onReportsReloadRequested);
    on<PricingReviewCandidateSelected>(_onCandidateSelected);
    on<PricingReviewReportExpanded>(_onReportExpanded);
    on<PricingReviewDecisionRequested>(_onDecisionRequested);
    on<PricingReviewFeedbackCleared>(_onFeedbackCleared);
  }

  Future<void> _onStarted(
    PricingReviewStarted event,
    Emitter<PricingReviewState> emit,
  ) => _loadOverview(emit);

  Future<void> _onReloadRequested(
    PricingReviewReloadRequested event,
    Emitter<PricingReviewState> emit,
  ) => _loadOverview(emit);

  void _onProviderSelected(
    PricingReviewProviderSelected event,
    Emitter<PricingReviewState> emit,
  ) {
    if (state.refreshingProvider != null) return;
    emit(
      state.copyWith(
        selectedProvider: event.provider.toLowerCase(),
        clearFeedback: true,
      ),
    );
  }

  Future<void> _loadOverview(Emitter<PricingReviewState> emit) async {
    emit(
      state.copyWith(
        isLoadingPricingHealth: true,
        isLoadingCloudAccess: true,
        clearPricingHealthError: true,
        clearCloudAccessError: true,
        clearFeedback: true,
      ),
    );

    try {
      final health = await _api.getPricingHealth();
      emit(
        state.copyWith(
          pricingHealth: health,
          isLoadingPricingHealth: false,
          clearPricingHealthError: true,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          isLoadingPricingHealth: false,
          pricingHealthError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }

    try {
      final access = await _api.getCloudAccessInventory();
      emit(
        state.copyWith(
          cloudAccess: access,
          isLoadingCloudAccess: false,
          clearCloudAccessError: true,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          isLoadingCloudAccess: false,
          cloudAccessError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onProviderRefreshRequested(
    PricingReviewProviderRefreshRequested event,
    Emitter<PricingReviewState> emit,
  ) async {
    final provider = event.provider.toLowerCase();
    final access = state.accessFor(provider);
    if (access == null ||
        !access.canRefreshPricing ||
        state.refreshingProvider != null ||
        (access.scope == 'public'
            ? event.connectionId != null
            : event.connectionId != access.connectionId) ||
        _refreshInFlight.contains(provider)) {
      return;
    }

    _refreshInFlight.add(provider);
    emit(
      state.copyWith(
        refreshingProvider: provider,
        selectedProvider: provider,
        reportErrorsByProvider: {...state.reportErrorsByProvider}
          ..remove(provider),
        clearFeedback: true,
      ),
    );

    try {
      final run = await _api.startPricingRefresh(
        provider,
        connectionId: event.connectionId,
      );
      final latestRuns = {...state.latestRuns, provider: run};
      if (!run.succeeded) {
        emit(
          state.copyWith(
            latestRuns: latestRuns,
            clearRefreshingProvider: true,
            feedback: PricingReviewFeedback.error(
              run.errorMessage ?? PricingReviewStrings.refreshFailed(provider),
            ),
          ),
        );
        return;
      }

      emit(
        state.copyWith(latestRuns: latestRuns, clearRefreshingProvider: true),
      );
      await _loadCandidateReports(emit, provider, run.refreshRunId);
      await _reloadHealth(emit);
      await _reloadCloudAccess(emit);
    } catch (error) {
      final message = ApiErrorHandler.extractMessage(error);
      emit(
        state.copyWith(
          clearRefreshingProvider: true,
          reportErrorsByProvider: {
            ...state.reportErrorsByProvider,
            provider: message,
          },
          feedback: PricingReviewFeedback.error(
            PricingReviewStrings.refreshRequestFailed(provider, message),
          ),
        ),
      );
    } finally {
      _refreshInFlight.remove(provider);
    }
  }

  Future<void> _loadCandidateReports(
    Emitter<PricingReviewState> emit,
    String provider,
    String refreshRunId,
  ) async {
    try {
      final reports = await _api.listPricingCandidateReports(
        provider,
        refreshRunId,
      );
      emit(
        state.copyWith(
          reportsByProvider: {
            ...state.reportsByProvider,
            provider: reports.reports,
          },
          reportErrorsByProvider: {...state.reportErrorsByProvider}
            ..remove(provider),
          selectedCandidateIds: {
            ...state.selectedCandidateIds,
            ..._defaultCandidateIds(reports.reports),
          },
          feedback: PricingReviewFeedback.success(
            PricingReviewStrings.refreshSucceeded(provider),
          ),
        ),
      );
    } catch (error) {
      final message = ApiErrorHandler.extractMessage(error);
      emit(
        state.copyWith(
          reportErrorsByProvider: {
            ...state.reportErrorsByProvider,
            provider: message,
          },
          feedback: PricingReviewFeedback.error(
            PricingReviewStrings.evidenceLoadFailed(provider, message),
          ),
        ),
      );
    }
  }

  Future<void> _onReportsReloadRequested(
    PricingReviewReportsReloadRequested event,
    Emitter<PricingReviewState> emit,
  ) async {
    final provider = event.provider.toLowerCase();
    final run = state.latestRuns[provider];
    if (run == null || !run.succeeded || state.refreshingProvider != null) {
      return;
    }
    await _loadCandidateReports(emit, provider, run.refreshRunId);
  }

  Map<String, String> _defaultCandidateIds(
    List<PricingCandidateReport> reports,
  ) {
    return {
      for (final report in reports)
        if (_defaultCandidateId(report) case final candidateId?)
          report.reportId: candidateId,
    };
  }

  String? _defaultCandidateId(PricingCandidateReport report) {
    final validIds = report.candidates
        .map((candidate) => candidate.candidateId)
        .toSet();
    final aiCandidateId = report.aiSuggestion.enabled
        ? report.aiSuggestion.candidateId
        : null;
    if (aiCandidateId != null && validIds.contains(aiCandidateId)) {
      return aiCandidateId;
    }
    final deterministicId = report.deterministicSelection.candidateId;
    return validIds.contains(deterministicId) ? deterministicId : null;
  }

  Future<void> _reloadHealth(Emitter<PricingReviewState> emit) async {
    try {
      final health = await _api.getPricingHealth();
      emit(
        state.copyWith(pricingHealth: health, clearPricingHealthError: true),
      );
    } catch (error) {
      emit(
        state.copyWith(
          pricingHealthError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _reloadCloudAccess(Emitter<PricingReviewState> emit) async {
    try {
      final access = await _api.getCloudAccessInventory();
      emit(state.copyWith(cloudAccess: access, clearCloudAccessError: true));
    } catch (error) {
      emit(
        state.copyWith(cloudAccessError: ApiErrorHandler.extractMessage(error)),
      );
    }
  }

  void _onCandidateSelected(
    PricingReviewCandidateSelected event,
    Emitter<PricingReviewState> emit,
  ) {
    final report = _reportById(event.reportId);
    if (report == null ||
        !report.deterministicSelection.selectable ||
        !report.candidates.any(
          (candidate) => candidate.candidateId == event.candidateId,
        )) {
      return;
    }
    emit(
      state.copyWith(
        selectedCandidateIds: {
          ...state.selectedCandidateIds,
          event.reportId: event.candidateId,
        },
      ),
    );
  }

  Future<void> _onReportExpanded(
    PricingReviewReportExpanded event,
    Emitter<PricingReviewState> emit,
  ) async {
    if (state.tracesByReportId.containsKey(event.reportId) ||
        state.loadingTraceReportIds.contains(event.reportId)) {
      return;
    }
    emit(
      state.copyWith(
        loadingTraceReportIds: {...state.loadingTraceReportIds, event.reportId},
        traceErrorsByReportId: {...state.traceErrorsByReportId}
          ..remove(event.reportId),
      ),
    );
    try {
      final trace = await _api.getPricingCandidateTrace(event.reportId);
      emit(
        state.copyWith(
          loadingTraceReportIds: {...state.loadingTraceReportIds}
            ..remove(event.reportId),
          tracesByReportId: {...state.tracesByReportId, event.reportId: trace},
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          loadingTraceReportIds: {...state.loadingTraceReportIds}
            ..remove(event.reportId),
          traceErrorsByReportId: {
            ...state.traceErrorsByReportId,
            event.reportId: ApiErrorHandler.extractMessage(error),
          },
        ),
      );
    }
  }

  Future<void> _onDecisionRequested(
    PricingReviewDecisionRequested event,
    Emitter<PricingReviewState> emit,
  ) async {
    if (state.savingDecisionReportIds.contains(event.reportId)) return;
    final report = _reportById(event.reportId);
    if (report == null) return;
    final candidateId = event.decision == 'defer'
        ? null
        : state.selectedCandidateIds[event.reportId];
    if (event.decision != 'defer' &&
        (candidateId == null ||
            !report.deterministicSelection.selectable ||
            !report.candidates.any(
              (candidate) => candidate.candidateId == candidateId,
            ))) {
      return;
    }

    emit(
      state.copyWith(
        savingDecisionReportIds: {
          ...state.savingDecisionReportIds,
          event.reportId,
        },
        clearFeedback: true,
      ),
    );
    try {
      final decision = await _api.createPricingReviewDecision(
        event.reportId,
        event.decision,
        candidateId: candidateId,
        rationale: event.rationale,
      );
      emit(
        state.copyWith(
          savingDecisionReportIds: {...state.savingDecisionReportIds}
            ..remove(event.reportId),
          decisionsByReportId: {
            ...state.decisionsByReportId,
            event.reportId: decision,
          },
          feedback: PricingReviewFeedback.success(
            PricingReviewStrings.decisionSaved,
          ),
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          savingDecisionReportIds: {...state.savingDecisionReportIds}
            ..remove(event.reportId),
          feedback: PricingReviewFeedback.error(
            PricingReviewStrings.decisionSaveFailed(
              ApiErrorHandler.extractMessage(error),
            ),
          ),
        ),
      );
    }
  }

  PricingCandidateReport? _reportById(String reportId) {
    for (final reports in state.reportsByProvider.values) {
      for (final report in reports) {
        if (report.reportId == reportId) return report;
      }
    }
    return null;
  }

  void _onFeedbackCleared(
    PricingReviewFeedbackCleared event,
    Emitter<PricingReviewState> emit,
  ) {
    emit(state.copyWith(clearFeedback: true));
  }
}
