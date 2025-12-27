import 'package:dio/dio.dart';
import '../config/api_config.dart';

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
  
  Future<List<dynamic>> getTwins() async {
    final response = await _dio.get('/twins/');
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
}

