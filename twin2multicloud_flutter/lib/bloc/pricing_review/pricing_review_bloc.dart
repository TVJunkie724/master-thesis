import 'package:flutter_bloc/flutter_bloc.dart';

import '../../models/twin.dart';
import '../../services/api_service.dart';
import '../../utils/api_error_handler.dart';
import 'pricing_review_event.dart';
import 'pricing_review_state.dart';

class PricingReviewBloc extends Bloc<PricingReviewEvent, PricingReviewState> {
  final ApiService _api;

  PricingReviewBloc({required ApiService api, String? initialTwinId})
    : _api = api,
      super(PricingReviewState(selectedTwinId: initialTwinId)) {
    on<PricingReviewStarted>(_onStarted);
    on<PricingReviewTwinSelected>(_onTwinSelected);
    on<PricingReviewReloadRequested>(_onReloadRequested);
    on<PricingReviewProviderRefreshRequested>(_onProviderRefreshRequested);
    on<PricingReviewFeedbackCleared>(_onFeedbackCleared);
  }

  Future<void> _onStarted(
    PricingReviewStarted event,
    Emitter<PricingReviewState> emit,
  ) async {
    emit(
      state.copyWith(
        isLoadingTwins: true,
        isLoadingReviewState: true,
        clearTwinsError: true,
        clearReviewStateError: true,
        clearReviewState: true,
      ),
    );

    String? selectedTwinId = state.selectedTwinId;
    try {
      final twins = await _loadTwins();
      if (selectedTwinId != null &&
          !twins.any((twin) => twin.id == selectedTwinId)) {
        selectedTwinId = null;
      }
      emit(
        state.copyWith(
          selectedTwinId: selectedTwinId,
          clearSelectedTwinId: selectedTwinId == null,
          twins: twins,
          isLoadingTwins: false,
          clearTwinsError: true,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          isLoadingTwins: false,
          twinsError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }

    await _loadReviewState(emit, selectedTwinId: selectedTwinId);
  }

  Future<void> _onTwinSelected(
    PricingReviewTwinSelected event,
    Emitter<PricingReviewState> emit,
  ) async {
    emit(
      state.copyWith(
        selectedTwinId: event.twinId,
        clearSelectedTwinId: event.twinId == null,
        clearFeedback: true,
      ),
    );
    await _loadReviewState(emit, selectedTwinId: event.twinId);
  }

  Future<void> _onReloadRequested(
    PricingReviewReloadRequested event,
    Emitter<PricingReviewState> emit,
  ) async {
    await _loadReviewState(emit, selectedTwinId: state.selectedTwinId);
  }

  Future<void> _onProviderRefreshRequested(
    PricingReviewProviderRefreshRequested event,
    Emitter<PricingReviewState> emit,
  ) async {
    final twinId = state.selectedTwinId;
    if (twinId == null || state.refreshingProvider != null) return;

    final provider = event.provider.toLowerCase();
    emit(state.copyWith(refreshingProvider: provider, clearFeedback: true));

    try {
      await _api.refreshPricing(provider, twinId);
      emit(
        state.copyWith(
          clearRefreshingProvider: true,
          feedback: PricingReviewFeedback.success(
            '${provider.toUpperCase()} pricing refresh requested.',
          ),
        ),
      );
      await _loadReviewState(emit, selectedTwinId: twinId);
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

  Future<List<Twin>> _loadTwins() async {
    final data = await _api.getTwins();
    return data
        .map((json) => Twin.fromJson(Map<String, dynamic>.from(json as Map)))
        .toList();
  }

  Future<void> _loadReviewState(
    Emitter<PricingReviewState> emit, {
    required String? selectedTwinId,
  }) async {
    emit(
      state.copyWith(
        isLoadingReviewState: true,
        clearReviewStateError: true,
        clearReviewState: true,
      ),
    );
    try {
      final reviewState = await _api.getPricingReviewState(selectedTwinId);
      emit(
        state.copyWith(
          reviewState: reviewState,
          isLoadingReviewState: false,
          clearReviewStateError: true,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          isLoadingReviewState: false,
          reviewStateError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }
}
