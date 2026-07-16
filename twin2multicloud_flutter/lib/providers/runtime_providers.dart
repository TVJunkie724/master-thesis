import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_runtime.dart';
import '../services/api_service.dart';
import '../services/log_stream_client.dart';
import '../services/external_auth_launcher.dart';
import '../services/system_external_auth_launcher.dart';
import '../services/management_api.dart';
import '../services/sse_service.dart';
import '../models/user.dart';

final appRuntimeProvider = Provider<AppRuntimeConfig>(
  (ref) => AppRuntimeConfig.fromEnvironment(),
);

final initialUserProvider = Provider<User?>((ref) => null);

final externalAuthLauncherProvider = Provider<ExternalAuthLauncher>(
  (ref) => createSystemExternalAuthLauncher(),
);

final authPollDelayProvider = Provider<Future<void> Function(Duration)>(
  (ref) => Future<void>.delayed,
);

final authClockProvider = Provider<DateTime Function()>(
  (ref) =>
      () => DateTime.now().toUtc(),
);

final apiServiceProvider = Provider<ManagementApi>((ref) {
  final runtime = ref.watch(appRuntimeProvider);
  final baseUri = runtime.managementApiBaseUri;
  if (baseUri == null) {
    throw StateError('Network Management API requested in a demo runtime.');
  }
  return ApiService(baseUri: baseUri);
});

final logStreamClientFactoryProvider = Provider<LogStreamClientFactory>((ref) {
  final managementApi = ref.watch(apiServiceProvider);
  final runtime = ref.watch(appRuntimeProvider);
  final baseUri = runtime.managementApiBaseUri;
  if (baseUri == null) {
    throw StateError('Network log stream requested in a demo runtime.');
  }
  return () => SseService(
    baseUrl: baseUri.toString(),
    authTokenProvider: managementApi.getAuthToken,
  );
});
