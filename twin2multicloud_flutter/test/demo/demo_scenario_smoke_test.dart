import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/app.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/config/runtime_composition.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('empty and degraded scenarios expose their diagnostic states', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final expectations = {
      DemoScenario.empty: 'No digital twins yet',
      DemoScenario.degraded: 'Warehouse Twin',
    };

    for (final entry in expectations.entries) {
      final runtime = AppRuntimeConfig(
        mode: AppMode.demo,
        demoScenario: entry.key,
      );
      final composition = await RuntimeComposition.bootstrap(runtime);
      await tester.pumpWidget(
        ProviderScope(
          key: ValueKey(entry.key),
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

      expect(find.text(entry.value), findsOneWidget);
      expect(find.textContaining('Offline demo'), findsOneWidget);
      expect(tester.takeException(), isNull);
    }

    await tester.pumpWidget(const SizedBox.shrink());
  });
}
