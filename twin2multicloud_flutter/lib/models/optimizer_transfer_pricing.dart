import 'dart:collection';

import 'package:equatable/equatable.dart';

import 'cloud_connection.dart';
import 'json_contract.dart';
import 'pricing_catalog.dart';

const _transferContextVersion = 'complete-path-transfer-pricing.v1';
const _optimizationDiagnosticsVersion = 'complete-path-optimization.v1';
const _numericTolerance = 0.000000001;
const _maxEvidenceNumber = 1e30;
const _maxExactJsonInteger = 9007199254740991;

const _expectedEdges = <String, (String, String, String, String)>{
  'L1_to_L2': ('L1', 'L2', 'L1_INGESTION', 'L2_PROCESSING'),
  'L2_to_L3_hot': ('L2', 'L3_hot', 'L2_PROCESSING', 'L3_HOT_STORAGE'),
  'L3_hot_to_L3_cool': (
    'L3_hot',
    'L3_cool',
    'L3_HOT_STORAGE',
    'L3_COOL_STORAGE',
  ),
  'L3_cool_to_L3_archive': (
    'L3_cool',
    'L3_archive',
    'L3_COOL_STORAGE',
    'L3_ARCHIVE_STORAGE',
  ),
  'L3_hot_to_L4': ('L3_hot', 'L4', 'L3_HOT_STORAGE', 'L4_TWIN_MANAGEMENT'),
  'L4_to_L5': ('L4', 'L5', 'L4_TWIN_MANAGEMENT', 'L5_VISUALIZATION'),
};

const _providerPolicies = <CloudProvider, _ProviderTransferPolicy>{
  CloudProvider.aws: _ProviderTransferPolicy(
    networkTier: 'provider_default',
    billingScope: 'account_aggregate_public_egress',
    billingUnit: 'gb',
    bytesPerBillingUnit: 1000000000,
  ),
  CloudProvider.azure: _ProviderTransferPolicy(
    networkTier: 'microsoft_premium_global_network',
    billingScope: 'account_aggregate_public_egress',
    billingUnit: 'gb',
    bytesPerBillingUnit: 1000000000,
  ),
  CloudProvider.gcp: _ProviderTransferPolicy(
    networkTier: 'premium',
    billingScope: 'sku_account_aggregate_public_egress',
    billingUnit: 'gib',
    bytesPerBillingUnit: 1073741824,
  ),
};

final _identifierPattern = RegExp(r'^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,255}$');
final _regionPattern = RegExp(r'^[a-z][a-z0-9-]{1,62}$');
final _snapshotPattern = RegExp(r'^pcs_[0-9a-f]{64}$');

class OptimizerTransferEvidence extends Equatable {
  final TransferPricingContext context;
  final CompletePathOptimizationDiagnostics diagnostics;

  const OptimizerTransferEvidence({
    required this.context,
    required this.diagnostics,
  });

  factory OptimizerTransferEvidence.fromResult(
    Map<String, dynamic> result, {
    required PricingCatalogContext pricingCatalogContext,
  }) {
    final selectedProviders = _selectedProviders(result);
    final context = TransferPricingContext.fromJson(
      JsonContract.requiredObject(result, 'transferPricingContext'),
      selectedProviders: selectedProviders,
      pricingCatalogContext: pricingCatalogContext,
    );
    final diagnostics = CompletePathOptimizationDiagnostics.fromJson(
      JsonContract.requiredObject(result, 'optimizationDiagnostics'),
    );
    final currency = _requiredEnum(result, 'currency', const {
      'USD',
      'EUR',
    }, 'optimizer result');
    if (context.currency != currency ||
        diagnostics.scoreUnit != '$currency/month') {
      throw const FormatException(
        'Invalid API contract: transfer evidence currency is inconsistent.',
      );
    }

    final expectedCandidate = [
      for (final layer in const [
        'L1',
        'L2',
        'L3_hot',
        'L3_cool',
        'L3_archive',
        'L4',
        'L5',
      ])
        selectedProviders[layer]!.apiValue,
    ].join('|');
    if (diagnostics.winningCandidateId != expectedCandidate) {
      throw const FormatException(
        'Invalid API contract: optimizer winning candidate is inconsistent.',
      );
    }

    final chargedRoutes = context.routes
        .where((route) => route.isCrossProvider)
        .toList(growable: false);
    final transferTotal = chargedRoutes.fold<double>(
      0,
      (sum, route) => sum + route.totalCost,
    );
    if (!_close(diagnostics.winningTransferCost, transferTotal)) {
      throw const FormatException(
        'Invalid API contract: optimizer transfer total is inconsistent.',
      );
    }
    final resultTotal = _requiredNumber(result, 'totalCost');
    if (!_close(diagnostics.winningScore, resultTotal)) {
      throw const FormatException(
        'Invalid API contract: optimizer winning score is inconsistent.',
      );
    }
    _validateFlatTransferCosts(result, chargedRoutes);
    return OptimizerTransferEvidence(
      context: context,
      diagnostics: diagnostics,
    );
  }

