import '../models/calc_params.dart';
import '../models/calc_result.dart';
import '../models/wizard_cache.dart';
import '../services/api_service.dart';
import '../core/result.dart';

/// Controller for Step 2 Optimizer business logic.
/// 
/// Extracts calculation and pricing management from the UI layer.
/// This follows Clean Architecture principles by separating:
/// - UI (Step2Optimizer widget) - presentation
/// - Controller (this class) - coordination
/// - Service (ApiService) - data access
class OptimizerController {
  final ApiService _api;
  final WizardCache _cache;
  
  OptimizerController(this._api, this._cache);
  
  /// Perform cost calculation with the given parameters.
  /// 
  /// Updates the cache on success with:
  /// - calcParams
  /// - calcResult  
  /// - calcResultRaw (for persistence)
  Future<Result<CalcResult>> calculate(CalcParams params) async {
    try {
      // Call API and get raw response first
      final response = await _api.calculateCosts(params.toJson());
      final calcResult = CalcResult.fromJson(response);
      
      // Update cache with results
      _cache.calcParams = params;
      _cache.calcResult = calcResult;
      // Store raw response for later persistence
      _cache.calcResultRaw = response;
      _cache.markDirty();
      
      return Success(calcResult);
    } on Exception catch (e) {
      return Failure(AppException('Calculation failed: $e'));
    }
  }
  
  /// Load pricing status for all providers.
  Future<Result<Map<String, dynamic>>> loadPricingStatus() async {
    return _api.getPricingStatusResult();
  }
  
  /// Cache pricing snapshots for persistence.
  /// 
  /// Called after successful calculation to store pricing data
  /// for auditability purposes.
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
        // Non-critical: pricing export failure doesn't block calculation
        snapshots[provider] = null;
        timestamps[provider] = null;
      }
    }
    
    _cache.pricingSnapshots = snapshots;
    _cache.pricingTimestamps = timestamps;
  }
  
  /// Check if a calculation result exists in the cache.
  bool get hasCalculationResult => _cache.calcResult != null;
  
  /// Get the current calculation result from cache.
  CalcResult? get cachedResult => _cache.calcResult;
  
  /// Get the current calculation params from cache.
  CalcParams? get cachedParams => _cache.calcParams;
}
