import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/widgets/cloud_connections/cloud_connection_import_dialog.dart';

void main() {
  for (final provider in CloudProvider.values) {
    testWidgets('returns a typed ${provider.label} import request', (
      tester,
    ) async {
      CloudConnectionImportRequest? captured;
      final extension = provider == CloudProvider.aws ? 'csv' : 'json';
      await _pumpLauncher(
        tester,
        provider: provider,
        pickFile: (_) async => PlatformFile(
          name: 'credentials.$extension',
          size: 3,
          bytes: Uint8List.fromList([1, 2, 3]),
        ),
        onResult: (request) => captured = request,
      );

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Display name'),
        '${provider.label} Administrator',
      );
      if (provider != CloudProvider.aws) {
        final label = provider == CloudProvider.azure
            ? 'Subscription ID'
            : 'Project ID';
        await tester.enterText(
          find.widgetWithText(TextFormField, label),
          'scope-1',
        );
      }
      final selectFile = find.byKey(const Key('select-cloud-credential-file'));
      await tester.ensureVisible(selectFile);
      await tester.pumpAndSettle();
      await tester.tap(selectFile);
      await tester.pumpAndSettle();
      expect(find.text('credentials.$extension'), findsOneWidget);
      expect(find.textContaining('1, 2, 3'), findsNothing);

      final submit = find.byKey(const Key('import-cloud-credential'));
      await tester.ensureVisible(submit);
      await tester.pumpAndSettle();
      await tester.tap(submit);
      await tester.pumpAndSettle();

      expect(captured?.provider, provider);
      expect(captured?.filename, 'credentials.$extension');
      expect(captured?.bytes, [1, 2, 3]);
      expect(
        captured?.targetScopeId,
        provider == CloudProvider.aws ? null : 'scope-1',
      );
    });
  }

  testWidgets('rejects a wrong extension locally and keeps contents hidden', (
    tester,
  ) async {
    CloudConnectionImportRequest? captured;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.aws,
      pickFile: (_) async => PlatformFile(
        name: 'credentials.json',
        size: 9,
        bytes: Uint8List.fromList([9, 8, 7]),
      ),
      onResult: (request) => captured = request,
    );

    final selectFile = find.byKey(const Key('select-cloud-credential-file'));
    await tester.ensureVisible(selectFile);
    await tester.pumpAndSettle();
    await tester.tap(selectFile);
    await tester.pumpAndSettle();

    expect(find.text('AWS requires a .csv file.'), findsOneWidget);
    expect(find.textContaining('9, 8, 7'), findsNothing);
    expect(captured, isNull);
  });

  testWidgets('cancelled picker retains metadata and returns no request', (
    tester,
  ) async {
    CloudConnectionImportRequest? captured;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.gcp,
      pickFile: (_) async => null,
      onResult: (request) => captured = request,
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Display name'),
      'GCP Administrator',
    );

    final selectFile = find.byKey(const Key('select-cloud-credential-file'));
    await tester.ensureVisible(selectFile);
    await tester.pumpAndSettle();
    await tester.tap(selectFile);
    await tester.pumpAndSettle();

    expect(find.text('GCP Administrator'), findsOneWidget);
    expect(captured, isNull);
  });
}

Future<void> _pumpLauncher(
  WidgetTester tester, {
  required CloudProvider provider,
  required CloudCredentialFilePicker pickFile,
  required ValueChanged<CloudConnectionImportRequest?> onResult,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: FilledButton(
            onPressed: () async {
              final result = await showDialog<CloudConnectionImportRequest>(
                context: context,
                builder: (_) => CloudConnectionImportDialog(
                  provider: provider,
                  pickFile: pickFile,
                ),
              );
              onResult(result);
            },
            child: const Text('Open'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Open'));
  await tester.pumpAndSettle();
}
