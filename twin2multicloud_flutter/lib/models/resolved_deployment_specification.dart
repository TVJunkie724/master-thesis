import 'dart:collection';
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:equatable/equatable.dart';

import 'cloud_connection.dart';
import 'json_contract.dart';

enum DeploymentCompatibility {
  ready('ready'),
  legacyNotDeployable('legacy_not_deployable');

  final String apiValue;

  const DeploymentCompatibility(this.apiValue);

  static DeploymentCompatibility parse(Object? value) => values.firstWhere(
    (candidate) => candidate.apiValue == value,
    orElse: () => throw const FormatException(
      'Invalid API contract: deployment compatibility is unsupported.',
    ),
  );
}

enum DeploymentDimensionClassification {
  deployableSelection('deployable_selection', 'Deployable selection'),
  usageTier('usage_tier', 'Usage tier'),
  accountScope('account_scope', 'Account scope'),
  nonDeployableAssumption(
    'non_deployable_assumption',
    'Calculation assumption',
  );

  final String apiValue;
  final String label;

  const DeploymentDimensionClassification(this.apiValue, this.label);

  static DeploymentDimensionClassification parse(
    Object? value,
  ) => values.firstWhere(
    (candidate) => candidate.apiValue == value,
    orElse: () => throw const FormatException(
      'Invalid API contract: deployment dimension classification is unsupported.',
    ),
  );
}

enum ResolvedDeploymentSlot {
  l1Ingestion('l1_ingestion', 'L1', true, 0),
  l2Processing('l2_processing', 'L2', true, 1),
  l3HotStorage('l3_hot_storage', 'L3 hot', true, 2),
  l3CoolStorage('l3_cool_storage', 'L3 cool', true, 3),
  l3ArchiveStorage('l3_archive_storage', 'L3 archive', true, 4),
  l4TwinState('l4_twin_state', 'L4', true, 5),
  l5Visualization('l5_visualization', 'L5', true, 6),
  transitionRuntime('transition_runtime', 'Transition', false, 7),
  crossCloudGlue('cross_cloud_glue', 'Cross-cloud', false, 8);

  final String apiValue;
  final String label;
  final bool isArchitectureSlot;
  final int sortOrder;

  const ResolvedDeploymentSlot(
    this.apiValue,
    this.label,
    this.isArchitectureSlot,
    this.sortOrder,
  );

  static ResolvedDeploymentSlot parse(Object? value) => values.firstWhere(
    (candidate) => candidate.apiValue == value,
    orElse: () => throw const FormatException(
      'Invalid API contract: deployment component slot is unsupported.',
    ),
  );
}

sealed class ResolvedDeploymentSpecificationData extends Equatable {
  static const v1SchemaVersion = 'resolved-deployment-specification.v1';
  static const v2SchemaVersion = 'resolved-deployment-specification.v2';

  final String schemaVersion;
  final String calculationRunId;
  final String digest;

  const ResolvedDeploymentSpecificationData({
    required this.schemaVersion,
    required this.calculationRunId,
    required this.digest,
  });

  bool get isSupported;

  static String calculateDigest(Map<String, dynamic> specification) =>
      _calculateDigest(specification);

  factory ResolvedDeploymentSpecificationData.fromJson(
    Map<String, dynamic> json,
  ) {
    final schemaVersion = JsonContract.requiredString(json, 'schema_version');
    if (schemaVersion == v2SchemaVersion) {
      return ResolvedDeploymentSpecificationV2.fromJson(json);
    }
    if (schemaVersion != v1SchemaVersion) {
      return UnsupportedResolvedDeploymentSpecification(
        schemaVersion: schemaVersion,
        calculationRunId: JsonContract.requiredString(
          json,
          'calculation_run_id',
        ),
        digest: _digest(json, 'digest'),
      );
    }
    return ResolvedDeploymentSpecificationV1.fromJson(json);
  }

  @override
  List<Object?> get props => [schemaVersion, calculationRunId, digest];
}

final class UnsupportedResolvedDeploymentSpecification
    extends ResolvedDeploymentSpecificationData {
  const UnsupportedResolvedDeploymentSpecification({
    required super.schemaVersion,
    required super.calculationRunId,
    required super.digest,
  });

  @override
  bool get isSupported => false;
}

final class ResolvedDeploymentSpecificationV1
    extends ResolvedDeploymentSpecificationData {
  final ResolvedArchitectureProfile architectureProfile;
  final ResolvedOptimizationContext optimizationContext;
  final String currency;
  final List<ResolvedDeploymentComponent> components;

  const ResolvedDeploymentSpecificationV1({
    required super.calculationRunId,
    required super.digest,
    required this.architectureProfile,
    required this.optimizationContext,
    required this.currency,
    required this.components,
  }) : super(
         schemaVersion: ResolvedDeploymentSpecificationData.v1SchemaVersion,
       );

  factory ResolvedDeploymentSpecificationV1.fromJson(
    Map<String, dynamic> json,
  ) {
    _expectExactKeys(json, const {
      'schema_version',
      'calculation_run_id',
      'architecture_profile',
      'optimization_context',
      'currency',
      'components',
      'digest',
    }, 'resolved deployment specification');
    final schemaVersion = JsonContract.requiredString(json, 'schema_version');
    if (schemaVersion != ResolvedDeploymentSpecificationData.v1SchemaVersion) {
      throw const FormatException(
        'Invalid API contract: resolved deployment specification version is unsupported.',
      );
    }
    final calculationRunId = JsonContract.requiredString(
      json,
      'calculation_run_id',
    );
    final currency = JsonContract.requiredString(json, 'currency');
    if (currency != 'USD') {
      throw const FormatException(
        'Invalid API contract: resolved deployment currency must be USD.',
      );
    }
    final components =
        _objectList(
            json,
            'components',
            minLength: 7,
            maxLength: 64,
          ).map(ResolvedDeploymentComponent.fromJson).toList(growable: false)
          ..sort(_compareComponents);
    if (components.map((component) => component.componentId).toSet().length !=
        components.length) {
      throw const FormatException(
        'Invalid API contract: deployment component IDs must be unique.',
      );
    }
    for (final slot in ResolvedDeploymentSlot.values.where(
      (candidate) => candidate.isArchitectureSlot,
    )) {
      final providers = components
          .where((component) => component.slot == slot)
          .map((component) => component.provider)
          .toSet();
      if (providers.length != 1) {
        throw FormatException(
          'Invalid API contract: ${slot.apiValue} must resolve to one provider.',
        );
      }
    }
    final digest = _digest(json, 'digest');
    final expectedDigest = _calculateDigest(json);
    if (digest != expectedDigest) {
      throw const FormatException(
        'Invalid API contract: resolved deployment specification digest mismatch.',
      );
    }
    return ResolvedDeploymentSpecificationV1(
      calculationRunId: calculationRunId,
      digest: digest,
      architectureProfile: ResolvedArchitectureProfile.fromJson(
        JsonContract.requiredObject(json, 'architecture_profile'),
      ),
      optimizationContext: ResolvedOptimizationContext.fromJson(
        JsonContract.requiredObject(json, 'optimization_context'),
      ),
      currency: currency,
      components: List.unmodifiable(components),
    );
  }

  @override
  bool get isSupported => true;

  List<ResolvedDeploymentComponent> get architectureComponents =>
      List.unmodifiable(
        components.where((component) => component.slot.isArchitectureSlot),
      );

  List<ResolvedDeploymentComponent> get supportingComponents =>
      List.unmodifiable(
        components.where((component) => !component.slot.isArchitectureSlot),
      );

  Set<CloudProvider> get providers =>
      Set.unmodifiable(components.map((component) => component.provider));

  @override
  List<Object?> get props => [
    ...super.props,
    architectureProfile,
    optimizationContext,
    currency,
    components,
  ];
}

