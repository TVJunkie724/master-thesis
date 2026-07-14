import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/deployment_operations.dart';

void main() {
  group('operation contracts', () {
    test('parses operation and active session responses', () {
      final session = OperationSession.fromJson({
        'session_id': 'session-1',
        'sse_url': '/sse/deploy/session-1',
      });
      final active = ActiveDeploymentSession.fromJson({
        'session_id': 'session-1',
        'sse_url': '/sse/deploy/session-1',
        'operation_type': 'deploy',
      });

      expect(session.sessionId, 'session-1');
      expect(session.sseUrl, '/sse/deploy/session-1');
      expect(active.operationType, DeploymentOperationType.deploy);
    });

    test('rejects absolute or protocol-relative stream URLs', () {
      for (final url in ['https://deployer.test/sse', '//deployer.test/sse']) {
        expect(
          () => OperationSession.fromJson({
            'session_id': 'session-1',
            'sse_url': url,
          }),
          throwsContractError,
        );
      }
    });
  });

  group('deployment snapshots', () {
    test('parses complete status and outputs snapshots', () {
      final operation = operationJson();
      final status = DeploymentStatusSnapshot.fromJson({
        'schema_version': 'deployment-status.v1',
        'state': 'deploying',
        'last_error': null,
        'deployed_at': null,
        'destroyed_at': null,
        'active_session': {
          'session_id': 'session-1',
          'sse_url': '/sse/deploy/session-1',
          'operation_type': 'deploy',
        },
        'latest_deployment': operation,
      });
      final outputs = DeploymentOutputsSnapshot.fromJson({
        'schema_version': 'deployment-outputs.v1',
        'outputs': {'endpoint': 'https://example.test'},
        'deployed_at': '2026-07-14T08:30:00Z',
        'source_deployment': operation,
        'redacted': true,
      });

      expect(status.state, DeploymentTwinState.deploying);
      expect(status.activeSession?.sessionId, 'session-1');
      expect(
        status.latestDeployment?.status,
        DeploymentOperationStatus.running,
      );
      expect(outputs.outputs, {'endpoint': 'https://example.test'});
      expect(outputs.redacted, isTrue);
      expect(outputs.deployedAt, DateTime.parse('2026-07-14T08:30:00Z'));
    });

    test('parses typed empty output response', () {
      final outputs = DeploymentOutputsSnapshot.fromJson({
        'schema_version': 'deployment-outputs.v1',
        'outputs': null,
        'deployed_at': null,
        'source_deployment': null,
        'redacted': false,
      });

      expect(outputs.outputs, isNull);
      expect(outputs.sourceDeployment, isNull);
      expect(outputs.redacted, isFalse);
    });

    test('deeply protects parsed output snapshots from mutation', () {
      final outputs = DeploymentOutputsSnapshot.fromJson({
        'schema_version': 'deployment-outputs.v1',
        'outputs': {
          'nested': {
            'values': [1, 2],
          },
        },
        'deployed_at': null,
        'source_deployment': null,
        'redacted': true,
      });

      expect(
        () => (outputs.outputs!['nested'] as Map<String, dynamic>)['new'] = 3,
        throwsUnsupportedError,
      );
      expect(
        () =>
            ((outputs.outputs!['nested'] as Map<String, dynamic>)['values']
                    as List<dynamic>)
                .add(3),
        throwsUnsupportedError,
      );
    });

    test('rejects unsupported schema versions', () {
      expect(
        () => DeploymentStatusSnapshot.fromJson({
          'schema_version': 'deployment-status.v2',
          'state': 'deployed',
        }),
        throwsContractError,
      );
    });

    test('rejects unknown lifecycle and operation enum values', () {
      expect(
        () => DeploymentStatusSnapshot.fromJson({
          'schema_version': 'deployment-status.v1',
          'state': 'paused',
        }),
        throwsContractError,
      );
      expect(
        () => DeploymentOperationSummary.fromJson({
          ...operationJson(),
          'status': 'cancelled',
        }),
        throwsContractError,
      );
    });

    test('rejects invalid timestamps and reversed operation dates', () {
      expect(
        () => DeploymentOutputsSnapshot.fromJson({
          'schema_version': 'deployment-outputs.v1',
          'outputs': null,
          'deployed_at': 'not-a-date',
          'source_deployment': null,
          'redacted': true,
        }),
        throwsContractError,
      );
      expect(
        () => DeploymentOperationSummary.fromJson({
          ...operationJson(),
          'started_at': '2026-07-14T10:00:00Z',
          'completed_at': '2026-07-14T09:00:00Z',
        }),
        throwsContractError,
      );
    });

    test('parses deployment history with typed summaries', () {
      final history = DeploymentHistory.fromJson({
        'schema_version': 'deployment-history.v1',
        'deployments': [operationJson()],
      });

      expect(history.deployments, hasLength(1));
      expect(
        history.deployments.single.operationType,
        DeploymentOperationType.deploy,
      );
    });
  });

  group('deployment log page', () {
    test('parses an ascending cursor page', () {
      final page = DeploymentLogPage.fromJson(logPageJson());

      expect(page.logs.map((entry) => entry.eventId), [3, 4]);
      expect(page.nextAfterEventId, 4);
      expect(page.latestEventId, 6);
      expect(page.hasMore, isTrue);
    });

    test('parses a typed empty page without advancing the cursor', () {
      final page = DeploymentLogPage.fromJson({
        ...logPageJson(),
        'logs': <Object>[],
        'has_more': false,
        'next_after_event_id': 2,
        'latest_event_id': 2,
      });

      expect(page.logs, isEmpty);
      expect(page.nextAfterEventId, page.afterEventId);
    });

    test('rejects duplicate, descending, and pre-cursor events', () {
      for (final ids in [
        [3, 3],
        [4, 3],
        [2, 3],
      ]) {
        expect(
          () => DeploymentLogPage.fromJson({
            ...logPageJson(),
            'logs': ids.map(logJson).toList(),
            'next_after_event_id': ids.last,
          }),
          throwsContractError,
        );
      }
    });

    test('rejects cursor regression and inconsistent page cursors', () {
      expect(
        () => DeploymentLogPage.fromJson({
          ...logPageJson(),
          'next_after_event_id': 1,
        }),
        throwsContractError,
      );
      expect(
        () => DeploymentLogPage.fromJson({
          ...logPageJson(),
          'next_after_event_id': 5,
        }),
        throwsContractError,
      );
      expect(
        () => DeploymentLogPage.fromJson({
          ...logPageJson(),
          'latest_event_id': 3,
        }),
        throwsContractError,
      );
    });

    test('rejects an out-of-contract page limit', () {
      expect(
        () => DeploymentLogPage.fromJson({...logPageJson(), 'limit': 501}),
        throwsContractError,
      );
    });
  });

  group('trace and binary download contracts', () {
    test('parses trace metadata with optional stream session', () {
      final result = LogTraceStartResult.fromJson({
        'trace_id': 'TRACE-1',
        'sent_at': '2026-07-14T08:30:00Z',
        'l1_provider': 'aws',
        'providers': ['aws', 'azure'],
        'message': 'Trace accepted.',
        'session_id': 'session-trace',
        'sse_url': '/sse/deploy/session-trace',
      });

      expect(result.traceId, 'TRACE-1');
      expect(result.providers, ['aws', 'azure']);
      expect(result.sessionId, 'session-trace');
    });

    test('rejects empty, duplicate, and absolute trace metadata', () {
      for (final providers in [
        <String>[],
        ['aws', 'aws'],
      ]) {
        expect(
          () => LogTraceStartResult.fromJson({
            'trace_id': 'TRACE-1',
            'sent_at': '2026-07-14T08:30:00Z',
            'l1_provider': 'aws',
            'providers': providers,
            'message': 'Trace accepted.',
          }),
          throwsContractError,
        );
      }
      expect(
        () => LogTraceStartResult.fromJson({
          'trace_id': 'TRACE-1',
          'sent_at': '2026-07-14T08:30:00Z',
          'l1_provider': 'aws',
          'providers': ['aws'],
          'message': 'Trace accepted.',
          'sse_url': 'https://deployer.test/trace',
        }),
        throwsContractError,
      );
    });

    test('rejects inconsistent trace paths and partial stream sessions', () {
      for (final metadata in [
        {
          'l1_provider': 'gcp',
          'providers': ['aws'],
        },
        {
          'l1_provider': 'aws',
          'providers': ['aws'],
          'session_id': 'trace-session',
        },
        {
          'l1_provider': 'aws',
          'providers': ['aws'],
          'sse_url': '/sse/deploy/trace-session',
        },
        {
          'l1_provider': 'aws',
          'providers': ['aws'],
          'session_id': 'trace-session',
          'sse_url': '//external.test/stream',
        },
      ]) {
        expect(
          () => LogTraceStartResult.fromJson({
            'trace_id': 'TRACE-1',
            'sent_at': '2026-07-14T08:30:00Z',
            'message': 'Trace accepted.',
            ...metadata,
          }),
          throwsContractError,
        );
      }
    });

    test('rejects non-string trace provider entries', () {
      expect(
        () => LogTraceStartResult.fromJson({
          'trace_id': 'TRACE-1',
          'sent_at': '2026-07-14T08:30:00Z',
          'l1_provider': 'aws',
          'providers': ['aws', 42],
          'message': 'Trace accepted.',
        }),
        throwsContractError,
      );
    });

    test('copies binary bytes and accepts a safe ZIP filename', () {
      final source = Uint8List.fromList([1, 2, 3]);
      final download = BinaryDownload(
        bytes: source,
        filename: 'simulator_factory_aws.zip',
        mediaType: 'application/zip',
      );
      source[0] = 9;
      final exposed = download.bytes;
      exposed[1] = 9;

      expect(download.bytes, [1, 2, 3]);
      expect(download.filename, 'simulator_factory_aws.zip');
      expect(download.containsSensitiveRuntimeCredentials, isTrue);
    });

    test('rejects traversal, path, control, and non-ZIP filenames', () {
      for (final filename in [
        '../simulator.zip',
        'folder/simulator.zip',
        r'folder\simulator.zip',
        'simulator\n.zip',
        'simulator.tar',
      ]) {
        expect(
          () => BinaryDownload(
            bytes: Uint8List(0),
            filename: filename,
            mediaType: 'application/zip',
          ),
          throwsContractError,
        );
      }
    });
  });
}

Map<String, dynamic> operationJson() {
  return {
    'id': 'deployment-1',
    'session_id': 'session-1',
    'operation_id': 'operation-1',
    'operation_type': 'deploy',
    'status': 'running',
    'error_code': null,
    'error_message': null,
    'started_at': '2026-07-14T08:00:00Z',
    'completed_at': null,
  };
}

Map<String, dynamic> logPageJson() {
  return {
    'schema_version': 'deployment-log-page.v1',
    'twin_id': 'twin-1',
    'session_id': 'session-1',
    'after_event_id': 2,
    'limit': 2,
    'logs': [logJson(3), logJson(4)],
    'has_more': true,
    'next_after_event_id': 4,
    'latest_event_id': 6,
  };
}

Map<String, dynamic> logJson(int eventId) {
  return {
    'event_id': eventId,
    'session_id': 'session-1',
    'timestamp': '2026-07-14T08:00:0${eventId}Z',
    'level': 'info',
    'message': 'Event $eventId',
    'operation_type': 'deploy',
  };
}

Matcher get throwsContractError => throwsA(
  isA<AppException>().having(
    (error) => error.code,
    'code',
    'DEPLOYMENT_CONTRACT_INVALID',
  ),
);
