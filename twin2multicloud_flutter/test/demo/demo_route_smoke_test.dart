import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:twin2multicloud_flutter/app.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/config/runtime_composition.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/screens/dashboard_screen.dart';
import 'package:twin2multicloud_flutter/screens/pricing_review/pricing_review_screen.dart';
import 'package:twin2multicloud_flutter/screens/settings_screen.dart';
import 'package:twin2multicloud_flutter/screens/twin_overview/twin_overview_screen.dart';
import 'package:twin2multicloud_flutter/screens/wizard/wizard_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final routes = <String, Type>{
    '/dashboard': DashboardScreen,
    '/settings': SettingsScreen,
    '/pricing-review': PricingReviewScreen,
    '/wizard': WizardScreen,
    '/wizard/demo-configured': WizardScreen,
    '/twins/demo-deployed/overview': TwinOverviewScreen,
  };

  testWidgets('offline demo renders every application route', (tester) async {
    tester.view.physicalSize = const Size(1440, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    const runtime = AppRuntimeConfig(mode: AppMode.demo);
    final composition = await RuntimeComposition.bootstrap(runtime);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          appRuntimeProvider.overrideWithValue(runtime),
          apiServiceProvider.overrideWithValue(composition.managementApi),
          logStreamClientFactoryProvider.overrideWithValue(
            composition.logStreamClientFactory,
          ),
          initialUserProvider.overrideWithValue(composition.initialUser),
        ],
        child: const Twin2MultiCloudApp(),
      ),
    );
    await tester.pump(const Duration(milliseconds: 500));
    final router = GoRouter.of(tester.element(find.byType(DashboardScreen)));

    for (final entry in routes.entries) {
      router.go(entry.key);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));

      expect(find.byType(entry.value), findsOneWidget);
      expect(find.textContaining('Offline demo'), findsOneWidget);
      expect(tester.takeException(), isNull);
    }

    await tester.pumpWidget(const SizedBox.shrink());
  });
}
