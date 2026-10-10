import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/screens/wizard/step2_optimizer.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';
import 'package:twin2multicloud_flutter/widgets/results/cheapest_path_visualization.dart';
import 'package:twin2multicloud_flutter/widgets/results/layer_cost_card.dart';
import 'package:twin2multicloud_flutter/widgets/results/logical_resolved_flow.dart';

import '../fixtures/architecture_wizard_fixture.dart';
import '../fixtures/typed_api_fixtures.dart';

class _Api extends Mock implements ManagementApi {}

void main() {
  for (final width in [640.0, 1280.0]) {
    testWidgets('native result uses actual graph and costs at $width', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, 1600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final currency = width == 640 ? 'EUR' : 'USD';
      final resolved = resolvedArchitectureFixture(currency: currency);
      final bloc = WizardBloc(
        api: _Api(),
        initialState: architectureReadyWizardState().copyWith(
          calcResult: TypedApiFixtures.optimization().result,
          resolvedArchitecture: resolved,
          resolvedArchitecturePhase: ResolvedArchitecturePhase.ready,
        ),
      );
      addTearDown(bloc.close);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BlocProvider.value(
              value: bloc,
              child: const Step2Optimizer(
                taskId: ConfigurationTaskId.reviewImmutableResult,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(LogicalResolvedFlow), findsOneWidget);
      expect(find.byType(CheapestPathVisualization), findsNothing);
      expect(find.byType(LayerCostCard), findsNothing);
      expect(find.text('Independent Event Layer'), findsOneWidget);
      expect(find.text('145.69038186 $currency / month'), findsOneWidget);
      expect(find.textContaining('not a cloud bill'), findsOneWidget);
      expect(find.text('Functionally complete'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }
}
