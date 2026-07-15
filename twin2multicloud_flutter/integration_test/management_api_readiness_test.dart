import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/config/api_config.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

const _providers = {'aws', 'azure', 'gcp'};
const _forbiddenPayloadKeys = {
  'access_key_id',
  'secret_access_key',
  'client_secret',
  'private_key',
  'service_account_json',
  'access_token',
  'refresh_token',
};

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMessageHandler('flutter/keyevent', (_) async => null);
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMessageHandler('flutter/rawKeyboard', (_) async => null);

  final apiUri = Uri.parse(ApiConfig.baseUrl);
  final api = ApiService();

  group('Management API read-only readiness', () {
    testWidgets('runtime config supplies an HTTP Management API origin', (
      tester,
    ) async {
      expect(apiUri.scheme, anyOf('http', 'https'));
      expect(apiUri.host, isNotEmpty);
      expect(apiUri.path, anyOf('', '/'));
      expect(apiUri.query, isEmpty);
      expect(apiUri.fragment, isEmpty);
    });

    testWidgets('decodes dashboard statistics with valid invariants', (
      tester,
    ) async {
      final stats = await _readOrFail(
        '/dashboard/stats',
        api.getDashboardStats,
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

    testWidgets('decodes the complete cloud access inventory', (tester) async {
      final inventory = await _readOrFail(
        '/cloud-access',
        api.getCloudAccessInventory,
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
        api.listCloudConnections,
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

    testWidgets('decodes all provider pricing health states', (tester) async {
      final health = await _readOrFail(
        '/optimizer/pricing-health',
        api.getPricingHealth,
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
      baseUrl: ApiConfig.baseUrl,
      validateStatus: (_) => true,
      headers: {
        if (authenticated) 'Authorization': 'Bearer ${ApiConfig.devAuthToken}',
      },
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
      baseUrl: ApiConfig.baseUrl,
      validateStatus: (status) => status != null && status < 400,
      headers: {'Authorization': 'Bearer ${ApiConfig.devAuthToken}'},
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

String _safeDioFailure(String endpoint, DioException error) {
  final status = error.response?.statusCode?.toString() ?? 'none';
  return 'Management API request failed at ${ApiConfig.baseUrl}$endpoint; '
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
