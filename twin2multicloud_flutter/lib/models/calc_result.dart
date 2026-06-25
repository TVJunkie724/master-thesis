/// Calculation result from Optimizer API.
///
/// Contains cost breakdown for all providers, cheapest path,
/// optimization overrides, and comparison tables.
class CalcResult {
  /// Total monthly cost (computed by backend engine, includes layer costs + transfer costs)
  final double totalCost;

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

  /// Additive trace metadata emitted by the optimizer.
  final String? traceSchemaVersion;
  final OptimizationProfileTrace? optimizationProfile;
  final Map<String, dynamic>? evidenceReferences;
  final IntentResultTrace? intentTrace;

  /// Input params used for the calculation (for invalidation detection)
  final InputParamsUsed inputParamsUsed;

  CalcResult({
    required this.totalCost,
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
    this.traceSchemaVersion,
    this.optimizationProfile,
    this.evidenceReferences,
    this.intentTrace,
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
      throw FormatException(
        'Invalid CalcResult format: missing result or awsCosts key. Keys: ${json.keys}',
      );
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
      totalCost: (result['totalCost'] as num?)?.toDouble() ?? 0,
      awsCosts: ProviderCosts.fromJson(
        result['awsCosts'] as Map<String, dynamic>,
      ),
      azureCosts: ProviderCosts.fromJson(
        result['azureCosts'] as Map<String, dynamic>,
      ),
      gcpCosts: ProviderCosts.fromJson(
        result['gcpCosts'] as Map<String, dynamic>? ?? {},
      ),
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
      l2ArchiveOptimizationOverride:
          result['l2ArchiveOptimizationOverride'] != null
          ? OptimizationOverride.fromJson(
              result['l2ArchiveOptimizationOverride'],
            )
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
      traceSchemaVersion: result['trace_schema_version']?.toString(),
      optimizationProfile: result['optimizationProfile'] is Map
          ? OptimizationProfileTrace.fromJson(
              Map<String, dynamic>.from(result['optimizationProfile'] as Map),
            )
          : null,
      evidenceReferences: result['evidenceReferences'] is Map
          ? Map<String, dynamic>.from(result['evidenceReferences'] as Map)
          : null,
      intentTrace: result['intentTrace'] is Map
          ? IntentResultTrace.fromJson(
              Map<String, dynamic>.from(result['intentTrace'] as Map),
            )
          : null,
      inputParamsUsed: InputParamsUsed.fromJson(
        result['inputParamsUsed'] as Map<String, dynamic>? ?? {},
      ),
    );
  }
}

class OptimizationProfileTrace {
  final String? profileId;
  final String? objective;
  final List<String> metricProviderIds;
  final List<String> calculationModelIds;
  final String? scoringStrategyId;
  final List<String> intentGroupIds;
  final String? resultSchemaVersion;
  final String? pricingRegistryVersion;

  const OptimizationProfileTrace({
    this.profileId,
    this.objective,
    this.metricProviderIds = const [],
    this.calculationModelIds = const [],
    this.scoringStrategyId,
    this.intentGroupIds = const [],
    this.resultSchemaVersion,
    this.pricingRegistryVersion,
  });

  factory OptimizationProfileTrace.fromJson(Map<String, dynamic> json) {
    return OptimizationProfileTrace(
      profileId: json['profile_id']?.toString(),
      objective: json['objective']?.toString(),
      metricProviderIds: _stringList(json['metric_provider_ids']),
      calculationModelIds: _stringList(json['calculation_model_ids']),
      scoringStrategyId: json['scoring_strategy_id']?.toString(),
      intentGroupIds: _stringList(json['intent_group_ids']),
      resultSchemaVersion: json['result_schema_version']?.toString(),
      pricingRegistryVersion: json['pricing_registry_version']?.toString(),
    );
  }
}

class IntentResultTrace {
  final String schemaVersion;
  final OptimizationProfileTrace? profile;
  final IntentTraceWorkload? workload;
  final List<IntentTraceSelectedPathEntry> selectedPath;
  final List<IntentTraceTransferEntry> transferTrace;
  final List<IntentTraceRecord> records;
  final IntentTraceSummary summary;

  const IntentResultTrace({
    required this.schemaVersion,
    this.profile,
    this.workload,
    this.selectedPath = const [],
    this.transferTrace = const [],
    this.records = const [],
    required this.summary,
  });

