import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/screens/wizard/step3_deployer.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

import '../../fixtures/architecture_wizard_fixture.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  Widget buildTask(ConfigurationTaskId taskId) {
    final state = architectureReadyWizardState(profileId: 'six-layer-eventing')
        .copyWith(
          calcParams: CalcParams.sixLayer(
            scenario: SixLayerWorkloadScenario.small,
          ),
          calcResult: null,
        );
    final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
    addTearDown(bloc.close);

    return MaterialApp(
      home: Scaffold(
        body: BlocProvider.value(
          value: bloc,
          child: Step3Deployer(taskId: taskId),
        ),
      ),
    );
  }

  testWidgets('user logic is available before optimization', (tester) async {
    await tester.pumpWidget(buildTask(ConfigurationTaskId.userLogic));
    await tester.pump();

    expect(
      find.byKey(const ValueKey('deployment-user-logic-section')),
      findsOneWidget,
    );
    expect(
      find.text('No reviewed user-function extension slots are available.'),
      findsOneWidget,
    );
    expect(find.text('No Optimization Result'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('deployment artifacts still require optimization', (
    tester,
  ) async {
    await tester.pumpWidget(buildTask(ConfigurationTaskId.dataContracts));
    await tester.pump();

    expect(find.text('No Optimization Result'), findsOneWidget);
    expect(
      find.byKey(const ValueKey('deployment-config-section')),
      findsNothing,
    );
    expect(tester.takeException(), isNull);
  });
}
