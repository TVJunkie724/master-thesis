// Mock API Service for Flutter Testing
// Provides configurable responses for deterministic testing

import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';

/// A mock implementation of ApiService for testing.
/// 
/// Usage:
/// ```dart
/// final mock = MockApiService();
/// mock.getTwinsResponse = () async => {'twins': [...]};
/// mock.throwOnNextCall = true;
/// ```
class MockApiService {
  // ================================================================
  // Configuration
  // ================================================================
  
  String? _token;
  bool throwOnNextCall = false;
  Exception? exceptionToThrow;
  int callDelayMs = 0;
  
  // Call tracking
  final List<String> calledMethods = [];
  final Map<String, int> callCounts = {};
  final Map<String, List<dynamic>> callArgs = {};
  
  void _trackCall(String method, [List<dynamic>? args]) {
    calledMethods.add(method);
    callCounts[method] = (callCounts[method] ?? 0) + 1;
    if (args != null) {
      callArgs[method] = args;
    }
  }
  
  Future<T> _maybeThrow<T>(String method, Future<T> Function() action) async {
    _trackCall(method);
    
    if (callDelayMs > 0) {
      await Future.delayed(Duration(milliseconds: callDelayMs));
    }
    
    if (throwOnNextCall) {
      throwOnNextCall = false;
      throw exceptionToThrow ?? Exception('Mock error for $method');
    }
    
    return action();
  }
  
  void reset() {
    _token = null;
    throwOnNextCall = false;
    exceptionToThrow = null;
    callDelayMs = 0;
    calledMethods.clear();
    callCounts.clear();
    callArgs.clear();
  }
  
  // ================================================================
  // Configurable Responses
  // ================================================================
  
  // Twins
  Future<Map<String, dynamic>> Function()? getTwinsResponse;
  Future<Map<String, dynamic>> Function()? getDashboardStatsResponse;
  Future<Map<String, dynamic>> Function(String)? getTwinResponse;
  Future<Map<String, dynamic>> Function(String)? createTwinResponse;
  Future<Map<String, dynamic>> Function(String, {String? name, String? state})? updateTwinResponse;
  Future<void> Function(String)? deleteTwinResponse;
  
  // Config
  Future<Map<String, dynamic>> Function(String)? getTwinConfigResponse;
  Future<Map<String, dynamic>> Function(String, Map<String, dynamic>)? updateTwinConfigResponse;
  
  // Credentials
  Future<Map<String, dynamic>> Function(String, String)? validateCredentialsResponse;
  Future<Map<String, dynamic>> Function(String, Map<String, dynamic>)? validateCredentialsInlineResponse;
  Future<Map<String, dynamic>> Function(String, Map<String, dynamic>)? validateCredentialsDualResponse;
  Future<Map<String, dynamic>> Function(String, String)? validateStoredCredentialsDualResponse;
  
  // Optimizer
  Future<Map<String, dynamic>> Function()? getPricingStatusResponse;
  Future<Map<String, dynamic>> Function()? getRegionsStatusResponse;
  Future<Map<String, dynamic>> Function(String, String)? refreshPricingResponse;
  Future<Map<String, dynamic>> Function(Map<String, dynamic>)? calculateCostsResponse;
  Future<Map<String, dynamic>> Function(String)? getOptimizerConfigResponse;
  Future<void> Function(String, Map<String, dynamic>)? saveOptimizerParamsResponse;
  Future<void> Function(String, {
    required Map<String, dynamic> params,
    required Map<String, dynamic> result,
    required Map<String, String?> cheapestPath,
    required Map<String, dynamic> pricingSnapshots,
    required Map<String, String?> pricingTimestamps,
  })? saveOptimizerResultResponse;
  Future<Map<String, dynamic>> Function(String)? exportPricingResponse;
  
  // Deployer
  Future<Map<String, dynamic>> Function(String)? getDeployerConfigResponse;
  Future<Map<String, dynamic>> Function(String, Map<String, dynamic>)? updateDeployerConfigResponse;
  Future<Map<String, dynamic>> Function(String, String, String)? validateDeployerConfigResponse;
  Future<Map<String, dynamic>> Function(String, String, String, String)? validateL2ContentResponse;
  Future<Map<String, dynamic>> Function(String, String, String, String)? validateL4ContentResponse;
  Future<Map<String, dynamic>> Function(String, String, String, String)? validateL5ContentResponse;
  
