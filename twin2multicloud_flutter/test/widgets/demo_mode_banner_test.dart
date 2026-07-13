import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/widgets/demo_mode_banner.dart';

void main() {
  for (final scenario in DemoScenario.values) {
    testWidgets('renders ${scenario.name} without overflow at compact width', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(320, 180);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: DemoModeBanner(scenario: scenario)),
        ),
      );

      expect(find.textContaining('Offline demo'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}
