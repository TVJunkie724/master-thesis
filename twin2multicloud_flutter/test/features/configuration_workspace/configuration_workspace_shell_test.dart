import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_task_selector.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_task_sidebar.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_workspace_shell.dart';

void main() {
  testWidgets('uses the task sidebar on wide layouts', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1200, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_app(_journey()));

    expect(find.byType(ConfigurationTaskSidebar), findsOneWidget);
    expect(find.byType(ConfigurationTaskSelector), findsNothing);
    expect(find.text('Define twin'), findsOneWidget);
    expect(find.text('Describe workload'), findsOneWidget);
    expect(find.text('Identity and mode'), findsOneWidget);
    expect(find.text('Device traffic'), findsNothing);
  });

  testWidgets('uses a compact task selector on narrow layouts', (tester) async {
    await tester.binding.setSurfaceSize(const Size(700, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_app(_journey()));

    expect(find.byType(ConfigurationTaskSelector), findsOneWidget);
    expect(find.byType(ConfigurationTaskSidebar), findsNothing);
    expect(find.text('Identity and mode'), findsOneWidget);
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

    await tester.tap(find.text('Describe workload'));
    await tester.pump();
    expect(selected, isNull);

    // The active phase alone expands. Requesting a workload task makes it
    // visible and independently navigable.
    await tester.pumpWidget(
      _app(
        _journey(
          named: true,
          requestedTaskId: ConfigurationTaskId.deviceTraffic,
        ),
        onSelected: (value) => selected = value,
      ),
    );
    await tester.tap(find.text('Retention'));
    expect(selected, ConfigurationTaskId.retention);
  });
}

Widget _app(
  ConfigurationJourney journey, {
  ValueChanged<ConfigurationTaskId>? onSelected,
}) => MaterialApp(
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
  ConfigurationTaskId? requestedTaskId,
}) => ConfigurationJourney.fromWizardState(
  WizardState(
    status: WizardStatus.ready,
    twinName: named ? 'Factory twin' : null,
  ),
  requestedTaskId: requestedTaskId,
);
