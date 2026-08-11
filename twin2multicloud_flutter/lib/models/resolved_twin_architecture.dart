import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:equatable/equatable.dart';

import 'architecture_profile.dart';
import 'cloud_connection.dart';
import 'json_contract.dart';

enum ArchitectureCompatibilityStatus {
  ready('ready'),
  legacyNotResolvable('legacy_not_resolvable');

  final String apiValue;

  const ArchitectureCompatibilityStatus(this.apiValue);

  static ArchitectureCompatibilityStatus parse(Object? value) =>
      values.firstWhere(
        (candidate) => candidate.apiValue == value,
        orElse: () => throw const FormatException(
          'Invalid API contract: architecture compatibility is unsupported.',
        ),
      );
}

enum ResolvedArchitectureOrigin {
  nativeV1('native_v1'),
  reconstructedV1('reconstructed_v1'),
  nativeV2('native_v2');

  final String apiValue;

  const ResolvedArchitectureOrigin(this.apiValue);

  static ResolvedArchitectureOrigin parse(Object? value) => values.firstWhere(
    (candidate) => candidate.apiValue == value,
    orElse: () => throw const FormatException(
      'Invalid API contract: architecture origin is unsupported.',
    ),
  );
}

class ResolvedMoney extends Equatable {
  final String currency;
  final String monthlyAmount;

  const ResolvedMoney({required this.currency, required this.monthlyAmount});

  factory ResolvedMoney.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'currency',
      'monthly_amount',
    }, 'architecture cost contribution');
    return ResolvedMoney(
      currency: _currency(json, 'currency'),
      monthlyAmount: _decimal(json, 'monthly_amount'),
    );
  }

  @override
  List<Object?> get props => [currency, monthlyAmount];
}

class ResolvedProviderProfileReference extends Equatable {
  final String id;
  final String version;
  final String digest;
  final CloudProvider? provider;

  const ResolvedProviderProfileReference({
    required this.id,
    required this.version,
    required this.digest,
    this.provider,
  });

  factory ResolvedProviderProfileReference.fromJson(
    Map<String, dynamic> json, {
    required bool includesProvider,
  }) {
    _expectExactKeys(
      json,
      includesProvider
          ? const {'id', 'version', 'digest', 'provider'}
          : const {'id', 'version', 'digest'},
      'provider profile reference',
    );
    return ResolvedProviderProfileReference(
      id: JsonContract.requiredString(json, 'id'),
      version: _positiveVersion(json, 'version'),
      digest: _digest(json, 'digest'),
      provider: includesProvider ? _provider(json['provider']) : null,
    );
  }

  @override
  List<Object?> get props => [id, version, digest, provider];
}

class ResolvedComponentAssignment extends Equatable {
  final String assignmentId;
  final String logicalComponentId;
  final String responsibilityId;
  final CloudProvider provider;
  final ResolvedProviderProfileReference providerProfileRef;
  final String deploymentComponentId;
  final String deploymentComponentVersion;
  final String serviceId;
  final String region;
  final bool required;
  final List<String> deploymentSpecificationComponentIds;
  final List<String> capabilityEvidence;
  final List<String> pricingModelRefs;
  final List<String> formulaRefs;
  final ResolvedMoney costContribution;

  const ResolvedComponentAssignment({
    required this.assignmentId,
    required this.logicalComponentId,
    required this.responsibilityId,
    required this.provider,
    required this.providerProfileRef,
    required this.deploymentComponentId,
    required this.deploymentComponentVersion,
    required this.serviceId,
    required this.region,
    required this.required,
    required this.deploymentSpecificationComponentIds,
    required this.capabilityEvidence,
    required this.pricingModelRefs,
    required this.formulaRefs,
    required this.costContribution,
  });