  @override
  List<Object?> get props => [context, diagnostics];
}

class TransferPricingContext extends Equatable {
  final String schemaVersion;
  final String currency;
  final List<String> assumptions;
  final List<TransferRouteEvidence> routes;
  final List<TransferBillingPoolEvidence> pools;

  const TransferPricingContext({
    required this.schemaVersion,
    required this.currency,
    required this.assumptions,
    required this.routes,
    required this.pools,
  });

  factory TransferPricingContext.fromJson(
    Map<String, dynamic> json, {
    required Map<String, CloudProvider> selectedProviders,
    required PricingCatalogContext pricingCatalogContext,
  }) {
    _requireExactKeys(
      json,
      required: const {
        'schemaVersion',
        'currency',
        'assumptions',
        'routes',
        'pools',
      },
      field: 'transferPricingContext',
    );
    final schemaVersion = JsonContract.requiredString(json, 'schemaVersion');
    if (schemaVersion != _transferContextVersion) {
      throw const FormatException(
        'Invalid API contract: transferPricingContext.schemaVersion is unsupported.',
      );
    }
    final assumptions = _boundedStringList(json, 'assumptions', maxLength: 32);
    final routeValues = _requiredObjectList(
      json,
      'routes',
      exactLength: _expectedEdges.length,
    );
    final routes = routeValues
        .map(TransferRouteEvidence.fromJson)
        .toList(growable: false);
    final routesBySegment = {
      for (final route in routes) route.segmentId: route,
    };
    if (routesBySegment.length != routes.length ||
        routesBySegment.keys
            .toSet()
            .difference(_expectedEdges.keys.toSet())
            .isNotEmpty ||
        _expectedEdges.keys
            .toSet()
            .difference(routesBySegment.keys.toSet())
            .isNotEmpty) {
      throw const FormatException(
        'Invalid API contract: transferPricingContext.routes must contain the exact baseline segments.',
      );
    }

    final poolValues = _requiredObjectList(json, 'pools', maxLength: 3);
    final pools = poolValues
        .map(TransferBillingPoolEvidence.fromJson)
        .toList(growable: false);
    final poolsById = {for (final pool in pools) pool.poolId: pool};
    if (poolsById.length != pools.length) {
      throw const FormatException(
        'Invalid API contract: transferPricingContext.pools contains duplicate identities.',
      );
    }

    for (final entry in _expectedEdges.entries) {
      final route = routesBySegment[entry.key]!;
      route.validateContext(
        edge: entry.value,
        selectedProviders: selectedProviders,
        pricingCatalogContext: pricingCatalogContext,
        poolsById: poolsById,
      );
    }
    _validatePools(
      pools,
      routes.where((route) => route.isCrossProvider).toList(growable: false),
      pricingCatalogContext,
    );

    return TransferPricingContext(
      schemaVersion: schemaVersion,
      currency: _requiredEnum(json, 'currency', const {
        'USD',
        'EUR',
      }, 'transferPricingContext'),
      assumptions: assumptions,
      routes: List.unmodifiable(routes),
      pools: List.unmodifiable(pools),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    currency,
    assumptions,
    routes,
    pools,
  ];
}

class TransferEndpointEvidence extends Equatable {
  static const _layers = {
    'L1_INGESTION',
    'L2_PROCESSING',
    'L3_HOT_STORAGE',
    'L3_COOL_STORAGE',
    'L3_ARCHIVE_STORAGE',
    'L4_TWIN_MANAGEMENT',
    'L5_VISUALIZATION',
  };

  final String layer;
  final CloudProvider provider;
  final String region;
  final String geography;

  const TransferEndpointEvidence({
    required this.layer,
    required this.provider,
    required this.region,
    required this.geography,
  });

