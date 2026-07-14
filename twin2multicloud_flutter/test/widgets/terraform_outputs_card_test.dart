import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/terraform_outputs_card.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('redacts sensitive outputs before display and clipboard copy', (
    tester,
  ) async {
    String? clipboardText;
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        clipboardText =
            (call.arguments as Map<Object?, Object?>)['text'] as String?;
      }
      return null;
    });
    addTearDown(
      () => messenger.setMockMethodCallHandler(SystemChannels.platform, null),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TerraformOutputsCard(
            outputs: const {
              'aws_connection_string': 'plaintext-secret',
              'aws_endpoint': 'iot.example.test',
              'metadata': {'token': 'nested-secret', 'region': 'eu-central-1'},
            },
            onCopyFeedback: (_) {},
          ),
        ),
      ),
    );

    expect(find.text('plaintext-secret'), findsNothing);
    expect(find.text('Show'), findsNothing);
    expect(find.text('[REDACTED]'), findsOneWidget);

    await tester.tap(find.text('Copy All'));
    await tester.pump();

    expect(clipboardText, isNotNull);
    expect(clipboardText, isNot(contains('plaintext-secret')));
    expect(clipboardText, isNot(contains('nested-secret')));
    final copied = jsonDecode(clipboardText!) as Map<String, dynamic>;
    expect(copied['aws_connection_string'], '[REDACTED]');
    expect((copied['metadata'] as Map<String, dynamic>)['token'], '[REDACTED]');
  });

  testWidgets('fits output controls at the supported 640 pixel viewport', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(640, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TerraformOutputsCard(
            outputs: const {
              'gcp_telemetry_endpoint':
                  'https://example.test/a/long/but/wrappable/path',
            },
            onCopyFeedback: (_) {},
          ),
        ),
      ),
    );

    expect(find.text('Terraform Outputs'), findsOneWidget);
    expect(find.text('Copy All'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
