import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/utils/azure_credential_file_parser.dart';

const _forbiddenPayloadKeys = {
  'access_key_id',
  'secret_access_key',
  'client_secret',
  'client_id',
  'preparation_client_id',
  'preparation_client_secret',
  'private_key',
  'service_account_json',
  'access_token',
  'refresh_token',
  'appid',
  'password',
};
final _runtime = AppRuntimeConfig.fromEnvironment();
final _apiUri =
    _runtime.managementApiBaseUri ??
    (throw StateError('Integration runtime requires a Management API origin.'));
final _authToken =
    _runtime.initialAuthToken ??
    (throw StateError('Integration tests require the development profile.'));
final _api = ApiService(baseUri: _apiUri, initialAuthToken: _authToken);

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMessageHandler('flutter/keyevent', (_) async => null);
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMessageHandler('flutter/rawKeyboard', (_) async => null);

  group('Management API credential-free contract', () {
    testWidgets('runtime config supplies an HTTP Management API origin', (
      tester,
    ) async {
      expect(_apiUri.scheme, anyOf('http', 'https'));
      expect(_apiUri.host, isNotEmpty);
      expect(_apiUri.path, anyOf('', '/'));
      expect(_apiUri.query, isEmpty);
      expect(_apiUri.fragment, isEmpty);
    });

    testWidgets('decodes canonical twin and configuration read models', (
      tester,
    ) async {
      final twins = await _readOrFail('/twins/', _api.getTwins);
      expect(twins, isA<List>());
      if (twins.isEmpty) {
        expect(twins, isEmpty);
        return;
      }

      final listed = twins.first;
      expect(listed.id, isNotEmpty);
      expect(listed.name, isNotEmpty);
      expect(listed.createdAt.isUtc, isTrue);
      expect(listed.updatedAt.isUtc, isTrue);

      final twin = await _readOrFail(
        '/twins/${listed.id}',
        () => _api.getTwin(listed.id),
      );
      expect(twin.id, listed.id);
      expect(twin.name, listed.name);

      final config = await _readOrFail(
        '/twins/${listed.id}/config/',
        () => _api.getTwinConfig(listed.id),
      );
      expect(config.twinId, listed.id);
      expect(config.id, isNotEmpty);
      expect(config.providers.keys.toSet(), CloudProvider.values.toSet());
      expect(config.updatedAt.isUtc, isTrue);

      final optimizer = await _readOrFail(
        '/twins/${listed.id}/optimizer-config',
        () => _api.getOptimizerConfig(listed.id),
      );
      if (optimizer != null) {
        expect(optimizer.twinId, listed.id);
        expect(optimizer.id, isNotEmpty);
        final context = optimizer.pricingCatalogContext;
        expect(optimizer.optimization?.result.pricingCatalogContext, context);
        if (context != null) {
          expect(context.catalogs.keys.toSet(), CloudProvider.values.toSet());
        }
      }

      final deployer = await _readOrFail(
        '/twins/${listed.id}/deployer/config',
        () => _api.getDeployerConfig(listed.id),
      );
      if (deployer != null) {
        expect(deployer.processorContents, isA<Map<String, String>>());
        expect(deployer.eventActionContents, isA<Map<String, String>>());
      }
    });

    testWidgets('decodes CloudConnections without credential payload keys', (
      tester,
    ) async {
      final rawConnections = await _authenticatedJsonRequest(
        '/cloud-connections/',
      );
      expect(
        _containsForbiddenKey(rawConnections),
        isFalse,
        reason: 'Raw CloudConnection responses must not expose credentials',
      );
      expect(rawConnections, isA<List<Object?>>());

      final connections = await _readOrFail(
        '/cloud-connections/',
        _api.listCloudConnections,
      );

      for (final connection in connections) {
        expect(connection.id, isNotEmpty);
        expect(CloudProvider.values, contains(connection.provider));
        expect(connection.displayName, isNotEmpty);
        expect(connection.authType, isNotEmpty);
      }
    });

    testWidgets('imports, lists, and deletes one redacted Azure bundle', (
      tester,
    ) async {
      const deploymentClientId = 'synthetic-deployment-principal';
      const deploymentSecret = 'synthetic-deployment-secret';
      const preparationClientId = 'synthetic-preparation-principal';
      const preparationSecret = 'synthetic-preparation-secret';
      String? connectionId;
      try {
        final selection = parseAzureCredentialFileSelection(
          Uint8List.fromList(
            utf8.encode(
              jsonEncode({
                'azure': {
                  'azure_subscription_id': 'synthetic-subscription',
                  'azure_tenant_id': 'synthetic-tenant',
                  'azure_client_id': deploymentClientId,
                  'azure_client_secret': deploymentSecret,
                  'azure_preparation_client_id': preparationClientId,
                  'azure_preparation_client_secret': preparationSecret,
                  'azure_region': 'westeurope',
                },
              }),
            ),
          ),
        );
        final request = CloudConnectionImportRequest(
          provider: CloudProvider.azure,
          displayName: 'Azure integration bundle',
          region: selection.region!,
          targetScopeId: selection.subscriptionId,
          preparationClientId: selection.preparationClientId,
          preparationClientSecret: selection.preparationClientSecret,
          filename: 'synthetic-azure.json',
          bytes: selection.normalizedUploadBytes,
        );
        final createdRaw = await _authenticatedImportPost(request);
        expect(_containsForbiddenKey(createdRaw), isFalse);
        expect(
          _containsAnyValue(createdRaw, const {
            deploymentClientId,
            deploymentSecret,
            preparationClientId,
            preparationSecret,
          }),
          isFalse,
        );
        final created = CloudConnection.fromJson(
          Map<String, dynamic>.from(createdRaw! as Map),
        );
        connectionId = created.id;
        expect(created.payloadSummary['preparation_client_configured'], isTrue);

        final listedRaw = await _authenticatedJsonRequest(
          '/cloud-connections/',
        );
        expect(_containsForbiddenKey(listedRaw), isFalse);
        expect(
          _containsAnyValue(listedRaw, const {
            deploymentClientId,
            deploymentSecret,
            preparationClientId,
            preparationSecret,
          }),
          isFalse,
        );
        final listed = await _api.listCloudConnections();
        expect(listed.map((item) => item.id), contains(connectionId));
      } finally {
        if (connectionId != null) {
          await _api.deleteCloudConnection(connectionId);
        }
      }

      final remaining = await _api.listCloudConnections();
      expect(remaining.map((item) => item.id), isNot(contains(connectionId)));
    });

    testWidgets('keeps readiness payloads free of credential keys', (
      tester,
    ) async {
      final twins = await _readOrFail('/twins/', _api.getTwins);
      if (twins.isEmpty) return;
      final endpoint = '/twins/${twins.first.id}/deployment-readiness';
      final payload = await _authenticatedJsonRequest(endpoint);
      expect(
        _containsForbiddenKey(payload),
        isFalse,
        reason: '$endpoint must expose credential metadata only',
      );
    });

    testWidgets('publishes one bounded calculation and pricing contract', (
      tester,
    ) async {
      final managementOpenApi = await _authenticatedJsonRequest(
        '/openapi.json',
      );
      final managementContract = _openApiSchema(
        managementOpenApi,
        'OptimizerCalculationParams',
      );

      expect(managementContract['additionalProperties'], isFalse);
      final managementProperties = managementContract['properties'] as Map;
      for (final field in const {
        'calculationRunId',
        'providerPricingCatalogs',
        'providerPricingContexts',
        'architectureProfile',
        'extensionBindings',
      }) {
        expect(
          managementProperties,
          isNot(contains(field)),
          reason: 'Clients must not supply trusted $field evidence.',
        );
      }

      expect(
        managementContract['required'],
        containsAll(const {
          'schemaVersion',
          'numberOfDevices',
          'twinEntityCount',
          'eventingScenarioId',
        }),
      );
      expect(
        (managementProperties['schemaVersion'] as Map)['const'],
        'six-layer-workload.v1',
      );
      expect(
        (managementProperties['numberOfDevices'] as Map)['exclusiveMinimum'],
        0,
      );
      expect((managementProperties['currency'] as Map)['default'], 'USD');

      final paths = (managementOpenApi as Map)['paths'] as Map;
      for (final removedPath in const {
        '/cloud-access',
        '/optimizer/pricing-health',
        '/optimizer/calculate',
        '/optimizer/calculate/stream',
        '/optimizer/status',
        '/pricing-refresh/runs',
        '/pricing-review/status',
      }) {
        expect(paths, isNot(contains(removedPath)));
      }
    });

    testWidgets('rejects missing authentication on protected inventory', (
      tester,
    ) async {
      final response = await _statusOnlyRequest('/cloud-connections/');
      expect(response, anyOf(401, 403));
    });

    testWidgets('returns 404 for an authenticated unknown route', (
      tester,
    ) async {
      final response = await _statusOnlyRequest(
        '/__phase_09_unknown_read_only_route__',
        authenticated: true,
      );
      expect(response, 404);
    });
  });
}

