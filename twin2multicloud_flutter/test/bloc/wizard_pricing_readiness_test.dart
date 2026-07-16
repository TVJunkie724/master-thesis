import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;

  setUpAll(() => registerFallbackValue(CalcParams.defaultParams()));
  setUp(() => api = MockApiService());

  test('loads complete pricing readiness into Wizard state', () async {
    when(() => api.getPricingHealth()).thenAnswer((_) async => _health());
    final bloc = WizardBloc(api: api)
      ..add(const WizardPricingHealthLoadRequested());

    await bloc.stream.firstWhere((state) => state.pricingHealth != null);

    expect(bloc.state.pricingCanCalculate, isTrue);
    expect(bloc.state.pricingBlockingProviders, isEmpty);
    await bloc.close();
  });

  test('preserves health but fails closed when retry fails', () async {
    var calls = 0;
    when(() => api.getPricingHealth()).thenAnswer((_) async {
      if (calls++ == 0) return _health();
      throw Exception('health unavailable');
    });
    final bloc = WizardBloc(api: api)
      ..add(const WizardPricingHealthLoadRequested());
    await bloc.stream.firstWhere((state) => state.pricingHealth != null);

    bloc.add(const WizardPricingHealthLoadRequested());
    await bloc.stream.firstWhere((state) => state.pricingHealthError != null);

    expect(bloc.state.pricingHealth, isNotNull);
    expect(bloc.state.pricingCanCalculate, isFalse);
    expect(bloc.state.pricingHealthError, 'An unexpected error occurred');
    await bloc.close();
  });

  test(
    'blocks calculation command when any provider cannot calculate',
    () async {
      when(
        () => api.getPricingHealth(),
      ).thenAnswer((_) async => _health(gcpCanCalculate: false));
      final bloc = WizardBloc(api: api)
        ..add(const WizardPricingHealthLoadRequested());
      await bloc.stream.firstWhere((state) => state.pricingHealth != null);
      bloc.add(WizardCalcParamsChanged(CalcParams.defaultParams()));
      await bloc.stream.firstWhere((state) => state.calcParams != null);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere((state) => state.errorMessage != null);

      expect(bloc.state.errorMessage, contains('Pricing data is not ready'));
      verifyNever(() => api.calculateCosts(any()));
      await bloc.close();
    },
  );

  test('requires all providers even when available entries are calculable', () {
    final complete = WizardState(
      calcParams: CalcParams.defaultParams(),
      pricingHealth: _health(),
    );
    final incomplete = WizardState(
      calcParams: CalcParams.defaultParams(),
      pricingHealth: _health(includeGcp: false),
    );

    expect(complete.canRequestCalculation, isTrue);
    expect(incomplete.canRequestCalculation, isFalse);
    expect(incomplete.pricingBlockingProviders, contains('gcp'));
  });

  test('rejects an unsupported pricing health contract version', () {
    final health = _health();
    final state = WizardState(
      calcParams: CalcParams.defaultParams(),
      pricingHealth: PricingHealthResponse(
        schemaVersion: 'pricing-health.v2',
        providers: health.providers,
      ),
    );

    expect(state.pricingCanCalculate, isFalse);
    expect(state.canRequestCalculation, isFalse);
  });

  test(
    'stale and review-required providers remain calculable when allowed',
    () {
      final state = WizardState(
        calcParams: CalcParams.defaultParams(),
        pricingHealth: _health(),
      );

      expect(state.pricingHealth?.provider('aws')?.state, 'stale');
      expect(state.pricingHealth?.provider('gcp')?.state, 'review_required');
      expect(state.pricingCanCalculate, isTrue);
    },
  );
}

PricingHealthResponse _health({
  bool includeGcp = true,
  bool gcpCanCalculate = true,
}) => PricingHealthResponse.fromJson({
  'schema_version': 'pricing-health.v1',
  'providers': {
    'aws': _provider('aws', state: 'stale', source: 'last_known_good'),
    'azure': _provider('azure', state: 'fresh'),
    if (includeGcp)
      'gcp': _provider(
        'gcp',
        state: 'review_required',
        source: 'last_known_good',
        canCalculate: gcpCanCalculate,
      ),
  },
});

Map<String, dynamic> _provider(
  String provider, {
  required String state,
  String source = 'fresh',
  bool canCalculate = true,
}) => {
  'provider': provider,
  'state': state,
  'severity': state == 'fresh' ? 'success' : 'warning',
  'review_required': state == 'review_required',
  'can_calculate': canCalculate,
  'calculation_source': source,
  'pricing_freshness': state == 'fresh' ? 'fresh' : 'stale',
  'source_label': '${provider.toUpperCase()} source',
  'credential_summary': {
    'provider': provider,
    'purpose': 'pricing',
    'scope': provider == 'azure' ? 'public' : 'user',
    'identity_label': '${provider.toUpperCase()} pricing',
    'status': 'active',
  },
  'primary_message': '$provider pricing status',
};