  factory ResolvedComponentAssignment.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'assignment_id',
      'logical_component_id',
      'responsibility_id',
      'provider',
      'provider_implementation_profile_ref',
      'deployment_component_id',
      'deployment_component_version',
      'service_id',
      'region',
      'required',
      'deployment_specification_component_ids',
      'capability_evidence',
      'pricing_model_refs',
      'formula_refs',
      'cost_contribution',
    }, 'resolved component assignment');
    final provider = _provider(json['provider']);
    final providerRef = ResolvedProviderProfileReference.fromJson(
      JsonContract.requiredObject(json, 'provider_implementation_profile_ref'),
      includesProvider: false,
    );
    return ResolvedComponentAssignment(
      assignmentId: JsonContract.requiredString(json, 'assignment_id'),
      logicalComponentId: JsonContract.requiredString(
        json,
        'logical_component_id',
      ),
      responsibilityId: JsonContract.requiredString(json, 'responsibility_id'),
      provider: provider,
      providerProfileRef: providerRef,
      deploymentComponentId: JsonContract.requiredString(
        json,
        'deployment_component_id',
      ),
      deploymentComponentVersion: _positiveVersion(
        json,
        'deployment_component_version',
      ),
      serviceId: JsonContract.requiredString(json, 'service_id'),
      region: JsonContract.requiredString(json, 'region'),
      required: JsonContract.requiredBool(json, 'required'),
      deploymentSpecificationComponentIds: _requiredStringList(
        json,
        'deployment_specification_component_ids',
      ),
      capabilityEvidence: _requiredStringList(json, 'capability_evidence'),
      pricingModelRefs: _requiredStringList(json, 'pricing_model_refs'),
      formulaRefs: _requiredStringList(json, 'formula_refs'),
      costContribution: ResolvedMoney.fromJson(
        JsonContract.requiredObject(json, 'cost_contribution'),
      ),
    );
  }

  @override
  List<Object?> get props => [
    assignmentId,
    logicalComponentId,
    responsibilityId,
    provider,
    providerProfileRef,
    deploymentComponentId,
    deploymentComponentVersion,
    serviceId,
    region,
    required,
    deploymentSpecificationComponentIds,
    capabilityEvidence,
    pricingModelRefs,
    formulaRefs,
    costContribution,
  ];
}

class ResolvedArchitectureEdge extends Equatable {
  final String resolvedEdgeId;
  final String edgeId;
  final String sourceAssignmentId;
  final String sourcePortId;
  final String destinationAssignmentId;
  final String destinationPortId;
  final String edgeImplementationId;
  final String mechanism;
  final String transferRouteClass;
  final List<String> deploymentOutputBindingIds;
  final List<String> deploymentInputBindingIds;
  final List<String> transferEvidenceRefs;
  final List<String> formulaRefs;
  final ResolvedMoney costContribution;
  final String deliveryMode;
  final String ordering;

  const ResolvedArchitectureEdge({
    required this.resolvedEdgeId,
    required this.edgeId,
    required this.sourceAssignmentId,
    required this.sourcePortId,
    required this.destinationAssignmentId,
    required this.destinationPortId,
    required this.edgeImplementationId,
    required this.mechanism,
    required this.transferRouteClass,
    required this.deploymentOutputBindingIds,
    required this.deploymentInputBindingIds,
    required this.transferEvidenceRefs,
    required this.formulaRefs,
    required this.costContribution,
    required this.deliveryMode,
    required this.ordering,
  });

  factory ResolvedArchitectureEdge.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'resolved_edge_id',
      'edge_id',
      'source_assignment_id',
      'source_port_id',
      'destination_assignment_id',
      'destination_port_id',
      'edge_implementation_id',
      'mechanism',
      'transfer_route_class',
      'deployment_output_binding_ids',
      'deployment_input_binding_ids',
      'delivery_semantics',
      'trust_contract_ref',
      'observability_contract_ref',
      'transfer_evidence_refs',
      'formula_refs',
      'cost_contribution',
    }, 'resolved architecture edge');
    final delivery = JsonContract.requiredObject(json, 'delivery_semantics');
    _expectExactKeys(delivery, const {
      'dead_letter_policy',
      'idempotency',
      'mode',
      'ordering',
      'replay',
      'retry_policy',
      'timeout_policy',
    }, 'resolved edge delivery semantics');
    _readVersionedReference(
      JsonContract.requiredObject(json, 'trust_contract_ref'),
      'resolved edge trust contract',
    );
    _readVersionedReference(
      JsonContract.requiredObject(json, 'observability_contract_ref'),
      'resolved edge observability contract',
    );
    for (final field in const [
      'dead_letter_policy',
      'idempotency',
      'mode',
      'ordering',
      'replay',
      'retry_policy',
      'timeout_policy',
    ]) {
      JsonContract.requiredString(delivery, field);
    }
    return ResolvedArchitectureEdge(
      resolvedEdgeId: JsonContract.requiredString(json, 'resolved_edge_id'),
      edgeId: JsonContract.requiredString(json, 'edge_id'),
      sourceAssignmentId: JsonContract.requiredString(
        json,
        'source_assignment_id',
      ),
      sourcePortId: JsonContract.requiredString(json, 'source_port_id'),
      destinationAssignmentId: JsonContract.requiredString(
        json,
        'destination_assignment_id',
      ),
      destinationPortId: JsonContract.requiredString(
        json,
        'destination_port_id',
      ),
      edgeImplementationId: JsonContract.requiredString(
        json,
        'edge_implementation_id',
      ),
      mechanism: JsonContract.requiredString(json, 'mechanism'),
      transferRouteClass: JsonContract.requiredString(
        json,
        'transfer_route_class',
      ),
      deploymentOutputBindingIds: _requiredStringList(
        json,
        'deployment_output_binding_ids',
      ),
      deploymentInputBindingIds: _requiredStringList(
        json,
        'deployment_input_binding_ids',
      ),
      transferEvidenceRefs: _requiredStringList(json, 'transfer_evidence_refs'),
      formulaRefs: _requiredStringList(json, 'formula_refs'),
      costContribution: ResolvedMoney.fromJson(
        JsonContract.requiredObject(json, 'cost_contribution'),
      ),
      deliveryMode: JsonContract.requiredString(delivery, 'mode'),
      ordering: JsonContract.requiredString(delivery, 'ordering'),
    );
  }

  bool get isCrossCloud => transferRouteClass.startsWith('cross_provider');

  @override
  List<Object?> get props => [
    resolvedEdgeId,
    edgeId,
    sourceAssignmentId,
    sourcePortId,
    destinationAssignmentId,
    destinationPortId,
    edgeImplementationId,
    mechanism,
    transferRouteClass,
    deploymentOutputBindingIds,
    deploymentInputBindingIds,
    transferEvidenceRefs,
    formulaRefs,
    costContribution,
    deliveryMode,
    ordering,
  ];
}

