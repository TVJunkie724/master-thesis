import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/cloud_access/cloud_access.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;

  setUpAll(() {
    registerFallbackValue(_createRequest());
    registerFallbackValue(_importRequest());
  });

  setUp(() => api = MockApiService());

  test('loads the deployment administrator list from Management', () async {
    when(() => api.listCloudConnections()).thenAnswer(
      (_) async => [
        _connection(id: 'aws-deploy'),
        _connection(id: 'azure-deploy', provider: CloudProvider.azure),
      ],
    );
    final bloc = CloudAccessBloc(api)..add(const CloudAccessStarted());

    await bloc.stream.firstWhere((state) => !state.isLoading);

    expect(bloc.state.connections.map((item) => item.id), [
      'aws-deploy',
      'azure-deploy',
    ]);
    await bloc.close();
  });

  test('preserves deployment list when reload fails', () async {
    var calls = 0;
    when(() => api.listCloudConnections()).thenAnswer((_) async {
      if (calls++ == 0) return [_connection(id: 'aws-deploy')];
      throw Exception('Management API unavailable');
    });
    final bloc = CloudAccessBloc(api)..add(const CloudAccessStarted());
    await bloc.stream.firstWhere((state) => state.connections.isNotEmpty);

    bloc.add(const CloudAccessReloadRequested());
    await bloc.stream.firstWhere((state) => state.loadError != null);

    expect(bloc.state.connections.single.id, 'aws-deploy');
    await bloc.close();
  });

  test('creates deployment access and reloads the list', () async {
    when(
      () => api.createCloudConnection(any()),
    ).thenAnswer((_) async => _connection(id: 'aws-deploy'));
    when(
      () => api.listCloudConnections(),
    ).thenAnswer((_) async => [_connection(id: 'aws-deploy')]);
    final bloc = CloudAccessBloc(api);

    bloc.add(CloudAccessCreateRequested(_createRequest()));
    await bloc.stream.firstWhere((state) => state.feedback?.isError == false);

    verify(() => api.createCloudConnection(any())).called(1);
    verify(() => api.listCloudConnections()).called(1);
    expect(bloc.state.connections.single.id, 'aws-deploy');
    expect(bloc.state.isCreating, isFalse);
    await bloc.close();
  });

  test('imports once while busy and reloads deployment connections', () async {
    final completion = Completer<CloudConnection>();
    when(
      () => api.importCloudConnection(any()),
    ).thenAnswer((_) => completion.future);
    when(
      () => api.listCloudConnections(),
    ).thenAnswer((_) async => [_connection(id: 'aws-imported')]);
    final bloc = CloudAccessBloc(api);

    bloc.add(CloudAccessImportRequested(_importRequest()));
    await bloc.stream.firstWhere((state) => state.isImporting);
    bloc.add(CloudAccessImportRequested(_importRequest()));
    await Future<void>.delayed(Duration.zero);
    verify(() => api.importCloudConnection(any())).called(1);

    completion.complete(_connection(id: 'aws-imported'));
    await bloc.stream.firstWhere((state) => state.feedback?.isError == false);
    expect(bloc.state.isImporting, isFalse);
    expect(bloc.state.connections.single.id, 'aws-imported');
    await bloc.close();
  });

  test('bound delete conflict keeps the row and clears busy state', () async {
    when(
      () => api.listCloudConnections(),
    ).thenAnswer((_) async => [_connection(id: 'aws-deploy')]);
    when(
      () => api.deleteCloudConnection('aws-deploy'),
    ).thenThrow(const AppException('Connection is bound to Factory Twin'));
    final bloc = CloudAccessBloc(api)..add(const CloudAccessStarted());
    await bloc.stream.firstWhere((state) => state.connections.isNotEmpty);

    bloc.add(const CloudAccessDeleteRequested('aws-deploy'));
    await bloc.stream.firstWhere((state) => state.feedback?.isError == true);

    expect(bloc.state.connections.single.id, 'aws-deploy');
    expect(bloc.state.busyConnectionIds, isEmpty);
    expect(bloc.state.feedback?.message, contains('Factory Twin'));
    await bloc.close();
  });

  test('reports successful mutation if only the list reload fails', () async {
    when(
      () => api.deleteCloudConnection('aws-deploy'),
    ).thenAnswer((_) async {});
    when(
      () => api.listCloudConnections(),
    ).thenThrow(Exception('List unavailable'));
    final bloc = CloudAccessBloc(api);

    bloc.add(const CloudAccessDeleteRequested('aws-deploy'));
    await bloc.stream.firstWhere((state) => state.feedback != null);

    expect(bloc.state.feedback?.isError, isFalse);
    expect(bloc.state.feedback?.message, contains('Refresh deployment'));
    expect(bloc.state.busyConnectionIds, isEmpty);
    await bloc.close();
  });
}

CloudConnectionCreateRequest _createRequest() =>
    const CloudConnectionCreateRequest(
      provider: CloudProvider.aws,
      displayName: 'AWS Administrator',
      credentials: {
        'access_key_id': 'TEST_ACCESS_KEY',
        'secret_access_key': 'TEST_SECRET_KEY',
        'region': 'eu-central-1',
      },
    );

CloudConnectionImportRequest _importRequest() => CloudConnectionImportRequest(
  provider: CloudProvider.aws,
  displayName: 'AWS Imported Administrator',
  region: 'eu-central-1',
  filename: 'credentials.csv',
  bytes: Uint8List.fromList([1, 2, 3]),
);

CloudConnection _connection({
  required String id,
  CloudProvider provider = CloudProvider.aws,
}) => CloudConnection(
  id: id,
  provider: provider,
  displayName: id,
  authType: 'administrator',
  cloudScope: const {},
  payloadFingerprint: 'opaque',
  payloadSummary: const {},
  validationStatus: 'valid',
  createdAt: DateTime.utc(2026, 8, 27),
  updatedAt: DateTime.utc(2026, 8, 27),
);
