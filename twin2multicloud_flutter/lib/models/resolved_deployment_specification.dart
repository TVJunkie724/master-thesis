import 'dart:collection';
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:equatable/equatable.dart';

import 'cloud_connection.dart';
import 'json_contract.dart';

enum DeploymentCompatibility {
  ready('ready');

  final String apiValue;

  const DeploymentCompatibility(this.apiValue);

  static DeploymentCompatibility parse(Object? value) => values.firstWhere(
    (candidate) => candidate.apiValue == value,
    orElse: () => throw const FormatException(
      'Invalid API contract: deployment compatibility is unsupported.',
    ),
  );
}

sealed class ResolvedDeploymentSpecificationData extends Equatable {
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
    if (schemaVersion != v2SchemaVersion) {
      return UnsupportedResolvedDeploymentSpecification(
        schemaVersion: schemaVersion,
        calculationRunId: JsonContract.requiredString(
          json,
          'calculation_run_id',
        ),
        digest: _digest(json, 'digest'),
      );
    }
    return ResolvedDeploymentSpecificationV2.fromJson(json);
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

enum SixLayerDimensionClassification {
  deployableSelection('deployable_selection'),
  capacity('capacity'),
  usage('usage'),
  fixedPoc('fixed_poc'),
  accountScope('account_scope');

  final String apiValue;

  const SixLayerDimensionClassification(this.apiValue);

  static SixLayerDimensionClassification parse(
    Object? value,
  ) => values.firstWhere(
    (candidate) => candidate.apiValue == value,
    orElse: () => throw const FormatException(
      'Invalid API contract: Six-layer dimension classification is unsupported.',
    ),
  );
}

class SixLayerPinnedReference extends Equatable {
  final String id;
  final String version;
  final String digest;

  const SixLayerPinnedReference({
    required this.id,
    required this.version,
    required this.digest,
  });

  factory SixLayerPinnedReference.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {'id', 'version', 'digest'}, 'v2 reference');
    return SixLayerPinnedReference(
      id: JsonContract.requiredString(json, 'id'),
      version: _positiveVersion(json, 'version'),
      digest: _digest(json, 'digest'),
    );
  }

  @override
  List<Object?> get props => [id, version, digest];
}

class SixLayerReadiness extends Equatable {
  final String status;
  final List<String> blockingGateIds;

  const SixLayerReadiness({
    required this.status,
    required this.blockingGateIds,
  });

  factory SixLayerReadiness.fromJson(Map<String, dynamic> json) {
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
        'Invalid API contract: Six-layer readiness is inconsistent.',
      );
    }
    return SixLayerReadiness(status: status, blockingGateIds: blockers);
  }

  bool get evaluationOnly => status == 'offline_contract_fixture';
  bool get deploymentReady => status == 'deployment_ready';

  @override
  List<Object?> get props => [status, blockingGateIds];
}

class SixLayerDimension extends Equatable {
  final String dimensionId;
  final SixLayerDimensionClassification classification;
  final Object value;
  final String unit;
  final String formulaReference;
  final String evidenceReference;
  final String? terraformTarget;

  const SixLayerDimension({
    required this.dimensionId,
    required this.classification,
    required this.value,
    required this.unit,
    required this.formulaReference,
    required this.evidenceReference,
    required this.terraformTarget,
  });

