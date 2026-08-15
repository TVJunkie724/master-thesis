import 'package:equatable/equatable.dart';

import 'cloud_connection.dart';
import 'json_contract.dart';

class PinnedArchitectureReference extends Equatable {
  final String id;
  final String version;
  final String digest;

  const PinnedArchitectureReference({
    required this.id,
    required this.version,
    required this.digest,
  });

  factory PinnedArchitectureReference.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {'id', 'version', 'digest'}, 'profile ref');
    return PinnedArchitectureReference(
      id: JsonContract.requiredString(json, 'id'),
      version: _positiveVersion(json, 'version'),
      digest: _digest(json, 'digest'),
    );
  }

  @override
  List<Object?> get props => [id, version, digest];
}

class ArchitectureResponsibility extends Equatable {
  final String responsibilityId;
  final String displayName;
  final bool required;
  final List<String> capabilityIds;
  final List<String> workloadFieldIds;

  const ArchitectureResponsibility({
    required this.responsibilityId,
    required this.displayName,
    required this.required,
    required this.capabilityIds,
    required this.workloadFieldIds,
  });

  factory ArchitectureResponsibility.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'responsibility_id',
      'display_name',
      'required',
      'capability_ids',
      'workload_field_ids',
    }, 'architecture responsibility');
    return ArchitectureResponsibility(
      responsibilityId: JsonContract.requiredString(json, 'responsibility_id'),
      displayName: JsonContract.requiredString(json, 'display_name'),
      required: JsonContract.requiredBool(json, 'required'),
      capabilityIds: _requiredStringList(json, 'capability_ids'),
      workloadFieldIds: _requiredStringList(json, 'workload_field_ids'),
    );
  }

  @override
  List<Object?> get props => [
    responsibilityId,
    displayName,
    required,
    capabilityIds,
    workloadFieldIds,
  ];
}

class ArchitectureProviderAvailability extends Equatable {
  final CloudProvider provider;
  final bool supported;
  final String profileId;
  final String profileVersion;
  final List<String> reasonCodes;

  const ArchitectureProviderAvailability({
    required this.provider,
    required this.supported,
    required this.profileId,
    required this.profileVersion,
    required this.reasonCodes,
  });

  factory ArchitectureProviderAvailability.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'provider',
      'supported',
      'profile_id',
      'profile_version',
      'reason_codes',
    }, 'architecture provider');
    return ArchitectureProviderAvailability(
      provider: _provider(json['provider']),
      supported: JsonContract.requiredBool(json, 'supported'),
      profileId: JsonContract.requiredString(json, 'profile_id'),
      profileVersion: _positiveVersion(json, 'profile_version'),
      reasonCodes: _requiredStringList(json, 'reason_codes'),
    );
  }

  @override
  List<Object?> get props => [
    provider,
    supported,
    profileId,
    profileVersion,
    reasonCodes,
  ];
}

class ArchitectureExtensionSlotSummary extends Equatable {
  final String slotId;
  final String slotVersion;
  final String logicalComponentId;

  const ArchitectureExtensionSlotSummary({
    required this.slotId,
    required this.slotVersion,
    required this.logicalComponentId,
  });

  factory ArchitectureExtensionSlotSummary.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'slot_id',
      'slot_version',
      'logical_component_id',
    }, 'architecture extension slot');
    return ArchitectureExtensionSlotSummary(
      slotId: JsonContract.requiredString(json, 'slot_id'),
      slotVersion: _positiveVersion(json, 'slot_version'),
      logicalComponentId: JsonContract.requiredString(
        json,
        'logical_component_id',
      ),
    );
  }

  @override
  List<Object?> get props => [slotId, slotVersion, logicalComponentId];
}

class ArchitectureProfileSummary extends Equatable {
  static const _keys = {
    'profile_id',
    'profile_version',
    'profile_digest',
    'display_name',
    'description',
    'lifecycle_status',
    'responsibilities',
    'capability_ids',
    'workload_contract_ref',
    'available_providers',
    'unsupported_providers',
    'extension_slots',
  };

