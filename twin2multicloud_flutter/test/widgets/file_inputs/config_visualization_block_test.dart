import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/file_inputs/config_visualization_block.dart';

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
              child: ConfigVisualizationBlock(
                filename: 'config_providers.json',
                description: 'Provider assignments',
                jsonContent: const {
                  'layer_1_provider': 'aws',
                  'layer_2_provider': 'gcp',
                }.toString(),
                visualContent:
                    ConfigVisualizationBlock.buildProvidersVisual(const {
                      'layer_1_provider': 'aws',
                      'layer_2_provider': 'gcp',
                      'layer_3_hot_provider': 'azure',
                    }),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pump();
  }

  testWidgets('stacks JSON and provider summary at compact width', (
    tester,
  ) async {
    await pumpBlock(tester, 560);

    expect(find.text('Layer Assignments'), findsOneWidget);
    expect(find.text('L1 Ingestion'), findsOneWidget);
    expect(find.text('AZURE'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('keeps split provider summary usable at wide width', (
    tester,
  ) async {
    await pumpBlock(tester, 1100);

    expect(find.text('config_providers.json'), findsOneWidget);
    expect(find.text('Layer Assignments'), findsOneWidget);
    expect(find.text('GCP'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
