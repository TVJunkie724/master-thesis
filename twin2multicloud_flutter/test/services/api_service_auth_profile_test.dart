import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

void main() {
  test('explicit development token is attached exactly once', () async {
    final seenAuthorization = <Object?>[];
    final dio = _recordingDio((options) {
      seenAuthorization.add(options.headers['Authorization']);
      return _jsonResponse([]);
    });
    final api = ApiService(dio: dio, initialAuthToken: 'local-token');

    await api.getTwins();
    await api.getTwins();

    expect(seenAuthorization, ['Bearer local-token', 'Bearer local-token']);
    expect(await api.getAuthToken(), 'local-token');
  });

  test('token-free adapter sends no Authorization header', () async {
    Object? authorization;
    final dio = _recordingDio((options) {
      authorization = options.headers['Authorization'];
      return _jsonResponse([]);
    });
    final api = ApiService(dio: dio);

    await api.getTwins();

    expect(authorization, isNull);
    expect(await api.getAuthToken(), isNull);
  });

  test('session token can be set and cleared without rebuilding', () async {
    final seenAuthorization = <Object?>[];
    final dio = _recordingDio((options) {
      seenAuthorization.add(options.headers['Authorization']);
      return _jsonResponse([]);
    });
    final api = ApiService(dio: dio);

    api.setToken('session-token');
    await api.getTwins();
    api.setToken(null);
    await api.getTwins();

    expect(seenAuthorization, ['Bearer session-token', null]);
    expect(await api.getAuthToken(), isNull);
  });

  test('invalid token is rejected without echoing its value', () {
    const secret = 'never echo this';
    try {
      ApiService(
        baseUri: Uri.parse('http://management.test'),
        initialAuthToken: secret,
      );
      fail('Expected whitespace-bearing token to fail');
    } on ArgumentError catch (error) {
      expect(error.message, contains('Authentication token'));
      expect(error.message, isNot(contains(secret)));
    }
  });

  test('construction requires exactly one transport source', () {
    expect(() => ApiService(), throwsArgumentError);
    expect(
      () => ApiService(
        dio: Dio(BaseOptions(baseUrl: 'http://management.test')),
        baseUri: Uri.parse('http://management.test'),
      ),
      throwsArgumentError,
    );
  });

  test('injected Dio must expose a valid Management API origin', () {
    expect(() => ApiService(dio: Dio()), throwsArgumentError);
    expect(
      () => ApiService(
        dio: Dio(BaseOptions(baseUrl: 'http://user@management.test/api')),
      ),
      throwsArgumentError,
    );
  });

  test('SSE paths resolve against the injected Management API origin', () {
    final api = ApiService(
      baseUri: Uri.parse('https://management.example.test/'),
    );

    expect(
      api.getSseUrl('/sse/deploy/session-1'),
      'https://management.example.test/sse/deploy/session-1',
    );
    expect(
      api.getSseUrl('/sse/deploy/session-1', lastEventId: 7),
      'https://management.example.test/sse/deploy/session-1?last_event_id=7',
    );
  });

  test('SSE URL builder rejects external and ambiguous paths', () {
    final api = ApiService(baseUri: Uri.parse('http://management.test'));

    for (final value in [
      'https://attacker.test/sse',
      '//attacker.test/sse',
      'sse/deploy/session-1',
      '/sse/deploy/session-1?token=unsafe',
      '/sse/deploy/session-1#fragment',
      '/sse/deploy/../other-session',
    ]) {
      expect(
        () => api.getSseUrl(value),
        throwsA(
          isA<AppException>().having(
            (error) => error.code,
            'code',
            'DEPLOYMENT_CONTRACT_INVALID',
          ),
        ),
        reason: value,
      );
    }
    expect(
      () => api.getSseUrl('/sse/deploy/session-1', lastEventId: -1),
      throwsA(
        isA<AppException>().having(
          (error) => error.code,
          'code',
          'DEPLOYMENT_CONTRACT_INVALID',
        ),
      ),
    );
  });
}

Dio _recordingDio(ResponseBody Function(RequestOptions) callback) {
  final dio = Dio(BaseOptions(baseUrl: 'http://management.test'));
  dio.httpClientAdapter = _CallbackAdapter(callback);
  return dio;
}

ResponseBody _jsonResponse(Object body) {
  return ResponseBody.fromString(
    jsonEncode(body),
    200,
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
  ) async {
    return callback(options);
  }

  @override
  void close({bool force = false}) {}
}
