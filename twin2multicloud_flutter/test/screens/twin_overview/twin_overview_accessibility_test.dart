import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:twin2multicloud_flutter/app.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/config/runtime_composition.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/screens/dashboard_screen.dart';
import 'package:twin2multicloud_flutter/screens/twin_overview/twin_overview_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'compact demo exposes guarded destructive and sensitive-download dialogs',
    (tester) async {
      tester.view.physicalSize = const Size(1440, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final semantics = tester.ensureSemantics();

      const runtime = AppRuntimeConfig.demo();
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
      router.go('/twins/demo-deployed/overview');
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      tester.view.physicalSize = const Size(640, 900);
      await tester.pump();

      expect(find.byType(TwinOverviewScreen), findsOneWidget);
      expect(find.byTooltip('Toggle theme'), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp('Telemetry trace')), findsOneWidget);
      expect(tester.takeException(), isNull);

      final destroy = find.text('DESTROY');
      await tester.ensureVisible(destroy);
      await tester.tap(destroy);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      final confirmDestroy = find.byKey(const Key('confirm-destroy'));
      expect(tester.widget<FilledButton>(confirmDestroy).onPressed, isNull);
      await tester.tap(find.byKey(const Key('acknowledge-destroy')));
      await tester.pump();
      expect(tester.widget<FilledButton>(confirmDestroy).onPressed, isNotNull);
      await tester.sendKeyEvent(LogicalKeyboardKey.escape);
      await tester.pumpAndSettle();
      expect(find.text('Destroy Cloud Resources?'), findsNothing);
      expect(tester.takeException(), isNull);

      final simulator = find.byKey(const Key('download-simulator'));
      await tester.ensureVisible(simulator);
      await tester.tap(simulator);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      final confirmDownload = find.byKey(
        const Key('confirm-simulator-download'),
      );
      expect(tester.widget<FilledButton>(confirmDownload).onPressed, isNull);
      await tester.tap(
        find.byKey(const Key('acknowledge-simulator-credentials')),
      );
      await tester.pump();
      expect(tester.widget<FilledButton>(confirmDownload).onPressed, isNotNull);
      await tester.sendKeyEvent(LogicalKeyboardKey.escape);
      await tester.pumpAndSettle();
      expect(find.text('Download simulator package?'), findsNothing);
      expect(tester.takeException(), isNull);

      semantics.dispose();
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );
}
