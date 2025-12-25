import 'package:dio/dio.dart';
import '../config/api_config.dart';

class ApiService {
  late final Dio _dio;
  String? _token;
  
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
}
