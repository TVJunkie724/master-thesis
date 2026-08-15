import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

import '../fixtures/architecture_profile_fixtures.dart';

void main() {
  test('uses only the seven Management architecture operations', () async {
    final architecture = Map<String, dynamic>.from(
      jsonDecode(
            File(
              '../contracts/architecture-profiles/v1/fixtures/valid/'
              'mixed-baseline-resolved-architecture.json',
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
      'origin': 'native_v1',
      'architecture': architecture,
    };
    final requests = <RequestOptions>[];
    final api = ApiService(
      dio: _dio((request) {
        requests.add(request);
        return switch ('${request.method} ${request.path}') {
          'GET /architecture-profiles' => _json([
            architectureProfileSummaryJson(),
          ]),
          'GET /architecture-profiles/fixture-profile/versions/2' => _json(
            architectureProfileDetailJson(),
          ),
          'GET /twins/twin-1/architecture-profile' => _json(
            architectureSelectionJson(),
          ),
          'POST /twins/twin-1/architecture-profile/change-preview' => _json(
            architecturePreviewJson(),
          ),
          'PUT /twins/twin-1/architecture-profile' => _json(
            architectureSelectionResultJson(),
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

    final profiles = await api.listArchitectureProfiles();
    final detail = await api.getArchitectureProfile('fixture-profile', '2');
    final selection = await api.getTwinArchitectureSelection('twin-1');
    final preview = await api.previewTwinArchitectureProfileChange(
      'twin-1',
      const ArchitectureProfileChangePreviewRequest(
        profileId: 'fixture-profile',
        profileVersion: '2',
        expectedRevision: 1,
      ),
    );
    final selected = await api.selectTwinArchitectureProfile(
      'twin-1',
      ArchitectureProfileSelectRequest.fromPreview(preview),
    );
    final twinResolved = await api.getSelectedResolvedArchitecture('twin-1');
    final runResolved = await api.getRunResolvedArchitecture(runId);

    expect(profiles.single.profileId, 'fixture-profile');
    expect(detail.logicalComponents.single.componentKind, 'ingress');
    expect(selection.revision, 1);
    expect(selected.revision, 2);
    expect(
      twinResolved.architecture.contentDigest,
      architecture['content_digest'],
    );
    expect(runResolved, twinResolved);
    expect(requests.map((item) => item.path), [
      '/architecture-profiles',
      '/architecture-profiles/fixture-profile/versions/2',
      '/twins/twin-1/architecture-profile',
      '/twins/twin-1/architecture-profile/change-preview',
      '/twins/twin-1/architecture-profile',
      '/twins/twin-1/resolved-architecture',
      '/optimizer-runs/$runId/resolved-architecture',
    ]);
    expect(requests[3].data, {
      'profile_id': 'fixture-profile',
      'profile_version': '2',
      'expected_revision': 1,
    });
    expect(requests[4].data, {
      'profile_id': 'fixture-profile',
      'profile_version': '2',
      'expected_revision': 1,
      'invalidation_digest': fixtureDigestB,
    });
  });

  test(
    'accepts the truthful empty catalog and rejects malformed entries',
    () async {
      final empty = ApiService(dio: _dio((_) => _json([])));
      expect(await empty.listArchitectureProfiles(), isEmpty);

      final malformed = ApiService(
        dio: _dio(
          (_) => _json([
            {...architectureProfileSummaryJson(), 'secret_key': 'forbidden'},
          ]),
        ),
      );
      await expectLater(
        malformed.listArchitectureProfiles(),
        throwsFormatException,
      );
    },
  );
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