  final String profileId;
  final String profileVersion;
  final String profileDigest;
  final String displayName;
  final String description;
  final List<ArchitectureResponsibility> responsibilities;
  final List<String> capabilityIds;
  final PinnedArchitectureReference workloadContractRef;
  final List<ArchitectureProviderAvailability> availableProviders;
  final List<ArchitectureProviderAvailability> unsupportedProviders;
  final List<ArchitectureExtensionSlotSummary> extensionSlots;

  const ArchitectureProfileSummary({
    required this.profileId,
    required this.profileVersion,
    required this.profileDigest,
    required this.displayName,
    required this.description,
    required this.responsibilities,
    required this.capabilityIds,
    required this.workloadContractRef,
    required this.availableProviders,
    required this.unsupportedProviders,
    required this.extensionSlots,
  });

  factory ArchitectureProfileSummary.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, _keys, 'architecture profile summary');
    return ArchitectureProfileSummary._fromJsonFields(json);
  }

  factory ArchitectureProfileSummary._fromJsonFields(
    Map<String, dynamic> json,
  ) {
    if (json['lifecycle_status'] != 'active') {
      throw const FormatException(
        'Invalid API contract: catalog profile must be active.',
      );
    }
    final responsibilities = _objectList(
      json,
      'responsibilities',
      minLength: 1,
    ).map(ArchitectureResponsibility.fromJson).toList(growable: false);
    _requireUnique(
      responsibilities.map((item) => item.responsibilityId),
      'architecture responsibility IDs',
    );
    final availableProviders = _objectList(
      json,
      'available_providers',
    ).map(ArchitectureProviderAvailability.fromJson).toList(growable: false);
    final unsupportedProviders = _objectList(
      json,
      'unsupported_providers',
    ).map(ArchitectureProviderAvailability.fromJson).toList(growable: false);
    if (availableProviders.any((item) => !item.supported) ||
        unsupportedProviders.any((item) => item.supported)) {
      throw const FormatException(
        'Invalid API contract: provider availability groups disagree.',
      );
    }
    _requireUnique(
      [
        ...availableProviders,
        ...unsupportedProviders,
      ].map((item) => item.provider.apiValue),
      'architecture providers',
    );
    final extensionSlots = _objectList(
      json,
      'extension_slots',
    ).map(ArchitectureExtensionSlotSummary.fromJson).toList(growable: false);
    _requireUnique(
      extensionSlots.map((item) => '${item.slotId}@${item.slotVersion}'),
      'architecture extension slots',
    );
    return ArchitectureProfileSummary(
      profileId: JsonContract.requiredString(json, 'profile_id'),
      profileVersion: _positiveVersion(json, 'profile_version'),
      profileDigest: _digest(json, 'profile_digest'),
      displayName: JsonContract.requiredString(json, 'display_name'),
      description: JsonContract.requiredString(json, 'description'),
      responsibilities: List.unmodifiable(responsibilities),
      capabilityIds: _requiredStringList(json, 'capability_ids'),
      workloadContractRef: PinnedArchitectureReference.fromJson(
        JsonContract.requiredObject(json, 'workload_contract_ref'),
      ),
      availableProviders: List.unmodifiable(availableProviders),
      unsupportedProviders: List.unmodifiable(unsupportedProviders),
      extensionSlots: List.unmodifiable(extensionSlots),
    );
  }

  PinnedArchitectureReference get ref => PinnedArchitectureReference(
    id: profileId,
    version: profileVersion,
    digest: profileDigest,
  );

  Set<String> get workloadFieldIds => Set.unmodifiable(
    responsibilities.expand((item) => item.workloadFieldIds),
  );

  @override
  List<Object?> get props => [
    profileId,
    profileVersion,
    profileDigest,
    displayName,
    description,
    responsibilities,
    capabilityIds,
    workloadContractRef,
    availableProviders,
    unsupportedProviders,
    extensionSlots,
  ];
}

class LogicalArchitectureComponent extends Equatable {
  final String componentId;
  final String componentKind;
  final String responsibilityId;
  final bool required;
  final List<String> requiredCapabilityIds;
  final List<String> inputPortIds;
  final List<String> outputPortIds;
  final List<String> extensionSlotIds;
  final List<String> costOwnerIds;
  final String observabilityContractId;

