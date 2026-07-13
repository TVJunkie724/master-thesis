import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/screens/wizard/wizard_screen.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  testWidgets('calculate stays disabled until pricing readiness passes', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1440, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final api = MockApiService();
    final health = Completer<PricingHealthResponse>();
    when(() => api.getPricingHealth()).thenAnswer((_) => health.future);
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);

    bloc.add(const WizardTwinNameChanged('Pricing gate test'));
    await bloc.stream.firstWhere((state) => state.twinName != null);
    bloc.add(const WizardCredentialsValidated('aws', true));
    await bloc.stream.firstWhere((state) => state.aws.isValid);
    bloc.add(const WizardNextStep());
    await bloc.stream.firstWhere((state) => state.currentStep == 1);
    bloc.add(WizardCalcParamsChanged(CalcParams.defaultParams()));
    await bloc.stream.firstWhere((state) => state.calcParams != null);

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: BlocProvider<WizardBloc>.value(
            value: bloc,
            child: const WizardView(),
          ),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Calculate alternatives'));
    await tester.pump();

    ElevatedButton calculateButton() => tester.widget<ElevatedButton>(
      find.widgetWithText(ElevatedButton, 'CALCULATE'),
    );

    expect(calculateButton().onPressed, isNull);

    health.complete(_health());
    await tester.pumpAndSettle();

    expect(calculateButton().onPressed, isNotNull);
    expect(tester.takeException(), isNull);
  });
}

PricingHealthResponse _health() => PricingHealthResponse.fromJson({
  'schema_version': 'pricing-health.v1',
  'providers': {
    for (final provider in ['aws', 'azure', 'gcp'])
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
