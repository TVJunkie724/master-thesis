import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/app.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/config/runtime_composition.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('demo boots directly into the dashboard without a backend', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 900);
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
    await tester.pumpAndSettle();

    expect(find.textContaining('Offline demo'), findsOneWidget);
    expect(find.text('Twin2MultiCloud'), findsOneWidget);
    expect(find.text('Login'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