  const LogicalArchitectureComponent({
    required this.componentId,
    required this.componentKind,
    required this.responsibilityId,
    required this.required,
    required this.requiredCapabilityIds,
    required this.inputPortIds,
    required this.outputPortIds,
    required this.extensionSlotIds,
    required this.costOwnerIds,
    required this.observabilityContractId,
  });

  factory LogicalArchitectureComponent.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'component_id',
      'component_kind',
      'cost_owner_ids',
      'extension_slot_ids',
      'input_port_ids',
      'observability_contract_id',
      'output_port_ids',
      'required',
      'required_capability_ids',
      'responsibility_id',
    }, 'logical architecture component');
    return LogicalArchitectureComponent(
      componentId: JsonContract.requiredString(json, 'component_id'),
      componentKind: JsonContract.requiredString(json, 'component_kind'),
      responsibilityId: JsonContract.requiredString(json, 'responsibility_id'),
      required: JsonContract.requiredBool(json, 'required'),
      requiredCapabilityIds: _requiredStringList(
        json,
        'required_capability_ids',
      ),
      inputPortIds: _requiredStringList(json, 'input_port_ids'),
      outputPortIds: _requiredStringList(json, 'output_port_ids'),
      extensionSlotIds: _requiredStringList(json, 'extension_slot_ids'),
      costOwnerIds: _requiredStringList(json, 'cost_owner_ids'),
      observabilityContractId: JsonContract.requiredString(
        json,
        'observability_contract_id',
      ),
    );
  }

  @override
  List<Object?> get props => [
    componentId,
    componentKind,
    responsibilityId,
    required,
    requiredCapabilityIds,
    inputPortIds,
    outputPortIds,
    extensionSlotIds,
    costOwnerIds,
    observabilityContractId,
  ];
}

class LogicalArchitectureEdge extends Equatable {
  final String edgeId;
  final String sourceComponentId;
  final String sourcePortId;
  final String destinationComponentId;
  final String destinationPortId;
  final String edgeContractId;
  final String edgeContractVersion;
  final bool required;
  final List<String> costOwnerIds;
  final String transferWorkloadId;
  final String deliveryMode;
  final String ordering;

  const LogicalArchitectureEdge({
    required this.edgeId,
    required this.sourceComponentId,
    required this.sourcePortId,
    required this.destinationComponentId,
    required this.destinationPortId,
    required this.edgeContractId,
    required this.edgeContractVersion,
    required this.required,
    required this.costOwnerIds,
    required this.transferWorkloadId,
    required this.deliveryMode,
    required this.ordering,
  });

  factory LogicalArchitectureEdge.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'cost_owner_ids',
      'delivery_requirements',
      'destination_component_id',
      'destination_port_id',
      'edge_contract_id',
      'edge_contract_version',
      'edge_id',
      'observability_requirements',
      'required',
      'source_component_id',
      'source_port_id',
      'transfer_workload_ref',
      'trust_requirements',
    }, 'logical architecture edge');
    final delivery = JsonContract.requiredObject(json, 'delivery_requirements');
    _expectExactKeys(delivery, const {
      'dead_letter_policy',
      'idempotency',
      'mode',
      'ordering',
      'replay',
      'retry_policy',
      'timeout_policy',
    }, 'logical architecture delivery requirements');
    final observability = JsonContract.requiredObject(
      json,
      'observability_requirements',
    );
    _expectExactKeys(observability, const {
      'bounded_error_contract',
      'correlation',
      'metrics',
    }, 'logical architecture observability requirements');
    final trust = JsonContract.requiredObject(json, 'trust_requirements');
    _expectExactKeys(trust, const {
      'authentication',
      'authorization',
      'transport',
    }, 'logical architecture trust requirements');
    final workload = JsonContract.requiredObject(json, 'transfer_workload_ref');
    _expectExactKeys(workload, const {
      'id',
      'version',
    }, 'logical architecture transfer workload');
    JsonContract.requiredString(observability, 'bounded_error_contract');
    JsonContract.requiredString(observability, 'correlation');
    JsonContract.requiredString(observability, 'metrics');
    JsonContract.requiredString(trust, 'authentication');
    JsonContract.requiredString(trust, 'authorization');
    JsonContract.requiredString(trust, 'transport');
    _positiveVersion(workload, 'version');
    return LogicalArchitectureEdge(
      edgeId: JsonContract.requiredString(json, 'edge_id'),
      sourceComponentId: JsonContract.requiredString(
        json,
        'source_component_id',
      ),
      sourcePortId: JsonContract.requiredString(json, 'source_port_id'),
      destinationComponentId: JsonContract.requiredString(
        json,
        'destination_component_id',
      ),
      destinationPortId: JsonContract.requiredString(
        json,
        'destination_port_id',
      ),
      edgeContractId: JsonContract.requiredString(json, 'edge_contract_id'),
      edgeContractVersion: _positiveVersion(json, 'edge_contract_version'),
      required: JsonContract.requiredBool(json, 'required'),
      costOwnerIds: _requiredStringList(json, 'cost_owner_ids'),
      transferWorkloadId: JsonContract.requiredString(workload, 'id'),
      deliveryMode: JsonContract.requiredString(delivery, 'mode'),
      ordering: JsonContract.requiredString(delivery, 'ordering'),
    );
  }

  @override
  List<Object?> get props => [
    edgeId,
    sourceComponentId,
    sourcePortId,
    destinationComponentId,
    destinationPortId,
    edgeContractId,
    edgeContractVersion,
    required,
    costOwnerIds,
    transferWorkloadId,
    deliveryMode,
    ordering,
  ];
}