enum FiveLayerV2DimensionClassification {
  deployableSelection('deployable_selection'),
  capacity('capacity'),
  usage('usage'),
  fixedPoc('fixed_poc'),
  accountScope('account_scope');

  final String apiValue;

  const FiveLayerV2DimensionClassification(this.apiValue);

  static FiveLayerV2DimensionClassification parse(
    Object? value,
  ) => values.firstWhere(
    (candidate) => candidate.apiValue == value,
    orElse: () => throw const FormatException(
      'Invalid API contract: Five-layer v2 dimension classification is unsupported.',
    ),
  );
}

class FiveLayerV2PinnedReference extends Equatable {
  final String id;
  final String version;
  final String digest;

  const FiveLayerV2PinnedReference({
    required this.id,
    required this.version,
    required this.digest,
  });

  factory FiveLayerV2PinnedReference.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {'id', 'version', 'digest'}, 'v2 reference');
    return FiveLayerV2PinnedReference(
      id: JsonContract.requiredString(json, 'id'),
      version: _positiveVersion(json, 'version'),
      digest: _digest(json, 'digest'),
    );
  }

  @override
  List<Object?> get props => [id, version, digest];
}

class FiveLayerV2Readiness extends Equatable {
  final String status;
  final List<String> blockingGateIds;

  const FiveLayerV2Readiness({
    required this.status,
    required this.blockingGateIds,
  });

  factory FiveLayerV2Readiness.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'status',
      'blocking_gate_ids',
    }, 'v2 readiness');
    final status = JsonContract.requiredString(json, 'status');
    final blockers = _requiredStringList(
      json,
      'blocking_gate_ids',
      maxLength: 16,
    );
    final ready = status == 'deployment_ready' && blockers.isEmpty;
    final offline = status == 'offline_contract_fixture' && blockers.isNotEmpty;
    if (!ready && !offline) {
      throw const FormatException(
        'Invalid API contract: Five-layer v2 readiness is inconsistent.',
      );
    }
    return FiveLayerV2Readiness(status: status, blockingGateIds: blockers);
  }

  bool get evaluationOnly => status == 'offline_contract_fixture';
  bool get deploymentReady => status == 'deployment_ready';

  @override
  List<Object?> get props => [status, blockingGateIds];
}

class FiveLayerV2Dimension extends Equatable {
  final String dimensionId;
  final FiveLayerV2DimensionClassification classification;
  final Object value;
  final String unit;
  final String formulaReference;
  final String evidenceReference;
  final String? terraformTarget;

  const FiveLayerV2Dimension({
    required this.dimensionId,
    required this.classification,
    required this.value,
    required this.unit,
    required this.formulaReference,
    required this.evidenceReference,
    required this.terraformTarget,
  });

  factory FiveLayerV2Dimension.fromJson(Map<String, dynamic> json) {
    _expectAllowedKeys(json, const {
      'dimension_id',
      'classification',
      'value',
      'unit',
      'formula_reference',
      'evidence_reference',
      'terraform_target',
    }, 'v2 dimension');
    _requireKeys(json, const {
      'dimension_id',
      'classification',
      'value',
      'unit',
      'formula_reference',
      'evidence_reference',
    }, 'v2 dimension');
    final value = json['value'];
    if (value is! String && value is! bool && value is! num) {
      throw const FormatException(
        'Invalid API contract: v2 dimension value is unsupported.',
      );
    }
    if (value is num && !value.isFinite) {
      throw const FormatException(
        'Invalid API contract: v2 dimension value must be finite.',
      );
    }
    final classification = FiveLayerV2DimensionClassification.parse(
      json['classification'],
    );
    final terraformTarget = JsonContract.optionalString(
      json,
      'terraform_target',
    );
    return FiveLayerV2Dimension(
      dimensionId: JsonContract.requiredString(json, 'dimension_id'),
      classification: classification,
      value: value,
      unit: JsonContract.requiredString(json, 'unit'),
      formulaReference: JsonContract.requiredString(json, 'formula_reference'),
      evidenceReference: _digest(json, 'evidence_reference'),
      terraformTarget: terraformTarget,
    );
  }

  @override
  List<Object?> get props => [
    dimensionId,
    classification,
    value,
    unit,
    formulaReference,
    evidenceReference,
    terraformTarget,
  ];
}

class FiveLayerV2ComponentSelection extends Equatable {
  final String selectionId;
  final String architectureAssignmentId;
  final String logicalComponentId;
  final String implementationComponentId;
  final String implementationComponentDigest;
  final CloudProvider provider;
  final String region;
  final bool required;
  final List<FiveLayerV2Dimension> dimensions;

