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
  static const supportedSchemaVersion = 'resolved-deployment-specification.v1';

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
    if (schemaVersion != supportedSchemaVersion) {
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
         schemaVersion:
             ResolvedDeploymentSpecificationData.supportedSchemaVersion,
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
    if (schemaVersion !=
        ResolvedDeploymentSpecificationData.supportedSchemaVersion) {
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
      'Invalid API contract: $field fields do not match schema v1.',
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
