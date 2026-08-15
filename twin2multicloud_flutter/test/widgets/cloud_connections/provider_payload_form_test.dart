import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/widgets/cloud_connections/provider_payload_form.dart';

void main() {
  testWidgets('write-only GCP payload is validated, taken once, and cleared', (
    tester,
  ) async {
    final key = GlobalKey<ProviderPayloadFormState>();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Form(
            child: ProviderPayloadForm(
              key: key,
              provider: CloudProvider.gcp,
              fields: const [
                ProviderPayloadField(
                  'service_account_json',
                  'Service-account JSON',
                  json: true,
                  secret: true,
                ),
              ],
            ),
          ),
        ),
      ),
    );
    final payload = jsonEncode({
      'type': 'service_account',
      'project_id': 'thesis-project',
      'private_key_id': 'private-key-id',
      'private_key':
          '-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----',
      'client_email': 'bootstrap@thesis-project.iam.gserviceaccount.com',
      'client_id': '12345678901234567890',
    });

    await tester.enterText(find.byType(TextFormField), payload);
    expect(
      tester.widget<EditableText>(find.byType(EditableText)).obscureText,
      isTrue,
    );
    expect(key.currentState!.validate(), isTrue);
    final taken = key.currentState!.takeCredentials();
    await tester.pump();

    expect(taken['service_account_json'], payload);
    expect(
      tester.widget<TextFormField>(find.byType(TextFormField)).controller?.text,
      isEmpty,
    );
  });

  testWidgets('write-only provider fields reject short bootstrap secrets', (
    tester,
  ) async {
    final key = GlobalKey<ProviderPayloadFormState>();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Form(
            child: ProviderPayloadForm(
              key: key,
              provider: CloudProvider.aws,
              fields: const [
                ProviderPayloadField(
                  'secret_access_key',
                  'Secret access key',
                  secret: true,
                  minimumLength: 16,
                ),
              ],
            ),
          ),
        ),
      ),
    );

    await tester.enterText(find.byType(TextFormField), 'too-short');

    expect(key.currentState!.validate(), isFalse);
  });
}
