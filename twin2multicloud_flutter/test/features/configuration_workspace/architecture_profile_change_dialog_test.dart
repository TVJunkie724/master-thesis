import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/architecture_profile_change_dialog.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

import '../../fixtures/architecture_profile_fixtures.dart';
import '../../fixtures/architecture_wizard_fixture.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  testWidgets('renders only the server-returned invalidation categories', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1000, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });
    final state = architectureReadyWizardState().copyWith(
      architectureChangePhase: ArchitectureChangePhase.awaitingConfirmation,
      architectureChangePreview: ArchitectureProfileChangePreview.fromJson(
        architecturePreviewJson(),
      ),
    );
    final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
    addTearDown(bloc.close);

    await tester.pumpWidget(_app(bloc));

    expect(find.text('• Legacy field', skipOffstage: false), findsOneWidget);
    expect(find.text('• legacy.slot', skipOffstage: false), findsOneWidget);
    expect(find.text('• architecture', skipOffstage: false), findsOneWidget);
    expect(find.text('• cloud_access', skipOffstage: false), findsOneWidget);
    expect(find.text('• run-old', skipOffstage: false), findsOneWidget);
    expect(
      find.textContaining(fixtureDigestB),
      findsNothing,
      reason: 'the server digest is submitted but never presented as content',
    );
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Change profile'),
          )
          .onPressed,
      isNotNull,
    );
  });

  testWidgets(
    'submitting state prevents dismissal and duplicate confirmation',
    (tester) async {
      final state = architectureReadyWizardState().copyWith(
        architectureChangePhase: ArchitectureChangePhase.submitting,
        architectureChangePreview: ArchitectureProfileChangePreview.fromJson(
          architecturePreviewJson(),
        ),
      );
      final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
      addTearDown(bloc.close);

      await tester.pumpWidget(_app(bloc));

      final popScope = tester.widget<PopScope<Object?>>(
        find.byWidgetPredicate((widget) => widget is PopScope<Object?>),
      );
      expect(popScope.canPop, isFalse);
      expect(
        tester
            .widget<TextButton>(find.widgetWithText(TextButton, 'Cancel'))
            .onPressed,
        isNull,
      );
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull,
      );
    },
  );

  testWidgets('mutation error remains visible without changing selection', (
    tester,
  ) async {
    final initial = architectureReadyWizardState().copyWith(
      architectureChangePhase: ArchitectureChangePhase.error,
      architectureChangePreview: ArchitectureProfileChangePreview.fromJson(
        architecturePreviewJson(),
      ),
      architectureChangeError: 'Safe mutation failure',
    );
    final bloc = WizardBloc(api: _MockManagementApi(), initialState: initial);
    addTearDown(bloc.close);

    await tester.pumpWidget(_app(bloc));

    expect(find.text('Change architecture profile?'), findsOneWidget);
    expect(find.text('Safe mutation failure'), findsOneWidget);
    expect(bloc.state.architectureSelection, initial.architectureSelection);
    expect(
      tester
          .widget<TextButton>(find.widgetWithText(TextButton, 'Cancel'))
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('Escape closes the safe dialog through cancellation', (
    tester,
  ) async {
    final state = architectureReadyWizardState().copyWith(
      architectureChangePhase: ArchitectureChangePhase.awaitingConfirmation,
      architectureChangePreview: ArchitectureProfileChangePreview.fromJson(
        architecturePreviewJson(),
      ),
    );
    final bloc = WizardBloc(api: _MockManagementApi(), initialState: state);
    final triggerFocusNode = FocusNode();
    addTearDown(bloc.close);
    addTearDown(triggerFocusNode.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: BlocProvider.value(
          value: bloc,
          child: Builder(
            builder: (context) => Scaffold(
              body: FilledButton(
                focusNode: triggerFocusNode,
                autofocus: true,
                onPressed: () => showDialog<void>(
                  context: context,
                  barrierDismissible: false,
                  builder: (_) => BlocProvider.value(
                    value: bloc,
                    child: const ArchitectureProfileChangeDialog(),
                  ),
                ),
                child: const Text('Open profile change'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open profile change'));
    await tester.pumpAndSettle();
    expect(find.text('Change architecture profile?'), findsOneWidget);

    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();

    expect(find.text('Change architecture profile?'), findsNothing);
    expect(find.text('Open profile change'), findsOneWidget);
    expect(triggerFocusNode.hasFocus, isTrue);
    expect(bloc.state.architectureChangePhase, ArchitectureChangePhase.idle);
    expect(bloc.state.architectureChangePreview, isNull);
  });
}

Widget _app(WizardBloc bloc) => MaterialApp(
  home: Scaffold(
    body: BlocProvider.value(
      value: bloc,
      child: const ArchitectureProfileChangeDialog(),
    ),
  ),
);