  factory TransferEndpointEvidence.fromJson(Map<String, dynamic> json) {
    _requireExactKeys(
      json,
      required: const {'layer', 'provider', 'region', 'geography'},
      field: 'transfer endpoint',
    );
    final layer = _requiredEnum(json, 'layer', _layers, 'transfer endpoint');
    final region = JsonContract.requiredString(json, 'region');
    if (!_regionPattern.hasMatch(region)) {
      throw const FormatException(
        'Invalid API contract: transfer endpoint region is invalid.',
      );
    }
    return TransferEndpointEvidence(
      layer: layer,
      provider: _requiredProvider(json, 'provider'),
      region: region,
      geography: _requiredEnum(json, 'geography', const {
        'europe',
      }, 'transfer endpoint'),
    );
  }

  @override
  List<Object?> get props => [layer, provider, region, geography];
}

class TransferTierContribution extends Equatable {
  final String tierId;
  final double fromQuantity;
  final double toQuantity;
  final double billableQuantity;
  final double unitPrice;
  final double cost;

  const TransferTierContribution({
    required this.tierId,
    required this.fromQuantity,
    required this.toQuantity,
    required this.billableQuantity,
    required this.unitPrice,
    required this.cost,
  });

  factory TransferTierContribution.fromJson(Map<String, dynamic> json) {
    _requireExactKeys(
      json,
      required: const {
        'tierId',
        'fromQuantity',
        'toQuantity',
        'billableQuantity',
        'unitPrice',
        'cost',
      },
      field: 'transfer tier contribution',
    );
    final tierId = _requiredIdentifier(json, 'tierId');
    final from = _requiredNumber(json, 'fromQuantity');
    final to = _requiredNumber(json, 'toQuantity', positive: true);
    final billable = _requiredNumber(json, 'billableQuantity', positive: true);
    final unitPrice = _requiredNumber(json, 'unitPrice');
    final cost = _requiredNumber(json, 'cost');
    if (to <= from ||
        !_close(billable, to - from) ||
        !_close(cost, billable * unitPrice)) {
      throw const FormatException(
        'Invalid API contract: transfer tier contribution arithmetic is inconsistent.',
      );
    }
    return TransferTierContribution(
      tierId: tierId,
      fromQuantity: from,
      toQuantity: to,
      billableQuantity: billable,
      unitPrice: unitPrice,
      cost: cost,
    );
  }

  @override
  List<Object?> get props => [
    tierId,
    fromQuantity,
    toQuantity,
    billableQuantity,
    unitPrice,
    cost,
  ];
}

class TransferRouteEvidence extends Equatable {
  static const _routeClasses = {
    'same_provider_same_region',
    'cross_provider_public_internet',
  };
  static const _networkTiers = {
    'not_applicable',
    'provider_default',
    'microsoft_premium_global_network',
    'premium',
  };

  final String segmentId;
  final TransferEndpointEvidence source;
  final TransferEndpointEvidence destination;
  final String routeClass;
  final String networkTier;
  final double volumeBytes;
  final String? poolId;
  final String? catalogSnapshotId;
  final String? evidenceId;
  final List<TransferTierContribution> tierContributions;
  final double egressCost;
  final double glueCost;
  final double totalCost;
  final List<String> assumptions;

  const TransferRouteEvidence({
    required this.segmentId,
    required this.source,
    required this.destination,
    required this.routeClass,
    required this.networkTier,
    required this.volumeBytes,
    required this.poolId,
    required this.catalogSnapshotId,
    required this.evidenceId,
    required this.tierContributions,
    required this.egressCost,
    required this.glueCost,
    required this.totalCost,
    required this.assumptions,
  });