  factory IntentResultTrace.fromJson(Map<String, dynamic> json) {
    return IntentResultTrace(
      schemaVersion: json['schema_version']?.toString() ?? '',
      profile: json['profile'] is Map
          ? OptimizationProfileTrace.fromJson(
              Map<String, dynamic>.from(json['profile'] as Map),
            )
          : null,
      workload: json['workload'] is Map
          ? IntentTraceWorkload.fromJson(
              Map<String, dynamic>.from(json['workload'] as Map),
            )
          : null,
      selectedPath: _mapList(
        json['selected_path'],
        IntentTraceSelectedPathEntry.fromJson,
      ),
      transferTrace: _mapList(
        json['transfer_trace'],
        IntentTraceTransferEntry.fromJson,
      ),
      records: _mapList(json['records'], IntentTraceRecord.fromJson),
      summary: json['summary'] is Map
          ? IntentTraceSummary.fromJson(
              Map<String, dynamic>.from(json['summary'] as Map),
            )
          : const IntentTraceSummary(),
    );
  }

  bool get publishable => summary.publishable;
  bool get hasReviewRequiredRecords => summary.reviewRequiredCount > 0;
}

class IntentTraceWorkload {
  final Map<String, dynamic> inputs;
  final Map<String, dynamic> derived;

  const IntentTraceWorkload({this.inputs = const {}, this.derived = const {}});

  factory IntentTraceWorkload.fromJson(Map<String, dynamic> json) {
    return IntentTraceWorkload(
      inputs: json['inputs'] is Map
          ? Map<String, dynamic>.from(json['inputs'] as Map)
          : const {},
      derived: json['derived'] is Map
          ? Map<String, dynamic>.from(json['derived'] as Map)
          : const {},
    );
  }
}

class IntentTraceSelectedPathEntry {
  final String? resultPath;
  final String? layerCostKey;
  final String? provider;
  final String? pathKey;
  final double? cost;

  const IntentTraceSelectedPathEntry({
    this.resultPath,
    this.layerCostKey,
    this.provider,
    this.pathKey,
    this.cost,
  });

  factory IntentTraceSelectedPathEntry.fromJson(Map<String, dynamic> json) {
    return IntentTraceSelectedPathEntry(
      resultPath: json['result_path']?.toString(),
      layerCostKey: json['layer_cost_key']?.toString(),
      provider: json['provider']?.toString(),
      pathKey: json['path_key']?.toString(),
      cost: _doubleOrNull(json['cost']),
    );
  }
}

class IntentTraceTransferEntry {
  final String? segment;
  final String? sourceLayer;
  final String? targetLayer;
  final String? sourceProvider;
  final String? targetProvider;
  final double? cost;
  final String? sourceIntentId;
  final List<String> evidenceReferenceIds;

  const IntentTraceTransferEntry({
    this.segment,
    this.sourceLayer,
    this.targetLayer,
    this.sourceProvider,
    this.targetProvider,
    this.cost,
    this.sourceIntentId,
    this.evidenceReferenceIds = const [],
  });

  factory IntentTraceTransferEntry.fromJson(Map<String, dynamic> json) {
    return IntentTraceTransferEntry(
      segment: json['segment']?.toString(),
      sourceLayer: json['source_layer']?.toString(),
      targetLayer: json['target_layer']?.toString(),
      sourceProvider: json['source_provider']?.toString(),
      targetProvider: json['target_provider']?.toString(),
      cost: _doubleOrNull(json['cost']),
      sourceIntentId: json['source_intent_id']?.toString(),
      evidenceReferenceIds: _stringList(json['evidence_reference_ids']),
    );
  }
}

class IntentTraceRecord {
  final String traceId;
  final String recordId;
  final String intentId;
  final String provider;
  final String layer;
  final String serviceKey;
  final String fieldId;
  final IntentTraceVerification verification;
  final Map<String, dynamic> source;
  final Map<String, dynamic> pricing;
  final Map<String, dynamic>? formula;
  final Map<String, dynamic> contribution;

  const IntentTraceRecord({
    required this.traceId,
    required this.recordId,
    required this.intentId,
    required this.provider,
    required this.layer,
    required this.serviceKey,
    required this.fieldId,
    required this.verification,
    this.source = const {},
    this.pricing = const {},
    this.formula,
    this.contribution = const {},
  });

