import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_review_task.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

import '../../fixtures/architecture_wizard_fixture.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  testWidgets(
    'Phase 8 summary reports frozen twin activity without 3D intent',
    (tester) async {
      final state =
          architectureReadyWizardState(
            profileId: 'five-layer-baseline',
          ).copyWith(
            calcParams: CalcParams.fiveLayerV2(
              scenario: FiveLayerWorkloadScenario.small,
            ),
          );
      final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
      addTearDown(bloc.close);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BlocProvider.value(
              value: bloc,
              child: ConfigurationReviewTask(
                taskId: ConfigurationTaskId.summary,
                onOpenTask: (_) {},
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      expect(find.text('Twin entities'), findsOneWidget);
      expect(find.text('Dashboard refreshes'), findsOneWidget);
      expect(find.text('3D representation'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
}