  factory TransferRouteEvidence.fromJson(Map<String, dynamic> json) {
    _requireExactKeys(
      json,
      required: const {
        'segmentId',
        'source',
        'destination',
        'routeClass',
        'networkTier',
        'volumeBytes',
        'poolId',
        'catalogSnapshotId',
        'evidenceId',
        'tierContributions',
        'egressCost',
        'glueCost',
        'totalCost',
        'assumptions',
      },
      field: 'transfer route',
    );
    final contributions = _requiredObjectList(
      json,
      'tierContributions',
      maxLength: 32,
    ).map(TransferTierContribution.fromJson).toList(growable: false);
    final egressCost = _requiredNumber(json, 'egressCost');
    final glueCost = _requiredNumber(json, 'glueCost');
    final totalCost = _requiredNumber(json, 'totalCost');
    if (!_close(
          egressCost,
          contributions.fold<double>(0, (sum, item) => sum + item.cost),
        ) ||
        !_close(totalCost, egressCost + glueCost)) {
      throw const FormatException(
        'Invalid API contract: transfer route cost arithmetic is inconsistent.',
      );
    }
    return TransferRouteEvidence(
      segmentId: _requiredIdentifier(json, 'segmentId'),
      source: TransferEndpointEvidence.fromJson(
        JsonContract.requiredObject(json, 'source'),
      ),
      destination: TransferEndpointEvidence.fromJson(
        JsonContract.requiredObject(json, 'destination'),
      ),
      routeClass: _requiredEnum(
        json,
        'routeClass',
        _routeClasses,
        'transfer route',
      ),
      networkTier: _requiredEnum(
        json,
        'networkTier',
        _networkTiers,
        'transfer route',
      ),
      volumeBytes: _requiredIntegralNumber(json, 'volumeBytes'),
      poolId: _optionalIdentifier(json, 'poolId'),
      catalogSnapshotId: _optionalSnapshot(json, 'catalogSnapshotId'),
      evidenceId: _optionalIdentifier(json, 'evidenceId'),
      tierContributions: List.unmodifiable(contributions),
      egressCost: egressCost,
      glueCost: glueCost,
      totalCost: totalCost,
      assumptions: _boundedStringList(json, 'assumptions', maxLength: 32),
    );
  }

  bool get isCrossProvider => routeClass == 'cross_provider_public_internet';

  void validateContext({
    required (String, String, String, String) edge,
    required Map<String, CloudProvider> selectedProviders,
    required PricingCatalogContext pricingCatalogContext,
    required Map<String, TransferBillingPoolEvidence> poolsById,
  }) {
    if (source.layer != edge.$3 || destination.layer != edge.$4) {
      throw const FormatException(
        'Invalid API contract: transfer route topology is inconsistent.',
      );
    }
    if (source.provider != selectedProviders[edge.$1] ||
        destination.provider != selectedProviders[edge.$2]) {
      throw const FormatException(
        'Invalid API contract: transfer route provider selection is inconsistent.',
      );
    }
    for (final endpoint in [source, destination]) {
      if (endpoint.region !=
          pricingCatalogContext.reference(endpoint.provider).pricingRegion) {
        throw const FormatException(
          'Invalid API contract: transfer route region is inconsistent.',
        );
      }
    }

    if (source.provider == destination.provider) {
      if (routeClass != 'same_provider_same_region' ||
          source.region != destination.region ||
          networkTier != 'not_applicable' ||
          poolId != null ||
          catalogSnapshotId != null ||
          evidenceId != null ||
          tierContributions.isNotEmpty ||
          !_close(egressCost, 0) ||
          !_close(glueCost, 0) ||
          !_close(totalCost, 0)) {
        throw const FormatException(
          'Invalid API contract: same-provider transfer route is inconsistent.',
        );
      }
      return;
    }

    final policy = _providerPolicies[source.provider]!;
    final sourceCatalog = pricingCatalogContext.reference(source.provider);
    final pool = poolId == null ? null : poolsById[poolId];
    if (routeClass != 'cross_provider_public_internet' ||
        networkTier != policy.networkTier ||
        catalogSnapshotId != sourceCatalog.snapshotId ||
        pool == null ||
        pool.provider != source.provider ||
        pool.networkTier != networkTier ||
        pool.catalogSnapshotId != catalogSnapshotId ||
        pool.evidenceId != evidenceId) {
      throw const FormatException(
        'Invalid API contract: cross-provider transfer route identity is inconsistent.',
      );
    }
  }

  @override
  List<Object?> get props => [
    segmentId,
    source,
    destination,
    routeClass,
    networkTier,
    volumeBytes,
    poolId,
    catalogSnapshotId,
    evidenceId,
    tierContributions,
    egressCost,
    glueCost,
    totalCost,
    assumptions,
  ];
}

class TransferBillingPoolEvidence extends Equatable {
  final String poolId;
  final CloudProvider provider;
  final String routeClass;
  final String sourceGeography;
  final String destinationGeography;
  final String networkTier;
  final String billingScope;
  final String billingUnit;
  final int bytesPerBillingUnit;
  final String catalogSnapshotId;
  final String evidenceId;
  final double aggregateVolumeBytes;
  final double aggregateEgressCost;

  const TransferBillingPoolEvidence({
    required this.poolId,
    required this.provider,
    required this.routeClass,
    required this.sourceGeography,
    required this.destinationGeography,
    required this.networkTier,
    required this.billingScope,
    required this.billingUnit,
    required this.bytesPerBillingUnit,
    required this.catalogSnapshotId,
    required this.evidenceId,
    required this.aggregateVolumeBytes,
    required this.aggregateEgressCost,
  });

