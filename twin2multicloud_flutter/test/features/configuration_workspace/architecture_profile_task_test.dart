import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/architecture_profile_choice.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/architecture_profile_task.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/logical_profile_flow.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

import '../../fixtures/architecture_profile_fixtures.dart';
import '../../fixtures/architecture_wizard_fixture.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  testWidgets('renders the truthful empty catalog and historical selection', (
    tester,
  ) async {
    final state = architectureReadyWizardState().copyWith(
      architectureCatalogPhase: ArchitectureCatalogPhase.empty,
      architectureProfiles: const [],
      architectureDetailPhase: ArchitectureDetailPhase.idle,
      clearArchitectureProfileDetail: true,
    );
    final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
    addTearDown(bloc.close);

    await tester.pumpWidget(_app(bloc));

    expect(find.text('Historical architecture (read-only)'), findsOneWidget);
    expect(
      find.text('No active architecture profile is available'),
      findsOneWidget,
    );
    expect(find.widgetWithText(OutlinedButton, 'Retry'), findsOneWidget);
    expect(find.byType(ArchitectureProfileChoice), findsNothing);
  });

  testWidgets('refresh keeps the loaded catalog and detail visible', (
    tester,
  ) async {
    final state = architectureReadyWizardState().copyWith(
      architectureCatalogPhase: ArchitectureCatalogPhase.loading,
      architectureDetailPhase: ArchitectureDetailPhase.loading,
    );
    final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
    addTearDown(bloc.close);

    await tester.pumpWidget(_app(bloc));

    expect(find.byType(ArchitectureProfileChoice), findsOneWidget);
    expect(find.byType(LogicalProfileFlow), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsNWidgets(2));
  });

  testWidgets('catalog error exposes one safe retry action', (tester) async {
    final state = architectureReadyWizardState().copyWith(
      architectureCatalogPhase: ArchitectureCatalogPhase.error,
      architectureCatalogError: 'Safe catalog failure',
    );
    final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
    addTearDown(bloc.close);

    await tester.pumpWidget(_app(bloc));

    expect(
      find.text('Architecture profiles could not be loaded'),
      findsOneWidget,
    );
    expect(find.text('Safe catalog failure'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, 'Retry'), findsOneWidget);
  });

  for (final width in [640.0, 719.0, 720.0, 959.0, 960.0, 1199.0, 1200.0]) {
    testWidgets('profile workflow has no overflow at width $width', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, 1800);
      tester.view.devicePixelRatio = 1;
      final bloc = WizardBloc(
        api: _MockManagementApi(),
        initialState: architectureReadyWizardState(),
      );
      addTearDown(bloc.close);
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });
      await tester.pumpWidget(_app(bloc, textScale: 2));
      await tester.pump();

      expect(
        find.byType(ArchitectureProfileChoice),
        findsOneWidget,
        reason: 'profile choice at width $width',
      );
      expect(find.byType(LogicalProfileFlow), findsOneWidget);
      expect(
        tester.takeException(),
        isNull,
        reason: 'overflow at width $width',
      );
    });
  }

  testWidgets('renders only declared edges and exposes graph controls', (
    tester,
  ) async {
    final state = architectureReadyWizardState(withExtensionSlot: false)
        .copyWith(
          architectureProfileDetail: ArchitectureProfileDetail.fromJson(
            architectureProfileDetailJson(
              withExtensionSlot: false,
              withFlow: true,
            ),
          ),
        );
    await _pumpTask(tester, state, width: 1200);

    expect(find.text('Overview'), findsOneWidget);
    expect(find.text('Components'), findsOneWidget);
    expect(find.byTooltip('Zoom in'), findsOneWidget);
    expect(find.text('Connections (1)'), findsOneWidget);
    await tester.tap(find.text('Connections (1)'));
    await tester.pumpAndSettle();
    expect(find.text('Ingestion → Storage'), findsOneWidget);

    await tester.tap(find.text('Components'));
    await tester.pumpAndSettle();
    expect(find.text('Connections (1)'), findsOneWidget);
  });

  testWidgets('compact projection labels declared targets without a canvas', (
    tester,
  ) async {
    final state = architectureReadyWizardState(withExtensionSlot: false)
        .copyWith(
          architectureProfileDetail: ArchitectureProfileDetail.fromJson(
            architectureProfileDetailJson(
              withExtensionSlot: false,
              withFlow: true,
            ),
          ),
        );
    await _pumpTask(tester, state, width: 719);

    expect(find.byTooltip('Zoom in'), findsNothing);
    expect(
      find.bySemanticsLabel(
        'Ingestion connects to Storage, edge-contract.telemetry',
      ),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('visiting Understand architecture acknowledges loaded detail', (
    tester,
  ) async {
    final state = architectureReadyWizardState().copyWith(
      architectureDetailAcknowledged: false,
    );
    final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
    addTearDown(bloc.close);
    final acknowledged = bloc.stream.firstWhere(
      (next) => next.architectureDetailAcknowledged,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BlocProvider.value(
            value: bloc,
            child: ArchitectureProfileTask(
              taskId: ConfigurationTaskId.understandArchitecture,
              onOpenTask: (_) {},
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect((await acknowledged).architectureWorkflowReady, isTrue);
  });

  testWidgets('focused profile row selects with keyboard activation', (
    tester,
  ) async {
    var selections = 0;
    final profile = ArchitectureProfileSummary.fromJson(
      architectureProfileSummaryJson(withExtensionSlot: false),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ArchitectureProfileChoice(
            profile: profile,
            selected: false,
            disabled: false,
            onSelect: () => selections++,
            onExpand: null,
          ),
        ),
      ),
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();

    expect(selections, 1);
    expect(
      find.bySemanticsLabel(
        'Fixture profile, version 2, not selected, 1 responsibilities, '
        '1 provider limitation(s)',
      ),
      findsOneWidget,
    );
  });

  for (final brightness in Brightness.values) {
    testWidgets('profile status is explicit in ${brightness.name} theme', (
      tester,
    ) async {
      final bloc = WizardBloc(
        api: _MockManagementApi(),
        initialState: architectureReadyWizardState(),
      );
      addTearDown(bloc.close);

      await tester.pumpWidget(_app(bloc, brightness: brightness));
      await tester.pump();

      expect(find.text('Active v2'), findsOneWidget);
      expect(find.byIcon(Icons.radio_button_checked), findsOneWidget);
      expect(
        find.bySemanticsLabel(
          'Fixture profile, version 2, selected, 1 responsibilities, '
          '1 provider limitation(s)',
        ),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    });
  }
}

Future<void> _pumpTask(
  WidgetTester tester,
  WizardState state, {
  required double width,
}) async {
  tester.view.physicalSize = Size(width, 1800);
  tester.view.devicePixelRatio = 1;
  final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
  addTearDown(bloc.close);
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
  await tester.pumpWidget(_app(bloc));
  await tester.pump();
}

Widget _app(
  WizardBloc bloc, {
  double textScale = 1,
  Brightness brightness = Brightness.light,
}) => MaterialApp(
  theme: ThemeData(brightness: brightness),
  home: Builder(
    builder: (context) => MediaQuery(
      data: MediaQuery.of(
        context,
      ).copyWith(textScaler: TextScaler.linear(textScale)),
      child: Scaffold(
        body: BlocProvider.value(
          value: bloc,
          child: ArchitectureProfileTask(
            taskId: ConfigurationTaskId.selectProfile,
            onOpenTask: (_) {},
          ),
        ),
      ),
    ),
  ),
);