  const FiveLayerV2ComponentSelection({
    required this.selectionId,
    required this.architectureAssignmentId,
    required this.logicalComponentId,
    required this.implementationComponentId,
    required this.implementationComponentDigest,
    required this.provider,
    required this.region,
    required this.required,
    required this.dimensions,
  });

  factory FiveLayerV2ComponentSelection.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'selection_id',
      'architecture_assignment_id',
      'logical_component_id',
      'implementation_component_id',
      'implementation_component_digest',
      'provider',
      'region',
      'required',
      'dimensions',
    }, 'v2 component selection');
    final dimensions = _objectList(
      json,
      'dimensions',
      minLength: 1,
      maxLength: 64,
    ).map(FiveLayerV2Dimension.fromJson).toList(growable: false);
    _requireUnique(
      dimensions.map((item) => item.dimensionId),
      'v2 dimension IDs',
    );
    return FiveLayerV2ComponentSelection(
      selectionId: JsonContract.requiredString(json, 'selection_id'),
      architectureAssignmentId: JsonContract.requiredString(
        json,
        'architecture_assignment_id',
      ),
      logicalComponentId: JsonContract.requiredString(
        json,
        'logical_component_id',
      ),
      implementationComponentId: JsonContract.requiredString(
        json,
        'implementation_component_id',
      ),
      implementationComponentDigest: _digest(
        json,
        'implementation_component_digest',
      ),
      provider: _provider(json['provider']),
      region: JsonContract.requiredString(json, 'region'),
      required: JsonContract.requiredBool(json, 'required'),
      dimensions: List.unmodifiable(dimensions),
    );
  }

  @override
  List<Object?> get props => [
    selectionId,
    architectureAssignmentId,
    logicalComponentId,
    implementationComponentId,
    implementationComponentDigest,
    provider,
    region,
    required,
    dimensions,
  ];
}

class FiveLayerV2Binding extends Equatable {
  final String bindingId;
  final String sourceKind;
  final String sourceRef;
  final String destinationSelectionId;
  final String destinationInputId;
  final String valueType;
  final String sensitivity;
  final String resolutionStage;
  final String validatorId;
  final String compatibilityVersion;

  const FiveLayerV2Binding({
    required this.bindingId,
    required this.sourceKind,
    required this.sourceRef,
    required this.destinationSelectionId,
    required this.destinationInputId,
    required this.valueType,
    required this.sensitivity,
    required this.resolutionStage,
    required this.validatorId,
    required this.compatibilityVersion,
  });

  factory FiveLayerV2Binding.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'binding_id',
      'source_kind',
      'source_ref',
      'destination_selection_id',
      'destination_input_id',
      'value_type',
      'sensitivity',
      'resolution_stage',
      'validator_id',
      'compatibility_version',
    }, 'v2 binding');
    if (!const {
          'catalog_constant',
          'deployment_dimension',
          'component_output',
          'platform_configuration',
          'extension_artifact',
          'platform_runtime_secret_reference',
        }.contains(json['source_kind']) ||
        !const {
          'public',
          'internal',
          'sensitive_reference',
        }.contains(json['sensitivity']) ||
        !const {
          'package',
          'preplan',
          'terraform',
          'postapply',
        }.contains(json['resolution_stage']) ||
        !const {
          'integer',
          'string',
          'number',
          'boolean',
          'json_document',
        }.contains(json['value_type'])) {
      throw const FormatException(
        'Invalid API contract: v2 binding semantics are unsupported.',
      );
    }
    final compatibilityVersion = _positiveVersion(
      json,
      'compatibility_version',
    );
    if (compatibilityVersion != '1') {
      throw const FormatException(
        'Invalid API contract: v2 binding compatibility version is unsupported.',
      );
    }
    return FiveLayerV2Binding(
      bindingId: JsonContract.requiredString(json, 'binding_id'),
      sourceKind: JsonContract.requiredString(json, 'source_kind'),
      sourceRef: JsonContract.requiredString(json, 'source_ref'),
      destinationSelectionId: JsonContract.requiredString(
        json,
        'destination_selection_id',
      ),
      destinationInputId: JsonContract.requiredString(
        json,
        'destination_input_id',
      ),
      valueType: JsonContract.requiredString(json, 'value_type'),
      sensitivity: JsonContract.requiredString(json, 'sensitivity'),
      resolutionStage: JsonContract.requiredString(json, 'resolution_stage'),
      validatorId: JsonContract.requiredString(json, 'validator_id'),
      compatibilityVersion: compatibilityVersion,
    );
  }

  @override
  List<Object?> get props => [
    bindingId,
    sourceKind,
    sourceRef,
    destinationSelectionId,
    destinationInputId,
    valueType,
    sensitivity,
    resolutionStage,
    validatorId,
    compatibilityVersion,
  ];
}