  factory TransferBillingPoolEvidence.fromJson(Map<String, dynamic> json) {
    _requireExactKeys(
      json,
      required: const {
        'poolId',
        'provider',
        'routeClass',
        'sourceGeography',
        'destinationGeography',
        'networkTier',
        'billingScope',
        'billingUnit',
        'bytesPerBillingUnit',
        'catalogSnapshotId',
        'evidenceId',
        'aggregateVolumeBytes',
        'aggregateEgressCost',
      },
      field: 'transfer billing pool',
    );
    return TransferBillingPoolEvidence(
      poolId: _requiredIdentifier(json, 'poolId'),
      provider: _requiredProvider(json, 'provider'),
      routeClass: _requiredEnum(json, 'routeClass', const {
        'cross_provider_public_internet',
      }, 'transfer billing pool'),
      sourceGeography: _requiredEnum(json, 'sourceGeography', const {
        'europe',
      }, 'transfer billing pool'),
      destinationGeography: _requiredEnum(json, 'destinationGeography', const {
        'europe',
      }, 'transfer billing pool'),
      networkTier: _requiredEnum(json, 'networkTier', const {
        'provider_default',
        'microsoft_premium_global_network',
        'premium',
      }, 'transfer billing pool'),
      billingScope: _requiredEnum(json, 'billingScope', const {
        'account_aggregate_public_egress',
        'sku_account_aggregate_public_egress',
      }, 'transfer billing pool'),
      billingUnit: _requiredEnum(json, 'billingUnit', const {
        'gb',
        'gib',
      }, 'transfer billing pool'),
      bytesPerBillingUnit: _requiredPositiveInt(json, 'bytesPerBillingUnit'),
      catalogSnapshotId: _requiredSnapshot(json, 'catalogSnapshotId'),
      evidenceId: _requiredIdentifier(json, 'evidenceId'),
      aggregateVolumeBytes: _requiredIntegralNumber(
        json,
        'aggregateVolumeBytes',
      ),
      aggregateEgressCost: _requiredNumber(json, 'aggregateEgressCost'),
    );
  }

  @override
  List<Object?> get props => [
    poolId,
    provider,
    routeClass,
    sourceGeography,
    destinationGeography,
    networkTier,
    billingScope,
    billingUnit,
    bytesPerBillingUnit,
    catalogSnapshotId,
    evidenceId,
    aggregateVolumeBytes,
    aggregateEgressCost,
  ];
}

class CompletePathOptimizationDiagnostics extends Equatable {
  final String schemaVersion;
  final int enumeratedPathCount;
  final int evaluatedPathCount;
  final int rejectedPathCount;
  final Map<String, int> rejectedByErrorCode;
  final String winningCandidateId;
  final double winningScore;
  final double winningLayerCost;
  final double winningTransferCost;
  final String tieBreakPolicy;
  final List<String> canonicalProviderOrder;
  final String scoreUnit;

  const CompletePathOptimizationDiagnostics({
    required this.schemaVersion,
    required this.enumeratedPathCount,
    required this.evaluatedPathCount,
    required this.rejectedPathCount,
    required this.rejectedByErrorCode,
    required this.winningCandidateId,
    required this.winningScore,
    required this.winningLayerCost,
    required this.winningTransferCost,
    required this.tieBreakPolicy,
    required this.canonicalProviderOrder,
    required this.scoreUnit,
  });

