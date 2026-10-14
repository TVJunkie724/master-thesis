import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/deployment_verification.dart';

void main() {
  group('InfrastructureVerificationResult', () {
    test('parses checks and summary defensively', () {
      final result = InfrastructureVerificationResult.fromJson({
        'checks': [
          {
            'layer': 'L1',
            'name': 'IoT endpoint',
            'provider': 'aws',
            'status': 'pass',
            'detail': 'ok',
          },
        ],
        'summary': {
          'pass_count': 1,
          'fail_count': 0,
          'skip_count': 0,
          'total': 1,
          'healthy': true,
        },
      });

      expect(result.summary.healthy, isTrue);
      expect(result.checks.single.layer, 'L1');
      expect(result.groupedByLayer()['L1'], hasLength(1));
    });
  });

  group('DataFlowVerificationSummary', () {
    test('parses counts, total time, failed phase, and hints', () {
      final summary = DataFlowVerificationSummary.fromJson({
        'pass_count': '2',
        'fail_count': 1,
        'skip_count': 0,
        'total_time': 12.5,
        'failed_phase': 'digital-twin',
        'hints': ['Check logs'],
      });

      expect(summary.passCount, 2);
      expect(summary.failCount, 1);
      expect(summary.allPass, isFalse);
      expect(summary.hints, ['Check logs']);
    });
  });

  group('persisted telemetry verification', () {
    test('parses exact three-phase pass evidence and record history', () {
      final record = TelemetryVerificationRecord.fromJson(
        _recordJson(result: _passEvidenceJson()),
      );
      final history = TelemetryVerificationHistory.fromJson({
        'schema_version': 'telemetry-verification-history.v1',
        'verifications': [_recordJson(result: _passEvidenceJson())],
      });

      expect(record.status, TelemetryVerificationStatus.pass);
      expect(record.traceId, 'VERIFY-A1B2C3D4');
      expect(record.result?.passCount, 3);
      expect(record.result?.evidence.map((item) => item.phase), [1, 2, 3]);
      expect(history.verifications.single.id, 'verification-1');
    });

    test('rejects unknown fields and mismatched L4 provider evidence', () {
      final extra = _passEvidenceJson()..['credential'] = 'forbidden';
      expect(
        () => TelemetryVerificationEvidence.fromJson(extra),
        throwsFormatException,
      );

      final mismatched = _passEvidenceJson();
      (mismatched['evidence'] as List)[2] = {
        'phase': 3,
        'kind': 'azure_twin_projection',
        'provider': 'aws',
        'correlation': 'source_sequence',
      };
      expect(
        () => TelemetryVerificationEvidence.fromJson(mismatched),
        throwsFormatException,
      );
    });

    test('rejects count inconsistency and out-of-order history', () {
      final inconsistent = _passEvidenceJson()..['pass_count'] = 2;
      expect(
        () => TelemetryVerificationEvidence.fromJson(inconsistent),
        throwsFormatException,
      );

      final older = _recordJson(result: _passEvidenceJson());
      final newer = _recordJson(result: _passEvidenceJson())
        ..['id'] = 'verification-2'
        ..['requested_at'] = '2026-08-27T10:01:00Z'
        ..['completed_at'] = '2026-08-27T10:01:05Z';
      expect(
        () => TelemetryVerificationHistory.fromJson({
          'schema_version': 'telemetry-verification-history.v1',
          'verifications': [older, newer],
        }),
        throwsFormatException,
      );
    });
  });

  group('DeploymentVerificationPayload', () {
    test('uses first payload from JSON array', () {
      final payload = DeploymentVerificationPayload.initialPayload(
        '[{"iotDeviceId":"device-1","temperature":21}]',
      );

      expect(payload, contains('"iotDeviceId": "device-1"'));
    });

    test('falls back for invalid JSON', () {
      expect(
        DeploymentVerificationPayload.initialPayload('not-json'),
        DeploymentVerificationPayload.fallback,
      );
    });
  });
}

Map<String, dynamic> _passEvidenceJson() => {
  'schema_version': 'telemetry-verification.v1',
  'trace_id': 'VERIFY-A1B2C3D4',
  'status': 'pass',
  'pass_count': 3,
  'fail_count': 0,
  'skip_count': 0,
  'total_time': 4.2,
  'failed_phase': null,
  'evidence': [
    {'phase': 1, 'kind': 'message_accepted', 'provider': 'aws'},
    {
      'phase': 2,
      'kind': 'trace_correlated_hot_record',
      'provider': 'gcp',
      'record_count': 1,
    },
    {
      'phase': 3,
      'kind': 'azure_twin_projection',
      'provider': 'azure',
      'correlation': 'source_sequence',
    },
  ],
};

Map<String, dynamic> _recordJson({required Map<String, dynamic> result}) => {
  'id': 'verification-1',
  'twin_id': 'twin-1',
  'deployment_id': 'deployment-1',
  'session_id': 'session-1',
  'device_id': 'device-1',
  'status': 'pass',
  'trace_id': 'VERIFY-A1B2C3D4',
  'result': result,
  'error_code': null,
  'error_message': null,
  'requested_at': '2026-08-27T10:00:00Z',
  'completed_at': '2026-08-27T10:00:05Z',
};