Future<T> _readOrFail<T>(String endpoint, Future<T> Function() request) async {
  try {
    return await request();
  } on DioException catch (error) {
    fail(_safeDioFailure(endpoint, error));
  } catch (error) {
    fail(
      'Management API contract failed for $endpoint '
      'with ${error.runtimeType}. Response content was suppressed.',
    );
  }
}

Future<int?> _statusOnlyRequest(
  String endpoint, {
  bool authenticated = false,
}) async {
  final dio = Dio(
    BaseOptions(
      baseUrl: _apiUri.toString(),
      validateStatus: (_) => true,
      headers: {if (authenticated) 'Authorization': 'Bearer $_authToken'},
    ),
  );
  try {
    final response = await dio.get<void>(endpoint);
    return response.statusCode;
  } on DioException catch (error) {
    fail(_safeDioFailure(endpoint, error));
  } finally {
    dio.close(force: true);
  }
}

Future<Object?> _authenticatedJsonRequest(String endpoint) async {
  final dio = Dio(
    BaseOptions(
      baseUrl: _apiUri.toString(),
      validateStatus: (status) => status != null && status < 400,
      headers: {'Authorization': 'Bearer $_authToken'},
    ),
  );
  try {
    final response = await dio.get<Object?>(endpoint);
    return response.data;
  } on DioException catch (error) {
    fail(_safeDioFailure(endpoint, error));
  } finally {
    dio.close(force: true);
  }
}

