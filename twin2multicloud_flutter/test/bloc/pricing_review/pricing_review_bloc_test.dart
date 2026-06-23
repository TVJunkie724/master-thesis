import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/pricing_review/pricing_review.dart';
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
      'selects credential context and clears feedback',
      build: () => PricingReviewBloc(api: api, initialTwinId: 'old-twin'),
      seed: () => PricingReviewState(
        selectedTwinId: 'old-twin',
        feedback: PricingReviewFeedback.error('Old feedback'),
      ),
      act: (bloc) => bloc.add(const PricingReviewTwinSelected('new-twin')),
      expect: () => [const PricingReviewState(selectedTwinId: 'new-twin')],
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
          refreshRevision: 1,
          lastRefreshedTwinId: 'twin-1',
        ),
      ],
      verify: (_) {
        verify(() => api.refreshPricing('aws', 'twin-1')).called(1);
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
