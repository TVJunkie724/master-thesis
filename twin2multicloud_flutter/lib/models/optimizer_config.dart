import 'package:equatable/equatable.dart';

import 'calc_params.dart';
import 'calc_result.dart';
import 'cloud_connection.dart';
import 'json_contract.dart';
import 'pricing_catalog.dart';
import 'resolved_deployment_specification.dart';

class OptimizationResultData extends Equatable {
  final CalcResult result;
  final Map<String, dynamic> payload;

  const OptimizationResultData({required this.result, required this.payload});

  factory OptimizationResultData.fromApiJson(Map<String, dynamic> json) {
    final payload = json['result'] == null
        ? JsonContract.immutableObject(json, 'calculation')
        : JsonContract.requiredObject(json, 'result');
    final data = OptimizationResultData.fromPayload(payload);
    if (data.result.pricingCatalogContext == null) {
      throw const FormatException(
        'Invalid API contract: calculation result is missing pricingCatalogs.',
      );
    }
    return data;
  }

  factory OptimizationResultData.fromPayload(Map<String, dynamic> payload) {
    final immutable = JsonContract.immutableObject(payload, 'optimizer_result');
    return OptimizationResultData(
      result: CalcResult.fromJson(immutable),
      payload: immutable,
    );
  }

  Map<String, dynamic> toEnvelopeJson() => {'result': payload};

  @override
  List<Object?> get props => [result, payload];
}

class OptimizerRunData extends Equatable {
  final String id;
  final String twinId;
  final OptimizationResultData optimization;
  final OptimizerDeploymentRunData deploymentRun;
  final double totalMonthlyCost;
  final String currency;
  final DateTime createdAt;
  final DateTime completedAt;

  const OptimizerRunData({
    required this.id,
    required this.twinId,
    required this.optimization,
    required this.deploymentRun,
    required this.totalMonthlyCost,
    required this.currency,
    required this.createdAt,
    required this.completedAt,
  });

  factory OptimizerRunData.fromJson(Map<String, dynamic> json) {
    final status = JsonContract.requiredString(json, 'status');
    if (status != 'succeeded') {
      throw const FormatException(
        'Invalid API contract: optimizer run status must be succeeded.',
      );
    }
    final result = OptimizationResultData.fromPayload(
      JsonContract.requiredObject(json, 'result_summary'),
    );
    if (result.result.transferPricingContext == null ||
        result.result.optimizationDiagnostics == null) {
      throw const FormatException(
        'Invalid API contract: optimizer run is missing exact transfer evidence.',
      );
    }
    final totalMonthlyCost = _requiredFiniteNonNegativeNumber(
      json,
      'total_monthly_cost',
    );
    if ((totalMonthlyCost - result.result.totalCost).abs() > 0.000000001) {
      throw const FormatException(
        'Invalid API contract: optimizer run total is inconsistent.',
      );
    }
    final currency = JsonContract.requiredString(json, 'currency');
    if (currency != 'USD' && currency != 'EUR') {
      throw const FormatException(
        'Invalid API contract: optimizer run currency is unsupported.',
      );
    }
    final createdAt = JsonContract.requiredDate(json, 'created_at');
    final completedAt = JsonContract.requiredDate(json, 'completed_at');
    if (completedAt.isBefore(createdAt)) {
      throw const FormatException(
        'Invalid API contract: optimizer run timestamps are inconsistent.',
      );
    }
    final id = JsonContract.requiredString(json, 'id');
    final twinId = JsonContract.requiredString(json, 'twin_id');
    final deploymentRun = OptimizerDeploymentRunData.fromDetailJson(json);
    if (deploymentRun.id != id || deploymentRun.twinId != twinId) {
      throw const FormatException(
        'Invalid API contract: optimizer deployment run identity is inconsistent.',
      );
    }
    return OptimizerRunData(
      id: id,
      twinId: twinId,
      optimization: result,
      deploymentRun: deploymentRun,
      totalMonthlyCost: totalMonthlyCost,
      currency: currency,
      createdAt: createdAt,
      completedAt: completedAt,
    );
  }

  @override
  List<Object?> get props => [
    id,
    twinId,
    optimization,
    deploymentRun,
    totalMonthlyCost,
    currency,
    createdAt,
    completedAt,
  ];
}

class CheapestPath extends Equatable {
  final CloudProvider? l1;
  final CloudProvider? l2;
  final CloudProvider? l3Hot;
  final CloudProvider? l3Cool;
  final CloudProvider? l3Archive;
  final CloudProvider? l4;
  final CloudProvider? l5;

  const CheapestPath({
    this.l1,
    this.l2,
    this.l3Hot,
    this.l3Cool,
    this.l3Archive,
    this.l4,
    this.l5,
  });

  factory CheapestPath.fromJson(Map<String, dynamic> json) => CheapestPath(
    l1: _optionalProvider(json, 'l1'),
    l2: _optionalProvider(json, 'l2'),
    l3Hot: _optionalProvider(json, 'l3_hot'),
    l3Cool: _optionalProvider(json, 'l3_cool'),
    l3Archive: _optionalProvider(json, 'l3_archive'),
    l4: _optionalProvider(json, 'l4'),
    l5: _optionalProvider(json, 'l5'),
  );