  factory SixLayerDimension.fromJson(Map<String, dynamic> json) {
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
    final classification = SixLayerDimensionClassification.parse(
      json['classification'],
    );
    final terraformTarget = JsonContract.optionalString(
      json,
      'terraform_target',
    );
    return SixLayerDimension(
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

class SixLayerComponentSelection extends Equatable {
  final String selectionId;
  final String architectureAssignmentId;
  final String logicalComponentId;
  final String implementationComponentId;
  final String implementationComponentDigest;
  final CloudProvider provider;
  final String region;
  final bool required;
  final List<SixLayerDimension> dimensions;

  const SixLayerComponentSelection({
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

  factory SixLayerComponentSelection.fromJson(Map<String, dynamic> json) {
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
    ).map(SixLayerDimension.fromJson).toList(growable: false);
    _requireUnique(
      dimensions.map((item) => item.dimensionId),
      'v2 dimension IDs',
    );
    final selectionId = JsonContract.requiredString(json, 'selection_id');
    final implementationComponentId = JsonContract.requiredString(
      json,
      'implementation_component_id',
    );
    final provider = _provider(json['provider']);
    if (selectionId !=
        'selection.${provider.apiValue}.$implementationComponentId') {
      throw const FormatException(
        'Invalid API contract: v2 selection and implementation IDs differ.',
      );
    }
    return SixLayerComponentSelection(
      selectionId: selectionId,
      architectureAssignmentId: JsonContract.requiredString(
        json,
        'architecture_assignment_id',
      ),
      logicalComponentId: JsonContract.requiredString(
        json,
        'logical_component_id',
      ),
      implementationComponentId: implementationComponentId,
      implementationComponentDigest: _digest(
        json,
        'implementation_component_digest',
      ),
      provider: provider,
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

class SixLayerBinding extends Equatable {
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

  const SixLayerBinding({
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

  factory SixLayerBinding.fromJson(Map<String, dynamic> json) {
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
    return SixLayerBinding(
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
  static const _coreLogicalComponents = {
    'component.ingestion',
    'component.processing',
    'component.hot-storage',
    'component.cool-storage',
    'component.archive-storage',
    'component.twin-state',
    'component.visualization',
  };
  static const _sixLayerLogicalComponents = {
    ..._coreLogicalComponents,
    'component.eventing',
  };

  final SixLayerPinnedReference architectureProfileRef;
  final Map<String, SixLayerPinnedReference> optimizationReferences;
  final Map<CloudProvider, String> pricingEvidenceDigests;
  final SixLayerReadiness readiness;
  final String currency;
  final Map<String, num> fixedDimensions;
  final List<SixLayerComponentSelection> componentSelections;
  final List<SixLayerBinding> bindings;

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
    final profile = SixLayerPinnedReference.fromJson(
      JsonContract.requiredObject(json, 'architecture_profile_ref'),
    );
    final expectedLogicalComponents = switch ((profile.id, profile.version)) {
      ('six-layer-eventing', '1') => _sixLayerLogicalComponents,
      _ => throw const FormatException(
        'Invalid API contract: Phase 8 profile reference is unsupported.',
      ),
    };
    final currency = JsonContract.requiredString(json, 'currency');
    if (currency != 'USD' && currency != 'EUR') {
      throw const FormatException(
        'Invalid API contract: Six-layer currency is unsupported.',
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
    final references = <String, SixLayerPinnedReference>{
      for (final field in const [
        'service_decision_ref',
        'component_catalog_ref',
        'workload_ref',
        'eventing_scenario_ref',
        'formula_set_ref',
      ])
        field: SixLayerPinnedReference.fromJson(
          JsonContract.requiredObject(context, field),
        ),
    };
    if (references['workload_ref']!.id != 'six-layer-workload' ||
        references['workload_ref']!.version != '1' ||
        references['eventing_scenario_ref']!.version != '1') {
      throw const FormatException(
        'Invalid API contract: Six-layer workload evidence is incompatible.',
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
    ).map(SixLayerComponentSelection.fromJson).toList(growable: false);
    _requireUnique(
      selections.map((item) => item.selectionId),
      'v2 selection IDs',
    );
    if (selections.any((item) => !item.required)) {
      throw const FormatException(
        'Invalid API contract: every Phase 8 service selection must be required.',
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
    if (logicalProviders.length != expectedLogicalComponents.length ||
        !expectedLogicalComponents.every(logicalProviders.containsKey) ||
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
    ).map(SixLayerBinding.fromJson).toList(growable: false);
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
      readiness: SixLayerReadiness.fromJson(
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
    if (run.specification == null) {
      return ResolvedDeploymentReview._(
        state: ResolvedDeploymentReviewState.unsupported,
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