  // Result wrappers
  Future<Result<CalcResult>> Function(Map<String, dynamic>)? calculateCostsResultResponse;
  Future<Result<Map<String, dynamic>>> Function()? getPricingStatusResultResponse;
  Future<Result<Map<String, dynamic>>> Function(String)? getTwinConfigResultResponse;
  
  // ================================================================
  // API Methods
  // ================================================================
  
  void setToken(String token) {
    _trackCall('setToken', [token]);
    _token = token;
  }
  
  String? getAuthToken() {
    _trackCall('getAuthToken');
    return _token;
  }
  
  Future<Map<String, dynamic>> updateUserPreferences({String? themePreference}) async {
    return _maybeThrow('updateUserPreferences', () async {
      return {'success': true, 'theme_preference': themePreference};
    });
  }
  
  Future<Map<String, dynamic>> getTwins() async {
    return _maybeThrow('getTwins', () async {
      if (getTwinsResponse != null) return getTwinsResponse!();
      return {'twins': []};
    });
  }
  
  Future<Map<String, dynamic>> getDashboardStats() async {
    return _maybeThrow('getDashboardStats', () async {
      if (getDashboardStatsResponse != null) return getDashboardStatsResponse!();
      return {'total': 0, 'deployed': 0, 'draft': 0, 'error': 0};
    });
  }
  
  Future<Map<String, dynamic>> getTwin(String twinId) async {
    return _maybeThrow('getTwin', () async {
      _trackCall('getTwin', [twinId]);
      if (getTwinResponse != null) return getTwinResponse!(twinId);
      return {'id': twinId, 'name': 'Mock Twin', 'state': 'draft'};
    });
  }
  
  Future<Map<String, dynamic>> createTwin(String name) async {
    return _maybeThrow('createTwin', () async {
      _trackCall('createTwin', [name]);
      if (createTwinResponse != null) return createTwinResponse!(name);
      return {'id': 'new-twin-id', 'name': name, 'state': 'draft'};
    });
  }
  
  Future<Map<String, dynamic>> updateTwin(String twinId, {String? name, String? state}) async {
    return _maybeThrow('updateTwin', () async {
      _trackCall('updateTwin', [twinId, name, state]);
      if (updateTwinResponse != null) {
        return updateTwinResponse!(twinId, name: name, state: state);
      }
      return {'id': twinId, 'name': name ?? 'Twin', 'state': state ?? 'draft'};
    });
  }
  
  Future<void> deleteTwin(String twinId) async {
    return _maybeThrow('deleteTwin', () async {
      _trackCall('deleteTwin', [twinId]);
      if (deleteTwinResponse != null) return deleteTwinResponse!(twinId);
    });
  }
  
  Future<Map<String, dynamic>> getTwinConfig(String twinId) async {
    return _maybeThrow('getTwinConfig', () async {
      _trackCall('getTwinConfig', [twinId]);
      if (getTwinConfigResponse != null) return getTwinConfigResponse!(twinId);
      return {
        'twin_id': twinId,
        'providers': ['AWS', 'Azure'],
        'aws_credentials': {},
        'azure_credentials': {},
        'gcp_credentials': {},
      };
    });
  }
  
  Future<Map<String, dynamic>> updateTwinConfig(String twinId, Map<String, dynamic> config) async {
    return _maybeThrow('updateTwinConfig', () async {
      _trackCall('updateTwinConfig', [twinId, config]);
      if (updateTwinConfigResponse != null) {
        return updateTwinConfigResponse!(twinId, config);
      }
      return {'success': true};
    });
  }
  
  Future<Map<String, dynamic>> validateCredentials(String twinId, String provider) async {
    return _maybeThrow('validateCredentials', () async {
      _trackCall('validateCredentials', [twinId, provider]);
      if (validateCredentialsResponse != null) {
        return validateCredentialsResponse!(twinId, provider);
      }
      return {'valid': true, 'message': 'Credentials valid'};
    });
  }
  
  Future<Map<String, dynamic>> validateCredentialsInline(
    String provider, 
    Map<String, dynamic> credentials
  ) async {
    return _maybeThrow('validateCredentialsInline', () async {
      _trackCall('validateCredentialsInline', [provider, credentials]);
      if (validateCredentialsInlineResponse != null) {
        return validateCredentialsInlineResponse!(provider, credentials);
      }
      return {'valid': true, 'message': 'Credentials valid'};
    });
  }
  
