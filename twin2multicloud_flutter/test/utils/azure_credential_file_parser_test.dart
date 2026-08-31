import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/utils/azure_credential_file_parser.dart';

void main() {
  group('parseAzureCredentialFileSelection', () {
    test('normalizes canonical service-principal JSON', () {
      final result = _parse({
        'appId': 'deployment-client',
        'password': 'deployment-secret',
        'tenant': 'tenant',
        'subscriptionId': 'subscription',
      });

      expect(result.kind, AzureCredentialFileKind.servicePrincipal);
      expect(result.subscriptionId, 'subscription');
      expect(result.preparationClientId, isNull);
      expect(_normalized(result), {
        'appId': 'deployment-client',
        'password': 'deployment-secret',
        'tenant': 'tenant',
        'subscriptionId': 'subscription',
      });
    });

    test('extracts a complete wrapped compatibility bundle', () {
      final result = _parse({
        'aws': {'ignored': 'aws-marker'},
        'gcp': {'ignored': 'gcp-marker'},
        'azure': _completeBundle(),
      });

      expect(result.kind, AzureCredentialFileKind.compatibilityBundle);
      expect(result.subscriptionId, 'subscription');
      expect(result.region, 'westeurope');
      expect(result.regionIotHub, 'northeurope');
      expect(result.regionDigitalTwin, 'westeurope');
      expect(result.preparationClientId, 'preparation-client');
      expect(result.preparationClientSecret, 'preparation-secret');
      final normalizedText = utf8.decode(result.normalizedUploadBytes);
      expect(normalizedText, isNot(contains('aws-marker')));
      expect(normalizedText, isNot(contains('gcp-marker')));
      expect(normalizedText, isNot(contains('preparation-client')));
      expect(_normalized(result), {
        'appId': 'deployment-client',
        'password': 'deployment-secret',
        'tenant': 'tenant',
        'subscriptionId': 'subscription',
      });
    });

    test('extracts a direct compatibility object', () {
      final result = _parse(_completeBundle());

      expect(result.kind, AzureCredentialFileKind.compatibilityBundle);
      expect(result.preparationClientId, 'preparation-client');
      expect(_normalized(result).keys, {
        'appId',
        'password',
        'tenant',
        'subscriptionId',
      });
    });

    test('rejects malformed and non-object JSON with fixed codes', () {
      for (final bytes in [
        Uint8List.fromList(utf8.encode('{broken')),
        Uint8List.fromList(utf8.encode('[]')),
      ]) {
        expect(
          () => parseAzureCredentialFileSelection(bytes),
          throwsA(
            isA<FormatException>().having(
              (error) => error.message,
              'message',
              AzureCredentialFileErrorCode.invalidJson,
            ),
          ),
        );
      }
    });

    test('rejects unknown root and Azure fields', () {
      expect(
        () => _parse({'azure': _completeBundle(), 'other': {}}),
        _throwsCode(AzureCredentialFileErrorCode.unsupportedShape),
      );
      expect(
        () => _parse({..._completeBundle(), 'azure_unknown': 'value'}),
        _throwsCode(AzureCredentialFileErrorCode.unsupportedShape),
      );
    });

    test('allows absent optional compatibility regions', () {
      final bundle = _completeBundle()
        ..remove('azure_region')
        ..remove('azure_region_iothub')
        ..remove('azure_region_digital_twin');

      final result = _parse(bundle);

      expect(result.region, isNull);
      expect(result.regionIotHub, isNull);
      expect(result.regionDigitalTwin, isNull);
    });

    test('rejects one client ID reused for both principals', () {
      final bundle = _completeBundle()
        ..['azure_preparation_client_id'] = 'deployment-client';

      expect(
        () => _parse(bundle),
        _throwsCode(AzureCredentialFileErrorCode.sharedPrincipal),
      );
    });

    test('accepts UTF-8 BOM input', () {
      final body = utf8.encode(jsonEncode(_completeBundle()));
      final bytes = Uint8List.fromList([0xEF, 0xBB, 0xBF, ...body]);

      final result = parseAzureCredentialFileSelection(bytes);

      expect(result.kind, AzureCredentialFileKind.compatibilityBundle);
    });

    test('rejects empty and oversized files before decoding', () {
      expect(
        () => parseAzureCredentialFileSelection(Uint8List(0)),
        _throwsCode(AzureCredentialFileErrorCode.invalidSize),
      );
      expect(
        () => parseAzureCredentialFileSelection(Uint8List(128 * 1024 + 1)),
        _throwsCode(AzureCredentialFileErrorCode.invalidSize),
      );
    });

    test('accepts existing standard aliases and safe display metadata', () {
      final result = _parse({
        'clientId': 'deployment-client',
        'clientSecret': 'deployment-secret',
        'tenantId': 'tenant',
        'subscription': 'subscription',
        'displayName': 'Thesis Azure',
      });

      expect(result.displayName, 'Thesis Azure');
      expect(result.subscriptionId, 'subscription');
      expect(_normalized(result)['appId'], 'deployment-client');
    });

    test('falls back from empty standard aliases', () {
      final result = _parse({
        'clientId': ' ',
        'appId': 'deployment-client',
        'clientSecret': '',
        'password': 'deployment-secret',
        'tenantId': null,
        'tenant': 'tenant',
      });

      expect(_normalized(result), {
        'appId': 'deployment-client',
        'password': 'deployment-secret',
        'tenant': 'tenant',
      });
    });

    test(
      'keeps a missing standard subscription available for manual entry',
      () {
        final result = _parse({
          'appId': 'deployment-client',
          'password': 'deployment-secret',
          'tenant': 'tenant',
        });

        expect(result.subscriptionId, isNull);
        expect(_normalized(result), isNot(contains('subscriptionId')));
      },
    );

    test('rejects incomplete bundles without echoing input values', () {
      final bundle = _completeBundle()
        ..remove('azure_preparation_client_secret');

      expect(
        () => _parse(bundle),
        throwsA(
          isA<FormatException>()
              .having(
                (error) => error.message,
                'message',
                AzureCredentialFileErrorCode.incompleteBundle,
              )
              .having(
                (error) => error.toString(),
                'text',
                isNot(contains('deployment-secret')),
              ),
        ),
      );
    });
  });
}

AzureCredentialFileSelection _parse(Map<String, dynamic> value) =>
    parseAzureCredentialFileSelection(
      Uint8List.fromList(utf8.encode(jsonEncode(value))),
    );

Map<String, dynamic> _normalized(AzureCredentialFileSelection selection) =>
    jsonDecode(utf8.decode(selection.normalizedUploadBytes))
        as Map<String, dynamic>;

Map<String, dynamic> _completeBundle() => {
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

Matcher _throwsCode(String code) => throwsA(
  isA<FormatException>().having((error) => error.message, 'message', code),
);
