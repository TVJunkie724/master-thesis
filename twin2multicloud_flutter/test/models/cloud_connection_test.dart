import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';

void main() {
  group('CloudConnection', () {
    test('parses AWS response without secret fields', () {
      final connection = CloudConnection.fromJson({
        'id': 'connection-aws',
        'provider': 'aws',
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
        'created_at': '2026-05-01T09:00:00Z',
        'updated_at': '2026-05-01T10:00:00Z',
      });

      expect(connection.id, 'connection-aws');
      expect(connection.provider, CloudProvider.aws);
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
      expect(json['aws'], isA<Map<String, dynamic>>());
      expect(json.containsKey('azure'), false);
      expect(json.containsKey('gcp'), false);
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
    test('parses nested optimizer and deployer status', () {
      final result = CloudConnectionValidationResult.fromJson({
        'id': 'connection-aws',
        'provider': 'aws',
        'valid': false,
        'validation_status': 'invalid',
        'message': 'Validation failed',
        'optimizer': {'valid': true, 'message': 'ok'},
        'deployer': {'valid': false, 'message': 'missing permission'},
      });

      expect(result.id, 'connection-aws');
      expect(result.provider, CloudProvider.aws);
      expect(result.valid, false);
      expect(result.optimizer?['valid'], true);
      expect(result.deployer?['message'], 'missing permission');
    });
  });
}
