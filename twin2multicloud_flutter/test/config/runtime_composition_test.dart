import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/config/runtime_composition.dart';
import 'package:twin2multicloud_flutter/demo/demo_log_stream_client.dart';
import 'package:twin2multicloud_flutter/demo/demo_management_api.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/services/sse_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'demo composition selects in-memory adapters and fixture identity',
    () async {
      const config = AppRuntimeConfig.demo(demoScenario: DemoScenario.degraded);

      final composition = await RuntimeComposition.bootstrap(config);

      expect(composition.config, same(config));
      expect(composition.managementApi, isA<DemoManagementApi>());
      expect(composition.logStreamClientFactory(), isA<DemoLogStreamClient>());
      expect(composition.initialUser?.id, 'demo-degraded-user');
    },
  );

  test('non-demo composition retains real infrastructure adapters', () async {
    final config = AppRuntimeConfig.development(
      managementApiBaseUri: Uri.parse('http://management.test'),
      developmentAuthToken: 'local-token',
    );

    final composition = await RuntimeComposition.bootstrap(config);

    expect(composition.managementApi, isA<ApiService>());
    expect(composition.logStreamClientFactory(), isA<SseService>());
    expect(composition.initialUser, isNull);
    expect(await composition.managementApi.getAuthToken(), isNull);
  });

  test('production composition starts without a bearer token', () async {
    final config = AppRuntimeConfig.production(
      managementApiBaseUri: Uri.parse('https://management.example.test'),
    );

    final composition = await RuntimeComposition.bootstrap(config);

    expect(composition.managementApi, isA<ApiService>());
    expect(await composition.managementApi.getAuthToken(), isNull);
  });
}
