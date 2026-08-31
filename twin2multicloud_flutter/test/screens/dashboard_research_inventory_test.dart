import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';
import 'package:twin2multicloud_flutter/models/twin_transfer.dart';
import 'package:twin2multicloud_flutter/models/user.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/screens/dashboard_screen.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  late _MockManagementApi api;

  setUp(() => api = _MockManagementApi());

  testWidgets('empty inventory exposes one primary experiment action', (
    tester,
  ) async {
    await _pumpDashboard(tester, api: api, twins: const []);

    expect(find.text('Twin experiments'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Import Twin'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'New Twin'), findsOneWidget);
    expect(find.text('No Twin experiments yet'), findsOneWidget);
    expect(find.text('Pricing readiness'), findsNothing);
    expect(find.text('Est. Cost'), findsNothing);
    expect(find.text('Total Twins'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'destroyed Twin exposes continuation and compact management menu',
    (tester) async {
      await _pumpDashboard(
        tester,
        api: api,
        twins: [_twin(name: 'Destroyed Twin', state: 'destroyed')],
      );

      expect(
        find.widgetWithText(OutlinedButton, 'Open lifecycle'),
        findsOneWidget,
      );
      expect(find.byTooltip('More actions for Destroyed Twin'), findsOneWidget);
      expect(find.byIcon(Icons.copy_outlined), findsNothing);

      await tester.tap(find.byTooltip('More actions for Destroyed Twin'));
      await tester.pumpAndSettle();

      expect(find.text('Duplicate'), findsOneWidget);
      expect(find.text('Export'), findsOneWidget);
      expect(find.text('Delete'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('duplicate name submits on Enter and opens the new draft', (
    tester,
  ) async {
    final request = TwinDuplicateRequest(name: 'Entered copy');
    when(() => api.duplicateTwin('source', request)).thenAnswer(
      (_) async => _twin(id: 'copy-id', name: 'Entered copy', state: 'draft'),
    );
    await _pumpDashboard(
      tester,
      api: api,
      twins: [_twin(id: 'source', name: 'Source Twin', state: 'draft')],
    );

    await tester.tap(find.byTooltip('More actions for Source Twin'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Duplicate'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Twin name'),
      'Entered copy',
    );
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();

    verify(() => api.duplicateTwin('source', request)).called(1);
    expect(find.text('Wizard destination copy-id'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('draft and non-draft continuations preserve their routes', (
    tester,
  ) async {
    await _pumpDashboard(
      tester,
      api: api,
      twins: [
        _twin(id: 'draft-id', name: 'Draft Twin', state: 'draft'),
        _twin(id: 'configured-id', name: 'Ready Twin', state: 'configured'),
      ],
    );

    await tester.tap(
      find.widgetWithText(OutlinedButton, 'Continue configuration'),
    );
    await tester.pumpAndSettle();
    expect(find.text('Wizard destination draft-id'), findsOneWidget);

    final router = GoRouter.of(
      tester.element(find.text('Wizard destination draft-id')),
    );
    router.go('/dashboard');
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(OutlinedButton, 'Open lifecycle'));
    await tester.pumpAndSettle();
    expect(find.text('Lifecycle destination configured-id'), findsOneWidget);
  });

  testWidgets('deployed Twin deletion is blocked with lifecycle guidance', (
    tester,
  ) async {
    await _pumpDashboard(
      tester,
      api: api,
      twins: [_twin(id: 'live', name: 'Live Twin', state: 'deployed')],
    );

    await tester.tap(find.byTooltip('More actions for Live Twin'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();

    expect(find.text('Cannot delete'), findsOneWidget);
    expect(
      find.textContaining('Open lifecycle and run Destroy first'),
      findsOneWidget,
    );
    verifyNever(() => api.deleteTwin(any()));
  });

  testWidgets('cloud access utility opens settings without a profile claim', (
    tester,
  ) async {
    await _pumpDashboard(tester, api: api, twins: const []);

    expect(find.byTooltip('Open cloud access'), findsOneWidget);
    expect(find.byTooltip('Open profile and CloudConnections'), findsNothing);
    await tester.tap(find.byTooltip('Open cloud access'));
    await tester.pumpAndSettle();

    expect(find.text('Cloud access destination'), findsOneWidget);
  });

  testWidgets('load failure is safe and retryable', (tester) async {
    when(() => api.getTwins()).thenThrow(Exception('Management unavailable'));
    await _pumpDashboard(tester, api: api, twins: null);

    expect(find.text('Failed to load Twin experiments'), findsOneWidget);
    expect(find.text('An unexpected error occurred'), findsOneWidget);
    expect(find.textContaining('Management unavailable'), findsNothing);
    expect(find.widgetWithText(OutlinedButton, 'Retry'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  for (final textScale in [1.5, 2.0]) {
    testWidgets(
      'compact inventory remains reachable at ${(textScale * 100).toInt()} percent text',
      (tester) async {
        await _pumpDashboard(
          tester,
          api: api,
          twins: [_twin(name: 'Compact Twin', state: 'draft')],
          size: const Size(640, 1200),
          textScale: textScale,
        );

        expect(find.text('Import Twin'), findsOneWidget);
        expect(find.text('Continue configuration'), findsOneWidget);
        expect(find.byTooltip('More actions for Compact Twin'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}

Future<void> _pumpDashboard(
  WidgetTester tester, {
  required _MockManagementApi api,
  required List<Twin>? twins,
  Size size = const Size(1200, 900),
  double textScale = 1,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  if (twins != null) {
    when(() => api.getTwins()).thenAnswer((_) async => twins);
  }
  final router = GoRouter(
    initialLocation: '/dashboard',
    routes: [
      GoRoute(
        path: '/dashboard',
        builder: (context, state) => const DashboardScreen(),
      ),
      GoRoute(
        path: '/settings',
        builder: (context, state) =>
            const Scaffold(body: Text('Cloud access destination')),
      ),
      GoRoute(
        path: '/wizard',
        builder: (context, state) =>
            const Scaffold(body: Text('New wizard destination')),
      ),
      GoRoute(
        path: '/wizard/:twinId',
        builder: (context, state) => Scaffold(
          body: Text('Wizard destination ${state.pathParameters['twinId']}'),
        ),
      ),
      GoRoute(
        path: '/twins/:twinId/overview',
        builder: (context, state) => Scaffold(
          body: Text('Lifecycle destination ${state.pathParameters['twinId']}'),
        ),
      ),
    ],
  );
  addTearDown(router.dispose);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appRuntimeProvider.overrideWithValue(
          AppRuntimeConfig.demo(demoScenario: DemoScenario.empty),
        ),
        apiServiceProvider.overrideWithValue(api),
        initialUserProvider.overrideWithValue(
          User(id: 'demo-user', email: 'demo@example.test'),
        ),
      ],
      child: MaterialApp.router(
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!,
        ),
        routerConfig: router,
      ),
    ),
  );
  await tester.pump();
  await tester.pumpAndSettle();
}

Twin _twin({String? id, required String name, required String state}) => Twin(
  id: id ?? name.toLowerCase().replaceAll(' ', '-'),
  name: name,
  state: state,
  createdAt: DateTime.utc(2026, 8, 27),
  updatedAt: DateTime.utc(2026, 8, 27),
  destroyedAt: state == 'destroyed' ? DateTime.utc(2026, 8, 27) : null,
);