  Future<Map<String, dynamic>> validateCredentialsDual(
    String provider,
    Map<String, dynamic> credentials
  ) async {
    return _maybeThrow('validateCredentialsDual', () async {
      _trackCall('validateCredentialsDual', [provider, credentials]);
      if (validateCredentialsDualResponse != null) {
        return validateCredentialsDualResponse!(provider, credentials);
      }
      return {
        'provider': provider,
        'valid': true,
        'optimizer': {'valid': true, 'message': 'OK'},
        'deployer': {'valid': true, 'message': 'OK'},
      };
    });
  }
  
  Future<Map<String, dynamic>> validateStoredCredentialsDual(
    String twinId,
    String provider
  ) async {
    return _maybeThrow('validateStoredCredentialsDual', () async {
      _trackCall('validateStoredCredentialsDual', [twinId, provider]);
      if (validateStoredCredentialsDualResponse != null) {
        return validateStoredCredentialsDualResponse!(twinId, provider);
      }
      return {
        'provider': provider,
        'valid': true,
        'optimizer': {'valid': true, 'message': 'OK'},
        'deployer': {'valid': true, 'message': 'OK'},
      };
    });
  }
  
  Future<Map<String, dynamic>> getPricingStatus() async {
    return _maybeThrow('getPricingStatus', () async {
      if (getPricingStatusResponse != null) return getPricingStatusResponse!();
      return {
        'aws': {'fresh': true, 'age_hours': 1},
        'azure': {'fresh': true, 'age_hours': 2},
        'gcp': {'fresh': true, 'age_hours': 3},
      };
    });
  }
  
  Future<Map<String, dynamic>> getRegionsStatus() async {
    return _maybeThrow('getRegionsStatus', () async {
      if (getRegionsStatusResponse != null) return getRegionsStatusResponse!();
      return {
        'aws': {'fresh': true},
        'azure': {'fresh': true},
        'gcp': {'fresh': true},
      };
    });
  }
  
  Future<Map<String, dynamic>> refreshPricing(String provider, String twinId) async {
    return _maybeThrow('refreshPricing', () async {
      _trackCall('refreshPricing', [provider, twinId]);
      if (refreshPricingResponse != null) return refreshPricingResponse!(provider, twinId);
      return {'success': true};
    });
  }
  
  Future<Map<String, dynamic>> calculateCosts(Map<String, dynamic> params) async {
    return _maybeThrow('calculateCosts', () async {
      _trackCall('calculateCosts', [params]);
      if (calculateCostsResponse != null) return calculateCostsResponse!(params);
      return {
        'result': {
          'awsCosts': {'L1': {'cost': 10.0}},
          'azureCosts': {'L1': {'cost': 12.0}},
          'gcpCosts': {'L1': {'cost': 11.0}},
          'cheapestPath': ['L1_AWS'],
        }
      };
    });
  }
  
  Future<Map<String, dynamic>> getOptimizerConfig(String twinId) async {
    return _maybeThrow('getOptimizerConfig', () async {
      _trackCall('getOptimizerConfig', [twinId]);
      if (getOptimizerConfigResponse != null) return getOptimizerConfigResponse!(twinId);
      return {'params': {}, 'result': null, 'cheapest_path': null};
    });
  }
  
  Future<void> saveOptimizerParams(String twinId, Map<String, dynamic> params) async {
    return _maybeThrow('saveOptimizerParams', () async {
      _trackCall('saveOptimizerParams', [twinId, params]);
      if (saveOptimizerParamsResponse != null) {
        return saveOptimizerParamsResponse!(twinId, params);
      }
    });
  }
  
  Future<void> saveOptimizerResult(String twinId, {
    required Map<String, dynamic> params,
    required Map<String, dynamic> result,
    required Map<String, String?> cheapestPath,
    required Map<String, dynamic> pricingSnapshots,
    required Map<String, String?> pricingTimestamps,
  }) async {
    return _maybeThrow('saveOptimizerResult', () async {
      _trackCall('saveOptimizerResult', [twinId, params, result]);
      if (saveOptimizerResultResponse != null) {
        return saveOptimizerResultResponse!(
          twinId,
          params: params,
          result: result,
          cheapestPath: cheapestPath,
          pricingSnapshots: pricingSnapshots,
          pricingTimestamps: pricingTimestamps,
        );
      }
    });
  }
  
