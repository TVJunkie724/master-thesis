import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
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

    test('creates a durable optimizer run with immutable evidence', () async {
      RequestOptions? captured;
      final api = ApiService(
        dio: _dio((request) {
          captured = request;
          return switch (request.path) {
            '/twins/twin-1/optimizer-runs/' => _json(
              _optimizerRunJson('twin-1'),
            ),
            _ => _json({}, statusCode: 404),
          };
        }),
      );

      final run = await api.createOptimizerRun(
        'twin-1',
        TestFixtures.defaultCalcParams,
      );

      final calculation = run.optimization;
      expect(captured?.method, 'POST');
      expect(captured?.data, {
        'params': TestFixtures.defaultCalcParams.toJson(),
      });
      expect(run.id, 'run-1');
      expect(run.twinId, 'twin-1');
      expect(calculation.result.cheapestPath, isNotEmpty);
      expect(calculation.result.pricingCatalogContext, isNotNull);
      expect(
        calculation.result.pricingCatalogContext!.catalogs.keys,
        hasLength(3),
      );
      expect(run.deploymentRun.specification, isNotNull);
    });

    test(
      'loads a newer unselected run without inheriting the older selection',
      () async {
        final older = _optimizerRunJson('twin-1', runId: 'run-older')
          ..['created_at'] = '2026-07-17T10:00:00Z'
          ..['selected_for_deployment_at'] = '2026-07-17T10:01:00Z'
          ..remove('result_summary')
          ..remove('total_monthly_cost')
          ..remove('completed_at');
        final latest = _optimizerRunJson('twin-1', runId: 'run-latest')
          ..remove('result_summary')
          ..remove('total_monthly_cost')
          ..remove('completed_at');
        final detail = _optimizerRunJson('twin-1', runId: 'run-latest');
        final requests = <String>[];
        final api = ApiService(
          dio: _dio((request) {
            requests.add(request.path);
            return switch (request.path) {
              '/twins/twin-1/optimizer-runs/' => _json([older, latest]),
              '/twins/twin-1/optimizer-runs/run-latest' => _json(detail),
              _ => _json({}, statusCode: 404),
            };
          }),
        );

        final run = await api.getLatestOptimizerRun('twin-1');

        expect(run?.id, 'run-latest');
        expect(run?.selectedForDeploymentAt, isNull);
        expect(requests, [
          '/twins/twin-1/optimizer-runs/',
          '/twins/twin-1/optimizer-runs/run-latest',
        ]);
      },
    );

    test('rejects duplicate selected optimizer run summaries', () async {
      final first = _optimizerRunJson('twin-1', runId: 'run-1')
        ..['selected_for_deployment_at'] = '2026-07-18T10:01:00Z';
      final second = _optimizerRunJson('twin-1', runId: 'run-2')
        ..['selected_for_deployment_at'] = '2026-07-18T10:02:00Z';
      final api = ApiService(dio: _dio((_) => _json([first, second])));

      await expectLater(
        api.getLatestOptimizerRun('twin-1'),
        throwsFormatException,
      );
    });

    test('selects a run only through the Management API contract', () async {
      final selectedAt = '2026-07-18T10:02:00Z';
      RequestOptions? captured;
      final specification = TypedApiFixtures.deploymentSpecificationJson(
        runId: 'run-1',
      );
      final summary = _optimizerRunJson('twin-1')
        ..remove('result_summary')
        ..remove('total_monthly_cost')
        ..remove('completed_at')
        ..remove('resolved_deployment_specification')
        ..['selected_for_deployment_at'] = selectedAt;
      final api = ApiService(
        dio: _dio((request) {
          captured = request;
          return _json({
            'run': summary,
            'selected_for_deployment_at': selectedAt,
            'resolved_deployment_specification': specification,
          });
        }),
      );

      final result = await api.selectOptimizerRunForDeployment(
        'twin-1',
        'run-1',
      );

      expect(captured?.method, 'POST');
      expect(
        captured?.path,
        '/twins/twin-1/optimizer-runs/run-1/select-for-deployment',
      );
      expect(result.run.selectedForDeploymentAt, isNotNull);
    });

    test('rejects an inconsistent durable run total', () async {
      final response = _optimizerRunJson('twin-1')
        ..['total_monthly_cost'] = 999;
      final api = ApiService(dio: _dio((_) => _json(response)));

      await expectLater(
        api.createOptimizerRun('twin-1', TestFixtures.defaultCalcParams),
        throwsFormatException,
      );
    });

    test('rejects a new durable run without exact transfer evidence', () async {
      final response = _optimizerRunJson('twin-1')
        ..['result_summary'] = TestFixtures.calcResultJson['result'];
      final api = ApiService(dio: _dio((_) => _json(response)));

      await expectLater(
        api.createOptimizerRun('twin-1', TestFixtures.defaultCalcParams),
        throwsFormatException,
      );
    });

    test('rejects an optimizer run from a different request context', () async {
      final response = _optimizerRunJson('other-twin');
      final api = ApiService(dio: _dio((_) => _json(response)));

      await expectLater(
        api.createOptimizerRun('twin-1', TestFixtures.defaultCalcParams),
        throwsFormatException,
      );
    });

    test('rejects inconsistent optimizer run timestamps', () async {
      final response = _optimizerRunJson('twin-1')
        ..['completed_at'] = '2026-07-18T09:59:59Z';
      final api = ApiService(dio: _dio((_) => _json(response)));

      await expectLater(
        api.createOptimizerRun('twin-1', TestFixtures.defaultCalcParams),
        throwsFormatException,
      );
    });

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

Map<String, dynamic> _optimizerRunJson(
  String twinId, {
  String runId = 'run-1',
}) => {
  'id': runId,
  'twin_id': twinId,
  'status': 'succeeded',
  'result_summary': TestFixtures.calcResultWithTransferEvidenceJson['result'],
  'total_monthly_cost': 55.67,
  'currency': 'USD',
  'deployment_compatibility_status': 'ready',
  'deployment_specification_digest':
      TypedApiFixtures.deploymentSpecificationJson(runId: runId)['digest'],
  'deployment_specification_version': 'resolved-deployment-specification.v1',
  'resolved_deployment_specification':
      TypedApiFixtures.deploymentSpecificationJson(runId: runId),
  'selected_for_deployment_at': null,
  'created_at': '2026-07-18T10:00:00Z',
  'completed_at': '2026-07-18T10:00:01Z',
};

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
