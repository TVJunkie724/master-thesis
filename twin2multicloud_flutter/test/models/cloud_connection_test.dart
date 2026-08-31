import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';

void main() {
  group('CloudConnection', () {
    test('parses AWS response without secret fields', () {
      final connection = CloudConnection.fromJson({
        'id': 'connection-aws',
        'provider': 'aws',
        'purpose': 'deployment',
        'scope': 'user',
        'display_name': 'AWS thesis dev',
        'auth_type': 'access_key',
        'cloud_scope': {'region': 'eu-central-1'},
        'payload_fingerprint': 'sha256',
        'payload_summary': {
          'region': 'eu-central-1',
          'account_identity_configured': true,
        },
        'validation_status': 'valid',
        'validation_message': 'Validation complete',
        'last_validated_at': '2026-05-01T10:00:00Z',
        'last_used_at': '2026-05-01T11:00:00Z',
        'created_at': '2026-05-01T09:00:00Z',
        'updated_at': '2026-05-01T10:00:00Z',
      });

      expect(connection.id, 'connection-aws');
      expect(connection.provider, CloudProvider.aws);
      expect(connection.lastUsedAt, DateTime.parse('2026-05-01T11:00:00Z'));
      expect(connection.displayName, 'AWS thesis dev');
      expect(connection.payloadSummary['region'], 'eu-central-1');
      expect(connection.payloadSummary.containsKey('secret_access_key'), false);
      expect(connection.isValid, true);
    });

    test('create request emits only selected provider payload', () {
      const request = CloudConnectionCreateRequest(
        provider: CloudProvider.aws,
        displayName: 'AWS dev',
        credentials: {
          'access_key_id': 'AKIA12345678901234',
          'secret_access_key': 'secretsecretsecret',
          'region': 'eu-central-1',
        },
      );

      final json = request.toJson();

      expect(json['provider'], 'aws');
      expect(json.containsKey('purpose'), false);
      expect(json.containsKey('scope'), false);
      expect(json['aws'], isA<Map<String, dynamic>>());
      expect(json.containsKey('azure'), false);
      expect(json.containsKey('gcp'), false);
    });

    test('rejects a legacy pricing connection at the response boundary', () {
      final payload = {
        'id': 'connection-aws',
        'provider': 'aws',
        'purpose': 'pricing',
        'scope': 'user',
        'display_name': 'Unsupported',
        'auth_type': 'access_key',
        'cloud_scope': <String, dynamic>{},
        'payload_fingerprint': 'opaque',
        'payload_summary': <String, dynamic>{},
        'validation_status': 'untested',
        'created_at': '2026-07-12T10:00:00Z',
        'updated_at': '2026-07-12T10:00:00Z',
      };

      expect(() => CloudConnection.fromJson(payload), throwsFormatException);
    });

    test('GCP create request requires service account JSON', () {
      const request = CloudConnectionCreateRequest(
        provider: CloudProvider.gcp,
        displayName: 'GCP dev',
        credentials: {'project_id': 'thesis-project', 'region': 'europe-west1'},
      );

      expect(request.toJson, throwsArgumentError);
    });
  });

  group('CloudConnectionValidationResult', () {
    test('parses the Deployer-owned validation status', () {
      final result = CloudConnectionValidationResult.fromJson({
        'id': 'connection-aws',
        'provider': 'aws',
        'valid': false,
        'validation_status': 'invalid',
        'message': 'Validation failed',
        'deployer': {'valid': false, 'message': 'missing permission'},
      });

      expect(result.id, 'connection-aws');
      expect(result.provider, CloudProvider.aws);
      expect(result.valid, false);
      expect(result.deployer?['message'], 'missing permission');
    });
  });

  group('CloudConnectionImportRequest', () {
    test('emits deployment-only Azure metadata without file contents', () {
      final request = CloudConnectionImportRequest(
        provider: CloudProvider.azure,
        displayName: 'Azure thesis',
        region: 'westeurope',
        targetScopeId: 'subscription-1',
        regionIotHub: 'westeurope',
        regionDigitalTwin: 'westeurope',
        preparationClientId: 'preparation-client',
        preparationClientSecret: 'preparation-secret',
        filename: 'service-principal.json',
        bytes: Uint8List.fromList(utf8.encode('{"clientSecret":"hidden"}')),
      );

      expect(jsonDecode(request.metadataJson), {
        'provider': 'azure',
        'display_name': 'Azure thesis',
        'region': 'westeurope',
        'target_scope_id': 'subscription-1',
        'region_iothub': 'westeurope',
        'region_digital_twin': 'westeurope',
        'preparation_client_id': 'preparation-client',
        'preparation_client_secret': 'preparation-secret',
      });
      expect(request.toString(), isNot(contains('clientSecret')));
    });

    test('rejects provider-mismatched metadata and file extensions', () {
      expect(
        () => CloudConnectionImportRequest(
          provider: CloudProvider.aws,
          displayName: 'AWS thesis',
          region: 'eu-central-1',
          targetScopeId: 'foreign',
          filename: 'credentials.csv',
          bytes: Uint8List.fromList([1]),
        ),
        throwsArgumentError,
      );
      expect(
        () => CloudConnectionImportRequest(
          provider: CloudProvider.gcp,
          displayName: 'GCP thesis',
          region: 'europe-west1',
          targetScopeId: 'project-1',
          filename: 'credentials.csv',
          bytes: Uint8List.fromList([1]),
        ),
        throwsArgumentError,
      );
    });
  });
}
