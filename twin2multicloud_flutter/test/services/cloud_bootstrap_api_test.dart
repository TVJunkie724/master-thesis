import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_bootstrap.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

void main() {
  test('uses only Management guide/session operations and executes once', () async {
    final guideJson = _fixture('aws-guide.json');
    final readyJson = _fixture('aws-ready-session.json');
    final draftJson = Map<String, dynamic>.from(readyJson)
      ..['revision'] = 1
      ..['state'] = 'draft'
      ..remove('credential_origin')
      ..remove('disposal_status')
      ..remove('credential_expires_at')
      ..remove('safe_credential_identifier')
      ..remove('finding')
      ..remove('connection')
      ..['command_permissions'] = ['execute', 'cancel'];
    final cancelledJson = Map<String, dynamic>.from(draftJson)
      ..['revision'] = 2
      ..['state'] = 'cancelled'
      ..['command_permissions'] = ['start_new'];
    final requests = <RequestOptions>[];
    Map<String, dynamic>? executeBody;
    final api = ApiService(
      dio: _dio((request) {
        requests.add(request);
        if (request.method == 'GET' &&
            request.path == '/cloud-bootstrap/sessions/${draftJson['id']}') {
          return _json(draftJson);
        }
        if (request.method == 'POST' &&
            request.path ==
                '/cloud-bootstrap/sessions/${draftJson['id']}/execute') {
          executeBody = Map<String, dynamic>.from(
            jsonDecode(jsonEncode(request.data)) as Map,
          );
          return _json(readyJson);
        }
        if (request.method == 'POST' &&
            request.path ==
                '/cloud-bootstrap/sessions/${draftJson['id']}/acknowledge-manual-revocation') {
          return _json(readyJson);
        }
        if (request.method == 'POST' &&
            request.path ==
                '/cloud-bootstrap/sessions/${draftJson['id']}/cancel') {
          return _json(cancelledJson);
        }
        return switch ('${request.method} ${request.path}') {
          'POST /cloud-bootstrap/aws/guide' => _json(guideJson),
          'GET /cloud-bootstrap/sessions' => _json({'items': <Object>[]}),
          'POST /cloud-bootstrap/sessions' => _json(draftJson),
          _ => _json({}, statusCode: 404),
        };
      }),
    );
    final target = CloudBootstrapTarget.aws(
      accountId: '123456789012',
      region: 'eu-central-1',
    );

    final guide = await api.getCloudBootstrapGuide(CloudProvider.aws, target);
    expect(
      await api.listCloudBootstrapSessions(provider: CloudProvider.aws),
      isEmpty,
    );
    final draft = await api.createCloudBootstrapSession(
      guide: guide,
      entryPoint: CloudBootstrapEntryPoint.settings,
      displayName: 'Thesis AWS deployment access',
      idempotencyKey: 'create-command-00000001',
    );
    await api.getCloudBootstrapSession(draft.id);
    const secret = 'submitted-bootstrap-secret';
    final ready = await api.executeCloudBootstrapSession(
      draft.id,
      CloudBootstrapExecuteRequest(
        expectedRevision: draft.revision,
        idempotencyKey: 'execute-command-00000001',
        credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
        credential: const {
          'provider': 'aws',
          'access_key_id': 'AKIAEXAMPLE00000001',
          'secret_access_key': secret,
        },
      ),
    );
    await api.acknowledgeCloudBootstrapRevocation(draft.id, 3);
    await api.cancelCloudBootstrapSession(draft.id, draft.revision);

    expect(ready.connection?.validationStatus, 'valid');
    expect(requests.map((item) => '${item.method} ${item.path}'), [
      'POST /cloud-bootstrap/aws/guide',
      'GET /cloud-bootstrap/sessions',
      'POST /cloud-bootstrap/sessions',
      'GET /cloud-bootstrap/sessions/${draft.id}',
      'POST /cloud-bootstrap/sessions/${draft.id}/execute',
      'POST /cloud-bootstrap/sessions/${draft.id}/acknowledge-manual-revocation',
      'POST /cloud-bootstrap/sessions/${draft.id}/cancel',
    ]);
    final execute = requests[4];
    expect(execute.extra['sensitiveRequestBody'], isTrue);
    expect(
      executeBody?['credential'],
      containsPair('secret_access_key', secret),
    );
    expect(execute.data, isEmpty);
    expect(requests[5].data, {'expected_revision': 3});
    expect(requests[6].data, {'expected_revision': draft.revision});
    expect(jsonEncode(readyJson), isNot(contains(secret)));
  });
}

Map<String, dynamic> _fixture(String name) => Map<String, dynamic>.from(
  jsonDecode(
        File(
          'assets/contracts/cloud-bootstrap/v1/fixtures/valid/$name',
        ).readAsStringSync(),
      )
      as Map,
);

Dio _dio(ResponseBody Function(RequestOptions) callback) {
  final dio = Dio(BaseOptions(baseUrl: 'http://management.test'));
  dio.httpClientAdapter = _CallbackAdapter(callback);
  return dio;
}

ResponseBody _json(Object body, {int statusCode = 200}) =>
    ResponseBody.fromString(
      jsonEncode(body),
      statusCode,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );

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
