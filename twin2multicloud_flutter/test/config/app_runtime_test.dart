import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';

void main() {
  group('AppRuntimeConfig', () {
    test('parses canonical and abbreviated application modes', () {
      expect(AppRuntimeConfig.parseMode('development'), AppMode.development);
      expect(AppRuntimeConfig.parseMode('DEV'), AppMode.development);
      expect(AppRuntimeConfig.parseMode('production'), AppMode.production);
      expect(AppRuntimeConfig.parseMode('prod'), AppMode.production);
      expect(AppRuntimeConfig.parseMode('demo'), AppMode.demo);
    });

    test('parses every supported demo scenario', () {
      expect(AppRuntimeConfig.parseScenario('showcase'), DemoScenario.showcase);
      expect(AppRuntimeConfig.parseScenario('empty'), DemoScenario.empty);
      expect(AppRuntimeConfig.parseScenario('degraded'), DemoScenario.degraded);
    });

    test('rejects an unsupported application mode', () {
      expect(
        () => AppRuntimeConfig.parseMode('preview'),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('Unsupported APP_MODE'),
          ),
        ),
      );
    });

    test('rejects a missing application mode', () {
      expect(
        () => AppRuntimeConfig.fromValues(appMode: ''),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('APP_MODE is required'),
          ),
        ),
      );
    });

    test('builds an explicit development profile', () {
      final config = AppRuntimeConfig.fromValues(
        appMode: ' development ',
        apiBaseUrl: 'http://localhost:5005/',
        devAuthToken: 'local-token',
      );

      expect(config.mode, AppMode.development);
      expect(config.managementApiBaseUri, Uri.parse('http://localhost:5005'));
      expect(config.initialAuthToken, 'local-token');
      expect(config.isDemo, isFalse);
    });

    test('builds a token-free HTTPS production profile', () {
      final config = AppRuntimeConfig.fromValues(
        appMode: 'prod',
        apiBaseUrl: 'https://management.example.test',
      );

      expect(config.mode, AppMode.production);
      expect(
        config.managementApiBaseUri,
        Uri.parse('https://management.example.test'),
      );
      expect(config.initialAuthToken, isNull);
    });

    test('builds a network-free demo profile', () {
      final config = AppRuntimeConfig.fromValues(
        appMode: 'demo',
        demoScenario: 'degraded',
      );

      expect(config.mode, AppMode.demo);
      expect(config.demoScenario, DemoScenario.degraded);
      expect(config.managementApiBaseUri, isNull);
      expect(config.initialAuthToken, isNull);
    });

    test('requires development URL and token', () {
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'development',
          devAuthToken: 'local-token',
        ),
        throwsA(isA<StateError>()),
      );
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'development',
          apiBaseUrl: 'http://localhost:5005',
        ),
        throwsA(isA<StateError>()),
      );
    });

    test('rejects development token whitespace without echoing the token', () {
      const secret = 'must not appear anywhere';
      try {
        AppRuntimeConfig.fromValues(
          appMode: 'development',
          apiBaseUrl: 'http://localhost:5005',
          devAuthToken: secret,
        );
        fail('Expected invalid development token to fail');
      } on StateError catch (error) {
        expect(error.message, contains('DEV_AUTH_TOKEN'));
        expect(error.message, isNot(contains(secret)));
      }
    });

    test('rejects development token control characters safely', () {
      const secret = 'opaque\u0000token';
      try {
        AppRuntimeConfig.fromValues(
          appMode: 'development',
          apiBaseUrl: 'http://localhost:5005',
          devAuthToken: secret,
        );
        fail('Expected control-character token to fail');
      } on StateError catch (error) {
        expect(error.message, contains('control characters'));
        expect(error.message, isNot(contains(secret)));
      }
    });

    test('production rejects HTTP and development tokens', () {
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'production',
          apiBaseUrl: 'http://management.example.test',
        ),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('HTTPS'),
          ),
        ),
      );
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'production',
          apiBaseUrl: 'https://management.example.test',
          devAuthToken: 'forbidden-token',
        ),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('forbidden in production'),
          ),
        ),
      );
    });

    test('demo rejects network and authentication configuration', () {
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'demo',
          apiBaseUrl: 'https://management.example.test',
        ),
        throwsA(isA<StateError>()),
      );
      expect(
        () => AppRuntimeConfig.fromValues(
          appMode: 'demo',
          devAuthToken: 'forbidden-token',
        ),
        throwsA(isA<StateError>()),
      );
    });

    test('rejects URL credentials, paths, queries, and fragments', () {
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
          ),
          throwsA(isA<StateError>()),
          reason: value,
        );
      }
    });

    test('rejects an unsupported demo scenario', () {
      expect(
        () => AppRuntimeConfig.parseScenario('random'),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('Unsupported DEMO_SCENARIO'),
          ),
        ),
      );
    });
  });
}