final class ResolvedDeploymentSpecificationV2
    extends ResolvedDeploymentSpecificationData {
  static const _logicalComponents = {
    'component.ingestion',
    'component.processing',
    'component.hot-storage',
    'component.cool-storage',
    'component.archive-storage',
    'component.twin-state',
    'component.visualization',
  };

  final FiveLayerV2PinnedReference architectureProfileRef;
  final Map<String, FiveLayerV2PinnedReference> optimizationReferences;
  final Map<CloudProvider, String> pricingEvidenceDigests;
  final FiveLayerV2Readiness readiness;
  final String currency;
  final Map<String, num> fixedDimensions;
  final List<FiveLayerV2ComponentSelection> componentSelections;
  final List<FiveLayerV2Binding> bindings;

  const ResolvedDeploymentSpecificationV2({
    required super.calculationRunId,
    required super.digest,
    required this.architectureProfileRef,
    required this.optimizationReferences,
    required this.pricingEvidenceDigests,
    required this.readiness,
    required this.currency,
    required this.fixedDimensions,
    required this.componentSelections,
    required this.bindings,
  }) : super(
         schemaVersion: ResolvedDeploymentSpecificationData.v2SchemaVersion,
       );

  factory ResolvedDeploymentSpecificationV2.fromJson(
    Map<String, dynamic> json,
  ) {
    _rejectSecretLikePayload(json);
    _expectExactKeys(json, const {
      'schema_version',
      'calculation_run_id',
      'architecture_profile_ref',
      'optimization_context',
      'readiness',
      'currency',
      'fixed_dimensions',
      'component_selections',
      'bindings',
      'digest',
    }, 'resolved deployment specification v2');
    if (json['schema_version'] !=
        ResolvedDeploymentSpecificationData.v2SchemaVersion) {
      throw const FormatException(
        'Invalid API contract: resolved deployment specification v2 is unsupported.',
      );
    }
    final profile = FiveLayerV2PinnedReference.fromJson(
      JsonContract.requiredObject(json, 'architecture_profile_ref'),
    );
    if (profile.id != 'five-layer-baseline' || profile.version != '2') {
      throw const FormatException(
        'Invalid API contract: Five-layer v2 profile reference is unsupported.',
      );
    }
    final currency = JsonContract.requiredString(json, 'currency');
    if (currency != 'USD' && currency != 'EUR') {
      throw const FormatException(
        'Invalid API contract: Five-layer v2 currency is unsupported.',
      );
    }
    final context = JsonContract.requiredObject(json, 'optimization_context');
    _expectExactKeys(context, const {
      'service_decision_ref',
      'component_catalog_ref',
      'workload_ref',
      'eventing_scenario_ref',
      'formula_set_ref',
      'pricing_evidence_refs',
    }, 'v2 optimization context');
    final references = <String, FiveLayerV2PinnedReference>{
      for (final field in const [
        'service_decision_ref',
        'component_catalog_ref',
        'workload_ref',
        'eventing_scenario_ref',
        'formula_set_ref',
      ])
        field: FiveLayerV2PinnedReference.fromJson(
          JsonContract.requiredObject(context, field),
        ),
    };
    if (references['workload_ref']!.id != 'five-layer-workload' ||
        references['workload_ref']!.version != '2' ||
        references['eventing_scenario_ref']!.version != '1') {
      throw const FormatException(
        'Invalid API contract: Five-layer v2 workload evidence is incompatible.',
      );
    }
    final pricingEvidence = <CloudProvider, String>{};
    for (final item in _objectList(
      context,
      'pricing_evidence_refs',
      minLength: 1,
      maxLength: 3,
    )) {
      _expectExactKeys(item, const {
        'provider',
        'digest',
      }, 'v2 pricing evidence');
      final provider = _provider(item['provider']);
      if (pricingEvidence.containsKey(provider)) {
        throw const FormatException(
          'Invalid API contract: v2 pricing evidence providers must be unique.',
        );
      }
      pricingEvidence[provider] = _digest(item, 'digest');
    }
    final fixedRaw = JsonContract.requiredObject(json, 'fixed_dimensions');
    const fixedValues = <String, int>{
      'l4_inspection_sessions_per_month': 12,
      'l4_reads_per_inspection_session': 20,
      'visualized_numeric_metrics_per_record': 1,
      'rollup_bucket_seconds': 3600,
      'reader_timeout_seconds': 10,
      'reader_maximum_points': 1000,
      'gcp_grafana_persistent_disk_gib': 10,
      'storage_batch_interval_minutes': 5,
      'storage_task_max_input_mib': 512,
      'storage_object_max_uncompressed_mib': 64,
      'storage_transfer_retry_horizon_hours': 24,
      'storage_source_expiry_grace_hours': 48,
      'azure_mover_max_device_partitions_per_task': 1000,
    };
    _expectExactKeys(fixedRaw, fixedValues.keys.toSet(), 'v2 fixed dimensions');
    final fixedDimensions = <String, num>{};
    for (final entry in fixedRaw.entries) {
      if (entry.value is! int || entry.value != fixedValues[entry.key]) {
        throw const FormatException(
          'Invalid API contract: v2 fixed dimensions differ from the frozen PoC contract.',
        );
      }
      fixedDimensions[entry.key] = entry.value as int;
    }
    final selections = _objectList(
      json,
      'component_selections',
      minLength: 7,
      maxLength: 128,
    ).map(FiveLayerV2ComponentSelection.fromJson).toList(growable: false);
    _requireUnique(
      selections.map((item) => item.selectionId),
      'v2 selection IDs',
    );
    if (selections.any((item) => !item.required)) {
      throw const FormatException(
        'Invalid API contract: every Five-layer v2 selection must be required.',
      );
    }
    final logicalProviders = <String, Set<CloudProvider>>{};
    final logicalAssignments = <String, Set<String>>{};
    for (final selection in selections) {
      logicalProviders
          .putIfAbsent(selection.logicalComponentId, () => {})
          .add(selection.provider);
      logicalAssignments
          .putIfAbsent(selection.logicalComponentId, () => {})
          .add(selection.architectureAssignmentId);
    }
    if (logicalProviders.length != _logicalComponents.length ||
        !_logicalComponents.every(logicalProviders.containsKey) ||
        logicalProviders.values.any((providers) => providers.length != 1) ||
        logicalAssignments.values.any(
          (assignments) => assignments.length != 1,
        ) ||
        logicalProviders['component.hot-storage']!.single !=
            logicalProviders['component.visualization']!.single) {
      throw const FormatException(
        'Invalid API contract: v2 logical components or L3/L5 co-location differ.',
      );
    }
    _requireUnique(
      logicalAssignments.values.map((assignments) => assignments.single),
      'v2 architecture assignment IDs',
    );
    final usedProviders = selections.map((item) => item.provider).toSet();
    if (usedProviders.difference(pricingEvidence.keys.toSet()).isNotEmpty) {
      throw const FormatException(
        'Invalid API contract: v2 pricing evidence is incomplete.',
      );
    }
    final bindings = _objectList(
      json,
      'bindings',
      minLength: 7,
      maxLength: 256,
    ).map(FiveLayerV2Binding.fromJson).toList(growable: false);
    _requireUnique(bindings.map((item) => item.bindingId), 'v2 binding IDs');
    final selectionIds = selections.map((item) => item.selectionId).toSet();
    final dimensionIds = selections
        .expand((item) => item.dimensions)
        .map((item) => item.dimensionId)
        .toSet();
    if (bindings.any(
      (item) =>
          !selectionIds.contains(item.destinationSelectionId) ||
          (item.sourceKind == 'deployment_dimension' &&
              !dimensionIds.contains(item.sourceRef)),
    )) {
      throw const FormatException(
        'Invalid API contract: v2 binding reference is unresolved.',
      );
    }
    final digest = _digest(json, 'digest');
    if (digest != _calculateDigest(json)) {
      throw const FormatException(
        'Invalid API contract: resolved deployment specification v2 digest mismatch.',
      );
    }
    return ResolvedDeploymentSpecificationV2(
      calculationRunId: JsonContract.requiredString(json, 'calculation_run_id'),
      digest: digest,
      architectureProfileRef: profile,
      optimizationReferences: UnmodifiableMapView(references),
      pricingEvidenceDigests: UnmodifiableMapView(pricingEvidence),
      readiness: FiveLayerV2Readiness.fromJson(
        JsonContract.requiredObject(json, 'readiness'),
      ),
      currency: currency,
      fixedDimensions: UnmodifiableMapView(fixedDimensions),
      componentSelections: List.unmodifiable(selections),
      bindings: List.unmodifiable(bindings),
    );
  }

  @override
  bool get isSupported => true;

  Set<CloudProvider> get providers =>
      Set.unmodifiable(componentSelections.map((item) => item.provider));

  int get logicalComponentCount =>
      componentSelections.map((item) => item.logicalComponentId).toSet().length;

  @override
  List<Object?> get props => [
    ...super.props,
    architectureProfileRef,
    optimizationReferences,
    pricingEvidenceDigests,
    readiness,
    currency,
    fixedDimensions,
    componentSelections,
    bindings,
  ];
}

