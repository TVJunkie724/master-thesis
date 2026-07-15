import 'package:flutter/services.dart';

import '../demo/demo_fixture_store.dart';
import '../demo/demo_log_stream_client.dart';
import '../demo/demo_management_api.dart';
import '../models/user.dart';
import '../services/api_service.dart';
import '../services/log_stream_client.dart';
import '../services/management_api.dart';
import '../services/sse_service.dart';
import 'app_runtime.dart';

class RuntimeComposition {
  final AppRuntimeConfig config;
  final ManagementApi managementApi;
  final LogStreamClientFactory logStreamClientFactory;
  final User? initialUser;

  const RuntimeComposition({
    required this.config,
    required this.managementApi,
    required this.logStreamClientFactory,
    this.initialUser,
  });

  static Future<RuntimeComposition> bootstrap(
    AppRuntimeConfig config, {
    AssetBundle? assetBundle,
  }) async {
    if (config.isDemo) {
      final store = await DemoFixtureStore.load(
        config.demoScenario,
        bundle: assetBundle,
      );
      return RuntimeComposition(
        config: config,
        managementApi: DemoManagementApi(store: store),
        logStreamClientFactory: () => DemoLogStreamClient(store: store),
        initialUser: User.fromJson(store.user),
      );
    }

    final baseUri = config.managementApiBaseUri;
    if (baseUri == null) {
      throw StateError('A networked runtime requires a Management API origin.');
    }
    final managementApi = ApiService(baseUri: baseUri);
    return RuntimeComposition(
      config: config,
      managementApi: managementApi,
      logStreamClientFactory: () => SseService(
        baseUrl: baseUri.toString(),
        authTokenProvider: managementApi.getAuthToken,
      ),
    );
  }
}
