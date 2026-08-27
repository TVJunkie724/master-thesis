import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';

void main() {
  group('AppRuntimeConfig', () {
    test('parses the two network modes and offline demo mode', () {
      expect(AppRuntimeConfig.parseMode('development'), AppMode.development);
      expect(AppRuntimeConfig.parseMode('prod'), AppMode.production);
      expect(AppRuntimeConfig.parseMode('demo'), AppMode.demo);
    });

    test('builds a network profile with the local PoC bearer', () {
      final development = AppRuntimeConfig.fromValues(
        appMode: 'development',
        apiBaseUrl: 'http://localhost:5005/',
        pocAuthToken: 'local-token',
      );
      final production = AppRuntimeConfig.fromValues(
        appMode: 'production',
        apiBaseUrl: 'https://management.example.test',
        pocAuthToken: 'local-token',
      );

      expect(development.initialAuthToken, 'local-token');
      expect(production.initialAuthToken, 'local-token');
      expect(production.managementApiBaseUri?.scheme, 'https');
    });

    test('network modes require an origin and opaque PoC bearer', () {
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'development',
          pocAuthToken: 'local-token',
        ),
        throwsStateError,
      );
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'development',
          apiBaseUrl: 'http://localhost:5005',
        ),
        throwsStateError,
      );
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'production',
          apiBaseUrl: 'http://management.test',
          pocAuthToken: 'local-token',
        ),
        throwsStateError,
      );
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'production',
          apiBaseUrl: 'https://management.test',
          pocAuthToken: 'bad token',
        ),
        throwsStateError,
      );
    });

    test('token validation never echoes the rejected value', () {
      const secret = 'must not appear anywhere';
      try {
        AppRuntimeConfig.fromValues(
          appMode: 'development',
          apiBaseUrl: 'http://localhost:5005',
          pocAuthToken: secret,
        );
        fail('Expected invalid token to fail');
      } on StateError catch (error) {
        expect(error.message, contains('POC_AUTH_TOKEN'));
        expect(error.message, isNot(contains(secret)));
      }
    });

    test('demo is network-free and rejects a PoC bearer', () {
      final demo = AppRuntimeConfig.fromValues(
        appMode: 'demo',
        demoScenario: 'degraded',
      );
      expect(demo.isDemo, isTrue);
      expect(demo.initialAuthToken, isNull);
      expect(demo.demoScenario, DemoScenario.degraded);
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'demo',
          pocAuthToken: 'local-token',
        ),
        throwsStateError,
      );
    });

    test('rejects invalid modes, scenarios, and non-origin URLs', () {
      expect(() => AppRuntimeConfig.parseMode(''), throwsStateError);
      expect(() => AppRuntimeConfig.parseMode('preview'), throwsStateError);
      expect(() => AppRuntimeConfig.parseScenario('random'), throwsStateError);
      for (final value in [
        'https://user@example.test',
        'https://example.test/api',
        'https://example.test?debug=true',
        'https://example.test#fragment',
      ]) {
        expect(
          () => AppRuntimeConfig.fromValues(
            appMode: 'production',
            apiBaseUrl: value,
            pocAuthToken: 'local-token',
          ),
          throwsStateError,
        );
      }
    });
  });
}