class ResolvedArchitectureProfile extends Equatable {
  final String profileId;
  final String profileVersion;

  const ResolvedArchitectureProfile({
    required this.profileId,
    required this.profileVersion,
  });

  factory ResolvedArchitectureProfile.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'profile_id',
      'profile_version',
    }, 'architecture profile');
    final profileId = JsonContract.requiredString(json, 'profile_id');
    final profileVersion = JsonContract.requiredString(json, 'profile_version');
    if (profileId != 'five-layer-baseline' || profileVersion != '1') {
      throw const FormatException(
        'Invalid API contract: architecture profile is unsupported.',
      );
    }
    return ResolvedArchitectureProfile(
      profileId: profileId,
      profileVersion: profileVersion,
    );
  }

  @override
  List<Object?> get props => [profileId, profileVersion];
}

class ResolvedCatalogReference extends Equatable {
  final String snapshotId;
  final String pricingRegion;
  final String contentDigest;

  const ResolvedCatalogReference({
    required this.snapshotId,
    required this.pricingRegion,
    required this.contentDigest,
  });

  factory ResolvedCatalogReference.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'snapshot_id',
      'pricing_region',
      'content_digest',
    }, 'catalog reference');
    return ResolvedCatalogReference(
      snapshotId: JsonContract.requiredString(json, 'snapshot_id'),
      pricingRegion: JsonContract.requiredString(json, 'pricing_region'),
      contentDigest: _digest(json, 'content_digest'),
    );
  }

  @override
  List<Object?> get props => [snapshotId, pricingRegion, contentDigest];
}

class ResolvedOptimizationContext extends Equatable {
  final String optimizationProfileId;
  final String optimizationProfileVersion;
  final String calculationStrategyId;
  final String formulaSetId;
  final String workloadContractId;
  final String pricingRegistryVersion;
  final Map<CloudProvider, ResolvedCatalogReference> catalogReferences;

  const ResolvedOptimizationContext({
    required this.optimizationProfileId,
    required this.optimizationProfileVersion,
    required this.calculationStrategyId,
    required this.formulaSetId,
    required this.workloadContractId,
    required this.pricingRegistryVersion,
    required this.catalogReferences,
  });

  factory ResolvedOptimizationContext.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'optimization_profile_id',
      'optimization_profile_version',
      'calculation_strategy_id',
      'formula_set_id',
      'workload_contract_id',
      'pricing_registry_version',
      'catalog_references',
    }, 'optimization context');
    final references = JsonContract.requiredObject(json, 'catalog_references');
    if (references.keys.toSet().difference(const {
          'aws',
          'azure',
          'gcp',
        }).isNotEmpty ||
        references.length != 3) {
      throw const FormatException(
        'Invalid API contract: catalog references must contain AWS, Azure, and GCP.',
      );
    }
    return ResolvedOptimizationContext(
      optimizationProfileId: JsonContract.requiredString(
        json,
        'optimization_profile_id',
      ),
      optimizationProfileVersion: JsonContract.requiredString(
        json,
        'optimization_profile_version',
      ),
      calculationStrategyId: JsonContract.requiredString(
        json,
        'calculation_strategy_id',
      ),
      formulaSetId: JsonContract.requiredString(json, 'formula_set_id'),
      workloadContractId: JsonContract.requiredString(
        json,
        'workload_contract_id',
      ),
      pricingRegistryVersion: JsonContract.requiredString(
        json,
        'pricing_registry_version',
      ),
      catalogReferences: UnmodifiableMapView({
        for (final entry in references.entries)
          _provider(entry.key): ResolvedCatalogReference.fromJson(
            JsonContract.immutableObject(
              entry.value,
              'catalog_references.${entry.key}',
            ),
          ),
      }),
    );
  }

  @override
  List<Object?> get props => [
    optimizationProfileId,
    optimizationProfileVersion,
    calculationStrategyId,
    formulaSetId,
    workloadContractId,
    pricingRegistryVersion,
    catalogReferences,
  ];
}

class ResolvedDeploymentDimension extends Equatable {
  final String dimensionId;
  final DeploymentDimensionClassification classification;
  final Object value;
  final String formulaReference;
  final String evidenceReference;
  final String? unit;
  final String? terraformTarget;

  const ResolvedDeploymentDimension({
    required this.dimensionId,
    required this.classification,
    required this.value,
    required this.formulaReference,
    required this.evidenceReference,
    this.unit,
    this.terraformTarget,
  });

