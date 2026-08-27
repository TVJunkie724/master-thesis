import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/deployment_verification.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

void main() {
  test('uses typed start, history, and record Management routes', () async {
    final requests = <RequestOptions>[];
    final api = ApiService(
      dio: _dio((request) {
        requests.add(request);
        return switch ((request.method, request.path)) {
          ('POST', '/twins/twin-1/verify/dataflow') => _json({
            'schema_version': 'telemetry-verification-session.v1',
            'verification_id': 'verification-1',
            'session_id': 'session-1',
            'sse_url': '/sse/deploy/session-1',
            'status_url': '/twins/twin-1/verify/dataflow/verification-1',
            'status': 'running',
          }),
          ('GET', '/twins/twin-1/verify/dataflow/verification-1') => _json(
            _recordJson(),
          ),
          ('GET', '/twins/twin-1/verify/dataflow') => _json({
            'schema_version': 'telemetry-verification-history.v1',
            'verifications': [_recordJson()],
          }),
          _ => _json({}, statusCode: 404),
        };
      }),
    );

    final start = await api.verifyDataFlow('twin-1', {
      'iotDeviceId': 'device-1',
    });
    final record = await api.getDataFlowVerification(
      'twin-1',
      start.verificationId,
    );
    final history = await api.listDataFlowVerifications('twin-1', limit: 7);

    expect(start.status, TelemetryVerificationStatus.running);
    expect(record.result?.traceId, 'VERIFY-A1B2C3D4');
    expect(history.verifications.single.id, record.id);
    expect(requests[0].data, {
      'payload': {'iotDeviceId': 'device-1'},
    });
    expect(requests[2].queryParameters, {'limit': 7});
  });

  test('rejects history limits before Management I/O', () async {
    var calls = 0;
    final api = ApiService(
      dio: _dio((_) {
        calls += 1;
        return _json({});
      }),
    );

    await expectLater(
      api.listDataFlowVerifications('twin-1', limit: 0),
      throwsA(
        isA<AppException>().having(
          (error) => error.code,
          'code',
          'DEPLOYMENT_REQUEST_INVALID',
        ),
      ),
    );
    expect(calls, 0);
  });
}

Map<String, dynamic> _recordJson() => {
  'id': 'verification-1',
  'twin_id': 'twin-1',
  'deployment_id': 'deployment-1',
  'session_id': 'session-1',
  'device_id': 'device-1',
  'status': 'pass',
  'trace_id': 'VERIFY-A1B2C3D4',
  'result': {
    'schema_version': 'telemetry-verification.v1',
    'trace_id': 'VERIFY-A1B2C3D4',
    'status': 'pass',
    'pass_count': 3,
    'fail_count': 0,
    'skip_count': 0,
    'total_time': 4.2,
    'failed_phase': null,
    'evidence': [
      {
        'phase': 1,
        'kind': 'message_accepted',
        'provider': 'aws',
        'record_count': null,
        'correlation': null,
      },
      {
        'phase': 2,
        'kind': 'trace_correlated_hot_record',
        'provider': 'gcp',
        'record_count': 1,
        'correlation': null,
      },
      {
        'phase': 3,
        'kind': 'azure_twin_projection',
        'provider': 'azure',
        'record_count': null,
        'correlation': 'source_sequence',
      },
    ],
  },
  'error_code': null,
  'error_message': null,
  'requested_at': '2026-08-27T10:00:00Z',
  'completed_at': '2026-08-27T10:00:05Z',
};

Dio _dio(ResponseBody Function(RequestOptions) callback) {
  final dio = Dio(BaseOptions(baseUrl: 'http://management.test'));
  dio.httpClientAdapter = _CallbackAdapter(callback);
  return dio;
}

ResponseBody _json(Object body, {int statusCode = 200}) {
  return ResponseBody.fromString(
    jsonEncode(body),
    statusCode,
    headers: {
      Headers.contentTypeHeader: ['application/json'],
    },
  );
}

class _CallbackAdapter implements HttpClientAdapter {
  final ResponseBody Function(RequestOptions) callback;

  _CallbackAdapter(this.callback);

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async => callback(options);

  @override
  void close({bool force = false}) {}
}
