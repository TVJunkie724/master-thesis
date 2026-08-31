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
      final bytes = provider == CloudProvider.azure
          ? _jsonBytes(_standardAzureJson())
          : Uint8List.fromList([1, 2, 3]);
      await _pumpLauncher(
        tester,
        provider: provider,
        pickFile: (_) async => _file('credentials.$extension', bytes),
        onResult: (request) => captured = request,
      );

      final selectFile = find.byKey(const Key('select-cloud-credential-file'));
      await tester.tap(selectFile);
      await tester.pumpAndSettle();
      expect(find.text('credentials.$extension'), findsOneWidget);
      expect(find.textContaining('1, 2, 3'), findsNothing);

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Display name'),
        '${provider.label} Administrator',
      );
      if (provider == CloudProvider.gcp) {
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Project ID'),
          'scope-1',
        );
      }
      if (provider == CloudProvider.azure) {
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Preparation client ID'),
          'manual-preparation-client',
        );
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Preparation client secret'),
          'manual-preparation-secret',
        );
      }

      final submit = find.byKey(const Key('import-cloud-credential'));
      await tester.ensureVisible(submit);
      await tester.tap(submit);
      await tester.pumpAndSettle();

      expect(captured?.provider, provider);
      expect(captured?.filename, 'credentials.$extension');
      expect(captured?.targetScopeId, switch (provider) {
        CloudProvider.aws => null,
        CloudProvider.azure => 'subscription',
        CloudProvider.gcp => 'scope-1',
      });
      if (provider == CloudProvider.azure) {
        expect(captured?.preparationClientId, 'manual-preparation-client');
        expect(
          jsonDecode(captured!.metadataJson)['preparation_client_secret'],
          'manual-preparation-secret',
        );
        expect(_decodedBytes(captured!), _standardAzureJson());
        expect(
          captured.toString(),
          isNot(contains('manual-preparation-secret')),
        );
      } else {
        expect(captured?.bytes, [1, 2, 3]);
      }
    });
  }

  testWidgets('prefills and sanitizes a complete Azure bundle', (tester) async {
    CloudConnectionImportRequest? captured;
    final source = {
      'aws': {'marker': 'aws-not-uploaded'},
      'gcp': {'marker': 'gcp-not-uploaded'},
      'azure': _completeAzureBundle(),
    };
    await _pumpLauncher(
      tester,
      provider: CloudProvider.azure,
      pickFile: (_) async =>
          _file('config_credentials.json', _jsonBytes(source)),
      onResult: (request) => captured = request,
    );

    await tester.tap(find.byKey(const Key('select-cloud-credential-file')));
    await tester.pumpAndSettle();

    expect(find.text('Complete Azure bundle detected'), findsOneWidget);
    expect(_fieldText(tester, 'Display name'), 'Azure administrator');
    expect(_fieldText(tester, 'Primary region'), 'westeurope');
    expect(_fieldText(tester, 'Subscription ID'), 'subscription');
    expect(_fieldText(tester, 'IoT Hub region (optional)'), 'northeurope');
    expect(_fieldText(tester, 'Digital Twins region (optional)'), 'westeurope');
    expect(_fieldText(tester, 'Preparation client ID'), 'preparation-client');
    expect(
      _fieldText(tester, 'Preparation client secret'),
      'preparation-secret',
    );
    expect(
      tester
          .widget<EditableText>(
            find.descendant(
              of: find.widgetWithText(
                TextFormField,
                'Preparation client secret',
              ),
              matching: find.byType(EditableText),
            ),
          )
          .obscureText,
      isTrue,
    );

    final submit = find.byKey(const Key('import-cloud-credential'));
    await tester.ensureVisible(submit);
    await tester.tap(submit);
    await tester.pumpAndSettle();

    final normalized = _decodedBytes(captured!);
    expect(normalized, _standardAzureJson());
    expect(jsonEncode(normalized), isNot(contains('preparation-client')));
    expect(jsonEncode(normalized), isNot(contains('aws-not-uploaded')));
    expect(jsonEncode(normalized), isNot(contains('gcp-not-uploaded')));
    expect(captured!.preparationClientId, 'preparation-client');
  });

  testWidgets('shows fixed Azure parse errors and returns no request', (
    tester,
  ) async {
    CloudConnectionImportRequest? captured;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.azure,
      pickFile: (_) async =>
          _file('credentials.json', Uint8List.fromList(utf8.encode('{broken'))),
      onResult: (request) => captured = request,
    );

    await tester.tap(find.byKey(const Key('select-cloud-credential-file')));
    await tester.pumpAndSettle();

    expect(
      find.text('Azure credential JSON must contain one valid JSON object.'),
      findsOneWidget,
    );
    expect(find.textContaining('{broken'), findsNothing);
    expect(find.byKey(const Key('cloud-credential-file-status')), findsNothing);
    expect(captured, isNull);
  });

  testWidgets('standard Azure JSON keeps preparation fields required', (
    tester,
  ) async {
    CloudConnectionImportRequest? captured;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.azure,
      pickFile: (_) async =>
          _file('credentials.json', _jsonBytes(_standardAzureJson())),
      onResult: (request) => captured = request,
    );
    await tester.tap(find.byKey(const Key('select-cloud-credential-file')));
    await tester.pumpAndSettle();

    expect(find.text('Azure service-principal JSON detected'), findsOneWidget);
    final submit = find.byKey(const Key('import-cloud-credential'));
    await tester.ensureVisible(submit);
    await tester.tap(submit);
    await tester.pump();

    expect(find.text('Preparation client ID is required.'), findsOneWidget);
    expect(find.text('Preparation client secret is required.'), findsOneWidget);
    expect(captured, isNull);
  });

  testWidgets(
    'keeps a manually changed subscription separate from file bytes',
    (tester) async {
      CloudConnectionImportRequest? captured;
      await _pumpLauncher(
        tester,
        provider: CloudProvider.azure,
        pickFile: (_) async =>
            _file('credentials.json', _jsonBytes(_standardAzureJson())),
        onResult: (request) => captured = request,
      );
      await tester.tap(find.byKey(const Key('select-cloud-credential-file')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Subscription ID'),
        'edited-subscription',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Preparation client ID'),
        'manual-preparation-client',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Preparation client secret'),
        'manual-preparation-secret',
      );

      await tester.ensureVisible(
        find.byKey(const Key('import-cloud-credential')),
      );
      await tester.tap(find.byKey(const Key('import-cloud-credential')));
      await tester.pumpAndSettle();

      expect(captured?.targetScopeId, 'edited-subscription');
      expect(_decodedBytes(captured!)['subscriptionId'], 'subscription');
    },
  );

  testWidgets('Enter on the final Azure secret submits valid input', (
    tester,
  ) async {
    CloudConnectionImportRequest? captured;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.azure,
      pickFile: (_) async =>
          _file('bundle.json', _jsonBytes({'azure': _completeAzureBundle()})),
      onResult: (request) => captured = request,
    );
    await tester.tap(find.byKey(const Key('select-cloud-credential-file')));
    await tester.pumpAndSettle();
    final secret = find.widgetWithText(
      TextFormField,
      'Preparation client secret',
    );
    await tester.ensureVisible(secret);
    await tester.tap(secret);
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();

    expect(captured, isNotNull);
    expect(find.byType(CloudConnectionImportDialog), findsNothing);
  });

  testWidgets('shows both placeholder-only Azure JSON examples', (
    tester,
  ) async {
    await _pumpLauncher(
      tester,
      provider: CloudProvider.azure,
      pickFile: (_) async => null,
      onResult: (_) {},
    );

    final help = find.text('Accepted Azure JSON formats');
    await tester.tap(help);
    await tester.pumpAndSettle();

    expect(find.text('Standard Azure JSON'), findsOneWidget);
    expect(find.text('Twin2MultiCloud Azure bundle'), findsOneWidget);
    expect(find.textContaining('<deployment-client-id>'), findsNWidgets(2));
    expect(find.textContaining('<preparation-client-id>'), findsOneWidget);
    expect(find.textContaining('aws-not-uploaded'), findsNothing);
  });

  testWidgets('invalid replacement clears previous Azure bundle state', (
    tester,
  ) async {
    var selections = 0;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.azure,
      pickFile: (_) async {
        selections++;
        return selections == 1
            ? _file('valid.json', _jsonBytes({'azure': _completeAzureBundle()}))
            : _file('invalid.json', _jsonBytes({'azure_unknown': 'value'}));
      },
      onResult: (_) {},
    );

    final select = find.byKey(const Key('select-cloud-credential-file'));
    await tester.tap(select);
    await tester.pumpAndSettle();
    expect(
      _fieldText(tester, 'Preparation client secret'),
      'preparation-secret',
    );

    await tester.tap(select);
    await tester.pumpAndSettle();

    expect(
      find.text('Azure credential JSON does not match a supported format.'),
      findsOneWidget,
    );
    expect(_fieldText(tester, 'Preparation client secret'), isEmpty);
    expect(_fieldText(tester, 'Preparation client ID'), isEmpty);
    expect(find.text('Complete Azure bundle detected'), findsNothing);
  });

  testWidgets('cancelled picker retains a valid Azure selection', (
    tester,
  ) async {
    var selections = 0;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.azure,
      pickFile: (_) async {
        selections++;
        return selections == 1
            ? _file('valid.json', _jsonBytes({'azure': _completeAzureBundle()}))
            : null;
      },
      onResult: (_) {},
    );

    final select = find.byKey(const Key('select-cloud-credential-file'));
    await tester.tap(select);
    await tester.pumpAndSettle();
    await tester.tap(select);
    await tester.pumpAndSettle();

    expect(find.text('valid.json'), findsOneWidget);
    expect(find.text('Complete Azure bundle detected'), findsOneWidget);
    expect(_fieldText(tester, 'Subscription ID'), 'subscription');
  });

  testWidgets('rejects a wrong extension locally and keeps contents hidden', (
    tester,
  ) async {
    CloudConnectionImportRequest? captured;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.aws,
      pickFile: (_) async =>
          _file('credentials.json', Uint8List.fromList([9, 8, 7])),
      onResult: (request) => captured = request,
    );

    await tester.tap(find.byKey(const Key('select-cloud-credential-file')));
    await tester.pumpAndSettle();

    expect(find.text('AWS requires a .csv file.'), findsOneWidget);
    expect(find.textContaining('9, 8, 7'), findsNothing);
    expect(captured, isNull);
  });

  testWidgets('cancel clears a selected bundle without returning it', (
    tester,
  ) async {
    CloudConnectionImportRequest? captured;
    await _pumpLauncher(
      tester,
      provider: CloudProvider.azure,
      pickFile: (_) async =>
          _file('bundle.json', _jsonBytes({'azure': _completeAzureBundle()})),
      onResult: (request) => captured = request,
    );
    await tester.tap(find.byKey(const Key('select-cloud-credential-file')));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('Cancel'));
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(find.byType(CloudConnectionImportDialog), findsNothing);
    expect(find.textContaining('preparation-secret'), findsNothing);
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
        expect(find.text('Accepted Azure JSON formats'), findsOneWidget);
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

PlatformFile _file(String name, Uint8List bytes) =>
    PlatformFile(name: name, size: bytes.length, bytes: bytes);

Uint8List _jsonBytes(Map<String, dynamic> value) =>
    Uint8List.fromList(utf8.encode(jsonEncode(value)));

Map<String, dynamic> _standardAzureJson() => {
  'appId': 'deployment-client',
  'password': 'deployment-secret',
  'tenant': 'tenant',
  'subscriptionId': 'subscription',
};

Map<String, dynamic> _completeAzureBundle() => {
  'azure_subscription_id': 'subscription',
  'azure_client_id': 'deployment-client',
  'azure_client_secret': 'deployment-secret',
  'azure_preparation_client_id': 'preparation-client',
  'azure_preparation_client_secret': 'preparation-secret',
  'azure_tenant_id': 'tenant',
  'azure_region': 'westeurope',
  'azure_region_iothub': 'northeurope',
  'azure_region_digital_twin': 'westeurope',
};

String _fieldText(WidgetTester tester, String label) => tester
    .widget<TextFormField>(find.widgetWithText(TextFormField, label))
    .controller!
    .text;

Map<String, dynamic> _decodedBytes(CloudConnectionImportRequest request) =>
    jsonDecode(utf8.decode(request.bytes)) as Map<String, dynamic>;
