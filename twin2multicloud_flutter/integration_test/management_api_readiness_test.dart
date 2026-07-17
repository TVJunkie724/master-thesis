import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

const _providers = {'aws', 'azure', 'gcp'};
const _serverOwnedOptimizerFields = {
  'providerPricingCatalogs',
  'providerPricingContexts',
};
const _forbiddenPayloadKeys = {
  'access_key_id',
  'secret_access_key',
  'client_secret',
  'private_key',
  'service_account_json',
  'access_token',
  'refresh_token',
};
final _runtime = AppRuntimeConfig.fromEnvironment();
final _apiUri =
    _runtime.managementApiBaseUri ??
    (throw StateError('Integration runtime requires a Management API origin.'));
final _authToken =
    _runtime.initialAuthToken ??
    (throw StateError('Integration tests require the development profile.'));
const _optimizerApiBaseUrl = String.fromEnvironment(
  'TEST_OPTIMIZER_API_BASE_URL',
);
final _optimizerApiUri = _validatedTestOrigin(
  _optimizerApiBaseUrl,
  'TEST_OPTIMIZER_API_BASE_URL',
);
final _api = ApiService(baseUri: _apiUri, initialAuthToken: _authToken);

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMessageHandler('flutter/keyevent', (_) async => null);
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMessageHandler('flutter/rawKeyboard', (_) async => null);

  group('Management API read-only readiness', () {
    testWidgets('runtime config supplies an HTTP Management API origin', (
      tester,
    ) async {
      expect(_apiUri.scheme, anyOf('http', 'https'));
      expect(_apiUri.host, isNotEmpty);
      expect(_apiUri.path, anyOf('', '/'));
      expect(_apiUri.query, isEmpty);
      expect(_apiUri.fragment, isEmpty);
    });

    testWidgets('decodes dashboard statistics with valid invariants', (
      tester,
    ) async {
      final stats = await _readOrFail(
        '/dashboard/stats',
        _api.getDashboardStats,
      );

      expect(stats.totalTwins, greaterThanOrEqualTo(0));
      expect(stats.deployedCount, greaterThanOrEqualTo(0));
      expect(stats.draftCount, greaterThanOrEqualTo(0));
      expect(stats.estimatedMonthlyCost, greaterThanOrEqualTo(0));
      expect(
        stats.totalTwins,
        greaterThanOrEqualTo(stats.deployedCount + stats.draftCount),
      );
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

    testWidgets('decodes the complete cloud access inventory', (tester) async {
      final inventory = await _readOrFail(
        '/cloud-access',
        _api.getCloudAccessInventory,
      );

      expect(inventory.schemaVersion, 'cloud-access-inventory.v1');
      expect(inventory.providers.keys.toSet(), _providers);
      for (final provider in _providers) {
        final entry = inventory.providers[provider];
        expect(entry, isNotNull, reason: 'Missing $provider inventory');
        expect(entry!.provider, provider);
        expect(entry.pricing.provider, provider);
        expect(entry.pricing.purpose, 'pricing');
        expect(entry.pricing.scope, anyOf('public', 'user'));
        expect(entry.pricing.status, isNotEmpty);
        expect(entry.pricing.identityLabel, isNotEmpty);
        for (final option in [
          entry.pricing,
          ...entry.pricingOptions,
          ...entry.deployment,
        ]) {
          expect(option.provider, provider);
          expect(option.identityLabel, isNotEmpty);
          expect(option.status, isNotEmpty);
        }
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
        expect(CloudConnectionPurpose.values, contains(connection.purpose));
        expect(connection.displayName, isNotEmpty);
        expect(connection.authType, isNotEmpty);
        expect(connection.scope, isNotEmpty);
      }
    });

    testWidgets('keeps readiness payloads free of credential keys', (
      tester,
    ) async {
      for (final endpoint in ['/cloud-access', '/optimizer/pricing-health']) {
        final payload = await _authenticatedJsonRequest(endpoint);
        expect(
          _containsForbiddenKey(payload),
          isFalse,
          reason: '$endpoint must expose credential metadata only',
        );
      }
    });

    testWidgets('publishes one canonical optimizer workload contract', (
      tester,
    ) async {
      final managementOpenApi = await _authenticatedJsonRequest(
        '/openapi.json',
      );
      final optimizerOpenApi = await _publicJsonRequest(
        _optimizerApiUri,
        '/openapi.json',
      );
      final managementContract = _openApiSchema(
        managementOpenApi,
        'OptimizerCalculationParams',
      );
      final optimizerContract = _openApiSchema(optimizerOpenApi, 'CalcParams');

      expect(managementContract['additionalProperties'], isFalse);
      expect(optimizerContract['additionalProperties'], isFalse);
      final managementProperties = managementContract['properties'] as Map;
      final optimizerProperties = optimizerContract['properties'] as Map;
      expect(
        optimizerProperties.keys
            .map((key) => key.toString())
            .toSet()
            .difference(
              managementProperties.keys.map((key) => key.toString()).toSet(),
            ),
        _serverOwnedOptimizerFields,
        reason: 'Only documented server-owned pricing fields may differ.',
      );
      for (final field in _serverOwnedOptimizerFields) {
        expect(
          managementProperties,
          isNot(contains(field)),
          reason: 'Clients must not supply trusted $field evidence.',
        );
        expect(
          optimizerProperties,
          contains(field),
          reason: 'Management must own and inject $field downstream.',
        );
      }
      expect(
        optimizerContract['required'],
        contains('providerPricingCatalogs'),
      );
      expect(
        optimizerContract['required'],
        isNot(contains('providerPricingContexts')),
      );
      expect(
        _contractProjection(managementContract),
        _contractProjection(
          optimizerContract,
          excludedProperties: _serverOwnedOptimizerFields,
        ),
      );

      for (final field in [
        'averageDigitalTwinQueryUnitsPerQuery',
        'averageDigitalTwinQueryResponseSizeInKb',
      ]) {
        final contract = managementProperties[field] as Map?;
        expect(contract, isNotNull, reason: 'Missing $field');
        expect(contract!['exclusiveMinimum'], 0);
        expect(contract['default'], 1.0);
      }
    });

    testWidgets('decodes all provider pricing health states', (tester) async {
      final health = await _readOrFail(
        '/optimizer/pricing-health',
        _api.getPricingHealth,
      );

      expect(health.schemaVersion, 'pricing-health.v1');
      expect(health.providers.keys.toSet(), _providers);
      for (final provider in _providers) {
        final state = health.provider(provider);
        expect(state, isNotNull, reason: 'Missing $provider pricing health');
        expect(state!.provider, provider);
        expect(state.state, isNotEmpty);
        expect(state.severity, isNotEmpty);
        expect(state.calculationSource, isNotEmpty);
        expect(state.pricingFreshness, isNotEmpty);
        expect(state.sourceLabel, isNotEmpty);
        expect(state.primaryMessage, isNotEmpty);
        expect(state.credentialSummary.provider, provider);
        expect(state.credentialSummary.purpose, 'pricing');
        expect(state.credentialSummary.status, isNotEmpty);
      }
    });

    testWidgets('rejects missing authentication on protected inventory', (
      tester,
    ) async {
      final response = await _statusOnlyRequest('/cloud-access');
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

Future<Object?> _publicJsonRequest(Uri baseUri, String endpoint) async {
  final dio = Dio(
    BaseOptions(
      baseUrl: baseUri.toString(),
      validateStatus: (status) => status != null && status < 400,
    ),
  );
  try {
    final response = await dio.get<Object?>(endpoint);
    return response.data;
  } on DioException catch (error) {
    fail(_safeDioFailureForBase(endpoint, error, baseUri: baseUri));
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

Map<String, Object?> _contractProjection(
  Map contract, {
  Set<String> excludedProperties = const {},
}) {
  const contractKeywords = {
    'type',
    'default',
    'minimum',
    'maximum',
    'exclusiveMinimum',
    'exclusiveMaximum',
    'enum',
  };
  final properties = contract['properties'] as Map;
  return {
    'required': ((contract['required'] as List?) ?? const [])
        .map((value) => value.toString())
        .where((value) => !excludedProperties.contains(value))
        .toSet(),
    'properties': {
      for (final entry in properties.entries)
        if (!excludedProperties.contains(entry.key.toString()))
          entry.key.toString(): {
            for (final keyword in contractKeywords)
              if ((entry.value as Map).containsKey(keyword))
                keyword: entry.value[keyword],
          },
    },
  };
}

String _safeDioFailure(String endpoint, DioException error) {
  return _safeDioFailureForBase(endpoint, error, baseUri: _apiUri);
}

String _safeDioFailureForBase(
  String endpoint,
  DioException error, {
  required Uri baseUri,
}) {
  final status = error.response?.statusCode?.toString() ?? 'none';
  return 'Read-only API request failed at $baseUri$endpoint; '
      'type=${error.type.name}; status=$status. '
      'Response content and headers were suppressed.';
}

Uri _validatedTestOrigin(String value, String variable) {
  final uri = Uri.tryParse(value);
  if (uri == null ||
      !uri.isAbsolute ||
      uri.host.isEmpty ||
      !{'http', 'https'}.contains(uri.scheme) ||
      uri.userInfo.isNotEmpty ||
      uri.hasQuery ||
      uri.hasFragment ||
      (uri.path.isNotEmpty && uri.path != '/')) {
    throw StateError('$variable must be an absolute HTTP(S) origin.');
  }
  return uri.replace(path: '');
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