class ResolvedExtensionBinding extends Equatable {
  final String slotId;
  final String slotVersion;
  final String logicalComponentId;
  final String artifactId;
  final String artifactDigest;
  final String configurationDigest;
  final String validationContractVersion;

  const ResolvedExtensionBinding({
    required this.slotId,
    required this.slotVersion,
    required this.logicalComponentId,
    required this.artifactId,
    required this.artifactDigest,
    required this.configurationDigest,
    required this.validationContractVersion,
  });

  factory ResolvedExtensionBinding.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'slot_id',
      'slot_version',
      'logical_component_id',
      'artifact_id',
      'artifact_digest',
      'configuration_digest',
      'validation_contract_version',
    }, 'resolved extension binding');
    return ResolvedExtensionBinding(
      slotId: JsonContract.requiredString(json, 'slot_id'),
      slotVersion: _positiveVersion(json, 'slot_version'),
      logicalComponentId: JsonContract.requiredString(
        json,
        'logical_component_id',
      ),
      artifactId: JsonContract.requiredString(json, 'artifact_id'),
      artifactDigest: _digest(json, 'artifact_digest'),
      configurationDigest: _digest(json, 'configuration_digest'),
      validationContractVersion: _positiveVersion(
        json,
        'validation_contract_version',
      ),
    );
  }

  @override
  List<Object?> get props => [
    slotId,
    slotVersion,
    logicalComponentId,
    artifactId,
    artifactDigest,
    configurationDigest,
    validationContractVersion,
  ];
}

class ResolvedCostItem extends Equatable {
  final String itemId;
  final String monthlyAmount;

  const ResolvedCostItem({required this.itemId, required this.monthlyAmount});

  factory ResolvedCostItem.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'item_id',
      'monthly_amount',
    }, 'resolved cost item');
    return ResolvedCostItem(
      itemId: JsonContract.requiredString(json, 'item_id'),
      monthlyAmount: _decimal(json, 'monthly_amount'),
    );
  }

  @override
  List<Object?> get props => [itemId, monthlyAmount];
}

class ResolvedArchitectureCostSummary extends Equatable {
  final String currency;
  final String monthlyTotal;
  final List<ResolvedCostItem> responsibilityTotals;
  final List<ResolvedCostItem> componentTotals;
  final List<ResolvedCostItem> edgeTotals;

  const ResolvedArchitectureCostSummary({
    required this.currency,
    required this.monthlyTotal,
    required this.responsibilityTotals,
    required this.componentTotals,
    required this.edgeTotals,
  });

  factory ResolvedArchitectureCostSummary.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'currency',
      'monthly_total',
      'responsibility_totals',
      'component_totals',
      'edge_totals',
    }, 'resolved architecture cost summary');
    return ResolvedArchitectureCostSummary(
      currency: _currency(json, 'currency'),
      monthlyTotal: _decimal(json, 'monthly_total'),
      responsibilityTotals: _costItems(json, 'responsibility_totals'),
      componentTotals: _costItems(json, 'component_totals'),
      edgeTotals: _costItems(json, 'edge_totals'),
    );
  }

  @override
  List<Object?> get props => [
    currency,
    monthlyTotal,
    responsibilityTotals,
    componentTotals,
    edgeTotals,
  ];
}