  factory ResolvedDeploymentDimension.fromJson(Map<String, dynamic> json) {
    _expectAllowedKeys(json, const {
      'dimension_id',
      'classification',
      'value',
      'formula_reference',
      'evidence_reference',
      'unit',
      'terraform_target',
    }, 'deployment dimension');
    final value = json['value'];
    if (value is! String && value is! int && value is! bool) {
      throw const FormatException(
        'Invalid API contract: deployment dimension value must be a string, integer, or boolean.',
      );
    }
    final unit = JsonContract.optionalString(json, 'unit');
    final terraformTarget = JsonContract.optionalString(
      json,
      'terraform_target',
    );
    final classification = DeploymentDimensionClassification.parse(
      json['classification'],
    );
    if (classification ==
            DeploymentDimensionClassification.deployableSelection &&
        (terraformTarget == null || terraformTarget.isEmpty)) {
      throw const FormatException(
        'Invalid API contract: deployable dimensions require a Terraform target.',
      );
    }
    if (classification !=
            DeploymentDimensionClassification.deployableSelection &&
        terraformTarget != null) {
      throw const FormatException(
        'Invalid API contract: evidence-only dimensions cannot have a Terraform target.',
      );
    }
    return ResolvedDeploymentDimension(
      dimensionId: JsonContract.requiredString(json, 'dimension_id'),
      classification: classification,
      value: value,
      formulaReference: JsonContract.requiredString(json, 'formula_reference'),
      evidenceReference: JsonContract.requiredString(
        json,
        'evidence_reference',
      ),
      unit: unit,
      terraformTarget: terraformTarget,
    );
  }

  String get displayValue => unit == null ? '$value' : '$value $unit';

  @override
  List<Object?> get props => [
    dimensionId,
    classification,
    value,
    formulaReference,
    evidenceReference,
    unit,
    terraformTarget,
  ];
}

class ResolvedDeploymentComponent extends Equatable {
  final String componentId;
  final ResolvedDeploymentSlot slot;
  final CloudProvider provider;
  final String serviceId;
  final List<ResolvedDeploymentDimension> dimensions;

  const ResolvedDeploymentComponent({
    required this.componentId,
    required this.slot,
    required this.provider,
    required this.serviceId,
    required this.dimensions,
  });

  factory ResolvedDeploymentComponent.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'component_id',
      'slot_id',
      'provider',
      'service_id',
      'required',
      'dimensions',
    }, 'deployment component');
    if (JsonContract.requiredBool(json, 'required') != true) {
      throw const FormatException(
        'Invalid API contract: deployment components must be required.',
      );
    }
    final dimensions = _objectList(
      json,
      'dimensions',
      minLength: 1,
      maxLength: 16,
    ).map(ResolvedDeploymentDimension.fromJson).toList(growable: false);
    if (dimensions.map((dimension) => dimension.dimensionId).toSet().length !=
        dimensions.length) {
      throw const FormatException(
        'Invalid API contract: component dimension IDs must be unique.',
      );
    }
    return ResolvedDeploymentComponent(
      componentId: JsonContract.requiredString(json, 'component_id'),
      slot: ResolvedDeploymentSlot.parse(json['slot_id']),
      provider: _provider(json['provider']),
      serviceId: JsonContract.requiredString(json, 'service_id'),
      dimensions: List.unmodifiable(dimensions),
    );
  }

  List<ResolvedDeploymentDimension> get deployableDimensions =>
      List.unmodifiable(
        dimensions.where(
          (dimension) =>
              dimension.classification ==
              DeploymentDimensionClassification.deployableSelection,
        ),
      );

  @override
  List<Object?> get props => [
    componentId,
    slot,
    provider,
    serviceId,
    dimensions,
  ];
}

class OptimizerRunSummaryData extends Equatable {
  final String id;
  final String twinId;
  final String status;
  final DeploymentCompatibility deploymentCompatibility;
  final String? deploymentSpecificationDigest;
  final String? deploymentSpecificationVersion;
  final DateTime createdAt;
  final DateTime? selectedForDeploymentAt;

  const OptimizerRunSummaryData({
    required this.id,
    required this.twinId,
    required this.status,
    required this.deploymentCompatibility,
    required this.deploymentSpecificationDigest,
    required this.deploymentSpecificationVersion,
    required this.createdAt,
    required this.selectedForDeploymentAt,
  });

  factory OptimizerRunSummaryData.fromJson(Map<String, dynamic> json) {
    final compatibility = DeploymentCompatibility.parse(
      json['deployment_compatibility_status'],
    );
    final digest = JsonContract.optionalString(
      json,
      'deployment_specification_digest',
    );
    final version = JsonContract.optionalString(
      json,
      'deployment_specification_version',
    );
    if (compatibility == DeploymentCompatibility.ready) {
      if (digest == null || version == null) {
        throw const FormatException(
          'Invalid API contract: ready optimizer run is missing deployment metadata.',
        );
      }
      _validateDigest(digest, 'deployment_specification_digest');
    }
    final createdAt = _requiredUtcDate(json, 'created_at');
    final selectedForDeploymentAt = _optionalUtcDate(
      json,
      'selected_for_deployment_at',
    );
    if (selectedForDeploymentAt?.isBefore(createdAt) == true) {
      throw const FormatException(
        'Invalid API contract: optimizer run selection predates run creation.',
      );
    }
    return OptimizerRunSummaryData(
      id: JsonContract.requiredString(json, 'id'),
      twinId: JsonContract.requiredString(json, 'twin_id'),
      status: JsonContract.requiredString(json, 'status'),
      deploymentCompatibility: compatibility,
      deploymentSpecificationDigest: digest,
      deploymentSpecificationVersion: version,
      createdAt: createdAt,
      selectedForDeploymentAt: selectedForDeploymentAt,
    );
  }

  @override
  List<Object?> get props => [
    id,
    twinId,
    status,
    deploymentCompatibility,
    deploymentSpecificationDigest,
    deploymentSpecificationVersion,
    createdAt,
    selectedForDeploymentAt,
  ];
}

class OptimizerDeploymentRunData extends Equatable {
  final OptimizerRunSummaryData summary;
  final ResolvedDeploymentSpecificationData? specification;

  const OptimizerDeploymentRunData({
    required this.summary,
    required this.specification,
  });

  factory OptimizerDeploymentRunData.fromDetailJson(Map<String, dynamic> json) {
    final summary = OptimizerRunSummaryData.fromJson(json);
    final rawSpecification = JsonContract.optionalObject(
      json,
      'resolved_deployment_specification',
    );
    final specification = rawSpecification == null
        ? null
        : ResolvedDeploymentSpecificationData.fromJson(rawSpecification);
    _validateRunSpecification(summary, specification);
    return OptimizerDeploymentRunData(
      summary: summary,
      specification: specification,
    );
  }