class ArchitectureVisualizationNode extends Equatable {
  final String id;
  final String label;
  final String responsibilityId;

  const ArchitectureVisualizationNode({
    required this.id,
    required this.label,
    required this.responsibilityId,
  });

  factory ArchitectureVisualizationNode.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'id',
      'label',
      'responsibility_id',
    }, 'architecture visualization node');
    return ArchitectureVisualizationNode(
      id: JsonContract.requiredString(json, 'id'),
      label: JsonContract.requiredString(json, 'label'),
      responsibilityId: JsonContract.requiredString(json, 'responsibility_id'),
    );
  }

  @override
  List<Object?> get props => [id, label, responsibilityId];
}

class ArchitectureVisualizationEdge extends Equatable {
  final String id;
  final String source;
  final String destination;

  const ArchitectureVisualizationEdge({
    required this.id,
    required this.source,
    required this.destination,
  });

  factory ArchitectureVisualizationEdge.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'id',
      'source',
      'destination',
    }, 'architecture visualization edge');
    return ArchitectureVisualizationEdge(
      id: JsonContract.requiredString(json, 'id'),
      source: JsonContract.requiredString(json, 'source'),
      destination: JsonContract.requiredString(json, 'destination'),
    );
  }

  @override
  List<Object?> get props => [id, source, destination];
}

class ArchitectureVisualization extends Equatable {
  final List<ArchitectureVisualizationNode> nodes;
  final List<ArchitectureVisualizationEdge> edges;

  const ArchitectureVisualization({required this.nodes, required this.edges});

  factory ArchitectureVisualization.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'nodes',
      'edges',
    }, 'architecture visualization');
    final nodes = _objectList(
      json,
      'nodes',
      minLength: 1,
    ).map(ArchitectureVisualizationNode.fromJson).toList(growable: false);
    final edges = _objectList(
      json,
      'edges',
    ).map(ArchitectureVisualizationEdge.fromJson).toList(growable: false);
    _requireUnique(nodes.map((item) => item.id), 'visualization node IDs');
    _requireUnique(edges.map((item) => item.id), 'visualization edge IDs');
    final nodeIds = nodes.map((item) => item.id).toSet();
    if (edges.any(
      (item) =>
          !nodeIds.contains(item.source) || !nodeIds.contains(item.destination),
    )) {
      throw const FormatException(
        'Invalid API contract: visualization edge reference is unresolved.',
      );
    }
    return ArchitectureVisualization(
      nodes: List.unmodifiable(nodes),
      edges: List.unmodifiable(edges),
    );
  }

  @override
  List<Object?> get props => [nodes, edges];
}

class ArchitectureProfileDetail extends Equatable {
  final ArchitectureProfileSummary summary;
  final List<LogicalArchitectureComponent> logicalComponents;
  final List<LogicalArchitectureEdge> logicalEdges;
  final ArchitectureVisualization visualization;