  factory CheapestPath.fromSegments(List<String> segments) {
    CloudProvider? providerFor(String prefix) {
      final segment = segments.cast<String?>().firstWhere(
        (candidate) =>
            candidate?.toLowerCase().startsWith(prefix.toLowerCase()) == true,
        orElse: () => null,
      );
      if (segment == null) return null;
      final normalized = segment.toLowerCase().split('_');
      for (final part in normalized.reversed) {
        try {
          return CloudProvider.fromApiValue(part);
        } on ArgumentError {
          continue;
        }
      }
      throw FormatException(
        'Invalid optimizer result: $prefix path segment has no supported provider.',
      );
    }

    return CheapestPath(
      l1: providerFor('L1_'),
      l2: providerFor('L2_'),
      l3Hot: providerFor('L3_hot_'),
      l3Cool: providerFor('L3_cool_'),
      l3Archive: providerFor('L3_archive_'),
      l4: providerFor('L4_'),
      l5: providerFor('L5_'),
    );
  }

  CloudProvider? providerForLayer(String layer) => switch (layer) {
    'l1' => l1,
    'l2' => l2,
    'l3_hot' => l3Hot,
    'l3_cool' => l3Cool,
    'l3_archive' => l3Archive,
    'l4' => l4,
    'l5' => l5,
    _ => null,
  };

  Map<String, String?> toJson() => {
    'l1': l1?.apiValue,
    'l2': l2?.apiValue,
    'l3_hot': l3Hot?.apiValue,
    'l3_cool': l3Cool?.apiValue,
    'l3_archive': l3Archive?.apiValue,
    'l4': l4?.apiValue,
    'l5': l5?.apiValue,
  };

  @override
  List<Object?> get props => [l1, l2, l3Hot, l3Cool, l3Archive, l4, l5];
}

class OptimizerConfigData extends Equatable {
  final String id;
  final String twinId;
  final CalcParams? params;
  final OptimizationResultData? optimization;
  final CheapestPath? cheapestPath;
  final DateTime? calculatedAt;
  final PricingCatalogContext? pricingCatalogContext;
  final DateTime updatedAt;

  const OptimizerConfigData({
    required this.id,
    required this.twinId,
    this.params,
    this.optimization,
    this.cheapestPath,
    this.calculatedAt,
    this.pricingCatalogContext,
    required this.updatedAt,
  });

  factory OptimizerConfigData.fromJson(Map<String, dynamic> json) {
    final paramsJson = JsonContract.optionalObject(json, 'params');
    final resultJson = JsonContract.optionalObject(json, 'result');
    final pathJson = JsonContract.optionalObject(json, 'cheapest_path');
    final pricingContextJson = JsonContract.optionalObject(
      json,
      'pricing_catalog_context',
    );
    final pricingCatalogContext = pricingContextJson == null
        ? null
        : PricingCatalogContext.fromJson(pricingContextJson);
    final optimization = resultJson == null
        ? null
        : OptimizationResultData.fromPayload(resultJson);
    final resultContext = optimization?.result.pricingCatalogContext;
    if ((pricingCatalogContext == null) != (resultContext == null) ||
        (pricingCatalogContext != null &&
            pricingCatalogContext != resultContext)) {
      throw const FormatException(
        'Invalid API contract: optimizer pricing catalog evidence is inconsistent.',
      );
    }
    return OptimizerConfigData(
      id: JsonContract.requiredString(json, 'id'),
      twinId: JsonContract.requiredString(json, 'twin_id'),
      params: paramsJson == null ? null : CalcParams.fromJson(paramsJson),
      optimization: optimization,
      cheapestPath: pathJson == null ? null : CheapestPath.fromJson(pathJson),
      calculatedAt: JsonContract.optionalDate(json, 'calculated_at'),
      pricingCatalogContext: pricingCatalogContext,
      updatedAt: JsonContract.requiredDate(json, 'updated_at'),
    );
  }

  PricingCatalogReference? catalog(CloudProvider provider) =>
      pricingCatalogContext?.catalogs[provider];

  CloudProvider? get l1Provider => cheapestPath?.l1;

  @override
  List<Object?> get props => [
    id,
    twinId,
    params,
    optimization,
    cheapestPath,
    calculatedAt,
    pricingCatalogContext,
    updatedAt,
  ];
}

CloudProvider? _optionalProvider(Map<String, dynamic> json, String field) {
  final value = JsonContract.optionalString(json, field);
  if (value == null) return null;
  try {
    return CloudProvider.fromApiValue(value);
  } on ArgumentError {
    throw FormatException(
      'Invalid API contract: cheapest_path.$field contains an unknown provider.',
    );
  }
}

double _requiredFiniteNonNegativeNumber(
  Map<String, dynamic> json,
  String field,
) {
  final value = json[field];
  if (value is! num || !value.isFinite || value < 0) {
    throw FormatException(
      'Invalid API contract: $field must be a finite non-negative number.',
    );
  }
  return value.toDouble();
}
