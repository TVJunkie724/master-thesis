/// Calculation result from Optimizer API.
/// 
/// Contains cost breakdown for all providers, cheapest path,
/// optimization overrides, and comparison tables.
class CalcResult {
  /// AWS cost breakdown by layer
  final ProviderCosts awsCosts;

  /// Azure cost breakdown by layer
  final ProviderCosts azureCosts;

  /// GCP cost breakdown by layer (some layers null - L4/L5 not implemented)
  final ProviderCosts gcpCosts;

  /// Cheapest path as list of segments (e.g., ['L1_AWS', 'L2_Azure', ...])
  final List<String> cheapestPath;

  /// Optimization overrides - explain why non-cheapest was chosen
  final OptimizationOverride? l1OptimizationOverride;
  final OptimizationOverride? l2OptimizationOverride;
  final OptimizationOverride? l3OptimizationOverride;
  final OptimizationOverride? l2CoolOptimizationOverride;
  final OptimizationOverride? l2ArchiveOptimizationOverride;
  final OptimizationOverride? l4OptimizationOverride;

  /// Combination tables for comparison display
  final List<Map<String, dynamic>>? l2L3Combinations;
  final List<Map<String, dynamic>>? l2CoolCombinations;
  final List<Map<String, dynamic>>? l2ArchiveCombinations;

  /// Cross-cloud transfer costs (key -> cost)
  final Map<String, double>? transferCosts;
  
  /// Input params used for the calculation (for invalidation detection)
  final InputParamsUsed inputParamsUsed;

  CalcResult({
    required this.awsCosts,
    required this.azureCosts,
    required this.gcpCosts,
    required this.cheapestPath,
    this.l1OptimizationOverride,
    this.l2OptimizationOverride,
    this.l3OptimizationOverride,
    this.l2CoolOptimizationOverride,
    this.l2ArchiveOptimizationOverride,
    this.l4OptimizationOverride,
    this.l2L3Combinations,
    this.l2CoolCombinations,
    this.l2ArchiveCombinations,
    this.transferCosts,
    required this.inputParamsUsed,
  });

  /// Parse from API response
  /// Handles both wrapped {'result': {...}} and unwrapped response formats
  factory CalcResult.fromJson(Map<String, dynamic> json) {
    // Handle both wrapped and unwrapped response formats
    final Map<String, dynamic> result;
    if (json.containsKey('result') && json['result'] is Map<String, dynamic>) {
      result = json['result'] as Map<String, dynamic>;
    } else if (json.containsKey('awsCosts')) {
      // Direct format - the json IS the result
      result = json;
    } else {
      throw FormatException('Invalid CalcResult format: missing result or awsCosts key. Keys: ${json.keys}');
    }

    Map<String, double>? parseTransferCosts(dynamic data) {
      if (data == null) return null;
      final map = <String, double>{};
      (data as Map<String, dynamic>).forEach((key, value) {
        if (value is num) {
          map[key] = value.toDouble();
        }
      });
      return map;
    }

    return CalcResult(
      awsCosts: ProviderCosts.fromJson(result['awsCosts'] as Map<String, dynamic>),
      azureCosts: ProviderCosts.fromJson(result['azureCosts'] as Map<String, dynamic>),
      gcpCosts: ProviderCosts.fromJson(result['gcpCosts'] as Map<String, dynamic>? ?? {}),
      cheapestPath: List<String>.from(result['cheapestPath'] ?? []),
      l1OptimizationOverride: result['l1OptimizationOverride'] != null
          ? OptimizationOverride.fromJson(result['l1OptimizationOverride'])
          : null,
      l2OptimizationOverride: result['l2OptimizationOverride'] != null
          ? OptimizationOverride.fromJson(result['l2OptimizationOverride'])
          : null,
      l3OptimizationOverride: result['l3OptimizationOverride'] != null
          ? OptimizationOverride.fromJson(result['l3OptimizationOverride'])
          : null,
      l2CoolOptimizationOverride: result['l2CoolOptimizationOverride'] != null
          ? OptimizationOverride.fromJson(result['l2CoolOptimizationOverride'])
          : null,
      l2ArchiveOptimizationOverride: result['l2ArchiveOptimizationOverride'] != null
          ? OptimizationOverride.fromJson(result['l2ArchiveOptimizationOverride'])
          : null,
      l4OptimizationOverride: result['l4OptimizationOverride'] != null
          ? OptimizationOverride.fromJson(result['l4OptimizationOverride'])
          : null,
      l2L3Combinations: (result['l2_l3_combinations'] as List?)
          ?.map((e) => Map<String, dynamic>.from(e))
          .toList(),
      l2CoolCombinations: (result['l2_cool_combinations'] as List?)
          ?.map((e) => Map<String, dynamic>.from(e))
          .toList(),
      l2ArchiveCombinations: (result['l2_archive_combinations'] as List?)
          ?.map((e) => Map<String, dynamic>.from(e))
          .toList(),
      transferCosts: parseTransferCosts(result['transferCosts']),
      inputParamsUsed: InputParamsUsed.fromJson(
        result['inputParamsUsed'] as Map<String, dynamic>? ?? {},
      ),
    );
  }

