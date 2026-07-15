import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/file_inputs/config_json_visualization_block.dart';

void main() {
  Future<void> pumpBlock(WidgetTester tester, double width) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = Size(width, 900);
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: ConfigJsonVisualizationBlock(
                twinName: 'factory-twin',
                mode: 'production',
                hotStorageDays: 30,
                coldStorageDays: 365,
                onTwinNameChanged: (_) {},
                onValidate: (_) {},
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pump();
  }

  testWidgets('stacks JSON and summary without overflow at compact width', (
    tester,
  ) async {
    await pumpBlock(tester, 560);

    expect(find.text('Configuration Summary'), findsOneWidget);
    expect(find.text('Read-only'), findsOneWidget);
    expect(find.text('365 days'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('keeps JSON and summary usable at wide width', (tester) async {
    await pumpBlock(tester, 1100);

    expect(find.text('Configuration Summary'), findsOneWidget);
    expect(find.text('Read-only'), findsOneWidget);
    expect(find.text('factory-twin'), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
