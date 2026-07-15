import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/wizard_config_requests.dart';
import 'package:twin2multicloud_flutter/screens/wizard/wizard_screen.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

final class _MockApiService extends Mock implements ApiService {}

void main() {
  setUpAll(() => registerFallbackValue(const TwinConfigUpdateRequest()));

  testWidgets('Save & Leave navigates only after confirmed persistence', (
    tester,
  ) async {
    final api = _MockApiService();
    final persistence = Completer<Map<String, dynamic>>();
    when(
      () => api.createTwin('Factory twin'),
    ).thenAnswer((_) async => {'id': 'twin-1'});
    when(
      () => api.updateTwinConfigRequest('twin-1', any()),
    ).thenAnswer((_) => persistence.future);
    final harness = await _pumpWizard(tester, api);

    await tester.tap(find.byTooltip('Close'));
    await tester.pumpAndSettle();
    expect(find.text('Leave Wizard?'), findsOneWidget);
    expect(find.text('Dashboard destination'), findsNothing);

    await tester.tap(find.widgetWithText(FilledButton, 'Save & Leave'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(WizardView), findsOneWidget);
    expect(find.text('Dashboard destination'), findsNothing);
    verify(() => api.createTwin('Factory twin')).called(1);
    verify(() => api.updateTwinConfigRequest('twin-1', any())).called(1);

    persistence.complete({'twin_state': 'draft'});
    await _pumpUntil(
      tester,
      () =>
          harness.bloc.state.status == WizardStatus.ready &&
          !harness.bloc.state.hasUnsavedChanges,
      'wizard save success',
      diagnostic: () => harness.bloc.state.toString(),
    );
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Dashboard destination'), findsOneWidget);
  });

  testWidgets('failed exit save clears the pending navigation intent', (
    tester,
  ) async {
    final api = _MockApiService();
    when(
      () => api.createTwin('Factory twin'),
    ).thenThrow(Exception('transport unavailable'));
    final harness = await _pumpWizard(tester, api);

    await tester.tap(find.byTooltip('Close'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Save & Leave'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await _pumpUntil(
      tester,
      () => harness.bloc.state.errorMessage?.startsWith('Save failed:') == true,
      'wizard save failure',
      diagnostic: () => harness.bloc.state.toString(),
    );

    expect(find.byType(WizardView), findsOneWidget);
    expect(find.textContaining('Save failed:'), findsOneWidget);
    expect(find.text('Dashboard destination'), findsNothing);

    _stubSuccessfulSave(api);
    await tester.tap(find.widgetWithText(OutlinedButton, 'Save'));
    await _pumpUntil(
      tester,
      () =>
          harness.bloc.state.status == WizardStatus.ready &&
          !harness.bloc.state.hasUnsavedChanges,
      'manual wizard save success',
      diagnostic: () => harness.bloc.state.toString(),
    );

    expect(find.byType(WizardView), findsOneWidget);
    expect(find.text('Dashboard destination'), findsNothing);
    expect(
      find.text('Saved. Configuration reverted to draft.'),
      findsOneWidget,
    );
  });

  testWidgets('settings navigation uses the shared unsaved-exit contract', (
    tester,
  ) async {
    final api = _MockApiService();
    await _pumpWizard(tester, api);

    await tester.tap(find.byTooltip('Profile menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();
    expect(find.text('Leave Wizard?'), findsOneWidget);
    expect(find.text('Settings destination'), findsNothing);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(find.byType(WizardView), findsOneWidget);

    await tester.tap(find.byTooltip('Profile menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Discard Changes'));
    await tester.pumpAndSettle();
    expect(find.text('Settings destination'), findsOneWidget);
  });
}

void _stubSuccessfulSave(_MockApiService api) {
  when(
    () => api.createTwin('Factory twin'),
  ).thenAnswer((_) async => {'id': 'twin-1'});
  when(
    () => api.updateTwinConfigRequest('twin-1', any()),
  ).thenAnswer((_) async => {'twin_state': 'draft'});
}

Future<_WizardHarness> _pumpWizard(
  WidgetTester tester,
  _MockApiService api,
) async {
  tester.view.physicalSize = const Size(1200, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final bloc = WizardBloc(api: api);
  addTearDown(bloc.close);
  bloc.add(const WizardTwinNameChanged('Factory twin'));
  await bloc.stream.firstWhere((state) => state.twinName == 'Factory twin');

  final router = GoRouter(
    initialLocation: '/wizard',
    routes: [
      GoRoute(path: '/wizard', builder: (context, state) => const WizardView()),
      GoRoute(
        path: '/dashboard',
        builder: (context, state) =>
            const Scaffold(body: Text('Dashboard destination')),
      ),
      GoRoute(
        path: '/settings',
        builder: (context, state) =>
            const Scaffold(body: Text('Settings destination')),
      ),
      GoRoute(
        path: '/login',
        builder: (context, state) =>
            const Scaffold(body: Text('Login destination')),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      child: BlocProvider<WizardBloc>.value(
        value: bloc,
        child: MaterialApp.router(routerConfig: router),
      ),
    ),
  );
  await tester.pump();
  return _WizardHarness(bloc);
}

final class _WizardHarness {
  final WizardBloc bloc;

  const _WizardHarness(this.bloc);
}

Future<void> _pumpUntil(
  WidgetTester tester,
  bool Function() condition,
  String expectation, {
  String Function()? diagnostic,
}) async {
  for (var attempt = 0; attempt < 40; attempt++) {
    await tester.pump(const Duration(milliseconds: 50));
    if (condition()) return;
  }
  final details = diagnostic == null ? '' : ' Last state: ${diagnostic()}';
  fail('Timed out waiting for $expectation.$details');
}