class ResolvedFunctionalCompleteness extends Equatable {
  final String status;
  final String validatorVersion;
  final String validationDigest;
  final List<String> requiredCapabilityIds;
  final List<String> providedCapabilityIds;
  final List<String> missingCapabilityIds;
  final List<String> providerExtraCapabilityIds;

  const ResolvedFunctionalCompleteness({
    required this.status,
    required this.validatorVersion,
    required this.validationDigest,
    required this.requiredCapabilityIds,
    required this.providedCapabilityIds,
    required this.missingCapabilityIds,
    required this.providerExtraCapabilityIds,
  });

  factory ResolvedFunctionalCompleteness.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'status',
      'validator_version',
      'validation_digest',
      'required_capability_ids',
      'provided_capability_ids',
      'missing_capability_ids',
      'provider_extra_capability_ids',
    }, 'functional completeness');
    final status = JsonContract.requiredString(json, 'status');
    if (status != 'complete') {
      throw const FormatException(
        'Invalid API contract: resolved architecture must be complete.',
      );
    }
    final missing = _requiredStringList(json, 'missing_capability_ids');
    if (missing.isNotEmpty) {
      throw const FormatException(
        'Invalid API contract: complete architecture has missing capabilities.',
      );
    }
    return ResolvedFunctionalCompleteness(
      status: status,
      validatorVersion: _positiveVersion(json, 'validator_version'),
      validationDigest: _digest(json, 'validation_digest'),
      requiredCapabilityIds: _requiredStringList(
        json,
        'required_capability_ids',
      ),
      providedCapabilityIds: _requiredStringList(
        json,
        'provided_capability_ids',
      ),
      missingCapabilityIds: missing,
      providerExtraCapabilityIds: _requiredStringList(
        json,
        'provider_extra_capability_ids',
      ),
    );
  }

  @override
  List<Object?> get props => [
    status,
    validatorVersion,
    validationDigest,
    requiredCapabilityIds,
    providedCapabilityIds,
    missingCapabilityIds,
    providerExtraCapabilityIds,
  ];
}

class ResolvedTwinArchitecture extends Equatable {
  static const v1SchemaVersion = 'resolved-twin-architecture.v1';
  static const v2SchemaVersion = 'resolved-twin-architecture.v2';

  final String schemaVersion;
  final String? resolutionStatus;
  final String resolutionId;
  final String calculationRunId;
  final PinnedArchitectureReference profileRef;
  final String optimizationStrategyId;
  final List<ResolvedProviderProfileReference> providerProfileRefs;
  final PinnedArchitectureReference workloadContractRef;
  final List<String> pricingEvidenceDigests;
  final List<ResolvedComponentAssignment> componentAssignments;
  final List<ResolvedArchitectureEdge> resolvedEdges;
  final List<ResolvedExtensionBinding> extensionBindings;
  final String deploymentSpecificationDigest;
  final ResolvedArchitectureCostSummary costSummary;
  final ResolvedFunctionalCompleteness functionalCompleteness;
  final String contentDigest;

  const ResolvedTwinArchitecture({
    required this.schemaVersion,
    required this.resolutionStatus,
    required this.resolutionId,
    required this.calculationRunId,
    required this.profileRef,
    required this.optimizationStrategyId,
    required this.providerProfileRefs,
    required this.workloadContractRef,
    required this.pricingEvidenceDigests,
    required this.componentAssignments,
    required this.resolvedEdges,
    required this.extensionBindings,
    required this.deploymentSpecificationDigest,
    required this.costSummary,
    required this.functionalCompleteness,
    required this.contentDigest,
  });

  /// Recomputes the canonical content digest for a known architecture shape.
  ///
  /// This is also used by contract fixtures that intentionally replace pinned
  /// identities while preserving the production parser's digest guarantees.
  static String calculateDigest(Map<String, dynamic> architecture) {
    final schemaVersion = JsonContract.requiredString(
      architecture,
      'schema_version',
    );
    if (schemaVersion != v1SchemaVersion && schemaVersion != v2SchemaVersion) {
      throw const FormatException(
        'Unsupported resolved Twin architecture schema version.',
      );
    }
    return _calculateArchitectureDigest(
      architecture,
      isV2: schemaVersion == v2SchemaVersion,
    );
  }

