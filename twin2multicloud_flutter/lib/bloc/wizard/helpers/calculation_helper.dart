// lib/bloc/wizard/helpers/calculation_helper.dart
// Extracted calculation/optimizer logic

import '../../../models/calc_result.dart';
import '../wizard_state.dart';

/// Helper class for calculation-related operations
/// Extracts logic from WizardBloc to improve maintainability
class CalculationHelper {
  
  /// Check if calculation result differs in ways that affect Step 3
  /// Invalidates if inputParamsUsed changed OR cheapestPath changed
  static bool calculationInvalidatesStep3(
    CalcResult? oldResult, 
    CalcResult newResult
  ) {
    if (oldResult == null) return false;
    
    // Check inputParamsUsed
    final oldParams = oldResult.inputParamsUsed;
    final newParams = newResult.inputParamsUsed;
    
    final paramsChanged = 
           oldParams.useEventChecking != newParams.useEventChecking ||
           oldParams.triggerNotificationWorkflow != newParams.triggerNotificationWorkflow ||
           oldParams.returnFeedbackToDevice != newParams.returnFeedbackToDevice ||
           oldParams.integrateErrorHandling != newParams.integrateErrorHandling ||
           oldParams.needs3DModel != newParams.needs3DModel;
    
    // Check cheapestPath
    final pathChanged = !listEquals(oldResult.cheapestPath, newResult.cheapestPath);
    
    return paramsChanged || pathChanged;
  }
  
  /// Check list equality
  static bool listEquals<T>(List<T> a, List<T> b) {
    if (a.length != b.length) return false;
    for (int i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
  
  /// Get unconfigured providers from optimal path
  static Set<String> getUnconfiguredProviders(
    List<String> path, 
    Set<String> configuredProviders
  ) {
    final resultProviders = extractProvidersFromPath(path);
    return resultProviders.difference(configuredProviders);
  }
  
  /// Extract all providers from a cheapest path
  static Set<String> extractProvidersFromPath(List<String> path) {
    final resultProviders = <String>{};
    for (final segment in path) {
      final parts = segment.split('_');
      if (parts.length >= 3 && segment.startsWith('L3')) {
        resultProviders.add(parts[2].toUpperCase());
      } else if (parts.length >= 2) {
        resultProviders.add(parts[1].toUpperCase());
      }
    }
    return resultProviders;
  }
  
  /// Build warning message for calculation result
  static String? buildWarningMessage(
    CalcResult result,
    bool invalidatesStep3,
    Set<String> unconfiguredProviders,
  ) {
    if (invalidatesStep3) {
      return 'Calculation Changed: Step 3 configuration may need review. Proceeding will require confirmation.';
    } else if (unconfiguredProviders.isNotEmpty) {
      return 'Unconfigured provider(s) in optimal path: ${unconfiguredProviders.join(", ")}. Return to Step 1 to add credentials.';
    }
    return null;
  }
  
  /// Extract provider from path segment
  static String? extractProviderFromSegment(String segment) {
    final parts = segment.split('_');
    if (parts.length >= 3 && segment.startsWith('L3')) {
      return parts[2].toUpperCase();
    } else if (parts.length >= 2) {
      return parts[1].toUpperCase();
    }
    return null;
  }
  
  /// Get L4 provider from cheapest path
  static String? getL4Provider(CalcResult? result) {
    if (result == null) return null;
    for (final segment in result.cheapestPath) {
      if (segment.startsWith('L4_')) {
        return extractProviderFromSegment(segment);
      }
    }
    return null;
  }
  
  /// Get L5 provider from cheapest path
  static String? getL5Provider(CalcResult? result) {
    if (result == null) return null;
    for (final segment in result.cheapestPath) {
      if (segment.startsWith('L5_')) {
        return extractProviderFromSegment(segment);
      }
    }
    return null;
  }
}
