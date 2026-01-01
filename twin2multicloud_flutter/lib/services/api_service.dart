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
    _dio = Dio(BaseOptions(
      baseUrl: ApiConfig.baseUrl,
      headers: {'Content-Type': 'application/json'},
    ));
    
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_token != null) {
          options.headers['Authorization'] = 'Bearer $_token';
        }
        return handler.next(options);
      },
    ));
  }
  
  void setToken(String token) => _token = token;
  
  /// Get current auth token for SSE connections
  Future<String?> getAuthToken() async => _token;
  
  /// Update current user's preferences (e.g., theme)
  Future<Map<String, dynamic>> updateUserPreferences({String? themePreference}) async {
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
    String twinId, 
    {String? name, String? state}
  ) async {
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
    Map<String, dynamic> config
  ) async {
    final response = await _dio.put('/twins/$twinId/config/', data: config);
    return response.data;
  }
  
  Future<Map<String, dynamic>> validateCredentials(
    String twinId, 
    String provider
  ) async {
    final response = await _dio.post('/twins/$twinId/config/validate/$provider');
    return response.data;
  }
  
  /// Validate credentials without storing them (inline validation)
  Future<Map<String, dynamic>> validateCredentialsInline(
    String provider,
    Map<String, dynamic> credentials
  ) async {
    final response = await _dio.post(
      '/config/validate-inline',
      data: {
        'provider': provider,
        provider: credentials,
      },
    );
    return response.data;
  }

  /// Validate credentials against BOTH Optimizer and Deployer APIs
  /// Returns: { provider, valid, optimizer: {valid, message}, deployer: {valid, message} }
  Future<Map<String, dynamic>> validateCredentialsDual(
    String provider,
    Map<String, dynamic> credentials
  ) async {
    final response = await _dio.post(
      '/config/validate-dual',
      data: {
        'provider': provider,
        provider: credentials,
      },
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
  Future<Map<String, dynamic>> refreshPricing(String provider, String twinId) async {
    final response = await _dio.post(
      '/optimizer/refresh-pricing/$provider',
      queryParameters: {'twin_id': twinId},
    );
    return response.data;
  }

  /// Calculate costs using Optimizer
  /// Returns full result including costs, cheapest path, and overrides
  Future<Map<String, dynamic>> calculateCosts(Map<String, dynamic> params) async {
    final response = await _dio.put(
      '/optimizer/calculate',
      data: params,
    );
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
  Future<void> saveOptimizerParams(String twinId, Map<String, dynamic> params) async {
    await _dio.put('/twins/$twinId/optimizer-config/params', data: {'params': params});
  }

  /// Save full result with pricing snapshots (after calculation)
  Future<void> saveOptimizerResult(String twinId, {
    required Map<String, dynamic> params,
    required Map<String, dynamic> result,
    required Map<String, String?> cheapestPath,
    required Map<String, dynamic> pricingSnapshots,
    required Map<String, String?> pricingTimestamps,
  }) async {
    await _dio.put('/twins/$twinId/optimizer-config/result', data: {
      'params': params,
      'result': result,
      'cheapest_path': cheapestPath,
      'pricing_snapshots': pricingSnapshots,
      'pricing_timestamps': pricingTimestamps,
    });
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
    final response = await _dio.put('/twins/$twinId/deployer/config', data: config);
    return response.data;
  }

  /// Validate deployer config via Management API (proxies to Deployer)
  Future<Map<String, dynamic>> validateDeployerConfig(
    String twinId,
    String configType,  // 'config', 'events', or 'iot'
    String content,
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/deployer/validate/$configType',
      data: {'content': content},
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
  Future<Result<CalcResult>> calculateCostsResult(Map<String, dynamic> params) async {
    try {
      final response = await calculateCosts(params);
      final result = CalcResult.fromJson(response);
      return Success(result);
    } on DioException catch (e) {
      return Failure(AppException.fromDioError(e));
    } catch (e) {
      return Failure(AppException('Calculation failed: ${ApiErrorHandler.extractMessage(e)}'));
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
      return Failure(AppException('Failed to load pricing status: ${ApiErrorHandler.extractMessage(e)}'));
    }
  }
  
  /// Get twin config with structured error handling.
  Future<Result<Map<String, dynamic>>> getTwinConfigResult(String twinId) async {
    try {
      final data = await getTwinConfig(twinId);
      return Success(data);
    } on DioException catch (e) {
      return Failure(AppException.fromDioError(e));
    } catch (e) {
      return Failure(AppException('Failed to load twin config: ${ApiErrorHandler.extractMessage(e)}'));
    }
  }
}