Future<Object?> _authenticatedImportPost(
  CloudConnectionImportRequest request,
) async {
  final dio = Dio(
    BaseOptions(
      baseUrl: _apiUri.toString(),
      validateStatus: (status) => status != null && status < 400,
      headers: {'Authorization': 'Bearer $_authToken'},
    ),
  );
  try {
    final response = await dio.post<Object?>(
      '/cloud-connections/import',
      data: FormData.fromMap({
        'metadata': request.metadataJson,
        'file': MultipartFile.fromBytes(
          request.bytes,
          filename: request.filename,
        ),
      }),
    );
    return response.data;
  } on DioException catch (error) {
    fail(_safeDioFailure('/cloud-connections/import', error));
  } finally {
    dio.close(force: true);
  }
}

Map _openApiSchema(Object? openApi, String schemaName) {
  expect(openApi, isA<Map>());
  final components =
      (openApi as Map)['components'] as Map? ?? const <Object?, Object?>{};
  final schemas = components['schemas'] as Map? ?? const <Object?, Object?>{};
  final contract = schemas[schemaName] as Map?;
  expect(contract, isNotNull, reason: 'Missing OpenAPI schema $schemaName');
  return contract!;
}

String _safeDioFailure(String endpoint, DioException error) {
  final status = error.response?.statusCode?.toString() ?? 'none';
  return 'Read-only API request failed at $_apiUri$endpoint; '
      'type=${error.type.name}; status=$status. '
      'Response content and headers were suppressed.';
}

bool _containsForbiddenKey(Object? value) {
  if (value is Map) {
    for (final entry in value.entries) {
      if (_forbiddenPayloadKeys.contains(entry.key.toString().toLowerCase())) {
        return true;
      }
      if (_containsForbiddenKey(entry.value)) return true;
    }
  } else if (value is Iterable) {
    for (final item in value) {
      if (_containsForbiddenKey(item)) return true;
    }
  }
  return false;
}

bool _containsAnyValue(Object? value, Set<String> forbiddenValues) {
  if (value is Map) {
    return value.values.any((item) => _containsAnyValue(item, forbiddenValues));
  }
  if (value is Iterable) {
    return value.any((item) => _containsAnyValue(item, forbiddenValues));
  }
  return value is String && forbiddenValues.contains(value);
}
