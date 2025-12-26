import 'package:dio/dio.dart';
import '../config/api_config.dart';

class ApiService {
  late final Dio _dio;
  // TODO: Make configurable via environment variable or auth provider
  String? _token = 'dev-token';
  
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
  
  Future<List<dynamic>> getTwins() async {
    final response = await _dio.get('/twins');
    return response.data;
  }
  
  Future<Map<String, dynamic>> createTwin(String name) async {
    final response = await _dio.post('/twins', data: {'name': name});
    return response.data;
  }
  
  Future<Map<String, dynamic>> getTwinConfig(String twinId) async {
    final response = await _dio.get('/twins/$twinId/config');
    return response.data;
  }
  
  Future<Map<String, dynamic>> updateTwinConfig(
    String twinId, 
    Map<String, dynamic> config
  ) async {
    final response = await _dio.put('/twins/$twinId/config', data: config);
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
}

