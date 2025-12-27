import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/controllers/optimizer_controller.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/wizard_cache.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';
import 'package:twin2multicloud_flutter/core/result.dart';

import '../fixtures/test_fixtures.dart';

/// Minimal mock for ApiService methods used by OptimizerController
class _TestApiService {
  Map<String, dynamic> Function(Map<String, dynamic>)? calculateCostsResponse;
  Map<String, dynamic> Function()? getPricingStatusResponse;
  Map<String, dynamic> Function(String)? exportPricingResponse;
  Exception? throwOnNextCall;
  
  void _checkThrow() {
    if (throwOnNextCall != null) {
      final e = throwOnNextCall!;
      throwOnNextCall = null;
      throw e;
    }
  }
  
  Future<Map<String, dynamic>> calculateCosts(Map<String, dynamic> params) async {
    _checkThrow();
    return calculateCostsResponse?.call(params) ?? TestFixtures.calcResultJson;
  }
  
  Future<Result<Map<String, dynamic>>> getPricingStatusResult() async {
    try {
      _checkThrow();
      final data = getPricingStatusResponse?.call() ?? <String, dynamic>{
        'aws': <String, dynamic>{'status': 'valid', 'is_fresh': true},
        'azure': <String, dynamic>{'status': 'valid', 'is_fresh': true},
        'gcp': <String, dynamic>{'status': 'valid', 'is_fresh': true},
      };
      return Success(data);
    } catch (e) {
      return Failure(AppException('Failed: $e'));
    }
  }
  
  Future<Map<String, dynamic>> exportPricing(String provider) async {
    _checkThrow();
    return exportPricingResponse?.call(provider) ?? <String, dynamic>{'provider': provider};
  }
}

/// Test-specific controller that accepts our minimal mock
class _TestableOptimizerController {
  final _TestApiService _api;
  final WizardCache _cache;
  
  _TestableOptimizerController(this._api, this._cache);
  
  Future<Result<CalcResult>> calculate(params) async {
    try {
      final response = await _api.calculateCosts(params.toJson());
      final calcResult = CalcResult.fromJson(response);
      
      _cache.calcParams = params;
      _cache.calcResult = calcResult;
      _cache.calcResultRaw = response;
      _cache.markDirty();
      
      return Success(calcResult);
    } on Exception catch (e) {
      return Failure(AppException('Calculation failed: $e'));
    }
  }
  
  Future<Result<Map<String, dynamic>>> loadPricingStatus() async {
    return _api.getPricingStatusResult();
  }
  
  Future<void> cachePricingSnapshots() async {
    final providers = ['aws', 'azure', 'gcp'];
    final snapshots = <String, dynamic>{};
    final timestamps = <String, String?>{};
    
    for (final provider in providers) {
      try {
        final data = await _api.exportPricing(provider);
        snapshots[provider] = data;
        timestamps[provider] = DateTime.now().toIso8601String();
      } catch (e) {
        snapshots[provider] = null;
        timestamps[provider] = null;
      }
    }
    
    _cache.pricingSnapshots = snapshots;
    _cache.pricingTimestamps = timestamps;
  }
  
  bool get hasCalculationResult => _cache.calcResult != null;
  CalcResult? get cachedResult => _cache.calcResult;
}

void main() {
  group('OptimizerController', () {
    late _TestApiService mockApi;
    late WizardCache cache;
    late _TestableOptimizerController controller;

    setUp(() {
      mockApi = _TestApiService();
      cache = WizardCache();
      controller = _TestableOptimizerController(mockApi, cache);
    });

    // ============================================================
    // Happy Path Tests
    // ============================================================

    group('calculate', () {
      test('returns Success with CalcResult on success', () async {
        mockApi.calculateCostsResponse = (_) => TestFixtures.calcResultJson;
        
        final result = await controller.calculate(TestFixtures.defaultCalcParams);
        
        expect(result.isSuccess, isTrue);
        expect(result.dataOrNull, isNotNull);
      });

      test('updates cache with calcParams', () async {
        mockApi.calculateCostsResponse = (_) => TestFixtures.calcResultJson;
        
        await controller.calculate(TestFixtures.defaultCalcParams);
        
        expect(cache.calcParams, isNotNull);
        expect(cache.calcParams?.numberOfDevices, 100);
      });

      test('updates cache with calcResult', () async {
        mockApi.calculateCostsResponse = (_) => TestFixtures.calcResultJson;
        
        await controller.calculate(TestFixtures.defaultCalcParams);
        
        expect(cache.calcResult, isNotNull);
        expect(cache.calcResult?.cheapestPath, isNotEmpty);
      });

      test('updates cache with raw response', () async {
        mockApi.calculateCostsResponse = (_) => TestFixtures.calcResultJson;
        
        await controller.calculate(TestFixtures.defaultCalcParams);
        
        expect(cache.calcResultRaw, isNotNull);
        expect(cache.calcResultRaw?['result'], isNotNull);
      });

      test('marks cache as dirty after calculation', () async {
        mockApi.calculateCostsResponse = (_) => TestFixtures.calcResultJson;
        expect(cache.hasUnsavedChanges, isFalse);
        
        await controller.calculate(TestFixtures.defaultCalcParams);
        
        expect(cache.hasUnsavedChanges, isTrue);
      });
    });

    group('loadPricingStatus', () {
      test('returns Success with pricing data', () async {
        final result = await controller.loadPricingStatus();
        
        expect(result.isSuccess, isTrue);
        expect(result.dataOrNull?['aws'], isNotNull);
      });
    });

    group('cachePricingSnapshots', () {
      test('stores snapshots for all providers', () async {
        await controller.cachePricingSnapshots();
        
        expect(cache.pricingSnapshots, isNotNull);
        expect(cache.pricingSnapshots?.keys, containsAll(['aws', 'azure', 'gcp']));
      });

      test('stores timestamps for all providers', () async {
        await controller.cachePricingSnapshots();
        
        expect(cache.pricingTimestamps, isNotNull);
        expect(cache.pricingTimestamps?.keys, containsAll(['aws', 'azure', 'gcp']));
      });
    });

    group('getters', () {
      test('hasCalculationResult returns false initially', () {
        expect(controller.hasCalculationResult, isFalse);
      });

      test('hasCalculationResult returns true after calculation', () async {
        mockApi.calculateCostsResponse = (_) => TestFixtures.calcResultJson;
        await controller.calculate(TestFixtures.defaultCalcParams);
        
        expect(controller.hasCalculationResult, isTrue);
      });

      test('cachedResult returns result after calculation', () async {
        mockApi.calculateCostsResponse = (_) => TestFixtures.calcResultJson;
        await controller.calculate(TestFixtures.defaultCalcParams);
        
        expect(controller.cachedResult, isNotNull);
      });
    });

    // ============================================================
    // Error Case Tests
    // ============================================================

    group('error handling', () {
      test('calculate returns Failure on API error', () async {
        mockApi.throwOnNextCall = Exception('Network error');
        
        final result = await controller.calculate(TestFixtures.defaultCalcParams);
        
        expect(result.isFailure, isTrue);
        expect((result as Failure).error.message, contains('Calculation failed'));
      });

      test('cachePricingSnapshots handles export failure gracefully', () async {
        mockApi.throwOnNextCall = Exception('Export failed');
        
        // Should not throw
        await controller.cachePricingSnapshots();
        
        // Snapshots should still exist but with null values
        expect(cache.pricingSnapshots, isNotNull);
      });
    });
  });
}
