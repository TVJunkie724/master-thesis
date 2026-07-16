import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/authentication.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

void main() {
  test(
    'parses provider capabilities and authentication start contract',
    () async {
      final dio = Dio(BaseOptions(baseUrl: 'https://management.test'));
      dio.httpClientAdapter = _Adapter((options) {
        if (options.path == '/auth/providers') {
          return ResponseBody.fromString(
            '{"providers":[{"provider":"google","display_name":"Google",'
            '"enabled":true,"unavailable_reason":null}]}',
            200,
            headers: {
              Headers.contentTypeHeader: [Headers.jsonContentType],
            },
          );
        }
        return ResponseBody.fromString(
          '{"auth_url":"https://accounts.example.test/login",'
          '"transaction_id":"11111111-1111-4111-8111-111111111111",'
          '"poll_verifier":"poll-verifier-with-at-least-thirty-two-characters",'
          '"expires_at":"2030-01-01T00:00:00Z","poll_interval_ms":1000}',
          201,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          },
        );
      });
      final api = ApiService(dio: dio);

      final providers = await api.getAuthProviders();
      final transaction = await api.startExternalLogin(IdentityProvider.google);

      expect(providers.single.provider, IdentityProvider.google);
      expect(providers.single.enabled, isTrue);
      expect(transaction.authUri.scheme, 'https');
      expect(transaction.pollInterval, const Duration(seconds: 1));
    },
  );

  test(
    'rejects insecure provider URLs and malformed authenticated sessions',
    () {
      expect(
        () => AuthLoginTransaction.fromJson({
          'auth_url': 'http://accounts.example.test/login',
          'transaction_id': '11111111-1111-4111-8111-111111111111',
          'poll_verifier': 'poll-verifier-with-at-least-thirty-two-characters',
          'expires_at': '2030-01-01T00:00:00Z',
          'poll_interval_ms': 1000,
        }),
        throwsFormatException,
      );
      expect(
        () => AuthExchangeResult.fromJson({
          'status': 'authenticated',
          'access_token': 'token with whitespace',
          'token_type': 'bearer',
          'expires_in': 3600,
          'user': {'id': 'u1'},
        }),
        throwsFormatException,
      );
      expect(
        () => AuthLoginTransaction.fromJson({
          'auth_url': 'https://accounts.example.test/login',
          'transaction_id': 'not-a-canonical-uuid-value-000000000',
          'poll_verifier': 'poll-verifier-with-at-least-thirty-two-characters',
          'expires_at': '2030-01-01T00:00:00Z',
          'poll_interval_ms': 1000,
        }),
        throwsFormatException,
      );
    },
  );

  test('401 clears bearer and signals the auth composition boundary', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://management.test'));
    dio.httpClientAdapter = _Adapter(
      (_) => ResponseBody.fromString(
        '{"error_code":"INVALID_TOKEN"}',
        401,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      ),
    );
    final api = ApiService(dio: dio, initialAuthToken: 'opaque-token');
    var unauthorizedSignals = 0;
    api.setUnauthorizedHandler(() => unauthorizedSignals++);

    await expectLater(api.getCurrentUser(), throwsA(isA<DioException>()));

    expect(await api.getAuthToken(), isNull);
    expect(unauthorizedSignals, 1);
  });
}

class _Adapter implements HttpClientAdapter {
  _Adapter(this.handler);

  final ResponseBody Function(RequestOptions options) handler;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async => handler(options);

  @override
  void close({bool force = false}) {}
}
