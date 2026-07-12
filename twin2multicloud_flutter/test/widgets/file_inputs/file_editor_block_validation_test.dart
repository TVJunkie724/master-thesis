import 'package:flutter/material.dart';
import 'package:flutter_code_editor/flutter_code_editor.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/deployer_artifact_validation.dart';
import 'package:twin2multicloud_flutter/widgets/file_inputs/file_editor_block.dart';

void main() {
  Widget subject({
    ValueChanged<String>? onValidate,
    bool isValidating = false,
    DeployerArtifactValidationFeedback? feedback,
  }) => MaterialApp(
    home: Scaffold(
      body: SizedBox(
        width: 800,
        child: FileEditorBlock(
          filename: 'config.json',
          description: 'Configuration',
          initialContent: '{}',
          onValidate: onValidate,
          isValidating: isValidating,
          validationFeedback: feedback,
          showHeader: false,
        ),
      ),
    ),
  );

  testWidgets('emits exact current editor content for validation', (
    tester,
  ) async {
    String? validatedContent;
    await tester.pumpWidget(
      subject(onValidate: (content) => validatedContent = content),
    );

    await tester.enterText(find.byType(CodeField), '{"device": 1}');
    await tester.tap(find.widgetWithText(FilledButton, 'Validate'));
    await tester.pump();

    expect(validatedContent, '{"device": 1}');
  });

  testWidgets('controlled busy state disables validation', (tester) async {
    await tester.pumpWidget(subject(onValidate: (_) {}, isValidating: true));

    final button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Validate'),
    );
    expect(button.onPressed, isNull);
    expect(find.text('Validating...'), findsOneWidget);
  });
}
