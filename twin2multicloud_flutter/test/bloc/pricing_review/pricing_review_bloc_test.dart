import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/pricing_review/pricing_review.dart';
import 'package:twin2multicloud_flutter/models/pricing_review_state.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;

  setUp(() {
    api = MockApiService();
  });

  group('PricingReviewBloc', () {
    test('initializes with optional selected twin context', () {
      final bloc = PricingReviewBloc(api: api, initialTwinId: 'twin-1');
      expect(bloc.state.selectedTwinId, 'twin-1');
      expect(bloc.state.canRefreshProvider, isTrue);
      bloc.close();
    });

    blocTest<PricingReviewBloc, PricingReviewState>(
      'loads twins and pricing review state on start',
      build: () {
        when(() => api.getTwins()).thenAnswer((_) async => [_twinJson()]);
        when(
          () => api.getPricingReviewState('twin-1'),
        ).thenAnswer((_) async => _reviewState());
        return PricingReviewBloc(api: api, initialTwinId: 'twin-1');
      },
      act: (bloc) => bloc.add(const PricingReviewStarted()),
      expect: () => [
        isA<PricingReviewState>()
            .having((state) => state.isLoadingTwins, 'loading twins', isTrue)
            .having(
              (state) => state.isLoadingReviewState,
              'loading review',
              isTrue,
            ),
        isA<PricingReviewState>()
            .having((state) => state.twins.single.id, 'twin id', 'twin-1')
            .having((state) => state.isLoadingTwins, 'loading twins', isFalse),
        isA<PricingReviewState>()
            .having(
              (state) => state.reviewState?.schemaVersion,
              'schema version',
              'pricing-review.v1',
            )
            .having(
              (state) => state.isLoadingReviewState,
              'loading review',
              isFalse,
            ),
      ],
    );

    blocTest<PricingReviewBloc, PricingReviewState>(
      'selects credential context, clears feedback and reloads review state',
      build: () {
        when(
          () => api.getPricingReviewState('new-twin'),
        ).thenAnswer((_) async => _reviewState());
        return PricingReviewBloc(api: api, initialTwinId: 'old-twin');
      },
      seed: () => PricingReviewState(
        selectedTwinId: 'old-twin',
        reviewState: _reviewState(schemaVersion: 'old'),
        feedback: PricingReviewFeedback.error('Old feedback'),
      ),
      act: (bloc) => bloc.add(const PricingReviewTwinSelected('new-twin')),
      expect: () => [
        isA<PricingReviewState>()
            .having((state) => state.selectedTwinId, 'selected', 'new-twin')
            .having((state) => state.feedback, 'feedback', isNull),
        isA<PricingReviewState>()
            .having((state) => state.selectedTwinId, 'selected', 'new-twin')
            .having((state) => state.reviewState, 'review state', isNull)
            .having(
              (state) => state.isLoadingReviewState,
              'loading review',
              isTrue,
            ),
        isA<PricingReviewState>()
            .having((state) => state.selectedTwinId, 'selected', 'new-twin')
            .having(
              (state) => state.reviewState?.schemaVersion,
              'schema version',
              'pricing-review.v1',
            ),
      ],
    );

    blocTest<PricingReviewBloc, PricingReviewState>(
      'ignores provider refresh without selected twin',
      build: () => PricingReviewBloc(api: api),
      act: (bloc) =>
          bloc.add(const PricingReviewProviderRefreshRequested('aws')),
      expect: () => const <PricingReviewState>[],
      verify: (_) {
        verifyNever(() => api.refreshPricing(any(), any()));
      },
    );

    blocTest<PricingReviewBloc, PricingReviewState>(
      'refreshes provider pricing and emits success feedback',
      build: () {
        when(
          () => api.refreshPricing('aws', 'twin-1'),
        ).thenAnswer((_) async => {'success': true});
        when(
          () => api.getPricingReviewState('twin-1'),
        ).thenAnswer((_) async => _reviewState());
        return PricingReviewBloc(api: api, initialTwinId: 'twin-1');
      },
      act: (bloc) =>
          bloc.add(const PricingReviewProviderRefreshRequested('AWS')),
      expect: () => [
        const PricingReviewState(
          selectedTwinId: 'twin-1',
          refreshingProvider: 'aws',
        ),
        PricingReviewState(
          selectedTwinId: 'twin-1',
          feedback: PricingReviewFeedback.success(
            'AWS pricing refresh requested.',
          ),
        ),
        isA<PricingReviewState>()
            .having(
              (state) => state.isLoadingReviewState,
              'loading review',
              isTrue,
            )
            .having((state) => state.reviewState, 'review state', isNull),
        isA<PricingReviewState>().having(
          (state) => state.reviewState?.schemaVersion,
          'schema version',
          'pricing-review.v1',
        ),
      ],
      verify: (_) {
        verify(() => api.refreshPricing('aws', 'twin-1')).called(1);
        verify(() => api.getPricingReviewState('twin-1')).called(1);
      },
    );

    blocTest<PricingReviewBloc, PricingReviewState>(
      'reports refresh errors without incrementing refresh revision',
      build: () {
        when(
          () => api.refreshPricing('gcp', 'twin-1'),
        ).thenThrow(Exception('provider unavailable'));
        return PricingReviewBloc(api: api, initialTwinId: 'twin-1');
      },
      act: (bloc) =>
          bloc.add(const PricingReviewProviderRefreshRequested('gcp')),
      expect: () => [
        const PricingReviewState(
          selectedTwinId: 'twin-1',
          refreshingProvider: 'gcp',
        ),
        PricingReviewState(
          selectedTwinId: 'twin-1',
          feedback: PricingReviewFeedback.error(
            'Failed to refresh GCP pricing: provider unavailable',
          ),
        ),
      ],
    );
  });
}

Map<String, dynamic> _twinJson() {
  return {
    'id': 'twin-1',
    'name': 'Demo Twin',
    'state': 'configured',
    'providers': ['AWS'],
  };
}

PricingReviewStateResponse _reviewState({
  String schemaVersion = 'pricing-review.v1',
}) {
  return PricingReviewStateResponse(
    schemaVersion: schemaVersion,
    providers: const {
      'aws': ProviderPricingReviewState(
        provider: 'aws',
        state: 'fresh',
        reviewRequired: false,
        canCalculate: true,
        calculationSource: 'fresh',
        pricingFreshness: 'fresh',
        isFresh: true,
      ),
    },
  );
}
