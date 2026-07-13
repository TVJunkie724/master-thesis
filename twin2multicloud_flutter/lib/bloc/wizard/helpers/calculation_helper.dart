// lib/bloc/wizard/helpers/calculation_helper.dart
// Extracted calculation/optimizer logic

import 'package:collection/collection.dart';
import '../../../models/calc_result.dart';
import '../../../widgets/architecture/architecture_service_map.dart';

/// Helper class for calculation-related operations
/// Extracts logic from WizardBloc to improve maintainability
class CalculationHelper {
  /// Check if calculation result differs in ways that affect Step 3
  /// Invalidates if inputParamsUsed changed OR cheapestPath changed
  static bool calculationInvalidatesStep3(
    CalcResult? oldResult,
    CalcResult newResult,
  ) {
    if (oldResult == null) return false;

    // Check inputParamsUsed
    final oldParams = oldResult.inputParamsUsed;
    final newParams = newResult.inputParamsUsed;

    final paramsChanged =
        oldParams.useEventChecking != newParams.useEventChecking ||
        oldParams.triggerNotificationWorkflow !=
            newParams.triggerNotificationWorkflow ||
        oldParams.returnFeedbackToDevice != newParams.returnFeedbackToDevice ||
        oldParams.integrateErrorHandling != newParams.integrateErrorHandling ||
        oldParams.needs3DModel != newParams.needs3DModel;

    // Check cheapestPath - use package:collection for proper list equality
    final listEquality = const ListEquality<String>();
    final pathChanged = !listEquality.equals(
      oldResult.cheapestPath,
      newResult.cheapestPath,
    );

    return paramsChanged || pathChanged;
  }

  /// Get unconfigured providers from optimal path
  static Set<String> getUnconfiguredProviders(
    List<String> path,
    Set<String> configuredProviders,
  ) {
    final resultProviders = extractProvidersFromPath(path);
    return resultProviders.difference(configuredProviders);
  }

  /// Extract all providers from a cheapest path
  /// Delegates to ArchitectureServiceMap to avoid code duplication
  static Set<String> extractProvidersFromPath(List<String> path) {
    final resultProviders = <String>{};
    for (final segment in path) {
      final provider = ArchitectureServiceMap.extractProviderFromSegment(
        segment,
      );
      if (provider != null) {
        resultProviders.add(provider);
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
      return 'The architecture changed. Deployment preparation requires review before continuing.';
    } else if (unconfiguredProviders.isNotEmpty) {
      return 'Deployment access is missing for: ${unconfiguredProviders.join(", ")}. Open Cloud access to continue.';
    }
    return null;
  }

  /// Get L4 provider from cheapest path
  static String? getL4Provider(CalcResult? result) {
    if (result == null) return null;
    for (final segment in result.cheapestPath) {
      if (segment.startsWith('L4_')) {
        return ArchitectureServiceMap.extractProviderFromSegment(segment);
      }
    }
    return null;
  }

  /// Get L5 provider from cheapest path
  static String? getL5Provider(CalcResult? result) {
    if (result == null) return null;
    for (final segment in result.cheapestPath) {
      if (segment.startsWith('L5_')) {
        return ArchitectureServiceMap.extractProviderFromSegment(segment);
      }
    }
    return null;
  }
}