  factory ResolvedTwinArchitecture.fromJson(Map<String, dynamic> json) {
    final schemaVersion = JsonContract.requiredString(json, 'schema_version');
    final isV2 = schemaVersion == v2SchemaVersion;
    if (!isV2 && schemaVersion != v1SchemaVersion) {
      throw const FormatException(
        'Unsupported resolved Twin architecture schema version.',
      );
    }
    final expectedKeys = <String>{
      'schema_version',
      'resolution_id',
      'calculation_run_id',
      'architecture_profile_ref',
      'optimization_bundle_ref',
      'provider_profile_refs',
      'workload_contract_ref',
      'pricing_evidence_refs',
      'component_assignments',
      'resolved_edges',
      'extension_bindings',
      'deployment_specification_ref',
      'cost_summary',
      'functional_completeness',
      'content_digest',
      if (isV2) 'resolution_status',
    };
    _expectExactKeys(json, expectedKeys, 'resolved twin architecture');
    final resolutionStatus = isV2
        ? JsonContract.requiredString(json, 'resolution_status')
        : null;
    if (isV2 &&
        resolutionStatus != 'offline_contract_fixture' &&
        resolutionStatus != 'publishable') {
      throw const FormatException(
        'Invalid API contract: v2 resolution status is unsupported.',
      );
    }
    final assignments = _objectList(
      json,
      'component_assignments',
      minLength: 1,
    ).map(ResolvedComponentAssignment.fromJson).toList(growable: false);
    final edges = _objectList(
      json,
      'resolved_edges',
    ).map(ResolvedArchitectureEdge.fromJson).toList(growable: false);
    final extensions = _objectList(
      json,
      'extension_bindings',
    ).map(ResolvedExtensionBinding.fromJson).toList(growable: false);
    _requireUnique(
      assignments.map((item) => item.assignmentId),
      'assignment IDs',
    );
    _requireUnique(
      edges.map((item) => item.resolvedEdgeId),
      'resolved edge IDs',
    );
    final assignmentIds = assignments.map((item) => item.assignmentId).toSet();
    if (edges.any(
      (item) =>
          !assignmentIds.contains(item.sourceAssignmentId) ||
          !assignmentIds.contains(item.destinationAssignmentId),
    )) {
      throw const FormatException(
        'Invalid API contract: resolved edge assignment is unresolved.',
      );
    }
    final logicalComponentIds = assignments
        .map((item) => item.logicalComponentId)
        .toSet();
    if (extensions.any(
      (item) => !logicalComponentIds.contains(item.logicalComponentId),
    )) {
      throw const FormatException(
        'Invalid API contract: extension component is unresolved.',
      );
    }
    final optimization = JsonContract.requiredObject(
      json,
      'optimization_bundle_ref',
    );
    _expectExactKeys(optimization, const {
      'optimization_strategy_id',
      'optimization_strategy_version',
      'calculation_strategy_id',
      'calculation_strategy_version',
      'scoring_strategy_id',
      'scoring_strategy_version',
      'formula_set_id',
      'formula_set_version',
      'compatibility_digest',
    }, 'optimization bundle reference');
    for (final field in const [
      'optimization_strategy_version',
      'calculation_strategy_version',
      'scoring_strategy_version',
      'formula_set_version',
    ]) {
      _positiveVersion(optimization, field);
    }
    for (final field in const [
      'calculation_strategy_id',
      'scoring_strategy_id',
      'formula_set_id',
    ]) {
      JsonContract.requiredString(optimization, field);
    }
    _digest(optimization, 'compatibility_digest');
    final providerRefs = _objectList(json, 'provider_profile_refs')
        .map(
          (item) => ResolvedProviderProfileReference.fromJson(
            item,
            includesProvider: true,
          ),
        )
        .toList(growable: false);
    _requireUnique(
      providerRefs.map((item) => item.provider!.apiValue),
      'provider profile providers',
    );
    final providerRefByProvider = {
      for (final item in providerRefs) item.provider!: item,
    };
    if (assignments.any((item) {
      final registered = providerRefByProvider[item.provider];
      return registered == null ||
          registered.id != item.providerProfileRef.id ||
          registered.version != item.providerProfileRef.version ||
          registered.digest != item.providerProfileRef.digest;
    })) {
      throw const FormatException(
        'Invalid API contract: assignment provider profile is unresolved.',
      );
    }
    final pricingDigests = _objectList(json, 'pricing_evidence_refs')
        .map((item) {
          _expectExactKeys(item, const {
            'id',
            'version',
            'digest',
            'provider',
            'currency',
          }, 'pricing evidence reference');
          JsonContract.requiredString(item, 'id');
          _positiveVersion(item, 'version');
          _provider(item['provider']);
          _currency(item, 'currency');
          return _digest(item, 'digest');
        })
        .toList(growable: false);
    _requireUnique(pricingDigests, 'pricing evidence digests');
    final deployment = JsonContract.requiredObject(
      json,
      'deployment_specification_ref',
    );
    _expectExactKeys(deployment, const {
      'schema_version',
      'calculation_run_id',
      'digest',
    }, 'deployment specification reference');
    final expectedDeploymentSchema = isV2
        ? 'resolved-deployment-specification.v2'
        : 'resolved-deployment-specification.v1';
    if (deployment['schema_version'] != expectedDeploymentSchema) {
      throw const FormatException(
        'Invalid API contract: deployment specification version is unsupported.',
      );
    }
    final calculationRunId = JsonContract.requiredString(
      json,
      'calculation_run_id',
    );
    if (JsonContract.requiredString(deployment, 'calculation_run_id') !=
        calculationRunId) {
      throw const FormatException(
        'Invalid API contract: deployment calculation run differs.',
      );
    }
    final costSummary = ResolvedArchitectureCostSummary.fromJson(
      JsonContract.requiredObject(json, 'cost_summary'),
    );
    if (assignments.any(
          (item) => item.costContribution.currency != costSummary.currency,
        ) ||
        edges.any(
          (item) => item.costContribution.currency != costSummary.currency,
        )) {
      throw const FormatException(
        'Invalid API contract: architecture cost currencies differ.',
      );
    }
    final profileRef = PinnedArchitectureReference.fromJson(
      JsonContract.requiredObject(json, 'architecture_profile_ref'),
    );
    final contentDigest = _digest(json, 'content_digest');
    if (contentDigest != calculateDigest(json)) {
      throw const FormatException(
        'Invalid API contract: resolved architecture content digest mismatch.',
      );
    }
    return ResolvedTwinArchitecture(
      schemaVersion: schemaVersion,
      resolutionStatus: resolutionStatus,
      resolutionId: JsonContract.requiredString(json, 'resolution_id'),
      calculationRunId: calculationRunId,
      profileRef: profileRef,
      optimizationStrategyId: JsonContract.requiredString(
        optimization,
        'optimization_strategy_id',
      ),
      providerProfileRefs: List.unmodifiable(providerRefs),
      workloadContractRef: PinnedArchitectureReference.fromJson(
        JsonContract.requiredObject(json, 'workload_contract_ref'),
      ),
      pricingEvidenceDigests: List.unmodifiable(pricingDigests),
      componentAssignments: List.unmodifiable(assignments),
      resolvedEdges: List.unmodifiable(edges),
      extensionBindings: List.unmodifiable(extensions),
      deploymentSpecificationDigest: _digest(deployment, 'digest'),
      costSummary: costSummary,
      functionalCompleteness: ResolvedFunctionalCompleteness.fromJson(
        JsonContract.requiredObject(json, 'functional_completeness'),
      ),
      contentDigest: contentDigest,
    );
  }

