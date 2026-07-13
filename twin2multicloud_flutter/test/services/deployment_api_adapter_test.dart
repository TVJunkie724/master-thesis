import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/deployment_operations.dart';
import 'package:twin2multicloud_flutter/models/deployment_readiness.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

void main() {
  test('deployment adapter uses canonical paths and typed contracts', () async {
    final seen = <String>[];
    final dio = Dio(BaseOptions(baseUrl: 'http://management.test'));
    dio.httpClientAdapter = CallbackAdapter((options) {
      seen.add('${options.method} ${options.path}');
      return switch (options.path) {
        '/twins/twin-1/deployment-readiness' => jsonResponse(
          readinessResponse(DeploymentReadinessSnapshot.cachedSchemaVersion),
        ),
        '/twins/twin-1/deployment-preflight' => jsonResponse(
          readinessResponse(DeploymentReadinessSnapshot.preflightSchemaVersion),
        ),
        '/twins/twin-1/deploy' || '/twins/twin-1/destroy' => jsonResponse({
          'session_id': 'session-1',
          'sse_url': '/sse/deploy/session-1',
        }),
        '/twins/twin-1/deployment-status' => jsonResponse({
          'schema_version': 'deployment-status.v1',
          'state': 'deployed',
          'last_error': null,
          'deployed_at': '2026-07-14T08:30:00Z',
          'destroyed_at': null,
          'active_session': null,
          'latest_deployment': null,
        }),
        '/twins/twin-1/outputs' => jsonResponse({
          'schema_version': 'deployment-outputs.v1',
          'outputs': {'endpoint': 'https://example.test'},
          'deployed_at': '2026-07-14T08:30:00Z',
          'source_deployment': null,
          'redacted': true,
        }),
        '/twins/twin-1/deployments' => jsonResponse({
          'schema_version': 'deployment-history.v1',
          'deployments': <Object>[],
        }),
        '/twins/twin-1/logs' => jsonResponse({
          'schema_version': 'deployment-log-page.v1',
          'twin_id': 'twin-1',
          'session_id': 'session-1',
          'after_event_id': 4,
          'limit': 25,
          'logs': <Object>[],
          'has_more': false,
          'next_after_event_id': 4,
          'latest_event_id': 4,
        }),
        '/twins/twin-1/log-trace/start' => jsonResponse({
          'trace_id': 'TRACE-1',
          'sent_at': '2026-07-14T08:30:00Z',
          'l1_provider': 'aws',
          'providers': ['aws'],
          'message': 'Trace accepted.',
          'session_id': 'trace-session',
          'sse_url': '/sse/deploy/trace-session',
        }),
        _ => throw StateError('Unexpected request: ${options.path}'),
      };
    });
    final api = ApiService(dio: dio);

    expect((await api.getDeploymentReadiness('twin-1')).ready, isTrue);
    expect(
      (await api.runDeploymentPreflight('twin-1')).source,
      DeploymentReadinessSource.preflight,
    );
    expect((await api.deployTwin('twin-1')).sessionId, 'session-1');
    expect((await api.destroyTwin('twin-1')).sseUrl, '/sse/deploy/session-1');
    expect(
      (await api.getDeploymentStatus('twin-1')).state,
      DeploymentTwinState.deployed,
    );
    expect((await api.getDeploymentOutputs('twin-1')).outputs, {
      'endpoint': 'https://example.test',
    });
    expect(
      (await api.getDeploymentHistory('twin-1', limit: 7)).deployments,
      isEmpty,
    );
    expect(
      (await api.getDeploymentLogs(
        'twin-1',
        sessionId: 'session-1',
        afterEventId: 4,
        limit: 25,
      )).nextAfterEventId,
      4,
    );
    expect((await api.startLogTrace('twin-1')).traceId, 'TRACE-1');

    expect(seen, [
      'GET /twins/twin-1/deployment-readiness',
      'POST /twins/twin-1/deployment-preflight',
      'POST /twins/twin-1/deploy',
      'POST /twins/twin-1/destroy',
      'GET /twins/twin-1/deployment-status',
      'GET /twins/twin-1/outputs',
      'GET /twins/twin-1/deployments',
      'GET /twins/twin-1/logs',
      'POST /twins/twin-1/log-trace/start',
    ]);
  });

  test('deployment adapter rejects malformed contract responses', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://management.test'));
    dio.httpClientAdapter = CallbackAdapter(
      (_) => jsonResponse({
        'schema_version': 'deployment-status.v2',
        'state': 'deployed',
      }),
    );

    await expectLater(
      ApiService(dio: dio).getDeploymentStatus('twin-1'),
      throwsA(
        isA<AppException>().having(
          (error) => error.code,
          'code',
          'DEPLOYMENT_CONTRACT_INVALID',
        ),
      ),
    );
  });

  test('deployment adapter rejects invalid pagination before I/O', () async {
    var requestCount = 0;
    final dio = Dio(BaseOptions(baseUrl: 'http://management.test'));
    dio.httpClientAdapter = CallbackAdapter((_) {
      requestCount += 1;
      return jsonResponse(<String, dynamic>{});
    });
    final api = ApiService(dio: dio);

    await expectLater(
      api.getDeploymentHistory('twin-1', limit: 0),
      throwsRequestError,
    );
    await expectLater(
      api.getDeploymentLogs('twin-1', afterEventId: -1),
      throwsRequestError,
    );
    await expectLater(
      api.getDeploymentLogs('twin-1', sessionId: '  '),
      throwsRequestError,
    );
    await expectLater(
      api.getDeploymentLogs('twin-1', limit: 501),
      throwsRequestError,
    );
    expect(requestCount, 0);
  });

  test(
    'simulator adapter preserves safe server metadata and binary bytes',
    () async {
      final dio = Dio(BaseOptions(baseUrl: 'http://management.test'));
      dio.httpClientAdapter = CallbackAdapter(
        (_) => ResponseBody.fromBytes(
          [80, 75, 3, 4],
          200,
          headers: {
            Headers.contentTypeHeader: ['application/zip'],
            'content-disposition': [
              'attachment; filename="simulator_factory_aws.zip"',
            ],
          },
        ),
      );

      final download = await ApiService(dio: dio).downloadSimulator('twin-1');

      expect(download.bytes, [80, 75, 3, 4]);
      expect(download.filename, 'simulator_factory_aws.zip');
      expect(download.mediaType, 'application/zip');
    },
  );

  test(
    'simulator adapter rejects missing or unsafe server filenames',
    () async {
      for (final header in <String?>[
        null,
        'attachment; filename=../secret.zip',
      ]) {
        final dio = Dio(BaseOptions(baseUrl: 'http://management.test'));
        dio.httpClientAdapter = CallbackAdapter(
          (_) => ResponseBody.fromBytes(
            [80, 75, 3, 4],
            200,
            headers: {
              Headers.contentTypeHeader: ['application/zip'],
              if (header != null) 'content-disposition': [header],
            },
          ),
        );

        await expectLater(
          ApiService(dio: dio).downloadSimulator('twin-1'),
          throwsA(
            isA<AppException>().having(
              (error) => error.code,
              'code',
              'DEPLOYMENT_CONTRACT_INVALID',
            ),
          ),
        );
      }
    },
  );
}

