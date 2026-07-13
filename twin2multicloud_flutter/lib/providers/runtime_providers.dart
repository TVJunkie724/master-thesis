import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/api_config.dart';
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

final apiServiceProvider = Provider<ManagementApi>((ref) => ApiService());

final logStreamClientFactoryProvider = Provider<LogStreamClientFactory>(
  (ref) =>
      () => SseService(
        baseUrl: ApiConfig.baseUrl,
        authToken: ApiConfig.devAuthToken,
      ),
);