  const ArchitectureProfileDetail({
    required this.summary,
    required this.logicalComponents,
    required this.logicalEdges,
    required this.visualization,
  });

  factory ArchitectureProfileDetail.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, {
      ...ArchitectureProfileSummary._keys,
      'logical_components',
      'logical_edges',
      'visualization',
    }, 'architecture profile detail');
    final components = _objectList(
      json,
      'logical_components',
      minLength: 1,
    ).map(LogicalArchitectureComponent.fromJson).toList(growable: false);
    final edges = _objectList(
      json,
      'logical_edges',
    ).map(LogicalArchitectureEdge.fromJson).toList(growable: false);
    _requireUnique(components.map((item) => item.componentId), 'component IDs');
    _requireUnique(edges.map((item) => item.edgeId), 'logical edge IDs');
    final componentIds = components.map((item) => item.componentId).toSet();
    if (edges.any(
      (item) =>
          !componentIds.contains(item.sourceComponentId) ||
          !componentIds.contains(item.destinationComponentId),
    )) {
      throw const FormatException(
        'Invalid API contract: logical edge component reference is unresolved.',
      );
    }
    final summary = ArchitectureProfileSummary._fromJsonFields(json);
    final responsibilityIds = summary.responsibilities
        .map((item) => item.responsibilityId)
        .toSet();
    if (components.any(
      (item) => !responsibilityIds.contains(item.responsibilityId),
    )) {
      throw const FormatException(
        'Invalid API contract: component responsibility is unresolved.',
      );
    }
    final visualization = ArchitectureVisualization.fromJson(
      JsonContract.requiredObject(json, 'visualization'),
    );
    final visualizationNodeIds = visualization.nodes
        .map((item) => item.id)
        .toSet();
    final visualizationEdgeIds = visualization.edges
        .map((item) => item.id)
        .toSet();
    if (visualizationNodeIds.length != componentIds.length ||
        !visualizationNodeIds.containsAll(componentIds) ||
        visualizationEdgeIds.length != edges.length ||
        !visualizationEdgeIds.containsAll(edges.map((item) => item.edgeId))) {
      throw const FormatException(
        'Invalid API contract: visualization does not match the logical graph.',
      );
    }
    if (summary.extensionSlots.any(
      (item) => !componentIds.contains(item.logicalComponentId),
    )) {
      throw const FormatException(
        'Invalid API contract: extension slot component is unresolved.',
      );
    }
    return ArchitectureProfileDetail(
      summary: summary,
      logicalComponents: List.unmodifiable(components),
      logicalEdges: List.unmodifiable(edges),
      visualization: visualization,
    );
  }

  @override
  List<Object?> get props => [
    summary,
    logicalComponents,
    logicalEdges,
    visualization,
  ];
}

class TwinArchitectureSelection extends Equatable {
  final String twinId;
  final PinnedArchitectureReference profileRef;
  final int revision;
  final DateTime selectedAt;
  final DateTime updatedAt;
  final String selectedByUserId;

  const TwinArchitectureSelection({
    required this.twinId,
    required this.profileRef,
    required this.revision,
    required this.selectedAt,
    required this.updatedAt,
    required this.selectedByUserId,
  });

  factory TwinArchitectureSelection.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'twin_id',
      'profile_id',
      'profile_version',
      'profile_digest',
      'revision',
      'selected_at',
      'updated_at',
      'selected_by_user_id',
    }, 'architecture selection');
    final revision = JsonContract.requiredInt(json, 'revision');
    if (revision < 1) {
      throw const FormatException(
        'Invalid API contract: architecture revision must be positive.',
      );
    }
    return TwinArchitectureSelection(
      twinId: JsonContract.requiredString(json, 'twin_id'),
      profileRef: PinnedArchitectureReference(
        id: JsonContract.requiredString(json, 'profile_id'),
        version: _positiveVersion(json, 'profile_version'),
        digest: _digest(json, 'profile_digest'),
      ),
      revision: revision,
      selectedAt: JsonContract.requiredDate(json, 'selected_at'),
      updatedAt: JsonContract.requiredDate(json, 'updated_at'),
      selectedByUserId: JsonContract.requiredString(
        json,
        'selected_by_user_id',
      ),
    );
  }

  @override
  List<Object?> get props => [
    twinId,
    profileRef,
    revision,
    selectedAt,
    updatedAt,
    selectedByUserId,
  ];
}

