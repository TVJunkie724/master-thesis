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

  testWidgets('empty inventory exposes exactly the two portable Twin actions', (
    tester,
  ) async {
    await _pumpDashboard(tester, api: api, twins: const []);

    expect(find.text('Digital Twin research inventory'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, 'Import Twin'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'New Twin'), findsOneWidget);
    expect(find.text('Pricing readiness'), findsNothing);
    expect(find.text('Est. Cost'), findsNothing);
    expect(find.text('Total Twins'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('destroyed Twin retains exact named row actions', (tester) async {
    await _pumpDashboard(
      tester,
      api: api,
      twins: [_twin(name: 'Destroyed Twin', state: 'destroyed')],
    );

    expect(find.byTooltip('Open Destroyed Twin'), findsOneWidget);
    expect(find.byTooltip('Duplicate Destroyed Twin'), findsOneWidget);
    expect(find.byTooltip('Export Destroyed Twin'), findsOneWidget);
    expect(find.byTooltip('Delete Destroyed Twin'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

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

    await tester.tap(find.byTooltip('Duplicate Source Twin'));
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
        expect(find.byTooltip('Edit Compact Twin'), findsOneWidget);
        expect(find.byTooltip('Duplicate Compact Twin'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}

Future<void> _pumpDashboard(
  WidgetTester tester, {
  required _MockManagementApi api,
  required List<Twin> twins,
  Size size = const Size(1200, 900),
  double textScale = 1,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  when(() => api.getTwins()).thenAnswer((_) async => twins);
  final router = GoRouter(
    initialLocation: '/dashboard',
    routes: [
      GoRoute(
        path: '/dashboard',
        builder: (context, state) => const DashboardScreen(),
      ),
      GoRoute(
        path: '/wizard/:twinId',
        builder: (context, state) => Scaffold(
          body: Text('Wizard destination ${state.pathParameters['twinId']}'),
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
