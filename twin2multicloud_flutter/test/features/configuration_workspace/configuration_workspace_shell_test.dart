import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_task_selector.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_task_sidebar.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_workspace_shell.dart';

import '../../fixtures/architecture_wizard_fixture.dart';

void main() {
  testWidgets('uses the task sidebar on wide layouts', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1200, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_app(_journey()));

    expect(find.byType(ConfigurationTaskSidebar), findsOneWidget);
    expect(find.byType(ConfigurationTaskSelector), findsNothing);
    expect(find.text('Scenario'), findsOneWidget);
    expect(find.text('Optimize'), findsOneWidget);
    expect(find.text('Prepare'), findsOneWidget);
    expect(find.text('Review'), findsOneWidget);
    expect(find.text('Define Twin'), findsOneWidget);
    expect(find.text('Scenario and currency'), findsOneWidget);
    expect(find.text('Device traffic'), findsOneWidget);
  });

  testWidgets('uses a compact task selector on narrow layouts', (tester) async {
    await tester.binding.setSurfaceSize(const Size(700, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_app(_journey()));

    expect(find.byType(ConfigurationTaskSelector), findsOneWidget);
    expect(find.byType(ConfigurationTaskSidebar), findsNothing);
    expect(find.text('Scenario'), findsOneWidget);
    expect(find.text('Define Twin'), findsOneWidget);
  });

  testWidgets('navigates available tasks and keeps blocked tasks disabled', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1200, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    ConfigurationTaskId? selected;

    await tester.pumpWidget(
      _app(_journey(named: true), onSelected: (value) => selected = value),
    );

    await tester.tap(find.text('Scenario and currency'));
    await tester.pump();
    expect(selected, isNull);

    // The active phase alone expands. Requesting a workload task makes it
    // visible and independently navigable.
    await tester.pumpWidget(
      _app(
        _journey(
          architectureReady: true,
          requestedTaskId: ConfigurationTaskId.deviceTraffic,
        ),
        onSelected: (value) => selected = value,
      ),
    );
    await tester.tap(find.text('Retention'));
    expect(selected, ConfigurationTaskId.retention);
  });

  for (final textScale in [1.5, 2.0]) {
    testWidgets(
      'compact selector remains reachable at ${(textScale * 100).toInt()} percent text',
      (tester) async {
        await tester.binding.setSurfaceSize(const Size(640, 900));
        addTearDown(() => tester.binding.setSurfaceSize(null));

        await tester.pumpWidget(
          _app(_journey(architectureReady: true), textScale: textScale),
        );

        expect(find.byType(ConfigurationTaskSelector), findsOneWidget);
        expect(find.text('Scenario'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}

Widget _app(
  ConfigurationJourney journey, {
  ValueChanged<ConfigurationTaskId>? onSelected,
  double textScale = 1,
}) => MaterialApp(
  builder: (context, child) => MediaQuery(
    data: MediaQuery.of(
      context,
    ).copyWith(textScaler: TextScaler.linear(textScale)),
    child: child!,
  ),
  home: Scaffold(
    body: ConfigurationWorkspaceShell(
      journey: journey,
      onTaskSelected: onSelected ?? (_) {},
      child: const Center(child: Text('Task content')),
    ),
  ),
);

ConfigurationJourney _journey({
  bool named = false,
  bool architectureReady = false,
  ConfigurationTaskId? requestedTaskId,
}) => ConfigurationJourney.fromWizardState(
  architectureReady
      ? architectureReadyWizardState()
      : WizardState(
          status: WizardStatus.ready,
          twinName: named ? 'Factory twin' : null,
        ),
  requestedTaskId: requestedTaskId,
);