  factory IntentTraceRecord.fromJson(Map<String, dynamic> json) {
    return IntentTraceRecord(
      traceId: json['trace_id']?.toString() ?? '',
      recordId: json['record_id']?.toString() ?? '',
      intentId: json['intent_id']?.toString() ?? '',
      provider: json['provider']?.toString() ?? '',
      layer: json['layer']?.toString() ?? '',
      serviceKey: json['service_key']?.toString() ?? '',
      fieldId: json['field_id']?.toString() ?? '',
      verification: json['verification'] is Map
          ? IntentTraceVerification.fromJson(
              Map<String, dynamic>.from(json['verification'] as Map),
            )
          : const IntentTraceVerification(),
      source: json['source'] is Map
          ? Map<String, dynamic>.from(json['source'] as Map)
          : const {},
      pricing: json['pricing'] is Map
          ? Map<String, dynamic>.from(json['pricing'] as Map)
          : const {},
      formula: json['formula'] is Map
          ? Map<String, dynamic>.from(json['formula'] as Map)
          : null,
      contribution: json['contribution'] is Map
          ? Map<String, dynamic>.from(json['contribution'] as Map)
          : const {},
    );
  }

  bool get selected => contribution['selected'] == true;
}

class IntentTraceVerification {
  final String status;
  final bool reviewRequired;
  final bool publishable;
  final String? evidenceReferenceId;

  const IntentTraceVerification({
    this.status = '',
    this.reviewRequired = false,
    this.publishable = false,
    this.evidenceReferenceId,
  });

  factory IntentTraceVerification.fromJson(Map<String, dynamic> json) {
    return IntentTraceVerification(
      status: json['status']?.toString() ?? '',
      reviewRequired: json['review_required'] as bool? ?? false,
      publishable: json['publishable'] as bool? ?? false,
      evidenceReferenceId: json['evidence_reference_id']?.toString(),
    );
  }
}

class IntentTraceSummary {
  final int recordCount;
  final int selectedRecordCount;
  final int reviewRequiredCount;
  final int unsupportedCount;
  final int selectedPathCount;
  final int transferSegmentCount;
  final bool publishable;

  const IntentTraceSummary({
    this.recordCount = 0,
    this.selectedRecordCount = 0,
    this.reviewRequiredCount = 0,
    this.unsupportedCount = 0,
    this.selectedPathCount = 0,
    this.transferSegmentCount = 0,
    this.publishable = false,
  });

  factory IntentTraceSummary.fromJson(Map<String, dynamic> json) {
    return IntentTraceSummary(
      recordCount: _intValue(json['record_count']),
      selectedRecordCount: _intValue(json['selected_record_count']),
      reviewRequiredCount: _intValue(json['review_required_count']),
      unsupportedCount: _intValue(json['unsupported_count']),
      selectedPathCount: _intValue(json['selected_path_count']),
      transferSegmentCount: _intValue(json['transfer_segment_count']),
      publishable: json['publishable'] as bool? ?? false,
    );
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
      l3Cool: json['L3_cool'] != null
          ? LayerCost.fromJson(json['L3_cool'])
          : null,
      l3Archive: json['L3_archive'] != null
          ? LayerCost.fromJson(json['L3_archive'])
          : null,
      l4: json['L4'] != null ? LayerCost.fromJson(json['L4']) : null,
      l5: json['L5'] != null ? LayerCost.fromJson(json['L5']) : null,
    );
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

  LayerCost({required this.cost, required this.components, this.dataSizeInGB});

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
      triggerNotificationWorkflow:
          json['triggerNotificationWorkflow'] as bool? ?? false,
      returnFeedbackToDevice: json['returnFeedbackToDevice'] as bool? ?? false,
      integrateErrorHandling: json['integrateErrorHandling'] as bool? ?? false,
      needs3DModel: json['needs3DModel'] as bool? ?? false,
    );
  }
}

List<String> _stringList(dynamic value) {
  if (value is! List) return const [];
  return value.map((item) => item.toString()).toList();
}

List<T> _mapList<T>(dynamic value, T Function(Map<String, dynamic>) parser) {
  if (value is! List) return const [];
  return value
      .whereType<Map>()
      .map((item) => parser(Map<String, dynamic>.from(item)))
      .toList();
}

double? _doubleOrNull(dynamic value) {
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

int _intValue(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value) ?? 0;
  return 0;
}
