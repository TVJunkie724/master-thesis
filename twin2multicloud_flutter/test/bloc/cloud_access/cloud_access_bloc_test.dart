import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/cloud_access/cloud_access.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/cloud_access_inventory.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;

  setUpAll(() {
    registerFallbackValue(_createRequest());
  });

  setUp(() => api = MockApiService());

  test('loads purpose-aware cloud access inventory', () async {
    when(
      () => api.getCloudAccessInventory(),
    ).thenAnswer((_) async => _inventory());
    final bloc = CloudAccessBloc(api)..add(const CloudAccessStarted());

    await bloc.stream.firstWhere((state) => state.inventory != null);

    expect(
      bloc.state.inventory?.pricingFor('aws')?.connectionId,
      'aws-pricing',
    );
    expect(bloc.state.loadError, isNull);
    await bloc.close();
  });

  test('preserves inventory when reload fails', () async {
    var calls = 0;
    when(() => api.getCloudAccessInventory()).thenAnswer((_) async {
      if (calls++ == 0) return _inventory();
      throw Exception('Management API unavailable');
    });
    final bloc = CloudAccessBloc(api)..add(const CloudAccessStarted());
    await bloc.stream.firstWhere((state) => state.inventory != null);

    bloc.add(const CloudAccessReloadRequested());
    await bloc.stream.firstWhere((state) => state.loadError != null);

    expect(bloc.state.inventory, isNotNull);
    expect(bloc.state.loadError, 'An unexpected error occurred');
    await bloc.close();
  });

  test('creates access and reloads inventory', () async {
    when(
      () => api.createCloudConnection(any()),
    ).thenAnswer((_) async => _connection());
    when(
      () => api.getCloudAccessInventory(),
    ).thenAnswer((_) async => _inventory());
    final bloc = CloudAccessBloc(api);

    bloc.add(CloudAccessCreateRequested(_createRequest()));
    await bloc.stream.firstWhere((state) => state.feedback?.isError == false);

    verify(() => api.createCloudConnection(any())).called(1);
    verify(() => api.getCloudAccessInventory()).called(1);
    expect(bloc.state.isCreating, isFalse);
    await bloc.close();
  });

  test('sets pricing default and reloads inventory', () async {
    when(
      () => api.updateCloudConnection('aws-pricing', isDefaultForPricing: true),
    ).thenAnswer((_) async => _connection());
    when(
      () => api.getCloudAccessInventory(),
    ).thenAnswer((_) async => _inventory());
    final bloc = CloudAccessBloc(api);

    bloc.add(const CloudAccessDefaultRequested('aws-pricing'));
    await bloc.stream.firstWhere((state) => state.feedback?.isError == false);

    verify(
      () => api.updateCloudConnection('aws-pricing', isDefaultForPricing: true),
    ).called(1);
    await bloc.close();
  });

  test('mutation failure keeps inventory and clears busy state', () async {
    when(
      () => api.getCloudAccessInventory(),
    ).thenAnswer((_) async => _inventory());
    when(
      () => api.deleteCloudConnection('aws-pricing'),
    ).thenThrow(const AppException('Connection is still in use'));
    final bloc = CloudAccessBloc(api)..add(const CloudAccessStarted());
    await bloc.stream.firstWhere((state) => state.inventory != null);

    bloc.add(const CloudAccessDeleteRequested('aws-pricing'));
    await bloc.stream.firstWhere((state) => state.feedback?.isError == true);

    expect(bloc.state.inventory, isNotNull);
    expect(bloc.state.busyConnectionIds, isEmpty);
    expect(bloc.state.feedback?.message, contains('still in use'));
    await bloc.close();
  });

  test(
    'reports successful mutation accurately when only reload fails',
    () async {
      when(
        () => api.deleteCloudConnection('aws-pricing'),
      ).thenAnswer((_) async {});
      when(
        () => api.getCloudAccessInventory(),
      ).thenThrow(Exception('Inventory reload unavailable'));
      final bloc = CloudAccessBloc(api);

      bloc.add(const CloudAccessDeleteRequested('aws-pricing'));
      await bloc.stream.firstWhere((state) => state.feedback != null);

      expect(bloc.state.feedback?.isError, isFalse);
      expect(bloc.state.feedback?.message, contains('deleted'));
      expect(bloc.state.feedback?.message, contains('Refresh cloud access'));
      expect(bloc.state.loadError, 'An unexpected error occurred');
      expect(bloc.state.busyConnectionIds, isEmpty);
      await bloc.close();
    },
  );

  test('ignores duplicate command for the same connection', () async {
    final completion = Completer<CloudConnectionValidationResult>();
    when(
      () => api.validateCloudConnection('aws-pricing'),
    ).thenAnswer((_) => completion.future);
    when(
      () => api.getCloudAccessInventory(),
    ).thenAnswer((_) async => _inventory());
    final bloc = CloudAccessBloc(api);

    bloc.add(const CloudAccessValidateRequested('aws-pricing'));
    await bloc.stream.firstWhere(
      (state) => state.busyConnectionIds.contains('aws-pricing'),
    );
    bloc.add(const CloudAccessValidateRequested('aws-pricing'));
    await Future<void>.delayed(Duration.zero);
    completion.complete(_validation());
    await bloc.stream.firstWhere((state) => state.feedback?.isError == false);

    verify(() => api.validateCloudConnection('aws-pricing')).called(1);
    await bloc.close();
  });
}

CloudConnectionCreateRequest _createRequest() =>
    const CloudConnectionCreateRequest(
      provider: CloudProvider.aws,
      purpose: CloudConnectionPurpose.pricing,
      displayName: 'AWS Pricing',
      credentials: {
        'access_key_id': 'TEST_ACCESS_KEY',
        'secret_access_key': 'TEST_SECRET_KEY',
        'region': 'eu-central-1',
      },
    );

CloudConnection _connection() => CloudConnection(
  id: 'aws-pricing',
  provider: CloudProvider.aws,
  purpose: CloudConnectionPurpose.pricing,
  displayName: 'AWS Pricing',
  authType: 'access_key',
  cloudScope: const {'account_id': '123456789012'},
  payloadFingerprint: 'opaque',
  payloadSummary: const {},
  validationStatus: 'valid',
  createdAt: DateTime.utc(2026, 7, 12),
  updatedAt: DateTime.utc(2026, 7, 12),
);

CloudConnectionValidationResult _validation() =>
    const CloudConnectionValidationResult(
      id: 'aws-pricing',
      provider: CloudProvider.aws,
      valid: true,
      validationStatus: 'valid',
      message: 'Pricing access validated',
    );

CloudAccessInventory _inventory() => CloudAccessInventory.fromJson({
  'schema_version': 'cloud-access-inventory.v1',
  'providers': {
    'aws': {
      'provider': 'aws',
      'pricing': {
        'connection_id': 'aws-pricing',
        'provider': 'aws',
        'purpose': 'pricing',
        'scope': 'user',
        'identity_label': 'AWS Pricing',
        'status': 'active',
        'is_default_for_pricing': true,
        'actions': ['validate', 'delete', 'refresh_pricing'],
      },
      'pricing_options': [],
      'deployment': [],
    },
  },
});