  Set<CloudProvider> get providers =>
      Set.unmodifiable(componentAssignments.map((item) => item.provider));

  @override
  List<Object?> get props => [
    schemaVersion,
    resolutionStatus,
    resolutionId,
    calculationRunId,
    profileRef,
    optimizationStrategyId,
    providerProfileRefs,
    workloadContractRef,
    pricingEvidenceDigests,
    componentAssignments,
    resolvedEdges,
    extensionBindings,
    deploymentSpecificationDigest,
    costSummary,
    functionalCompleteness,
    contentDigest,
  ];
}

class ResolvedTwinArchitectureRead extends Equatable {
  final String twinId;
  final String calculationRunId;
  final DateTime? selectedForDeploymentAt;
  final ArchitectureCompatibilityStatus compatibilityStatus;
  final ResolvedArchitectureOrigin origin;
  final ResolvedTwinArchitecture architecture;

  const ResolvedTwinArchitectureRead({
    required this.twinId,
    required this.calculationRunId,
    required this.selectedForDeploymentAt,
    required this.compatibilityStatus,
    required this.origin,
    required this.architecture,
  });

  factory ResolvedTwinArchitectureRead.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'twin_id',
      'calculation_run_id',
      'selected_for_deployment_at',
      'architecture_compatibility_status',
      'origin',
      'architecture',
    }, 'resolved architecture read');
    final compatibility = ArchitectureCompatibilityStatus.parse(
      json['architecture_compatibility_status'],
    );
    if (compatibility != ArchitectureCompatibilityStatus.ready) {
      throw const FormatException(
        'Invalid API contract: unreadable legacy architecture returned data.',
      );
    }
    final architecture = ResolvedTwinArchitecture.fromJson(
      JsonContract.requiredObject(json, 'architecture'),
    );
    final calculationRunId = JsonContract.requiredString(
      json,
      'calculation_run_id',
    );
    if (architecture.calculationRunId != calculationRunId) {
      throw const FormatException(
        'Invalid API contract: resolved architecture run identity differs.',
      );
    }
    final origin = ResolvedArchitectureOrigin.parse(json['origin']);
    if ((architecture.schemaVersion ==
                ResolvedTwinArchitecture.v2SchemaVersion &&
            origin != ResolvedArchitectureOrigin.nativeV2) ||
        (architecture.schemaVersion ==
                ResolvedTwinArchitecture.v1SchemaVersion &&
            origin == ResolvedArchitectureOrigin.nativeV2)) {
      throw const FormatException(
        'Invalid API contract: architecture origin and schema differ.',
      );
    }
    return ResolvedTwinArchitectureRead(
      twinId: JsonContract.requiredString(json, 'twin_id'),
      calculationRunId: calculationRunId,
      selectedForDeploymentAt: JsonContract.optionalDate(
        json,
        'selected_for_deployment_at',
      ),
      compatibilityStatus: compatibility,
      origin: origin,
      architecture: architecture,
    );
  }

  @override
  List<Object?> get props => [
    twinId,
    calculationRunId,
    selectedForDeploymentAt,
    compatibilityStatus,
    origin,
    architecture,
  ];
}

