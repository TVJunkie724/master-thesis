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