class CallbackAdapter implements HttpClientAdapter {
  final ResponseBody Function(RequestOptions) callback;

  CallbackAdapter(this.callback);

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return callback(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody jsonResponse(Map<String, dynamic> body) {
  return ResponseBody.fromString(
    jsonEncode(body),
    200,
    headers: {
      Headers.contentTypeHeader: ['application/json'],
    },
  );
}

Matcher get throwsRequestError => throwsA(
  isA<AppException>().having(
    (error) => error.code,
    'code',
    'DEPLOYMENT_REQUEST_INVALID',
  ),
);

Map<String, dynamic> readinessResponse(String schemaVersion) {
  return {
    'schema_version': schemaVersion,
    'twin_id': 'twin-1',
    'ready': true,
    'summary': 'All required providers are ready for deployment.',
    'required_providers': ['aws'],
    'providers': [
      {
        'provider': 'aws',
        'connection_id': 'connection-1',
        'connection_display_name': 'AWS deployment',
        'ready': true,
        'status': 'ready',
        'summary': 'Cloud connection preflight passed',
        'expected_permission_set_version': 'thesis-demo-v1',
        'supplied_permission_set_version': 'thesis-demo-v1',
        'permission_set_status': 'matched',
        'checked_at': '2026-07-14T09:00:00Z',
        'checks': [
          {
            'component': 'optimizer',
            'status': 'passed',
            'code': 'OK',
            'message': 'Optimizer access passed.',
            'action': 'No action required.',
            'permissions': <String>[],
          },
        ],
      },
    ],
    'checked_at': '2026-07-14T09:00:00Z',
    'issues': <Object>[],
  };
}