  OptimizerDeploymentRunData applySelection(
    OptimizerRunSelectionData selection,
  ) {
    if (summary.id != selection.run.summary.id ||
        summary.twinId != selection.run.summary.twinId ||
        summary.status != selection.run.summary.status ||
        summary.deploymentCompatibility !=
            selection.run.summary.deploymentCompatibility ||
        summary.deploymentSpecificationDigest !=
            selection.run.summary.deploymentSpecificationDigest ||
        summary.deploymentSpecificationVersion !=
            selection.run.summary.deploymentSpecificationVersion ||
        summary.createdAt != selection.run.summary.createdAt ||
        specification != selection.run.specification) {
      throw const FormatException(
        'Invalid API contract: optimizer run selection changed deployment identity.',
      );
    }
    return selection.run;
  }

  String get id => summary.id;
  String get twinId => summary.twinId;
  DateTime? get selectedForDeploymentAt => summary.selectedForDeploymentAt;
  DeploymentCompatibility get compatibility => summary.deploymentCompatibility;

  @override
  List<Object?> get props => [summary, specification];
}

class OptimizerRunSelectionData extends Equatable {
  final OptimizerDeploymentRunData run;
  final DateTime selectedForDeploymentAt;

  const OptimizerRunSelectionData({
    required this.run,
    required this.selectedForDeploymentAt,
  });

  factory OptimizerRunSelectionData.fromJson(Map<String, dynamic> json) {
    final runJson = JsonContract.requiredObject(json, 'run');
    final specificationJson = JsonContract.requiredObject(
      json,
      'resolved_deployment_specification',
    );
    final selectedAt = _requiredUtcDate(json, 'selected_for_deployment_at');
    final merged = <String, dynamic>{
      ...runJson,
      'resolved_deployment_specification': specificationJson,
    };
    final run = OptimizerDeploymentRunData.fromDetailJson(merged);
    if (run.selectedForDeploymentAt != selectedAt) {
      throw const FormatException(
        'Invalid API contract: optimizer run selection timestamp mismatch.',
      );
    }
    return OptimizerRunSelectionData(
      run: run,
      selectedForDeploymentAt: selectedAt,
    );
  }

  @override
  List<Object?> get props => [run, selectedForDeploymentAt];
}

enum ResolvedDeploymentReviewState {
  absent,
  selectionRequired,
  selecting,
  ready,
  evaluationOnly,
  legacy,
  unsupported,
  failed,
}

class ResolvedDeploymentReview extends Equatable {
  final ResolvedDeploymentReviewState state;
  final OptimizerDeploymentRunData? run;

  const ResolvedDeploymentReview._({required this.state, required this.run});

  factory ResolvedDeploymentReview.fromRun(
    OptimizerDeploymentRunData? run, {
    bool isSelecting = false,
    bool selectionFailed = false,
  }) {
    if (run == null) {
      return const ResolvedDeploymentReview._(
        state: ResolvedDeploymentReviewState.absent,
        run: null,
      );
    }
    if (run.compatibility == DeploymentCompatibility.legacyNotDeployable ||
        run.specification == null) {
      return ResolvedDeploymentReview._(
        state: ResolvedDeploymentReviewState.legacy,
        run: run,
      );
    }
    if (!run.specification!.isSupported) {
      return ResolvedDeploymentReview._(
        state: ResolvedDeploymentReviewState.unsupported,
        run: run,
      );
    }
    final v2 = run.specification is ResolvedDeploymentSpecificationV2
        ? run.specification! as ResolvedDeploymentSpecificationV2
        : null;
    if (v2?.readiness.evaluationOnly == true) {
      return ResolvedDeploymentReview._(
        state: ResolvedDeploymentReviewState.evaluationOnly,
        run: run,
      );
    }
    if (isSelecting) {
      return ResolvedDeploymentReview._(
        state: ResolvedDeploymentReviewState.selecting,
        run: run,
      );
    }
    if (selectionFailed) {
      return ResolvedDeploymentReview._(
        state: ResolvedDeploymentReviewState.failed,
        run: run,
      );
    }
    if (run.selectedForDeploymentAt == null) {
      return ResolvedDeploymentReview._(
        state: ResolvedDeploymentReviewState.selectionRequired,
        run: run,
      );
    }
    return ResolvedDeploymentReview._(
      state: ResolvedDeploymentReviewState.ready,
      run: run,
    );
  }

  bool get ready => state == ResolvedDeploymentReviewState.ready;

  ResolvedDeploymentSpecificationV1? get supportedSpecification =>
      run?.specification is ResolvedDeploymentSpecificationV1
      ? run!.specification! as ResolvedDeploymentSpecificationV1
      : null;

  ResolvedDeploymentSpecificationV2? get supportedV2Specification =>
      run?.specification is ResolvedDeploymentSpecificationV2
      ? run!.specification! as ResolvedDeploymentSpecificationV2
      : null;

  @override
  List<Object?> get props => [state, run];
}

void _validateRunSpecification(
  OptimizerRunSummaryData summary,
  ResolvedDeploymentSpecificationData? specification,
) {
  if (summary.deploymentCompatibility ==
      DeploymentCompatibility.legacyNotDeployable) {
    if (specification != null ||
        summary.deploymentSpecificationDigest != null ||
        summary.deploymentSpecificationVersion != null ||
        summary.selectedForDeploymentAt != null) {
      throw const FormatException(
        'Invalid API contract: legacy run contains deployment specification metadata.',
      );
    }
    return;
  }
  if (summary.status != 'succeeded' || specification == null) {
    throw const FormatException(
      'Invalid API contract: ready optimizer run is incomplete.',
    );
  }
  if (specification.calculationRunId != summary.id ||
      specification.digest != summary.deploymentSpecificationDigest ||
      specification.schemaVersion != summary.deploymentSpecificationVersion) {
    throw const FormatException(
      'Invalid API contract: optimizer run and deployment specification differ.',
    );
  }
  if (specification is ResolvedDeploymentSpecificationV2 &&
      specification.readiness.evaluationOnly &&
      summary.selectedForDeploymentAt != null) {
    throw const FormatException(
      'Invalid API contract: evaluation-only v2 evidence cannot be selected.',
    );
  }
}

