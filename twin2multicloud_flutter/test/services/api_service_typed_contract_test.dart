import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/optimizer_config.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

import '../fixtures/test_fixtures.dart';
import '../fixtures/provider_capability_fixture.dart';
import '../fixtures/typed_api_fixtures.dart';

void main() {
  group('ApiService typed contracts', () {
    test(
      'decodes twin collections and rejects a malformed successful body',
      () async {
        final valid = ApiService(dio: _dio((_) => _json([_twinJson()])));
        final twins = await valid.getTwins();

        expect(twins.single.id, 'twin-1');
        expect(twins.single.createdAt, DateTime.utc(2026, 7, 15, 10));

        final malformed = ApiService(dio: _dio((_) => _json({'twins': []})));
        await expectLater(malformed.getTwins(), throwsFormatException);
      },
    );

    test('decodes calculation with immutable catalog evidence', () async {
      final api = ApiService(
        dio: _dio((request) {
          return switch (request.path) {
            '/optimizer/calculate' => _json(TestFixtures.calcResultJson),
            _ => _json({}, statusCode: 404),
          };
        }),
      );

      final calculation = await api.calculateCosts(
        TestFixtures.defaultCalcParams,
      );

      expect(calculation.result.cheapestPath, isNotEmpty);
      expect(calculation.result.pricingCatalogContext, isNotNull);
      expect(
        calculation.result.pricingCatalogContext!.catalogs.keys,
        hasLength(3),
      );
    });

    test(
      'persists only result data and lets Management verify evidence',
      () async {
        RequestOptions? captured;
        final api = ApiService(
          dio: _dio((request) {
            captured = request;
            return _json({});
          }),
        );
        final optimization = TypedApiFixtures.optimization();

        await api.saveOptimizerResult(
          'twin-1',
          params: TestFixtures.defaultCalcParams,
          optimization: optimization,
          cheapestPath: CheapestPath.fromSegments(
            optimization.result.cheapestPath,
          ),
        );

        expect(captured?.path, '/twins/twin-1/optimizer-config/result');
        final payload = Map<String, dynamic>.from(captured?.data as Map);
        expect(payload.keys.toSet(), {'params', 'result', 'cheapest_path'});
        expect(payload, isNot(contains('pricing_snapshots')));
        expect(payload, isNot(contains('pricing_timestamps')));
        expect((payload['result'] as Map)['pricingCatalogs'], isNotNull);
      },
    );

    test('maps only optional configuration 404 responses to null', () async {
      final api = ApiService(dio: _dio((_) => _json({}, statusCode: 404)));

      expect(await api.getOptimizerConfig('twin-1'), isNull);
      expect(await api.getDeployerConfig('twin-1'), isNull);
    });

    test('propagates server failures for optional configuration', () async {
      final api = ApiService(dio: _dio((_) => _json({}, statusCode: 500)));

      await expectLater(
        api.getOptimizerConfig('twin-1'),
        throwsA(isA<DioException>()),
      );
      await expectLater(
        api.getDeployerConfig('twin-1'),
        throwsA(isA<DioException>()),
      );
    });

    test('does not reinterpret malformed optional config as absent', () async {
      final api = ApiService(dio: _dio((_) => _json({'id': 'only-id'})));

      await expectLater(
        api.getOptimizerConfig('twin-1'),
        throwsFormatException,
      );
    });

    test('loads provider capabilities only through Management API', () async {
      final api = ApiService(
        dio: _dio((request) {
          expect(request.method, 'GET');
          expect(request.path, '/platform/provider-capabilities');
          return _json(platformProviderCapabilitiesJson());
        }),
      );

      final result = await api.getProviderCapabilities();

      expect(result.capability('gcp', 'l4').selectable, isFalse);
    });
  });
}

Map<String, dynamic> _twinJson() => {
  'id': 'twin-1',
  'name': 'Test Twin',
  'state': 'draft',
  'created_at': '2026-07-15T10:00:00Z',
  'updated_at': '2026-07-15T10:00:00Z',
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
