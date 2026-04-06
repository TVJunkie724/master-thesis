import 'dart:typed_data';

import 'package:dio/dio.dart';
import '../config/api_config.dart';
import '../core/result.dart';
import '../models/calc_result.dart';
import '../utils/api_error_handler.dart';

class ApiService {
  late final Dio _dio;
  // TODO: Make configurable via environment variable or auth provider
  String? _token = 'dev-token';

  /// Expose base URL for other services (e.g., SSE)
  static String get baseUrl => ApiConfig.baseUrl;

  ApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        headers: {'Content-Type': 'application/json'},
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (_token != null) {
            options.headers['Authorization'] = 'Bearer $_token';
          }
          return handler.next(options);
        },
      ),
    );
  }

  void setToken(String token) => _token = token;

  /// Get current auth token for SSE connections
  Future<String?> getAuthToken() async => _token;

  /// Update current user's preferences (e.g., theme)
  Future<Map<String, dynamic>> updateUserPreferences({
    String? themePreference,
  }) async {
    final data = <String, dynamic>{};
    if (themePreference != null) data['theme_preference'] = themePreference;
    final response = await _dio.patch('/auth/me', data: data);
    return response.data;
  }

  Future<List<dynamic>> getTwins() async {
    final response = await _dio.get('/twins/');
    return response.data;
  }

  Future<Map<String, dynamic>> getDashboardStats() async {
    final response = await _dio.get('/dashboard/stats');
    return response.data;
  }

  Future<Map<String, dynamic>> getTwin(String twinId) async {
    final response = await _dio.get('/twins/$twinId');
    return response.data;
  }

  Future<Map<String, dynamic>> createTwin(String name) async {
    final response = await _dio.post('/twins/', data: {'name': name});
    return response.data;
  }

  Future<Map<String, dynamic>> updateTwin(
    String twinId, {
    String? name,
    String? state,
  }) async {
    final data = <String, dynamic>{};
    if (name != null) data['name'] = name;
    if (state != null) data['state'] = state;

    final response = await _dio.put('/twins/$twinId', data: data);
    return response.data;
  }

  Future<void> deleteTwin(String twinId) async {
    await _dio.delete('/twins/$twinId');
  }

  Future<Map<String, dynamic>> getTwinConfig(String twinId) async {
    final response = await _dio.get('/twins/$twinId/config/');
    return response.data;
  }

  Future<Map<String, dynamic>> updateTwinConfig(
    String twinId,
    Map<String, dynamic> config,
  ) async {
    final response = await _dio.put('/twins/$twinId/config/', data: config);
    return response.data;
  }

  Future<Map<String, dynamic>> validateCredentials(
    String twinId,
    String provider,
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/config/validate/$provider',
    );
    return response.data;
  }

  /// Validate credentials without storing them (inline validation)
  Future<Map<String, dynamic>> validateCredentialsInline(
    String provider,
    Map<String, dynamic> credentials,
  ) async {
    final response = await _dio.post(
      '/config/validate-inline',
      data: {'provider': provider, provider: credentials},
    );
    return response.data;
  }

  /// Validate credentials against BOTH Optimizer and Deployer APIs
  /// Returns: { provider, valid, optimizer: {valid, message}, deployer: {valid, message} }
  Future<Map<String, dynamic>> validateCredentialsDual(
    String provider,
    Map<String, dynamic> credentials,
  ) async {
    final response = await _dio.post(
      '/config/validate-dual',
      data: {'provider': provider, provider: credentials},
    );
    return response.data;
  }

  /// Validate STORED credentials against BOTH APIs
  /// Used when fields are empty (hidden secrets)
  Future<Map<String, dynamic>> validateStoredCredentialsDual(
    String twinId,
    String provider,
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/config/validate-stored/$provider',
    );
    return response.data;
  }

  // ============================================================
  // Optimizer Endpoints (Step 2)
  // ============================================================

  /// Get pricing data freshness status for all providers
  Future<Map<String, dynamic>> getPricingStatus() async {
    final response = await _dio.get('/optimizer/pricing-status');
    return response.data;
  }

  /// Get regions data freshness status for all providers
  Future<Map<String, dynamic>> getRegionsStatus() async {
    final response = await _dio.get('/optimizer/regions-status');
    return response.data;
  }

  /// Refresh pricing for a specific provider
  /// Uses credentials from twin configuration
  Future<Map<String, dynamic>> refreshPricing(
    String provider,
    String twinId,
  ) async {
    final response = await _dio.post(
      '/optimizer/refresh-pricing/$provider',
      queryParameters: {'twin_id': twinId},
    );
    return response.data;
  }

  /// Calculate costs using Optimizer
  /// Returns full result including costs, cheapest path, and overrides
  Future<Map<String, dynamic>> calculateCosts(
    Map<String, dynamic> params,
  ) async {
    final response = await _dio.put('/optimizer/calculate', data: params);
    return response.data;
  }

  // ============================================================
  // Optimizer Config Persistence (Step 2)
  // ============================================================

  /// Get optimizer config (params + result + cheapest path)
  Future<Map<String, dynamic>> getOptimizerConfig(String twinId) async {
    final response = await _dio.get('/twins/$twinId/optimizer-config');
    return response.data;
  }

  /// Save params only (before calculation)
  Future<void> saveOptimizerParams(
    String twinId,
    Map<String, dynamic> params,
  ) async {
    await _dio.put(
      '/twins/$twinId/optimizer-config/params',
      data: {'params': params},
    );
  }

  /// Save full result with pricing snapshots (after calculation)
  Future<void> saveOptimizerResult(
    String twinId, {
    required Map<String, dynamic> params,
    required Map<String, dynamic> result,
    required Map<String, String?> cheapestPath,
    required Map<String, dynamic> pricingSnapshots,
    required Map<String, String?> pricingTimestamps,
  }) async {
    await _dio.put(
      '/twins/$twinId/optimizer-config/result',
      data: {
        'params': params,
        'result': result,
        'cheapest_path': cheapestPath,
        'pricing_snapshots': pricingSnapshots,
        'pricing_timestamps': pricingTimestamps,
      },
    );
  }

  /// Export pricing data from Optimizer (for snapshotting)
  Future<Map<String, dynamic>> exportPricing(String provider) async {
    final response = await _dio.get('/optimizer/pricing/export/$provider');
    return response.data;
  }

  // ============================================================
  // Deployer Config Endpoints (Step 3 Section 2)
  // ============================================================

  /// Get deployer config for a twin
  Future<Map<String, dynamic>> getDeployerConfig(String twinId) async {
    final response = await _dio.get('/twins/$twinId/deployer/config');
    return response.data;
  }

  /// Update deployer config for a twin
  Future<Map<String, dynamic>> updateDeployerConfig(
    String twinId,
    Map<String, dynamic> config,
  ) async {
    final response = await _dio.put(
      '/twins/$twinId/deployer/config',
      data: config,
    );
    return response.data;
  }

  /// Validate deployer config via Management API (proxies to Deployer)
  Future<Map<String, dynamic>> validateDeployerConfig(
    String twinId,
    String configType, // 'config', 'events', or 'iot'
    String content,
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/deployer/validate/$configType',
      data: {'content': content},
    );
    return response.data;
  }

  /// Validate L2 function code or state machine (proxies to Deployer)
  /// Returns normalized {valid: bool, message: String}
  Future<Map<String, dynamic>> validateL2Content(
    String twinId,
    String type, // 'function-code' or 'state-machine'
    String content,
    String provider, // 'aws', 'azure', 'gcp'
  ) async {
    // Map Flutter provider names to Deployer enum values
    final deployerProvider = provider.toLowerCase() == 'gcp'
        ? 'google'
        : provider.toLowerCase();
    final response = await _dio.post(
      '/twins/$twinId/deployer/validate/$type',
      data: {'content': content, 'provider': deployerProvider},
    );
    return response.data;
  }

  /// Validate L4/L5 content (hierarchy, scene-config, user-config)
  /// Returns normalized {valid: bool, message: String}
  Future<Map<String, dynamic>> validateL4Content(
    String twinId,
    String type, // 'hierarchy', 'scene-config', 'user-config'
    String content,
    String provider, // 'aws', 'azure'
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/deployer/validate/$type',
      data: {'content': content, 'provider': provider.toLowerCase()},
    );
    return response.data;
  }

  // ============================================================
  // GLB File Upload/Delete (L4 Scene)
  // ============================================================

  /// Upload scene.glb file for 3D visualization
  /// Returns {message: String, size_mb: double}
  Future<Map<String, dynamic>> uploadSceneGlb(
    String twinId,
    dynamic fileBytes, // Uint8List or File
    String filename,
  ) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(fileBytes, filename: filename),
    });
    final response = await _dio.post(
      '/twins/$twinId/deployer/upload-glb',
      data: formData,
    );
    return response.data;
  }

  /// Delete scene.glb file for a twin
  Future<void> deleteSceneGlb(String twinId) async {
    await _dio.delete('/twins/$twinId/deployer/upload-glb');
  }

  // ============================================================
  // Zip Upload and Extraction (Step 3 Auto-Population)
  // ============================================================

  /// Upload project.zip and extract contents for wizard auto-population.
  ///
  /// Returns extracted config files, function code, and assets.
  /// GLB files are automatically saved to the server if present.
  ///
  /// Validation errors are aggregated (not fail-fast) to provide
  /// maximum feedback on first upload.
  Future<Map<String, dynamic>> uploadProjectZip(
    String twinId,
    dynamic fileBytes, // Uint8List or File
    String filename,
  ) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(fileBytes, filename: filename),
    });
    final response = await _dio.post(
      '/twins/$twinId/deployer/upload-zip',
      data: formData,
      options: Options(
        sendTimeout: const Duration(seconds: 120),
        receiveTimeout: const Duration(seconds: 120),
      ),
    );
    return response.data;
  }

  // ============================================================
  // Result-Returning Methods (Type-Safe Error Handling)
  // ============================================================

  /// Calculate costs with structured error handling.
  ///
  /// Returns [Success] with [CalcResult] on success,
  /// or [Failure] with [AppException] on error.
  Future<Result<CalcResult>> calculateCostsResult(
    Map<String, dynamic> params,
  ) async {
    try {
      final response = await calculateCosts(params);
      final result = CalcResult.fromJson(response);
      return Success(result);
    } on DioException catch (e) {
      return Failure(AppException.fromDioError(e));
    } catch (e) {
      return Failure(
        AppException(
          'Calculation failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  /// Get pricing status with structured error handling.
  Future<Result<Map<String, dynamic>>> getPricingStatusResult() async {
    try {
      final data = await getPricingStatus();
      return Success(data);
    } on DioException catch (e) {
      return Failure(AppException.fromDioError(e));
    } catch (e) {
      return Failure(
        AppException(
          'Failed to load pricing status: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  /// Get twin config with structured error handling.
  Future<Result<Map<String, dynamic>>> getTwinConfigResult(
    String twinId,
  ) async {
    try {
      final data = await getTwinConfig(twinId);
      return Success(data);
    } on DioException catch (e) {
      return Failure(AppException.fromDioError(e));
    } catch (e) {
      return Failure(
        AppException(
          'Failed to load twin config: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  // ==========================================================================
  // Deployment Operations
  // ==========================================================================

  /// Deploy a twin's infrastructure
  Future<Map<String, dynamic>> deployTwin(String twinId) async {
    final response = await _dio.post('/twins/$twinId/deploy');
    return response.data as Map<String, dynamic>;
  }

  /// Destroy a twin's infrastructure
  Future<Map<String, dynamic>> destroyTwin(String twinId) async {
    final response = await _dio.post('/twins/$twinId/destroy');
    return response.data as Map<String, dynamic>;
  }

  /// Get deployment status (polling fallback)
  Future<Map<String, dynamic>> getDeploymentStatus(String twinId) async {
    final response = await _dio.get('/twins/$twinId/deployment-status');
    return response.data as Map<String, dynamic>;
  }

  /// Get terraform outputs from most recent successful deployment
  /// Returns {outputs: Map?, deployed_at: String?}
  Future<Map<String, dynamic>> getDeploymentOutputs(String twinId) async {
    final response = await _dio.get('/twins/$twinId/outputs');
    return response.data as Map<String, dynamic>;
  }

  // ==========================================================================
  // SSE Streaming and Logs
  // ==========================================================================

  /// Get full SSE URL for streaming deployment logs
  String getSseUrl(String sseUrl, {int? lastEventId}) {
    final base = '${ApiConfig.baseUrl}$sseUrl';
    if (lastEventId != null && lastEventId > 0) {
      return '$base?last_event_id=$lastEventId';
    }
    return base;
  }

  /// Get deployment logs from database (for catchup after reconnection)
  Future<Map<String, dynamic>> getDeploymentLogs(
    String twinId, {
    String? sessionId,
    int? afterEventId,
    int limit = 100,
  }) async {
    final queryParams = <String, dynamic>{'limit': limit};
    if (sessionId != null) queryParams['session_id'] = sessionId;
    if (afterEventId != null) queryParams['after_event_id'] = afterEventId;

    final response = await _dio.get(
      '/twins/$twinId/logs',
      queryParameters: queryParams,
    );
    return response.data as Map<String, dynamic>;
  }

  // ==========================================================================
  // Log Trace (Live Log Tracing)
  // ==========================================================================

  /// Start a log trace test for a deployed twin
  ///
  /// Sends a test IoT message with a unique trace_id and returns
  /// the trace_id for SSE streaming.
  ///
  /// Returns {trace_id, sent_at, l1_provider, providers, message}
  Future<Map<String, dynamic>> startLogTrace(String twinId) async {
    final response = await _dio.post('/twins/$twinId/log-trace/start');
    return response.data as Map<String, dynamic>;
  }

  // ==========================================================================
  // Deployment Verification
  // ==========================================================================

  /// Run structured infrastructure verification (L0-L5 checks)
  /// Returns {checks: List, summary: {pass_count, fail_count, skip_count, total, healthy}}
  Future<Map<String, dynamic>> verifyInfrastructure(String twinId) async {
    final response = await _dio.post(
      '/twins/$twinId/verify/infrastructure',
      options: Options(receiveTimeout: const Duration(seconds: 60)),
    );
    return response.data as Map<String, dynamic>;
  }

  /// Start data flow verification with SSE streaming.
  /// Returns {session_id, sse_url} for connecting to SSE.
  Future<Map<String, dynamic>> verifyDataFlow(
    String twinId,
    Map<String, dynamic> payload,
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/verify/dataflow',
      data: {'payload': payload},
      options: Options(receiveTimeout: const Duration(seconds: 30)),
    );
    return response.data as Map<String, dynamic>;
  }

  /// Download IoT simulator package (L1 provider determined by backend).
  /// Returns binary ZIP data.
  Future<Uint8List> downloadSimulator(String twinId) async {
    final response = await _dio.get(
      '/twins/$twinId/simulator/download',
      options: Options(
        responseType: ResponseType.bytes,
        receiveTimeout: const Duration(seconds: 60),
      ),
    );
    return response.data as Uint8List;
  }
}
