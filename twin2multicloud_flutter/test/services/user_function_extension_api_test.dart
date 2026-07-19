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
          '/user-function-artifacts/validate' => _json(_validationJson()),
          '/twins/twin-1/extension-bindings/processor.telemetry' => _json(
            _bindingJson(),
          ),
          _ => _json({}, statusCode: 404),
        };
      }),
    );

    final slot = (await api.listExtensionSlots()).single;
    final validation = await api.validateUserFunctionArtifact(
      UserFunctionArtifactUpload(
        slot: slot,
        draft: UserFunctionSourceDraft(
          filename: 'processor.zip',
          bytes: Uint8List.fromList([1, 2, 3]),
          configuration: const {'scale_factor': 1},
        ),
      ),
    );
    final binding = await api.bindTwinExtensionArtifact(
      'twin-1',
      slot,
      '00000000-0000-4000-8000-000000000001',
    );

    expect(validation.slotId, slot.slotId);
    expect(binding.revision, 1);
    final multipart = requests[1].data as FormData;
    expect(multipart.files.map((entry) => entry.key), {
      'metadata',
      'source_archive',
    });
    expect(requests[2].method, 'PUT');
    expect(requests[2].data, {
      'artifact_id': '00000000-0000-4000-8000-000000000001',
      'slot_version': '1',
    });
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

Map<String, dynamic> _bindingJson() => {
  'schema_version': 'twin-extension-binding.v1',
  'binding_id': '10000000-0000-4000-8000-000000000001',
  'twin_id': 'twin-1',
  'slot_id': 'processor.telemetry',
  'slot_version': '1',
  'artifact_id': '00000000-0000-4000-8000-000000000001',
  'artifact_digest': 'sha256:${List.filled(64, 'a').join()}',
  'binding_digest': 'sha256:${List.filled(64, 'b').join()}',
  'active': true,
  'revision': 1,
  'created_at': '2026-07-19T00:00:00Z',
  'unbound_at': null,
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