List<ResolvedCostItem> _costItems(Map<String, dynamic> json, String field) {
  final items = _objectList(
    json,
    field,
  ).map(ResolvedCostItem.fromJson).toList(growable: false);
  _requireUnique(items.map((item) => item.itemId), '$field item IDs');
  return List.unmodifiable(items);
}

void _readVersionedReference(Map<String, dynamic> json, String contract) {
  _expectExactKeys(json, const {'id', 'version'}, contract);
  JsonContract.requiredString(json, 'id');
  _positiveVersion(json, 'version');
}

void _expectExactKeys(
  Map<String, dynamic> json,
  Set<String> expected,
  String contract,
) {
  if (json.keys.toSet().difference(expected).isNotEmpty ||
      expected.difference(json.keys.toSet()).isNotEmpty) {
    throw FormatException(
      'Invalid API contract: $contract fields are incomplete or unsupported.',
    );
  }
}

List<Map<String, dynamic>> _objectList(
  Map<String, dynamic> json,
  String field, {
  int minLength = 0,
  int maxLength = 512,
}) {
  final value = json[field];
  if (value is! List || value.length < minLength || value.length > maxLength) {
    throw FormatException('Invalid API contract: $field must be an array.');
  }
  return List.unmodifiable(
    value.indexed.map(
      (entry) => JsonContract.immutableObject(entry.$2, '$field[${entry.$1}]'),
    ),
  );
}

List<String> _requiredStringList(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! List ||
      value.length > 512 ||
      value.any((item) => item is! String || item.isEmpty)) {
    throw FormatException(
      'Invalid API contract: $field must be a string array.',
    );
  }
  final result = List<String>.unmodifiable(value.cast<String>());
  _requireUnique(result, field);
  return result;
}

void _requireUnique(Iterable<String> values, String field) {
  final list = values.toList(growable: false);
  if (list.toSet().length != list.length) {
    throw FormatException('Invalid API contract: $field must be unique.');
  }
}

String _positiveVersion(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  if (!RegExp(r'^[1-9][0-9]*$').hasMatch(value)) {
    throw FormatException(
      'Invalid API contract: $field must be a positive version.',
    );
  }
  return value;
}

String _digest(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  if (!RegExp(r'^sha256:[0-9a-f]{64}$').hasMatch(value)) {
    throw FormatException('Invalid API contract: $field must be a digest.');
  }
  return value;
}

String _currency(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  if (!RegExp(r'^[A-Z]{3}$').hasMatch(value)) {
    throw FormatException('Invalid API contract: $field must be a currency.');
  }
  return value;
}

String _decimal(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  final parsed = double.tryParse(value);
  if (!RegExp(r'^(0|[1-9][0-9]*)(\.[0-9]+)?$').hasMatch(value) ||
      parsed == null ||
      !parsed.isFinite ||
      parsed < 0) {
    throw FormatException(
      'Invalid API contract: $field must be a non-negative decimal string.',
    );
  }
  return value;
}

const _v2SetArrayFields = {
  'capability_evidence',
  'component_assignments',
  'deployment_specification_component_ids',
  'extension_bindings',
  'formula_refs',
  'missing_capability_ids',
  'pricing_evidence_refs',
  'pricing_model_refs',
  'provided_capability_ids',
  'provider_extra_capability_ids',
  'provider_profile_refs',
  'required_capability_ids',
  'resolved_edges',
};

const _v2ArrayIdentityFields = <String, List<String>>{
  'component_assignments': ['assignment_id', 'logical_component_id'],
  'resolved_edges': ['resolved_edge_id', 'edge_id'],
  'extension_bindings': ['slot_id'],
  'provider_profile_refs': ['id'],
  'pricing_evidence_refs': ['id'],
};

