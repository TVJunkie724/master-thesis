import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

import '../fixtures/architecture_profile_fixtures.dart';

void main() {
  test(
    'uses only canonical architecture reads and resolved evidence',
    () async {
      final architecture = Map<String, dynamic>.from(
        jsonDecode(
              File(
                '../contracts/architecture-profiles/v2/fixtures/valid/'
                'six-layer-aws-azure-eventing-small-resolved.json',
              ).readAsStringSync(),
            )
            as Map,
      );
      final runId = architecture['calculation_run_id'].toString();
      final resolved = {
        'twin_id': 'twin-1',
        'calculation_run_id': runId,
        'selected_for_deployment_at': '2026-08-03T10:00:00Z',
        'architecture_compatibility_status': 'ready',
        'origin': 'native_v2',
        'architecture': architecture,
      };
      final requests = <RequestOptions>[];
      final api = ApiService(
        dio: _dio((request) {
          requests.add(request);
          return switch ('${request.method} ${request.path}') {
            'GET /architecture-contract' => _json(
              architectureProfileDetailJson(
                profileId: 'six-layer-eventing',
                profileVersion: '1',
              ),
            ),
            'GET /twins/twin-1/architecture-contract' => _json(
              architectureSelectionJson(
                profileId: 'six-layer-eventing',
                profileVersion: '1',
              ),
            ),
            'GET /twins/twin-1/resolved-architecture' => _json(resolved),
            _
                when request.method == 'GET' &&
                    request.path ==
                        '/optimizer-runs/$runId/resolved-architecture' =>
              _json(resolved),
            _ => _json({}, statusCode: 404),
          };
        }),
      );

      final detail = await api.getCanonicalArchitectureContract();
      final selection = await api.getTwinArchitectureContract('twin-1');
      final twinResolved = await api.getSelectedResolvedArchitecture('twin-1');
      final runResolved = await api.getRunResolvedArchitecture(runId);

      expect(detail.summary.ref, selection.profileRef);
      expect(
        twinResolved.architecture.contentDigest,
        architecture['content_digest'],
      );
      expect(runResolved, twinResolved);
      expect(requests.map((item) => '${item.method} ${item.path}'), [
        'GET /architecture-contract',
        'GET /twins/twin-1/architecture-contract',
        'GET /twins/twin-1/resolved-architecture',
        'GET /optimizer-runs/$runId/resolved-architecture',
      ]);
    },
  );

  test('rejects canonical detail whose response identity differs', () async {
    final api = ApiService(
      dio: _dio(
        (_) => _json(
          architectureProfileDetailJson(
            profileId: 'fixture-profile',
            profileVersion: '2',
          ),
        ),
      ),
    );

    await expectLater(
      api.getCanonicalArchitectureContract(),
      throwsFormatException,
    );
  });
}

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

final class _CallbackAdapter implements HttpClientAdapter {
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
