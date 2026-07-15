import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/step3/step3_glb_upload_card.dart';

void main() {
  Widget buildWidget(Widget child) {
    return MaterialApp(home: Scaffold(body: child));
  }

  group('Step3GlbUploadCard', () {
    testWidgets('renders upload action when no GLB is uploaded', (
      tester,
    ) async {
      var uploadTapped = false;

      await tester.pumpWidget(
        buildWidget(
          Step3GlbUploadCard(
            isUploaded: false,
            onDelete: () {},
            onUpload: () => uploadTapped = true,
          ),
        ),
      );

      expect(find.text('scene.glb'), findsOneWidget);
      expect(find.text('Upload 3D model for visualization'), findsOneWidget);
      expect(find.text('Upload GLB'), findsOneWidget);
      expect(find.byTooltip('Delete GLB'), findsNothing);

      await tester.tap(find.text('Upload GLB'));

      expect(uploadTapped, isTrue);
    });

    testWidgets('renders delete action when a GLB is uploaded', (tester) async {
      var deleteTapped = false;

      await tester.pumpWidget(
        buildWidget(
          Step3GlbUploadCard(
            isUploaded: true,
            onDelete: () => deleteTapped = true,
            onUpload: () {},
          ),
        ),
      );

      expect(find.text('scene.glb'), findsOneWidget);
      expect(find.text('3D model uploaded'), findsOneWidget);
      expect(find.text('Upload GLB'), findsNothing);
      expect(find.byTooltip('Delete GLB'), findsOneWidget);

      await tester.tap(find.byTooltip('Delete GLB'));

      expect(deleteTapped, isTrue);
    });

    testWidgets('disables file commands while a GLB command is active', (
      tester,
    ) async {
      var uploadTapped = false;

      await tester.pumpWidget(
        buildWidget(
          Step3GlbUploadCard(
            isUploaded: false,
            isBusy: true,
            onDelete: () {},
            onUpload: () => uploadTapped = true,
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Upload GLB'), findsNothing);
      expect(find.byTooltip('Delete GLB'), findsNothing);
      expect(uploadTapped, isFalse);
    });
  });
}