String _calculateArchitectureDigest(
  Map<String, dynamic> architecture, {
  required bool isV2,
}) {
  final payload = _stripArchitectureDigestFields(architecture);
  final encoded = _architectureCanonicalJson(payload, setSemantics: isV2);
  return 'sha256:${sha256.convert(utf8.encode(encoded))}';
}

Object? _stripArchitectureDigestFields(Object? value) {
  if (value is Map) {
    return {
      for (final entry in value.entries)
        if (entry.key != 'content_digest' &&
            entry.key != 'created_at' &&
            entry.key != 'updated_at' &&
            entry.key != 'selected_at' &&
            entry.key != 'validated_at')
          entry.key.toString(): _stripArchitectureDigestFields(entry.value),
    };
  }
  if (value is List) {
    return value.map(_stripArchitectureDigestFields).toList(growable: false);
  }
  return value;
}

String _architectureCanonicalJson(
  Object? value, {
  required bool setSemantics,
  String? fieldName,
}) {
  if (value == null || value is bool || value is num) return jsonEncode(value);
  if (value is String) {
    final normalized = setSemantics ? _normalizeDecimalString(value) : value;
    return _asciiJsonString(normalized);
  }
  if (value is List) {
    final entries = value
        .map(
          (item) => _architectureCanonicalJson(
            item,
            setSemantics: setSemantics,
            fieldName: fieldName,
          ),
        )
        .toList(growable: false);
    if (setSemantics && _v2SetArrayFields.contains(fieldName)) {
      final indexed =
          value.indexed
              .map(
                (entry) => (
                  key: _stableArchitectureItemKey(entry.$2, fieldName),
                  encoded: entries[entry.$1],
                ),
              )
              .toList(growable: false)
            ..sort((left, right) => left.key.compareTo(right.key));
      return '[${indexed.map((item) => item.encoded).join(',')}]';
    }
    return '[${entries.join(',')}]';
  }
  if (value is Map) {
    final entries =
        value.entries
            .map((entry) => MapEntry(entry.key.toString(), entry.value))
            .toList(growable: false)
          ..sort((left, right) => left.key.compareTo(right.key));
    return '{${entries.map((entry) => '${_asciiJsonString(entry.key)}:${_architectureCanonicalJson(entry.value, setSemantics: setSemantics, fieldName: entry.key)}').join(',')}}';
  }
  throw const FormatException(
    'Invalid API contract: architecture is not canonical JSON.',
  );
}

String _stableArchitectureItemKey(Object? value, String? fieldName) {
  if (value is String) return value;
  if (value is Map) {
    for (final field in _v2ArrayIdentityFields[fieldName] ?? const <String>[]) {
      final candidate = value[field];
      if (candidate is String) return candidate;
    }
    for (final field in const [
      'responsibility_id',
      'component_id',
      'edge_id',
      'deployment_component_id',
      'edge_implementation_id',
      'artifact_id',
      'assignment_id',
      'resolved_edge_id',
      'port_id',
      'bundle_id',
      'provider',
      'reference_id',
      'schema_version',
    ]) {
      final candidate = value[field];
      if (candidate is String) return candidate;
    }
  }
  return _architectureCanonicalJson(value, setSemantics: true);
}

String _normalizeDecimalString(String value) {
  final match = RegExp(r'^-?(0|[1-9][0-9]*)(\.[0-9]+)?$').firstMatch(value);
  if (match == null) return value;
  final negative = value.startsWith('-');
  final unsigned = negative ? value.substring(1) : value;
  final parts = unsigned.split('.');
  final fraction = parts.length == 2
      ? parts[1].replaceFirst(RegExp(r'0+$'), '')
      : '';
  final normalized = fraction.isEmpty ? parts[0] : '${parts[0]}.$fraction';
  if (normalized == '0') return '0';
  return negative ? '-$normalized' : normalized;
}

String _asciiJsonString(String value) {
  final encoded = jsonEncode(value);
  final buffer = StringBuffer();
  for (final rune in encoded.runes) {
    if (rune <= 0x7f) {
      buffer.writeCharCode(rune);
    } else if (rune <= 0xffff) {
      buffer.write('\\u${rune.toRadixString(16).padLeft(4, '0')}');
    } else {
      final adjusted = rune - 0x10000;
      final high = 0xd800 + (adjusted >> 10);
      final low = 0xdc00 + (adjusted & 0x3ff);
      buffer
        ..write('\\u${high.toRadixString(16)}')
        ..write('\\u${low.toRadixString(16)}');
    }
  }
  return buffer.toString();
}

CloudProvider _provider(Object? value) => CloudProvider.values.firstWhere(
  (candidate) => candidate.apiValue == value,
  orElse: () => throw const FormatException(
    'Invalid API contract: architecture provider is unsupported.',
  ),
);