class ArchitectureProfileChangePreviewRequest extends Equatable {
  final String profileId;
  final String profileVersion;
  final int expectedRevision;

  const ArchitectureProfileChangePreviewRequest({
    required this.profileId,
    required this.profileVersion,
    required this.expectedRevision,
  });

  Map<String, dynamic> toJson() => {
    'profile_id': profileId,
    'profile_version': profileVersion,
    'expected_revision': expectedRevision,
  };

  @override
  List<Object?> get props => [profileId, profileVersion, expectedRevision];
}

class ArchitectureProfileSelectRequest extends Equatable {
  final String profileId;
  final String profileVersion;
  final int expectedRevision;
  final String invalidationDigest;

  const ArchitectureProfileSelectRequest({
    required this.profileId,
    required this.profileVersion,
    required this.expectedRevision,
    required this.invalidationDigest,
  });

  factory ArchitectureProfileSelectRequest.fromPreview(
    ArchitectureProfileChangePreview preview,
  ) => ArchitectureProfileSelectRequest(
    profileId: preview.target.id,
    profileVersion: preview.target.version,
    expectedRevision: preview.expectedRevision,
    invalidationDigest: preview.invalidationDigest,
  );

  Map<String, dynamic> toJson() => {
    'profile_id': profileId,
    'profile_version': profileVersion,
    'expected_revision': expectedRevision,
    'invalidation_digest': invalidationDigest,
  };

  @override
  List<Object?> get props => [
    profileId,
    profileVersion,
    expectedRevision,
    invalidationDigest,
  ];
}

class IncompatibleWorkloadField extends Equatable {
  final String fieldId;
  final String displayLabel;

  const IncompatibleWorkloadField({
    required this.fieldId,
    required this.displayLabel,
  });

  factory IncompatibleWorkloadField.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'field_id',
      'display_label',
    }, 'incompatible workload field');
    return IncompatibleWorkloadField(
      fieldId: JsonContract.requiredString(json, 'field_id'),
      displayLabel: JsonContract.requiredString(json, 'display_label'),
    );
  }

  @override
  List<Object?> get props => [fieldId, displayLabel];
}

class IncompatibleExtensionBinding extends Equatable {
  final String slotId;
  final String slotVersion;
  final String artifactId;

  const IncompatibleExtensionBinding({
    required this.slotId,
    required this.slotVersion,
    required this.artifactId,
  });

  factory IncompatibleExtensionBinding.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'slot_id',
      'slot_version',
      'artifact_id',
    }, 'incompatible extension binding');
    return IncompatibleExtensionBinding(
      slotId: JsonContract.requiredString(json, 'slot_id'),
      slotVersion: _positiveVersion(json, 'slot_version'),
      artifactId: JsonContract.requiredString(json, 'artifact_id'),
    );
  }

  @override
  List<Object?> get props => [slotId, slotVersion, artifactId];
}

class ArchitectureProfileChangePreview extends Equatable {
  final PinnedArchitectureReference current;
  final PinnedArchitectureReference target;
  final int expectedRevision;
  final List<IncompatibleWorkloadField> incompatibleWorkloadFields;
  final List<IncompatibleExtensionBinding> incompatibleExtensionBindings;
  final String? selectedCalculationRunId;
  final List<String> deploymentReadinessSections;
  final String invalidationDigest;

  const ArchitectureProfileChangePreview({
    required this.current,
    required this.target,
    required this.expectedRevision,
    required this.incompatibleWorkloadFields,
    required this.incompatibleExtensionBindings,
    required this.selectedCalculationRunId,
    required this.deploymentReadinessSections,
    required this.invalidationDigest,
  });

