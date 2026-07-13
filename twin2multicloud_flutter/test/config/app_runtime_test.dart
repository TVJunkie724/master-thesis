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
