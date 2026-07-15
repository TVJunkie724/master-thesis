import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/screens/login_screen.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('development exposes one deliberate local sign-in action', (
    tester,
  ) async {
    final api = _MockManagementApi();
    await _pump(
      tester,
      runtime: AppRuntimeConfig.development(
        managementApiBaseUri: Uri.parse('http://management.test'),
        developmentAuthToken: 'local-token',
      ),
      api: api,
    );

    expect(find.text('Continue in local development'), findsOneWidget);
    expect(find.text('Sign in with UIBK'), findsNothing);
    expect(find.text('Sign in with Google'), findsNothing);

    await tester.tap(find.text('Continue in local development'));
    await tester.pumpAndSettle();

    expect(find.text('Authenticated destination'), findsOneWidget);
    verify(() => api.setToken('local-token')).called(1);
  });

  testWidgets('production is fail-closed without a development bypass', (
    tester,
  ) async {
    await _pump(
      tester,
      runtime: AppRuntimeConfig.production(
        managementApiBaseUri: Uri.parse('https://management.test'),
      ),
      api: _MockManagementApi(),
    );

    expect(find.text('Continue in local development'), findsNothing);
    expect(find.text('Sign in with UIBK'), findsOneWidget);
    expect(find.text('Sign in with Google'), findsOneWidget);
    expect(
      find.text('Production sign-in is not configured in this build.'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Sign in with UIBK'),
          )
          .onPressed,
      isNull,
    );
  });

  testWidgets('demo login surface cannot expose network sign-in controls', (
    tester,
  ) async {
    await _pump(
      tester,
      runtime: const AppRuntimeConfig.demo(),
      api: _MockManagementApi(),
    );

    expect(find.text('Continue in local development'), findsNothing);
    expect(find.text('Sign in with UIBK'), findsNothing);
    expect(find.text('Sign in with Google'), findsNothing);
    expect(find.textContaining('offline demo'), findsOneWidget);
  });

  testWidgets('compact dark layout wraps without exposing runtime values', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(640, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    const token = 'private-local-token';
    const origin = 'http://management.internal.test';

    await _pump(
      tester,
      runtime: AppRuntimeConfig.development(
        managementApiBaseUri: Uri.parse(origin),
        developmentAuthToken: token,
      ),
      api: _MockManagementApi(),
      theme: ThemeData.dark(useMaterial3: true),
      textScaler: const TextScaler.linear(1.5),
    );

    expect(tester.takeException(), isNull);
    final visibleText = tester
        .widgetList<Text>(find.byType(Text))
        .map((widget) => widget.data ?? '')
        .join(' ');
    expect(visibleText, isNot(contains(token)));
    expect(visibleText, isNot(contains(origin)));
    expect(find.text('Continue in local development'), findsOneWidget);
  });
}

Future<void> _pump(
  WidgetTester tester, {
  required AppRuntimeConfig runtime,
  required ManagementApi api,
  ThemeData? theme,
  TextScaler textScaler = TextScaler.noScaling,
}) async {
  final router = GoRouter(
    initialLocation: '/login',
    routes: [
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
      GoRoute(
        path: '/dashboard',
        builder: (_, _) => const Scaffold(
          body: Center(child: Text('Authenticated destination')),
        ),
      ),
    ],
  );
  addTearDown(router.dispose);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appRuntimeProvider.overrideWithValue(runtime),
        apiServiceProvider.overrideWithValue(api),
      ],
      child: MaterialApp.router(
        theme: theme,
        routerConfig: router,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: textScaler),
          child: child ?? const SizedBox.shrink(),
        ),
      ),
    ),
  );
  await tester.pump();
}