  factory ArchitectureProfileChangePreview.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'current',
      'target',
      'expected_revision',
      'incompatible_workload_fields',
      'incompatible_extension_bindings',
      'selected_calculation_run_id',
      'deployment_readiness_sections',
      'invalidation_digest',
    }, 'architecture profile change preview');
    final revision = JsonContract.requiredInt(json, 'expected_revision');
    if (revision < 1) {
      throw const FormatException(
        'Invalid API contract: expected revision must be positive.',
      );
    }
    return ArchitectureProfileChangePreview(
      current: PinnedArchitectureReference.fromJson(
        JsonContract.requiredObject(json, 'current'),
      ),
      target: PinnedArchitectureReference.fromJson(
        JsonContract.requiredObject(json, 'target'),
      ),
      expectedRevision: revision,
      incompatibleWorkloadFields: List.unmodifiable(
        _objectList(
          json,
          'incompatible_workload_fields',
        ).map(IncompatibleWorkloadField.fromJson),
      ),
      incompatibleExtensionBindings: List.unmodifiable(
        _objectList(
          json,
          'incompatible_extension_bindings',
        ).map(IncompatibleExtensionBinding.fromJson),
      ),
      selectedCalculationRunId: JsonContract.optionalString(
        json,
        'selected_calculation_run_id',
      ),
      deploymentReadinessSections: _requiredStringList(
        json,
        'deployment_readiness_sections',
      ),
      invalidationDigest: _digest(json, 'invalidation_digest'),
    );
  }

  @override
  List<Object?> get props => [
    current,
    target,
    expectedRevision,
    incompatibleWorkloadFields,
    incompatibleExtensionBindings,
    selectedCalculationRunId,
    deploymentReadinessSections,
    invalidationDigest,
  ];
}

class ArchitectureProfileSelectionResult extends Equatable {
  final TwinArchitectureSelection selection;
  final int revision;
  final String? invalidatedCalculationRunId;
  final List<String> unboundExtensionSlotIds;
  final List<String> clearedWorkloadFieldIds;
  final String deploymentReadinessState;

  const ArchitectureProfileSelectionResult({
    required this.selection,
    required this.revision,
    required this.invalidatedCalculationRunId,
    required this.unboundExtensionSlotIds,
    required this.clearedWorkloadFieldIds,
    required this.deploymentReadinessState,
  });

  factory ArchitectureProfileSelectionResult.fromJson(
    Map<String, dynamic> json,
  ) {
    _expectExactKeys(json, const {
      'selection',
      'revision',
      'invalidated_calculation_run_id',
      'unbound_extension_slot_ids',
      'cleared_workload_field_ids',
      'deployment_readiness_state',
    }, 'architecture selection result');
    final selection = TwinArchitectureSelection.fromJson(
      JsonContract.requiredObject(json, 'selection'),
    );
    final revision = JsonContract.requiredInt(json, 'revision');
    if (revision != selection.revision) {
      throw const FormatException(
        'Invalid API contract: architecture selection revisions differ.',
      );
    }
    final readiness = JsonContract.requiredString(
      json,
      'deployment_readiness_state',
    );
    if (!{'unchanged', 'invalidated'}.contains(readiness)) {
      throw const FormatException(
        'Invalid API contract: deployment readiness state is unsupported.',
      );
    }
    return ArchitectureProfileSelectionResult(
      selection: selection,
      revision: revision,
      invalidatedCalculationRunId: JsonContract.optionalString(
        json,
        'invalidated_calculation_run_id',
      ),
      unboundExtensionSlotIds: _requiredStringList(
        json,
        'unbound_extension_slot_ids',
      ),
      clearedWorkloadFieldIds: _requiredStringList(
        json,
        'cleared_workload_field_ids',
      ),
      deploymentReadinessState: readiness,
    );
  }

  @override
  List<Object?> get props => [
    selection,
    revision,
    invalidatedCalculationRunId,
    unboundExtensionSlotIds,
    clearedWorkloadFieldIds,
    deploymentReadinessState,
  ];
}

void _expectExactKeys(
  Map<String, dynamic> json,
  Set<String> expected,
  String contract,
) {
  if (json.keys.toSet().difference(expected).isNotEmpty ||
      expected.difference(json.keys.toSet()).isNotEmpty) {
    throw FormatException(
      'Invalid API contract: $contract fields do not match v1.',
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

CloudProvider _provider(Object? value) => CloudProvider.values.firstWhere(
  (candidate) => candidate.apiValue == value,
  orElse: () => throw const FormatException(
    'Invalid API contract: architecture provider is unsupported.',
  ),
);
