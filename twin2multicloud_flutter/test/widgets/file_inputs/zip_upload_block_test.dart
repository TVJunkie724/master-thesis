import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/file_inputs/zip_upload_block.dart';

void main() {
  Widget buildWidget({
    String? selectedFileName,
    bool isUploading = false,
    bool hasError = false,
    Future<void> Function()? onSelect,
    VoidCallback? onClear,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: ZipUploadBlock(
          selectedFileName: selectedFileName,
          isUploading: isUploading,
          hasError: hasError,
          onSelect: onSelect ?? () async {},
          onClear: onClear ?? () {},
        ),
      ),
    );
  }

  testWidgets('renders an empty presentation-only selector', (tester) async {
    await tester.pumpWidget(buildWidget());

    expect(
      find.text('Drop project.zip here or click to upload'),
      findsOneWidget,
    );
    expect(find.text('Supports .zip files only'), findsOneWidget);
    expect(find.text('Clear'), findsNothing);
  });

  testWidgets('delegates selection without owning feature state', (
    tester,
  ) async {
    var selected = false;
    await tester.pumpWidget(buildWidget(onSelect: () async => selected = true));

    await tester.tap(find.text('Drop project.zip here or click to upload'));
    await tester.pump();

    expect(selected, isTrue);
  });

  testWidgets('renders selected success and error states', (tester) async {
    await tester.pumpWidget(buildWidget(selectedFileName: 'project.zip'));
    expect(find.text('project.zip'), findsOneWidget);
    expect(find.text('Extraction complete'), findsOneWidget);
    expect(find.text('Clear'), findsOneWidget);

    await tester.pumpWidget(
      buildWidget(selectedFileName: 'project.zip', hasError: true),
    );
    expect(find.text('Extraction complete with errors'), findsOneWidget);
  });

  testWidgets('disables commands and shows progress during upload', (
    tester,
  ) async {
    var selected = false;
    await tester.pumpWidget(
      buildWidget(
        selectedFileName: 'project.zip',
        isUploading: true,
        onSelect: () async => selected = true,
      ),
    );

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Extracting and validating...'), findsOneWidget);
    expect(find.text('Clear'), findsNothing);
    final detector = tester.widget<GestureDetector>(
      find.byType(GestureDetector).first,
    );
    expect(detector.onTap, isNull);
    expect(selected, isFalse);
  });
}
