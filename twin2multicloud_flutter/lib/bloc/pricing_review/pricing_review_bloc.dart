import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/api_service.dart';
import '../../utils/api_error_handler.dart';
import 'pricing_review_event.dart';
import 'pricing_review_state.dart';

class PricingReviewBloc extends Bloc<PricingReviewEvent, PricingReviewState> {
  final ApiService _api;

  PricingReviewBloc({required ApiService api, String? initialTwinId})
    : _api = api,
      super(PricingReviewState(selectedTwinId: initialTwinId)) {
    on<PricingReviewTwinSelected>(_onTwinSelected);
    on<PricingReviewProviderRefreshRequested>(_onProviderRefreshRequested);
    on<PricingReviewFeedbackCleared>(_onFeedbackCleared);
  }

  void _onTwinSelected(
    PricingReviewTwinSelected event,
    Emitter<PricingReviewState> emit,
  ) {
    emit(
      state.copyWith(
        selectedTwinId: event.twinId,
        clearSelectedTwinId: event.twinId == null,
        clearFeedback: true,
      ),
    );
  }

  Future<void> _onProviderRefreshRequested(
    PricingReviewProviderRefreshRequested event,
    Emitter<PricingReviewState> emit,
  ) async {
    final twinId = state.selectedTwinId;
    if (twinId == null || state.refreshingProvider != null) return;

    final provider = event.provider.toLowerCase();
    emit(
      state.copyWith(
        refreshingProvider: provider,
        clearFeedback: true,
        clearLastRefreshedTwinId: true,
      ),
    );

    try {
      await _api.refreshPricing(provider, twinId);
      emit(
        state.copyWith(
          clearRefreshingProvider: true,
          feedback: PricingReviewFeedback.success(
            '${provider.toUpperCase()} pricing refresh requested.',
          ),
          refreshRevision: state.refreshRevision + 1,
          lastRefreshedTwinId: twinId,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          clearRefreshingProvider: true,
          feedback: PricingReviewFeedback.error(
            'Failed to refresh ${provider.toUpperCase()} pricing: '
            '${ApiErrorHandler.extractMessage(error)}',
          ),
        ),
      );
    }
  }

  void _onFeedbackCleared(
    PricingReviewFeedbackCleared event,
    Emitter<PricingReviewState> emit,
  ) {
    emit(state.copyWith(clearFeedback: true));
  }
}
