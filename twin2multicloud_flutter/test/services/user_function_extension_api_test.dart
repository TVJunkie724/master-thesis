import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/user_function_extension.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

void main() {
  test('uses typed Management routes and multipart field ownership', () async {
    final requests = <RequestOptions>[];
    final api = ApiService(
      dio: _dio((request) {
        requests.add(request);
        return switch (request.path) {
          '/architecture/extension-slots' => _json({
            'schema_version': 'user-function-extension-slot-list.v1',
            'slots': [_slotJson()],
          }),
          '/twins/twin-1/user-functions/processor.telemetry/validate' => _json(
            _validationJson(),
          ),
          '/twins/twin-1/user-functions/processor.telemetry' =>
            request.method == 'DELETE'
                ? ResponseBody.fromString('', 204)
                : _json(_userFunctionJson()),
          '/twins/twin-1/user-functions' => _json({
            'schema_version': 'twin-user-function-list.v1',
            'items': [_userFunctionJson()],
          }),
          _ => _json({}, statusCode: 404),
        };
      }),
    );

    final slot = (await api.listExtensionSlots()).single;
    final upload = UserFunctionSourceUpload(
      slot: slot,
      draft: UserFunctionSourceDraft(
        filename: 'processor.zip',
        bytes: Uint8List.fromList([1, 2, 3]),
        configuration: const {'scale_factor': 1},
      ),
    );
    final validation = await api.validateTwinUserFunction('twin-1', upload);
    final userFunction = await api.saveTwinUserFunction('twin-1', upload);
    final current = await api.listTwinUserFunctions('twin-1');
    await api.deleteTwinUserFunction('twin-1', slot);

    expect(validation.slotId, slot.slotId);
    expect(userFunction.twinId, 'twin-1');
    expect(current, [userFunction]);
    final multipart = requests[1].data as FormData;
    expect(multipart.files.map((entry) => entry.key), {
      'metadata',
      'source_archive',
    });
    expect(requests[2].method, 'PUT');
    final savedMultipart = requests[2].data as FormData;
    expect(savedMultipart.files.map((entry) => entry.key), {
      'metadata',
      'source_archive',
    });
    expect(requests[3].method, 'GET');
    expect(requests[4].method, 'DELETE');
    expect(requests[4].queryParameters, {'slot_version': '1'});
  });

  test('fails closed on an unknown list schema version', () async {
    final api = ApiService(
      dio: _dio(
        (_) => _json({
          'schema_version': 'user-function-extension-slot-list.v2',
          'slots': [_slotJson()],
        }),
      ),
    );

    await expectLater(api.listExtensionSlots(), throwsFormatException);
  });

  test('fails closed on additional list and slot platform fields', () async {
    final api = ApiService(
      dio: _dio(
        (_) => _json({
          'schema_version': 'user-function-extension-slot-list.v1',
          'slots': [
            {
              ..._slotJson(),
              'provider_handler': 'lambda_function.lambda_handler',
            },
          ],
          'terraform_workspace': '/tmp/forbidden',
        }),
      ),
    );

    await expectLater(api.listExtensionSlots(), throwsFormatException);
  });
}

Map<String, dynamic> _slotJson() => {
  'schema_version': 'user-function-extension-slot.v1',
  'slot_id': 'processor.telemetry',
  'slot_version': '1',
  'display_name': 'Telemetry processor',
  'entrypoint': 'process',
  'runtime_id': 'python311',
  'configuration_schema': {
    r'$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object',
    'additionalProperties': false,
    'properties': {
      'scale_factor': {
        'type': 'number',
        'title': 'Scale factor',
        'minimum': 0,
        'maximum': 1000,
        'user_editable': true,
        'secret': false,
      },
    },
    'required': ['scale_factor'],
  },
  'resource_limits': {
    'timeout_seconds': 30,
    'memory_mb': 256,
    'artifact_bytes': 10485760,
    'source_bytes': 2097152,
    'response_bytes': 1048576,
    'file_count': 64,
    'dependency_count': 64,
  },
  'permission_capabilities': ['capability.telemetry.process'],
  'secret_policy': 'forbidden',
};

Map<String, dynamic> _validationJson() => {
  'schema_version': 'user-function-validation-result.v1',
  'valid': true,
  'artifact_digest': 'sha256:${List.filled(64, 'a').join()}',
  'slot_id': 'processor.telemetry',
  'slot_version': '1',
  'runtime_id': 'python311',
  'source_files': ['process.py', 'requirements.lock'],
  'dependencies': <String>[],
  'checks': ['schema_valid'],
};

Map<String, dynamic> _userFunctionJson() => {
  'schema_version': 'twin-user-function.v1',
  'function_id': '10000000-0000-4000-8000-000000000001',
  'twin_id': 'twin-1',
  'slot_id': 'processor.telemetry',
  'slot_version': '1',
  'artifact_digest': 'sha256:${List.filled(64, 'a').join()}',
  'runtime_id': 'python311',
  'configuration': {'scale_factor': 1},
  'declared_capabilities': ['capability.telemetry.process'],
  'validator_version': 'user-function-validator.v1',
  'source_files': ['process.py', 'requirements.lock'],
  'dependencies': <String>[],
  'created_at': '2026-07-19T00:00:00Z',
  'updated_at': '2026-07-19T00:00:00Z',
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
