import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/code_viewer_dialog.dart';

void main() {
  testWidgets('names read-only artifact content for assistive technology', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => TextButton(
            onPressed: () => showCodeViewerDialog(
              context,
              title: 'Deployment Logs',
              code: 'Deployment completed.',
              filename: 'deployment_logs.txt',
            ),
            child: const Text('Open logs'),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open logs'));
    await tester.pumpAndSettle();

    final node = tester.getSemantics(
      find.bySemanticsLabel('Deployment Logs content'),
    );
    final data = node.getSemanticsData();
    expect(data.flagsCollection.isTextField, isTrue);
    expect(data.flagsCollection.isReadOnly, isTrue);
    semantics.dispose();
  });
}