  Future<Map<String, dynamic>> exportPricing(String provider) async {
    return _maybeThrow('exportPricing', () async {
      _trackCall('exportPricing', [provider]);
      if (exportPricingResponse != null) return exportPricingResponse!(provider);
      return {'data': {}};
    });
  }
  
  Future<Map<String, dynamic>> getDeployerConfig(String twinId) async {
    return _maybeThrow('getDeployerConfig', () async {
      _trackCall('getDeployerConfig', [twinId]);
      if (getDeployerConfigResponse != null) return getDeployerConfigResponse!(twinId);
      return {
        'twin_id': twinId,
        'config_json': null,
        'config_events': null,
        'config_iot': null,
      };
    });
  }
  
  Future<Map<String, dynamic>> updateDeployerConfig(
    String twinId,
    Map<String, dynamic> config
  ) async {
    return _maybeThrow('updateDeployerConfig', () async {
      _trackCall('updateDeployerConfig', [twinId, config]);
      if (updateDeployerConfigResponse != null) {
        return updateDeployerConfigResponse!(twinId, config);
      }
      return {'success': true};
    });
  }
  
  Future<Map<String, dynamic>> validateDeployerConfig(
    String twinId,
    String configType,
    String content
  ) async {
    return _maybeThrow('validateDeployerConfig', () async {
      _trackCall('validateDeployerConfig', [twinId, configType, content]);
      if (validateDeployerConfigResponse != null) {
        return validateDeployerConfigResponse!(twinId, configType, content);
      }
      return {'valid': true, 'message': 'Valid'};
    });
  }
  
  Future<Map<String, dynamic>> validateL2Content(
    String twinId,
    String type,
    String content,
    String provider
  ) async {
    return _maybeThrow('validateL2Content', () async {
      _trackCall('validateL2Content', [twinId, type, content, provider]);
      if (validateL2ContentResponse != null) {
        return validateL2ContentResponse!(twinId, type, content, provider);
      }
      return {'valid': true, 'message': 'Valid'};
    });
  }
  
  Future<Map<String, dynamic>> validateL4Content(
    String twinId,
    String type,
    String content,
    String provider
  ) async {
    return _maybeThrow('validateL4Content', () async {
      _trackCall('validateL4Content', [twinId, type, content, provider]);
      if (validateL4ContentResponse != null) {
        return validateL4ContentResponse!(twinId, type, content, provider);
      }
      return {'valid': true, 'message': 'Valid'};
    });
  }
  
  Future<Map<String, dynamic>> validateL5Content(
    String twinId,
    String type,
    String content,
    String provider
  ) async {
    return _maybeThrow('validateL5Content', () async {
      _trackCall('validateL5Content', [twinId, type, content, provider]);
      if (validateL5ContentResponse != null) {
        return validateL5ContentResponse!(twinId, type, content, provider);
      }
      return {'valid': true, 'message': 'Valid'};
    });
  }
  
  // ================================================================
  // Result Wrappers
  // ================================================================
  
  Future<Result<CalcResult>> calculateCostsResult(Map<String, dynamic> params) async {
    return _maybeThrow('calculateCostsResult', () async {
      _trackCall('calculateCostsResult', [params]);
      if (calculateCostsResultResponse != null) {
        return calculateCostsResultResponse!(params);
      }
      final response = await calculateCosts(params);
      return Result.success(CalcResult.fromJson(response));
    });
  }
  
  Future<Result<Map<String, dynamic>>> getPricingStatusResult() async {
    return _maybeThrow('getPricingStatusResult', () async {
      if (getPricingStatusResultResponse != null) {
        return getPricingStatusResultResponse!();
      }
      final response = await getPricingStatus();
      return Result.success(response);
    });
  }
  
  Future<Result<Map<String, dynamic>>> getTwinConfigResult(String twinId) async {
    return _maybeThrow('getTwinConfigResult', () async {
      _trackCall('getTwinConfigResult', [twinId]);
      if (getTwinConfigResultResponse != null) {
        return getTwinConfigResultResponse!(twinId);
      }
      final response = await getTwinConfig(twinId);
      return Result.success(response);
    });
  }
}
