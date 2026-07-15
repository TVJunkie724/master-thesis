import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_runtime.dart';
import '../services/api_service.dart';
import '../services/log_stream_client.dart';
import '../services/management_api.dart';
import '../services/sse_service.dart';
import '../models/user.dart';

final appRuntimeProvider = Provider<AppRuntimeConfig>(
  (ref) => AppRuntimeConfig.fromEnvironment(),
);

final initialUserProvider = Provider<User?>((ref) => null);

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
