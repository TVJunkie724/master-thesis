import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/screens/wizard/step2_optimizer.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

import '../fixtures/architecture_wizard_fixture.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  testWidgets(
    'loads pricing when the retained optimizer changes to an architecture task',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1200, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      final api = MockApiService();
      when(() => api.getPricingHealth()).thenAnswer((_) async => _health());
      final bloc = WizardBloc(api: api);
      addTearDown(bloc.close);

      Widget app(ConfigurationTaskId taskId) => MaterialApp(
        home: BlocProvider<WizardBloc>.value(
          value: bloc,
          child: Scaffold(body: Step2Optimizer(taskId: taskId)),
        ),
      );

      await tester.pumpWidget(app(ConfigurationTaskId.twinCapabilities));
      await tester.pump();
      verifyNever(() => api.getPricingHealth());

      await tester.pumpWidget(app(ConfigurationTaskId.calculateAlternatives));
      await tester.pumpAndSettle();

      verify(() => api.getPricingHealth()).called(1);
      expect(bloc.state.pricingCanCalculate, isTrue);
      expect(find.text('AWS  Fresh'), findsOneWidget);
      expect(find.text('Pricing readiness is unavailable.'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Phase 8 workload shows frozen twin activity without 3D intent', (
    tester,
  ) async {
    final api = MockApiService();
    final state = architectureReadyWizardState(profileId: 'six-layer-eventing')
        .copyWith(
          calcParams: CalcParams.sixLayer(
            scenario: SixLayerWorkloadScenario.small,
          ),
        );
    final bloc = WizardBloc(api: api, initialState: state);
    addTearDown(bloc.close);

    await tester.pumpWidget(
      MaterialApp(
        home: BlocProvider<WizardBloc>.value(
          value: bloc,
          child: const Scaffold(
            body: Step2Optimizer(taskId: ConfigurationTaskId.twinCapabilities),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(
      find.text('Review the frozen twin-state and dashboard activity.'),
      findsOneWidget,
    );
    expect(find.textContaining('3D representation'), findsNothing);
    expect(find.text('Twin and dashboard activity'), findsOneWidget);
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
        'calculation_source': 'latest_verified',
        'pricing_freshness': 'fresh',
        'source_label': '${provider.toUpperCase()} source',
        'credential_summary': {
          'provider': provider,
          'purpose': 'pricing',
          'scope': provider == 'azure' ? 'public' : 'user',
          'identity_label': '${provider.toUpperCase()} pricing',
          'status': 'active',
        },
        'primary_message': '$provider pricing is ready',
      },
  },
});
