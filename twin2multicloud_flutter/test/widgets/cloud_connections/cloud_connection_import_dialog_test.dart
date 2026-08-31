import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
      if (provider == CloudProvider.azure) {
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Preparation client ID'),
          'preparation-client',
        );
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Preparation client secret'),
          'preparation-secret',
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
      if (provider == CloudProvider.azure) {
        expect(captured?.preparationClientId, 'preparation-client');
        expect(
          jsonDecode(captured!.metadataJson)['preparation_client_secret'],
          'preparation-secret',
        );
        expect(captured.toString(), isNot(contains('preparation-secret')));
      }
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

  testWidgets('Azure requires both transient preparation fields', (
    tester,
  ) async {
    CloudConnectionImportRequest? captured;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.azure,
      pickFile: (_) async => PlatformFile(
        name: 'credentials.json',
        size: 3,
        bytes: Uint8List.fromList([1, 2, 3]),
      ),
      onResult: (request) => captured = request,
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Display name'),
      'Azure bundle',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Subscription ID'),
      'subscription',
    );
    final selectFile = find.byKey(const Key('select-cloud-credential-file'));
    await tester.ensureVisible(selectFile);
    await tester.tap(selectFile);
    await tester.pumpAndSettle();
    final submit = find.byKey(const Key('import-cloud-credential'));
    await tester.ensureVisible(submit);
    await tester.tap(submit);
    await tester.pump();

    expect(find.text('Preparation client ID is required.'), findsOneWidget);
    expect(find.text('Preparation client secret is required.'), findsOneWidget);
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

  testWidgets('Escape cancels import and restores invoking focus', (
    tester,
  ) async {
    final triggerFocus = FocusNode();
    addTearDown(triggerFocus.dispose);
    CloudConnectionImportRequest? captured;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.aws,
      pickFile: (_) async => null,
      onResult: (request) => captured = request,
      triggerFocus: triggerFocus,
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();

    expect(find.byType(CloudConnectionImportDialog), findsNothing);
    expect(captured, isNull);
    expect(triggerFocus.hasFocus, isTrue);
  });

  for (final textScale in [1.5, 2.0]) {
    testWidgets(
      'dialog remains reachable at compact ${(textScale * 100).toInt()} percent text',
      (tester) async {
        await _pumpLauncher(
          tester,
          provider: CloudProvider.azure,
          pickFile: (_) async => null,
          onResult: (_) {},
          width: 640,
          textScale: textScale,
        );

        expect(find.text('Import Azure administrator'), findsOneWidget);
        expect(find.text('Select JSON credential file'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}

Future<void> _pumpLauncher(
  WidgetTester tester, {
  required CloudProvider provider,
  required CloudCredentialFilePicker pickFile,
  required ValueChanged<CloudConnectionImportRequest?> onResult,
  double width = 1200,
  double textScale = 1,
  FocusNode? triggerFocus,
}) async {
  tester.view.physicalSize = Size(width, 1200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(
          context,
        ).copyWith(textScaler: TextScaler.linear(textScale)),
        child: child!,
      ),
      home: Builder(
        builder: (context) => Scaffold(
          body: FilledButton(
            focusNode: triggerFocus,
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
  if (triggerFocus != null) {
    triggerFocus.requestFocus();
    await tester.pump();
  }
  await tester.tap(find.text('Open'));
  await tester.pumpAndSettle();
}
