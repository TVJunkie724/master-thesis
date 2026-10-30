import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_phase_navigation.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_task_selector.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_workspace_shell.dart';

import '../../fixtures/architecture_wizard_fixture.dart';

void main() {
  testWidgets('wide workspace exposes four phases and one task selector', (
    tester,
  ) async {
    await _setSize(tester, const Size(1200, 800));
    await tester.pumpWidget(_app(_journey()));

    expect(find.byType(ConfigurationPhaseNavigation), findsOneWidget);
    expect(find.byType(ConfigurationTaskSelector), findsOneWidget);
    expect(find.text('1. Scenario'), findsOneWidget);
    expect(find.text('2. Optimize'), findsOneWidget);
    expect(find.text('3. Prepare'), findsOneWidget);
    expect(find.text('4. Review'), findsOneWidget);
    expect(find.text('Define Twin'), findsOneWidget);
    expect(
      find.bySemanticsLabel('Phase 1, Scenario, Current phase, Available'),
      findsOneWidget,
    );
    expect(find.text('Scenario and currency'), findsNothing);
    expect(find.text('Device traffic'), findsNothing);
  });

  testWidgets('task menu exposes only the active phase', (tester) async {
    await _setSize(tester, const Size(1200, 800));
    ConfigurationTaskId? selected;
    await tester.pumpWidget(
      _app(
        _journey(
          architectureReady: true,
          requestedTaskId: ConfigurationTaskId.deviceTraffic,
        ),
        onSelected: (value) => selected = value,
      ),
    );

    await tester.tap(
      find.descendant(
        of: find.byType(ConfigurationTaskSelector),
        matching: find.byType(OutlinedButton),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Retention'), findsOneWidget);
    expect(find.text('Calculate cost allocation'), findsNothing);
    expect(find.text('Cloud access'), findsNothing);
    await tester.tap(find.widgetWithText(MenuItemButton, 'Retention'));
    await tester.pump();
    expect(selected, ConfigurationTaskId.retention);
  });

  testWidgets('phase navigation emits the deterministic current target', (
    tester,
  ) async {
    await _setSize(tester, const Size(1200, 800));
    ConfigurationTaskId? selected;
    await tester.pumpWidget(
      _app(
        _journey(
          architectureReady: true,
          requestedTaskId: ConfigurationTaskId.deviceTraffic,
        ),
        onSelected: (value) => selected = value,
      ),
    );

    await tester.tap(find.widgetWithText(OutlinedButton, '1. Scenario'));
    expect(selected, ConfigurationTaskId.deviceTraffic);
  });

  testWidgets('blocked future phase is disabled and explains its blocker', (
    tester,
  ) async {
    await _setSize(tester, const Size(1200, 800));
    await tester.pumpWidget(_app(_journey()));

    final optimize = tester.widget<OutlinedButton>(
      find.widgetWithText(OutlinedButton, '2. Optimize'),
    );
    expect(optimize.onPressed, isNull);
    expect(
      find.byTooltip('Complete the scenario and required user logic first'),
      findsOneWidget,
    );
  });

  testWidgets('active command disables phase and task navigation', (
    tester,
  ) async {
    await _setSize(tester, const Size(1200, 800));
    await tester.pumpWidget(
      _app(_journey(architectureReady: true), isNavigationEnabled: false),
    );

    for (final button in tester.widgetList<OutlinedButton>(
      find.descendant(
        of: find.byType(ConfigurationWorkspaceShell),
        matching: find.byType(OutlinedButton),
      ),
    )) {
      expect(button.onPressed, isNull);
    }
    expect(
      find.byTooltip('Wait for the current command to finish'),
      findsNWidgets(5),
    );
  });

  testWidgets('800 pixel boundary keeps four phases in one row', (
    tester,
  ) async {
    await _setSize(tester, const Size(800, 900));
    await tester.pumpWidget(_app(_journey(architectureReady: true)));

    final phaseCenters = [
      for (final label in const [
        '1. Scenario',
        '2. Optimize',
        '3. Prepare',
        '4. Review',
      ])
        tester.getCenter(find.text(label)).dy,
    ];
    expect(phaseCenters.toSet().length, 1);
    expect(tester.takeException(), isNull);
  });

  for (final textScale in [1.5, 2.0]) {
    testWidgets(
      'compact phases remain reachable at ${(textScale * 100).toInt()} percent text',
      (tester) async {
        await _setSize(tester, const Size(640, 1100));
        await tester.pumpWidget(
          _app(_journey(architectureReady: true), textScale: textScale),
        );

        final scenarioY = tester.getCenter(find.text('1. Scenario')).dy;
        final optimizeY = tester.getCenter(find.text('2. Optimize')).dy;
        final prepareY = tester.getCenter(find.text('3. Prepare')).dy;
        expect(optimizeY, closeTo(scenarioY, 1));
        expect(prepareY, greaterThan(scenarioY));
        expect(find.byType(ConfigurationTaskSelector), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}

Future<void> _setSize(WidgetTester tester, Size size) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

Widget _app(
  ConfigurationJourney journey, {
  bool isNavigationEnabled = true,
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
      isNavigationEnabled: isNavigationEnabled,
      onTaskSelected: onSelected ?? (_) {},
      child: const Center(child: Text('Task content')),
    ),
  ),
);

ConfigurationJourney _journey({
  bool architectureReady = false,
  ConfigurationTaskId? requestedTaskId,
}) => ConfigurationJourney.fromWizardState(
  architectureReady
      ? architectureReadyWizardState()
      : const WizardState(status: WizardStatus.ready),
  requestedTaskId: requestedTaskId,
);
