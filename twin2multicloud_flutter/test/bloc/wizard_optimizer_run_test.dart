import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/optimizer_config.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

import '../fixtures/typed_api_fixtures.dart';

final class _MockApiService extends Mock implements ApiService {}

void main() {
  late _MockApiService api;

  setUpAll(() => registerFallbackValue(CalcParams.defaultParams()));
  setUp(() {
    api = _MockApiService();
    when(() => api.getPricingHealth()).thenAnswer((_) async => _health());
  });

  test('create mode creates one draft and one durable optimizer run', () async {
    final run = TypedApiFixtures.optimizerRun(twinId: 'new-twin');
    when(() => api.createTwin('Factory twin')).thenAnswer(
      (_) async => TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
    );
    when(
      () => api.createOptimizerRun('new-twin', any()),
    ).thenAnswer((_) async => run);
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    await _prepare(bloc);

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere((state) => state.calcResult != null);

    expect(bloc.state.twinId, 'new-twin');
    expect(bloc.state.calcResult, run.optimization.result);
    expect(bloc.state.optimizationResultData, run.optimization);
    verify(() => api.createTwin('Factory twin')).called(1);
    verify(() => api.createOptimizerRun('new-twin', any())).called(1);
  });

  test(
    'create mode retains draft identity after run failure and reuses it',
    () async {
      var runAttempts = 0;
      when(() => api.createTwin('Factory twin')).thenAnswer(
        (_) async =>
            TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
      );
      when(() => api.createOptimizerRun('new-twin', any())).thenAnswer((
        _,
      ) async {
        runAttempts += 1;
        if (runAttempts == 1) throw Exception('optimizer unavailable');
        return TypedApiFixtures.optimizerRun(twinId: 'new-twin');
      });
      final bloc = WizardBloc(api: api);
      addTearDown(bloc.close);
      await _prepare(bloc);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere(
        (state) => state.errorMessage != null && !state.isCalculating,
      );

      expect(bloc.state.twinId, 'new-twin');
      expect(bloc.state.calcResult, isNull);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere((state) => state.calcResult != null);

      verify(() => api.createTwin('Factory twin')).called(1);
      verify(() => api.createOptimizerRun('new-twin', any())).called(2);
    },
  );

  test('duplicate calculate command cannot create duplicate runs', () async {
    final completer = Completer<OptimizerRunData>();
    when(() => api.createTwin('Factory twin')).thenAnswer(
      (_) async => TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
    );
    when(
      () => api.createOptimizerRun('new-twin', any()),
    ).thenAnswer((_) => completer.future);
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    await _prepare(bloc);

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere(
      (state) => state.isCalculating && state.twinId == 'new-twin',
    );
    bloc.add(const WizardCalculateRequested());
    await Future<void>.delayed(Duration.zero);

    verify(() => api.createOptimizerRun('new-twin', any())).called(1);

    completer.complete(TypedApiFixtures.optimizerRun(twinId: 'new-twin'));
    await bloc.stream.firstWhere((state) => state.calcResult != null);
  });

  test('blank create-mode name blocks twin and optimizer calls', () async {
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    await _prepare(bloc, twinName: '   ');

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere((state) => state.errorMessage != null);

    expect(bloc.state.errorMessage, 'Twin name is required');
    verifyNever(() => api.createTwin(any()));
    verifyNever(() => api.createOptimizerRun(any(), any()));
  });
}

Future<void> _prepare(
  WizardBloc bloc, {
  String twinName = 'Factory twin',
}) async {
  bloc
    ..add(WizardTwinNameChanged(twinName))
    ..add(WizardCalcParamsChanged(CalcParams.defaultParams()))
    ..add(const WizardPricingHealthLoadRequested());
  await bloc.stream.firstWhere(
    (state) =>
        state.twinName == twinName &&
        state.calcParams != null &&
        state.pricingHealth != null,
  );
}

PricingHealthResponse _health() => PricingHealthResponse.fromJson({
  'schema_version': 'pricing-health.v1',
  'providers': {
    for (final provider in const ['aws', 'azure', 'gcp'])
      provider: {
        'provider': provider,
        'state': 'fresh',
        'severity': 'success',
        'review_required': false,
        'can_calculate': true,
        'calculation_source': 'fresh',
        'pricing_freshness': 'fresh',
        'source_label': '${provider.toUpperCase()} source',
        'credential_summary': {
          'provider': provider,
          'purpose': 'pricing',
          'scope': 'user',
          'identity_label': '${provider.toUpperCase()} pricing',
          'status': 'active',
        },
        'primary_message': '$provider pricing is ready',
      },
  },
});
