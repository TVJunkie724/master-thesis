import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:twin2multicloud_flutter/app.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/config/runtime_composition.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/screens/dashboard_screen.dart';
import 'package:twin2multicloud_flutter/screens/settings_screen.dart';
import 'package:twin2multicloud_flutter/screens/twin_overview/twin_overview_screen.dart';
import 'package:twin2multicloud_flutter/screens/wizard/wizard_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final routes = <String, Type>{
    '/dashboard': DashboardScreen,
    '/settings': SettingsScreen,
    '/wizard': WizardScreen,
    '/wizard/demo-configured': WizardScreen,
    '/twins/demo-deployed/overview': TwinOverviewScreen,
  };

  for (final scenario in DemoScenario.values) {
    testWidgets(
      'offline ${scenario.name} demo renders every application route',
      (tester) async {
        tester.view.physicalSize = const Size(1440, 1000);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final runtime = AppRuntimeConfig.demo(demoScenario: scenario);
        final composition = await tester.runAsync(
          () => RuntimeComposition.bootstrap(runtime),
        );
        expect(composition, isNotNull);
        final resolvedComposition = composition!;
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              appRuntimeProvider.overrideWithValue(runtime),
              apiServiceProvider.overrideWithValue(
                resolvedComposition.managementApi,
              ),
              logStreamClientFactoryProvider.overrideWithValue(
                resolvedComposition.logStreamClientFactory,
              ),
              initialUserProvider.overrideWithValue(
                resolvedComposition.initialUser,
              ),
            ],
            child: const Twin2MultiCloudApp(),
          ),
        );
        await tester.pump(const Duration(milliseconds: 500));
        final router = GoRouter.of(
          tester.element(find.byType(DashboardScreen)),
        );

        for (final entry in routes.entries) {
          router.go(entry.key);
          await tester.pump();
          await tester.pump(const Duration(seconds: 1));

          expect(find.byType(entry.value), findsOneWidget);
          expect(find.textContaining('Offline demo'), findsOneWidget);
          if (entry.key == '/dashboard') {
            expect(find.text('Twin experiments'), findsOneWidget);
            expect(find.text('Import Twin'), findsOneWidget);
            expect(find.text('New Twin'), findsOneWidget);
            expect(find.byType(FilterChip), findsNothing);
            expect(find.byType(DataTable), findsNothing);
            expect(find.text('Pricing readiness'), findsNothing);
            expect(find.text('Est. Cost'), findsNothing);
          }
          expect(tester.takeException(), isNull);
        }

        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump();
      },
    );
  }

  testWidgets('new twin enters the credential-free wizard directly', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final runtime = AppRuntimeConfig.demo(demoScenario: DemoScenario.showcase);
    final composition = await tester.runAsync(
      () => RuntimeComposition.bootstrap(runtime),
    );
    expect(composition, isNotNull);
    final resolvedComposition = composition!;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          appRuntimeProvider.overrideWithValue(runtime),
          apiServiceProvider.overrideWithValue(
            resolvedComposition.managementApi,
          ),
          logStreamClientFactoryProvider.overrideWithValue(
            resolvedComposition.logStreamClientFactory,
          ),
          initialUserProvider.overrideWithValue(
            resolvedComposition.initialUser,
          ),
        ],
        child: const Twin2MultiCloudApp(),
      ),
    );
    await tester.pump(const Duration(milliseconds: 500));

    await tester.tap(find.widgetWithText(FilledButton, 'New Twin'));
    await tester.pumpAndSettle(const Duration(milliseconds: 200));

    expect(find.byType(WizardScreen), findsOneWidget);
    expect(find.text('Set Up Cloud Credentials'), findsNothing);
    expect(tester.takeException(), isNull);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
  });
}