List<Map<String, dynamic>> _objectList(
  Map<String, dynamic> json,
  String field, {
  required int minLength,
  required int maxLength,
}) {
  final value = json[field];
  if (value is! List ||
      value.length < minLength ||
      value.length > maxLength ||
      value.any((item) => item is! Map)) {
    throw FormatException(
      'Invalid API contract: $field must contain between $minLength and $maxLength objects.',
    );
  }
  return List.unmodifiable(
    value.indexed.map(
      (entry) => JsonContract.immutableObject(entry.$2, '$field[${entry.$1}]'),
    ),
  );
}

CloudProvider _provider(Object? value) {
  if (value is! String) {
    throw const FormatException(
      'Invalid API contract: deployment provider must be a string.',
    );
  }
  try {
    return CloudProvider.fromApiValue(value);
  } on ArgumentError {
    throw const FormatException(
      'Invalid API contract: deployment provider is unsupported.',
    );
  }
}

int _compareComponents(
  ResolvedDeploymentComponent left,
  ResolvedDeploymentComponent right,
) {
  final slotComparison = left.slot.sortOrder.compareTo(right.slot.sortOrder);
  return slotComparison != 0
      ? slotComparison
      : left.componentId.compareTo(right.componentId);
}

void _expectExactKeys(
  Map<String, dynamic> json,
  Set<String> expected,
  String field,
) {
  if (json.keys.toSet().difference(expected).isNotEmpty ||
      expected.difference(json.keys.toSet()).isNotEmpty) {
    throw FormatException(
      'Invalid API contract: $field fields are incomplete or unsupported.',
    );
  }
}

void _expectAllowedKeys(
  Map<String, dynamic> json,
  Set<String> allowed,
  String field,
) {
  if (json.keys.toSet().difference(allowed).isNotEmpty) {
    throw FormatException(
      'Invalid API contract: $field contains unsupported fields.',
    );
  }
  const required = {
    'dimension_id',
    'classification',
    'value',
    'formula_reference',
    'evidence_reference',
  };
  if (required.difference(json.keys.toSet()).isNotEmpty) {
    throw FormatException(
      'Invalid API contract: $field is missing required fields.',
    );
  }
}

void _requireKeys(
  Map<String, dynamic> json,
  Set<String> required,
  String field,
) {
  if (required.difference(json.keys.toSet()).isNotEmpty) {
    throw FormatException(
      'Invalid API contract: $field is missing required fields.',
    );
  }
}

List<String> _requiredStringList(
  Map<String, dynamic> json,
  String field, {
  int maxLength = 512,
}) {
  final value = json[field];
  if (value is! List ||
      value.length > maxLength ||
      value.any((item) => item is! String || item.isEmpty)) {
    throw FormatException(
      'Invalid API contract: $field must be a bounded string array.',
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

void _rejectSecretLikePayload(Object? value, {int depth = 0}) {
  if (depth > 32) {
    throw const FormatException(
      'Invalid API contract: deployment specification is too deeply nested.',
    );
  }
  if (value is Map) {
    for (final entry in value.entries) {
      final key = entry.key.toString().toLowerCase();
      if (const [
        'access_key',
        'account_key',
        'api_key',
        'client_secret',
        'connection_string',
        'credential',
        'password',
        'private_key',
        'secret',
        'token',
      ].any(key.contains)) {
        throw const FormatException(
          'Invalid API contract: deployment specification contains secret-like fields.',
        );
      }
      _rejectSecretLikePayload(entry.value, depth: depth + 1);
    }
    return;
  }
  if (value is List) {
    for (final item in value) {
      _rejectSecretLikePayload(item, depth: depth + 1);
    }
    return;
  }
  if (value is String &&
      (value.contains('PRIVATE KEY-----') ||
          RegExp(r'\bAKIA[0-9A-Z]{16}\b').hasMatch(value) ||
          RegExp(
            r'(AccountKey|SharedAccessKey)=[A-Za-z0-9+/=]{12,}',
          ).hasMatch(value))) {
    throw const FormatException(
      'Invalid API contract: deployment specification contains secret-like values.',
    );
  }
}

String _digest(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  _validateDigest(value, field);
  return value;
}

void _validateDigest(String value, String field) {
  if (!RegExp(r'^sha256:[0-9a-f]{64}$').hasMatch(value)) {
    throw FormatException(
      'Invalid API contract: $field must be a SHA-256 digest.',
    );
  }
}

DateTime _requiredUtcDate(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  return _parseUtcDate(value, field);
}

DateTime? _optionalUtcDate(Map<String, dynamic> json, String field) {
  final value = JsonContract.optionalString(json, field);
  return value == null ? null : _parseUtcDate(value, field);
}

DateTime _parseUtcDate(String value, String field) {
  if (!RegExp(r'(Z|[+-]00:00)$').hasMatch(value)) {
    throw FormatException(
      'Invalid API contract: $field must use an explicit UTC offset.',
    );
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null) {
    throw FormatException(
      'Invalid API contract: $field must be an ISO-8601 timestamp.',
    );
  }
  return parsed.toUtc();
}

String _calculateDigest(Map<String, dynamic> specification) {
  final payload = Map<String, dynamic>.from(specification)..remove('digest');
  return 'sha256:${sha256.convert(utf8.encode(_canonicalJson(payload)))}';
}

String _canonicalJson(Object? value) {
  if (value == null || value is bool || value is num) return jsonEncode(value);
  if (value is String) return _asciiJsonString(value);
  if (value is List) {
    return '[${value.map(_canonicalJson).join(',')}]';
  }
  if (value is Map) {
    final entries =
        value.entries
            .map((entry) => MapEntry(entry.key.toString(), entry.value))
            .toList(growable: false)
          ..sort((left, right) => left.key.compareTo(right.key));
    return '{${entries.map((entry) => '${_asciiJsonString(entry.key)}:${_canonicalJson(entry.value)}').join(',')}}';
  }
  throw const FormatException(
    'Invalid API contract: deployment specification is not canonical JSON.',
  );
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
