import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/deployer_artifact_validation.dart';
import 'package:twin2multicloud_flutter/widgets/file_inputs/artifact_validation_feedback_view.dart';

void main() {
  Widget subject({
    DeployerArtifactValidationFeedback? feedback,
    bool isValidating = false,
  }) => MaterialApp(
    home: Scaffold(
      body: SizedBox(
        width: 320,
        child: ArtifactValidationFeedbackView(
          feedback: feedback,
          isValidating: isValidating,
        ),
      ),
    ),
  );

  testWidgets('renders controlled success and failure text', (tester) async {
    await tester.pumpWidget(
      subject(
        feedback: const DeployerArtifactValidationFeedback(
          valid: true,
          message: 'Configuration valid',
        ),
      ),
    );
    expect(find.text('Configuration valid'), findsOneWidget);
    expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);

    await tester.pumpWidget(
      subject(
        feedback: const DeployerArtifactValidationFeedback(
          valid: false,
          message: 'Invalid provider configuration',
        ),
      ),
    );
    expect(find.text('Invalid provider configuration'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsOneWidget);
  });

  testWidgets('renders bounded busy state without overflow', (tester) async {
    await tester.binding.setSurfaceSize(const Size(360, 160));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(subject(isValidating: true));

    expect(find.text('Validating...'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