  factory CompletePathOptimizationDiagnostics.fromJson(
    Map<String, dynamic> json,
  ) {
    _requireExactKeys(
      json,
      required: const {
        'schemaVersion',
        'enumeratedPathCount',
        'evaluatedPathCount',
        'rejectedPathCount',
        'rejectedByErrorCode',
        'winningCandidateId',
        'winningScore',
        'winningLayerCost',
        'winningTransferCost',
        'tieBreakPolicy',
        'canonicalProviderOrder',
        'scoreUnit',
      },
      field: 'optimizationDiagnostics',
    );
    final schemaVersion = JsonContract.requiredString(json, 'schemaVersion');
    if (schemaVersion != _optimizationDiagnosticsVersion) {
      throw const FormatException(
        'Invalid API contract: optimizationDiagnostics.schemaVersion is unsupported.',
      );
    }
    final enumerated = _requiredBoundedInt(
      json,
      'enumeratedPathCount',
      min: 1,
      max: 10000000,
    );
    final evaluated = _requiredBoundedInt(
      json,
      'evaluatedPathCount',
      min: 1,
      max: 10000000,
    );
    final rejected = _requiredBoundedInt(
      json,
      'rejectedPathCount',
      min: 0,
      max: 10000000,
    );
    final rejectedByErrorCode = _positiveCountMap(
      json,
      'rejectedByErrorCode',
      maxLength: 64,
    );
    final winningScore = _requiredNumber(json, 'winningScore');
    final winningLayerCost = _requiredNumber(json, 'winningLayerCost');
    final winningTransferCost = _requiredNumber(json, 'winningTransferCost');
    final providerOrder = _boundedStringList(
      json,
      'canonicalProviderOrder',
      exactLength: 3,
      maxLength: 3,
    );
    if (evaluated + rejected != enumerated ||
        rejectedByErrorCode.values.fold<int>(0, (sum, value) => sum + value) !=
            rejected ||
        !_close(winningScore, winningLayerCost + winningTransferCost) ||
        !_listEquals(providerOrder, const ['aws', 'azure', 'gcp'])) {
      throw const FormatException(
        'Invalid API contract: optimization diagnostics are inconsistent.',
      );
    }
    final winningCandidateId = JsonContract.requiredString(
      json,
      'winningCandidateId',
    );
    if (!RegExp(
      r'^(aws|azure|gcp)(\|(aws|azure|gcp)){6}$',
    ).hasMatch(winningCandidateId)) {
      throw const FormatException(
        'Invalid API contract: optimization diagnostics candidate is invalid.',
      );
    }
    return CompletePathOptimizationDiagnostics(
      schemaVersion: schemaVersion,
      enumeratedPathCount: enumerated,
      evaluatedPathCount: evaluated,
      rejectedPathCount: rejected,
      rejectedByErrorCode: UnmodifiableMapView(rejectedByErrorCode),
      winningCandidateId: winningCandidateId,
      winningScore: winningScore,
      winningLayerCost: winningLayerCost,
      winningTransferCost: winningTransferCost,
      tieBreakPolicy: _requiredEnum(json, 'tieBreakPolicy', const {
        'canonical_provider_order',
      }, 'optimizationDiagnostics'),
      canonicalProviderOrder: List.unmodifiable(providerOrder),
      scoreUnit: _requiredEnum(json, 'scoreUnit', const {
        'USD/month',
        'EUR/month',
      }, 'optimizationDiagnostics'),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    enumeratedPathCount,
    evaluatedPathCount,
    rejectedPathCount,
    rejectedByErrorCode,
    winningCandidateId,
    winningScore,
    winningLayerCost,
    winningTransferCost,
    tieBreakPolicy,
    canonicalProviderOrder,
    scoreUnit,
  ];
}

void _validatePools(
  List<TransferBillingPoolEvidence> pools,
  List<TransferRouteEvidence> routes,
  PricingCatalogContext pricingCatalogContext,
) {
  final routesByPool = <String, List<TransferRouteEvidence>>{};
  for (final route in routes) {
    if (route.poolId != null) {
      routesByPool.putIfAbsent(route.poolId!, () => []).add(route);
    }
  }
  if (pools
          .map((pool) => pool.poolId)
          .toSet()
          .difference(routesByPool.keys.toSet())
          .isNotEmpty ||
      routesByPool.keys
          .toSet()
          .difference(pools.map((pool) => pool.poolId).toSet())
          .isNotEmpty) {
    throw const FormatException(
      'Invalid API contract: transfer billing pools do not match charged routes.',
    );
  }
  for (final pool in pools) {
    final policy = _providerPolicies[pool.provider]!;
    final catalog = pricingCatalogContext.reference(pool.provider);
    final poolRoutes = routesByPool[pool.poolId] ?? const [];
    if (pool.networkTier != policy.networkTier ||
        pool.billingScope != policy.billingScope ||
        pool.billingUnit != policy.billingUnit ||
        pool.bytesPerBillingUnit != policy.bytesPerBillingUnit ||
        pool.catalogSnapshotId != catalog.snapshotId ||
        !_close(
          pool.aggregateVolumeBytes,
          poolRoutes.fold<double>(0, (sum, route) => sum + route.volumeBytes),
        ) ||
        !_close(
          pool.aggregateEgressCost,
          poolRoutes.fold<double>(0, (sum, route) => sum + route.egressCost),
        )) {
      throw const FormatException(
        'Invalid API contract: transfer billing pool is inconsistent.',
      );
    }
    _validateTierAllocation(pool, poolRoutes);
  }
}

void _validateTierAllocation(
  TransferBillingPoolEvidence pool,
  List<TransferRouteEvidence> routes,
) {
  var consumed = 0.0;
  for (final route in routes) {
    final routeQuantity = route.volumeBytes / pool.bytesPerBillingUnit;
    if (_close(routeQuantity, 0)) {
      if (route.tierContributions.isNotEmpty) {
        throw const FormatException(
          'Invalid API contract: transfer tier allocation is inconsistent.',
        );
      }
      continue;
    }
    if (route.tierContributions.isEmpty) {
      throw const FormatException(
        'Invalid API contract: transfer tier allocation is incomplete.',
      );
    }
    var cursor = consumed;
    for (final contribution in route.tierContributions) {
      if (!_close(contribution.fromQuantity, cursor)) {
        throw const FormatException(
          'Invalid API contract: transfer tier allocation is discontinuous.',
        );
      }
      cursor = contribution.toQuantity;
    }
    if (!_close(cursor - consumed, routeQuantity)) {
      throw const FormatException(
        'Invalid API contract: transfer tier allocation has an invalid quantity.',
      );
    }
    consumed += routeQuantity;
  }
  if (!_close(consumed, pool.aggregateVolumeBytes / pool.bytesPerBillingUnit)) {
    throw const FormatException(
      'Invalid API contract: transfer billing pool allocation is inconsistent.',
    );
  }
}

void _validateFlatTransferCosts(
  Map<String, dynamic> result,
  List<TransferRouteEvidence> routes,
) {
  final value = result['transferCosts'];
  if (value is! Map || value.keys.any((key) => key is! String)) {
    throw const FormatException(
      'Invalid API contract: transferCosts must be an object.',
    );
  }
  final costs = Map<String, dynamic>.from(value);
  final expected = {
    for (final route in routes) route.segmentId: route.totalCost,
  };
  if (costs.keys.toSet().difference(expected.keys.toSet()).isNotEmpty ||
      expected.keys.toSet().difference(costs.keys.toSet()).isNotEmpty) {
    throw const FormatException(
      'Invalid API contract: transferCosts identities are inconsistent.',
    );
  }
  for (final entry in expected.entries) {
    final actual = costs[entry.key];
    if (actual is! num ||
        !actual.isFinite ||
        actual < 0 ||
        !_close(actual.toDouble(), entry.value)) {
      throw const FormatException(
        'Invalid API contract: transferCosts value is inconsistent.',
      );
    }
  }
}

Map<String, CloudProvider> _selectedProviders(Map<String, dynamic> result) {
  final calculation = JsonContract.requiredObject(result, 'calculationResult');
  final l3 = JsonContract.requiredObject(calculation, 'L3');
  CloudProvider provider(Map<String, dynamic> json, String field) {
    final value = JsonContract.requiredString(json, field);
    return switch (value) {
      'AWS' => CloudProvider.aws,
      'Azure' => CloudProvider.azure,
      'GCP' => CloudProvider.gcp,
      _ => throw FormatException(
        'Invalid API contract: calculationResult.$field is unsupported.',
      ),
    };
  }

  return {
    'L1': provider(calculation, 'L1'),
    'L2': provider(calculation, 'L2'),
    'L3_hot': provider(l3, 'Hot'),
    'L3_cool': provider(l3, 'Cool'),
    'L3_archive': provider(l3, 'Archive'),
    'L4': provider(calculation, 'L4'),
    'L5': provider(calculation, 'L5'),
  };
}

CloudProvider _requiredProvider(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  try {
    return CloudProvider.fromApiValue(value);
  } on ArgumentError {
    throw FormatException(
      'Invalid API contract: $field contains an unsupported provider.',
    );
  }
}

String _requiredEnum(
  Map<String, dynamic> json,
  String field,
  Set<String> allowed,
  String owner,
) {
  final value = JsonContract.requiredString(json, field);
  if (!allowed.contains(value)) {
    throw FormatException(
      'Invalid API contract: $owner.$field is unsupported.',
    );
  }
  return value;
}

double _requiredNumber(
  Map<String, dynamic> json,
  String field, {
  bool positive = false,
}) {
  final value = json[field];
  if (value is! num ||
      !value.isFinite ||
      value < 0 ||
      value > _maxEvidenceNumber ||
      (positive && value <= 0)) {
    throw FormatException(
      'Invalid API contract: $field must be a bounded JSON number.',
    );
  }
  return value.toDouble();
}

double _requiredIntegralNumber(Map<String, dynamic> json, String field) {
  final value = _requiredNumber(json, field);
  if (value > _maxExactJsonInteger || value != value.truncateToDouble()) {
    throw FormatException(
      'Invalid API contract: $field must be an exact JSON integer.',
    );
  }
  return value;
}

int _requiredPositiveInt(Map<String, dynamic> json, String field) =>
    _requiredBoundedInt(json, field, min: 1, max: 2147483647);

int _requiredBoundedInt(
  Map<String, dynamic> json,
  String field, {
  required int min,
  required int max,
}) {
  final value = json[field];
  if (value is! int || value < min || value > max) {
    throw FormatException(
      'Invalid API contract: $field must be a bounded integer.',
    );
  }
  return value;
}

String _requiredIdentifier(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  if (!_identifierPattern.hasMatch(value)) {
    throw FormatException(
      'Invalid API contract: $field must be a valid identifier.',
    );
  }
  return value;
}

String? _optionalIdentifier(Map<String, dynamic> json, String field) {
  final value = JsonContract.optionalString(json, field);
  if (value != null && !_identifierPattern.hasMatch(value)) {
    throw FormatException(
      'Invalid API contract: $field must be a valid identifier.',
    );
  }
  return value;
}

String _requiredSnapshot(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  if (!_snapshotPattern.hasMatch(value)) {
    throw FormatException(
      'Invalid API contract: $field must be a valid snapshot identifier.',
    );
  }
  return value;
}

String? _optionalSnapshot(Map<String, dynamic> json, String field) {
  final value = JsonContract.optionalString(json, field);
  if (value != null && !_snapshotPattern.hasMatch(value)) {
    throw FormatException(
      'Invalid API contract: $field must be a valid snapshot identifier.',
    );
  }
  return value;
}

List<Map<String, dynamic>> _requiredObjectList(
  Map<String, dynamic> json,
  String field, {
  int? exactLength,
  int? maxLength,
}) {
  final value = json[field];
  if (value is! List ||
      (exactLength != null && value.length != exactLength) ||
      (maxLength != null && value.length > maxLength) ||
      value.any((item) => item is! Map)) {
    throw FormatException(
      'Invalid API contract: $field must be a bounded object array.',
    );
  }
  return List.unmodifiable(
    value.map((item) => JsonContract.immutableObject(item, field)),
  );
}

List<String> _boundedStringList(
  Map<String, dynamic> json,
  String field, {
  int? exactLength,
  required int maxLength,
}) {
  final value = json[field];
  if (value is! List ||
      (exactLength != null && value.length != exactLength) ||
      value.length > maxLength ||
      value.any(
        (item) => item is! String || item.trim().isEmpty || item.length > 512,
      )) {
    throw FormatException(
      'Invalid API contract: $field must be a bounded string array.',
    );
  }
  return List<String>.unmodifiable(value.cast<String>());
}

Map<String, int> _positiveCountMap(
  Map<String, dynamic> json,
  String field, {
  required int maxLength,
}) {
  final value = json[field];
  if (value is! Map ||
      value.length > maxLength ||
      value.entries.any(
        (entry) =>
            entry.key is! String ||
            (entry.key as String).isEmpty ||
            (entry.key as String).length > 128 ||
            entry.value is! int ||
            (entry.value as int) <= 0,
      )) {
    throw FormatException(
      'Invalid API contract: $field must contain positive integer counts.',
    );
  }
  return {
    for (final entry in value.entries) entry.key as String: entry.value as int,
  };
}

void _requireExactKeys(
  Map<String, dynamic> json, {
  required Set<String> required,
  required String field,
}) {
  if (required.difference(json.keys.toSet()).isNotEmpty ||
      json.keys.toSet().difference(required).isNotEmpty) {
    throw FormatException(
      'Invalid API contract: $field has an unexpected shape.',
    );
  }
}

bool _close(double left, double right) =>
    (left - right).abs() <= _numericTolerance;

bool _listEquals(List<String> left, List<String> right) {
  if (left.length != right.length) return false;
  for (var index = 0; index < left.length; index += 1) {
    if (left[index] != right[index]) return false;
  }
  return true;
}

class _ProviderTransferPolicy {
  final String networkTier;
  final String billingScope;
  final String billingUnit;
  final int bytesPerBillingUnit;

  const _ProviderTransferPolicy({
    required this.networkTier,
    required this.billingScope,
    required this.billingUnit,
    required this.bytesPerBillingUnit,
  });
}
