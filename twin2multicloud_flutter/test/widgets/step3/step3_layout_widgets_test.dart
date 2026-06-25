import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/step3/step3_layout_widgets.dart';

void main() {
  Widget buildWidget(Widget child) {
    return MaterialApp(home: Scaffold(body: child));
  }

  group('Step3 layout widgets', () {
    testWidgets('quick upload section renders zip upload entry point', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(
          const Step3QuickUploadSection(uploadBlock: Text('ZIP Upload Block')),
        ),
      );

      expect(find.text('Quick Upload'), findsOneWidget);
      expect(
        find.text('Import an existing deployment project'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Upload a complete project ZIP'),
        findsOneWidget,
      );
      expect(find.text('ZIP Upload Block'), findsOneWidget);
    });

    testWidgets('manual separator renders label', (tester) async {
      await tester.pumpWidget(buildWidget(const Step3ManualSeparator()));

      expect(find.text('Or configure manually'), findsOneWidget);
    });

    testWidgets('no result message guides user back to Step 2', (tester) async {
      await tester.pumpWidget(buildWidget(const Step3NoResultMessage()));

      expect(find.text('No Optimization Result'), findsOneWidget);
      expect(
        find.text('Please complete Step 2 (Optimizer) first.'),
        findsOneWidget,
      );
    });

    testWidgets('flow header shows data flow column when enabled', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(
          const Step3FlowHeader(showFlowchart: true, flowchartWidth: 320),
        ),
      );

      expect(find.text('Data Flow'), findsOneWidget);
      expect(find.text('Configuration Files'), findsOneWidget);
    });

    testWidgets('layer row switches between compact and flow layouts', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(
          const Step3LayerRow(
            showFlowchart: true,
            flowchartWidth: 320,
            flowchart: Text('Flowchart'),
            editors: [Text('Editor')],
          ),
        ),
      );

      expect(find.text('Flowchart'), findsOneWidget);
      expect(find.text('Editor'), findsOneWidget);

      await tester.pumpWidget(
        buildWidget(
          const Step3LayerRow(
            showFlowchart: false,
            flowchartWidth: 320,
            flowchart: Text('Hidden flowchart'),
            editors: [Text('Compact editor')],
          ),
        ),
      );

      expect(find.text('Hidden flowchart'), findsNothing);
      expect(find.text('Compact editor'), findsOneWidget);
    });
  });
}