  /// Calculate total cost from selected providers in cheapest path
  double get totalCost {
    double total = 0;
    // Parse cheapest path and sum costs
    for (final segment in cheapestPath) {
      final parts = segment.split('_');
      if (parts.length >= 2) {
        final layer = parts[0];
        final provider = parts[1].toLowerCase();
        
        final ProviderCosts costs;
        if (provider == 'aws') {
          costs = awsCosts;
        } else if (provider == 'azure') {
          costs = azureCosts;
        } else {
          costs = gcpCosts;
        }
        
        final LayerCost? layerCost = costs.getLayer(layer);
        if (layerCost != null) {
          total += layerCost.cost;
        }
      }
    }
    
    // Add transfer costs if any
    if (transferCosts != null) {
      for (final cost in transferCosts!.values) {
        total += cost;
      }
    }
    
    return total;
  }
}

/// Cost breakdown for a single cloud provider
class ProviderCosts {
  final LayerCost? l1;
  final LayerCost? l2;
  final LayerCost? l3Hot;
  final LayerCost? l3Cool;
  final LayerCost? l3Archive;
  final LayerCost? l4;
  final LayerCost? l5;

  ProviderCosts({
    this.l1,
    this.l2,
    this.l3Hot,
    this.l3Cool,
    this.l3Archive,
    this.l4,
    this.l5,
  });

  factory ProviderCosts.fromJson(Map<String, dynamic> json) {
    return ProviderCosts(
      l1: json['L1'] != null ? LayerCost.fromJson(json['L1']) : null,
      l2: json['L2'] != null ? LayerCost.fromJson(json['L2']) : null,
      l3Hot: json['L3_hot'] != null ? LayerCost.fromJson(json['L3_hot']) : null,
      l3Cool: json['L3_cool'] != null ? LayerCost.fromJson(json['L3_cool']) : null,
      l3Archive: json['L3_archive'] != null ? LayerCost.fromJson(json['L3_archive']) : null,
      l4: json['L4'] != null ? LayerCost.fromJson(json['L4']) : null,
      l5: json['L5'] != null ? LayerCost.fromJson(json['L5']) : null,
    );
  }

  /// Get layer cost by key (L1, L2, L3, etc.)
  LayerCost? getLayer(String key) {
    switch (key.toUpperCase()) {
      case 'L1':
        return l1;
      case 'L2':
        return l2;
      case 'L3':
      case 'L3_HOT':
        return l3Hot;
      case 'L3_COOL':
        return l3Cool;
      case 'L3_ARCHIVE':
        return l3Archive;
      case 'L4':
        return l4;
      case 'L5':
        return l5;
      default:
        return null;
    }
  }
}

/// Cost for a single layer
class LayerCost {
  /// Total cost for this layer
  final double cost;

  /// Component breakdown (service name -> cost)
  final Map<String, double> components;

  /// Data size in GB (optional, for storage layers)
  final double? dataSizeInGB;

  LayerCost({
    required this.cost,
    required this.components,
    this.dataSizeInGB,
  });

  factory LayerCost.fromJson(Map<String, dynamic> json) {
    final componentsRaw = json['components'] as Map<String, dynamic>? ?? {};
    final components = <String, double>{};
    
    componentsRaw.forEach((key, value) {
      if (value is num) {
        components[key] = value.toDouble();
      }
    });

    return LayerCost(
      cost: (json['cost'] as num?)?.toDouble() ?? 0,
      components: components,
      dataSizeInGB: (json['dataSizeInGB'] as num?)?.toDouble(),
    );
  }
}

/// Optimization override info
/// Explains why a non-cheapest provider was selected
class OptimizationOverride {
  /// The provider that was selected
  final String selectedProvider;

  /// The cheapest provider (that wasn't selected)
  final String cheapestProvider;

  /// Candidate comparison data
  final List<Map<String, dynamic>>? candidates;

  OptimizationOverride({
    required this.selectedProvider,
    required this.cheapestProvider,
    this.candidates,
  });

  factory OptimizationOverride.fromJson(Map<String, dynamic> json) {
    return OptimizationOverride(
      selectedProvider: json['selectedProvider'] as String? ?? '',
      cheapestProvider: json['cheapestProvider'] as String? ?? '',
      candidates: (json['candidates'] as List?)
          ?.map((e) => Map<String, dynamic>.from(e))
          .toList(),
    );
  }
}

/// Input parameters that affect Step 3 configuration
/// Changes to these trigger Step 3 invalidation
class InputParamsUsed {
  final bool useEventChecking;
  final bool triggerNotificationWorkflow;
  final bool returnFeedbackToDevice;
  final bool integrateErrorHandling;
  final bool needs3DModel;

  const InputParamsUsed({
    this.useEventChecking = false,
    this.triggerNotificationWorkflow = false,
    this.returnFeedbackToDevice = false,
    this.integrateErrorHandling = false,
    this.needs3DModel = false,
  });

  factory InputParamsUsed.fromJson(Map<String, dynamic> json) {
    return InputParamsUsed(
      useEventChecking: json['useEventChecking'] as bool? ?? false,
      triggerNotificationWorkflow: json['triggerNotificationWorkflow'] as bool? ?? false,
      returnFeedbackToDevice: json['returnFeedbackToDevice'] as bool? ?? false,
      integrateErrorHandling: json['integrateErrorHandling'] as bool? ?? false,
      needs3DModel: json['needs3DModel'] as bool? ?? false,
    );
  }
}
