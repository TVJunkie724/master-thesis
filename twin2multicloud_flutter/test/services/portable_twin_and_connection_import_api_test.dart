import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/twin_transfer.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

void main() {
  test(
    'uses exact duplicate, import, and export Management contracts',
    () async {
      final requests = <RequestOptions>[];
      final api = ApiService(
        dio: _dio((request) {
          requests.add(request);
          return switch (request.path) {
            '/twins/source/duplicate' => _json(_twinJson('copy', 'Copy')),
            '/twins/import' => _json(_twinJson('imported', 'Imported')),
            '/twins/source/export' => ResponseBody.fromBytes(
              [80, 75, 3, 4],
              200,
              headers: {
                Headers.contentTypeHeader: ['application/zip'],
                'content-disposition': [
                  'attachment; filename="source.twin.zip"',
                ],
              },
            ),
            _ => _json({}, statusCode: 404),
          };
        }),
      );

      final duplicate = await api.duplicateTwin(
        'source',
        TwinDuplicateRequest(name: 'Copy'),
      );
      final imported = await api.importTwin(
        TwinImportRequest(
          newName: 'Imported',
          filename: 'source.twin.zip',
          bytes: Uint8List.fromList([80, 75, 3, 4]),
        ),
      );
      final exported = await api.exportTwin('source');

      expect(duplicate.id, 'copy');
      expect(imported.id, 'imported');
      expect(exported.filename, 'source.twin.zip');
      expect(exported.bytes, [80, 75, 3, 4]);
      expect(requests[0].data, {'name': 'Copy'});
      final importForm = requests[1].data as FormData;
      expect(importForm.fields, hasLength(1));
      expect(importForm.fields.single.key, 'new_name');
      expect(importForm.fields.single.value, 'Imported');
      expect(importForm.files.single.key, 'archive');
      expect(importForm.files.single.value.filename, 'source.twin.zip');
      expect(requests[2].method, 'GET');
    },
  );

  test(
    'imports a provider file through one deployment-only multipart request',
    () async {
      RequestOptions? captured;
      final api = ApiService(
        dio: _dio((request) {
          captured = request;
          return _json(_connectionJson());
        }),
      );
      final connection = await api.importCloudConnection(
        CloudConnectionImportRequest(
          provider: CloudProvider.gcp,
          displayName: 'GCP thesis',
          region: 'europe-west1',
          targetScopeId: 'project-1',
          filename: 'service-account.json',
          bytes: Uint8List.fromList(utf8.encode('{"private_key":"hidden"}')),
        ),
      );

      expect(connection.purpose, CloudConnectionPurpose.deployment);
      expect(captured?.path, '/cloud-connections/import');
      final form = captured?.data as FormData;
      expect(form.fields.single.key, 'metadata');
      expect(jsonDecode(form.fields.single.value), {
        'provider': 'gcp',
        'purpose': 'deployment',
        'display_name': 'GCP thesis',
        'region': 'europe-west1',
        'target_scope_id': 'project-1',
      });
      expect(form.files.single.key, 'file');
      expect(form.files.single.value.filename, 'service-account.json');
      expect(form.fields.single.value, isNot(contains('private_key')));
    },
  );

  test('fails closed on an unsafe portable export filename', () async {
    final api = ApiService(
      dio: _dio(
        (_) => ResponseBody.fromBytes(
          [80, 75, 3, 4],
          200,
          headers: {
            Headers.contentTypeHeader: ['application/zip'],
            'content-disposition': ['attachment; filename="../secret.zip"'],
          },
        ),
      ),
    );

    await expectLater(api.exportTwin('source'), throwsFormatException);
  });
}

Map<String, dynamic> _twinJson(String id, String name) => {
  'id': id,
  'name': name,
  'state': 'draft',
  'providers': <String>[],
  'created_at': '2026-08-27T10:00:00Z',
  'updated_at': '2026-08-27T10:00:00Z',
  'last_deployed_at': null,
  'deployed_at': null,
  'destroyed_at': null,
  'last_error': null,
  'last_deployment_logs': null,
};

Map<String, dynamic> _connectionJson() => {
  'id': 'gcp-1',
  'provider': 'gcp',
  'purpose': 'deployment',
  'scope': 'user',
  'is_default_for_pricing': false,
  'display_name': 'GCP thesis',
  'auth_type': 'service_account',
  'cloud_scope': {'project_id': 'project-1'},
  'payload_fingerprint': 'opaque',
  'payload_summary': {'region': 'europe-west1'},
  'validation_status': 'untested',
  'validation_message': null,
  'last_validated_at': null,
  'last_used_at': null,
  'created_at': '2026-08-27T10:00:00Z',
  'updated_at': '2026-08-27T10:00:00Z',
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
