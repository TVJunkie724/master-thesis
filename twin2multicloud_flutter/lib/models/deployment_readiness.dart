import 'package:equatable/equatable.dart';

import '../core/result.dart';
import 'cloud_connection.dart';

enum DeploymentReadinessSource { cached, preflight }

enum DeploymentReadinessCheckStatus {
  passed('passed'),
  failed('failed');

  final String apiValue;

  const DeploymentReadinessCheckStatus(this.apiValue);

  static DeploymentReadinessCheckStatus parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw _contractError('$field contains an unknown status.'),
    );
  }
}

enum ProviderDeploymentReadinessStatus {
  ready('ready'),
  reviewRequired('review_required'),
  notChecked('not_checked'),
  stale('stale');

  final String apiValue;

  const ProviderDeploymentReadinessStatus(this.apiValue);

  static ProviderDeploymentReadinessStatus parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw _contractError('$field contains an unknown status.'),
    );
  }
}

enum DeploymentRequirementReadinessStatus {
  ready('ready'),
  preparable('preparable'),
  manualAction('manual_action'),
  replaceConnection('replace_connection'),
  transient('transient'),
  unsupported('unsupported');

  final String apiValue;

  const DeploymentRequirementReadinessStatus(this.apiValue);

  static DeploymentRequirementReadinessStatus parse(
    Object? value,
    String field,
  ) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw _contractError('$field contains an unknown status.'),
    );
  }
}

enum DeploymentPreparationMode {
  none('none'),
  confirmedAccount('confirmed_account'),
  manualExternal('manual_external'),
  terraform('terraform');

  final String apiValue;

  const DeploymentPreparationMode(this.apiValue);

  static DeploymentPreparationMode parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw _contractError('$field contains an unknown mode.'),
    );
  }
}

class DeploymentRequirementReadiness extends Equatable {
  final String requirementId;
  final String requirementType;
  final CloudProvider provider;
  final String capabilityId;
  final DeploymentPreparationMode preparationMode;
  final bool mandatory;
  final DeploymentRequirementReadinessStatus status;
  final String message;
  final String action;
  final List<String> sourceNodeIds;
  final List<String> sourceEdgeIds;

  const DeploymentRequirementReadiness({
    required this.requirementId,
    required this.requirementType,
    required this.provider,
    required this.capabilityId,
    required this.preparationMode,
    required this.mandatory,
    required this.status,
    required this.message,
    required this.action,
    required this.sourceNodeIds,
    required this.sourceEdgeIds,
  });

  factory DeploymentRequirementReadiness.fromJson(
    Map<String, dynamic> json,
    String path,
  ) {
    return DeploymentRequirementReadiness(
      requirementId: _boundedString(
        json,
        'requirement_id',
        path,
        maxLength: 300,
      ),
      requirementType: _boundedString(
        json,
        'requirement_type',
        path,
        maxLength: 80,
      ),
      provider: _provider(json['provider'], '$path.provider'),
      capabilityId: _boundedString(json, 'capability_id', path, maxLength: 300),
      preparationMode: DeploymentPreparationMode.parse(
        json['preparation_mode'],
        '$path.preparation_mode',
      ),
      mandatory: _requiredBool(json, 'mandatory', path),
      status: DeploymentRequirementReadinessStatus.parse(
        json['status'],
        '$path.status',
      ),
      message: _boundedString(json, 'message', path, maxLength: 2000),
      action: _boundedString(json, 'action', path, maxLength: 2000),
      sourceNodeIds: _boundedStringList(
        json,
        'source_node_ids',
        path,
        maxItems: 512,
        maxLength: 300,
      ),
      sourceEdgeIds: _boundedStringList(
        json,
        'source_edge_ids',
        path,
        maxItems: 512,
        maxLength: 300,
      ),
    );
  }

  @override
  List<Object?> get props => [
    requirementId,
    requirementType,
    provider,
    capabilityId,
    preparationMode,
    mandatory,
    status,
    message,
    action,
    sourceNodeIds,
    sourceEdgeIds,
  ];
}

class AccountPreparationAction extends Equatable {
  final String actionId;
  final CloudProvider provider;
  final String actionType;
  final String capabilityId;
  final String scope;
  final List<String> requirementIds;
  final String reason;

  const AccountPreparationAction({
    required this.actionId,
    required this.provider,
    required this.actionType,
    required this.capabilityId,
    required this.scope,
    required this.requirementIds,
    required this.reason,
  });

  factory AccountPreparationAction.fromJson(
    Map<String, dynamic> json,
    String path,
  ) {
    final provider = _provider(json['provider'], '$path.provider');
    if (provider == CloudProvider.aws) {
      throw _contractError('$path.provider is not automatically preparable.');
    }
    final actionType = _boundedString(json, 'action_type', path, maxLength: 80);
    if (!{
      'register_resource_provider',
      'enable_project_api',
    }.contains(actionType)) {
      throw _contractError('$path.action_type is unsupported.');
    }
    if (json['persistent_after_destroy'] is! bool ||
        json['persistent_after_destroy'] != true ||
        json['destructive'] is! bool ||
        json['destructive'] != false) {
      throw _contractError('$path mutation flags are invalid.');
    }
    final requirementIds = _boundedStringList(
      json,
      'requirement_ids',
      path,
      maxItems: 64,
      maxLength: 300,
    );
    if (requirementIds.isEmpty) {
      throw _contractError('$path.requirement_ids must not be empty.');
    }
    return AccountPreparationAction(
      actionId: _boundedString(json, 'action_id', path, maxLength: 500),
      provider: provider,
      actionType: actionType,
      capabilityId: _boundedString(json, 'capability_id', path, maxLength: 300),
      scope: _boundedString(json, 'scope', path, maxLength: 80),
      requirementIds: requirementIds,
      reason: _boundedString(json, 'reason', path, maxLength: 2000),
    );
  }

  @override
  List<Object?> get props => [
    actionId,
    provider,
    actionType,
    capabilityId,
    scope,
    requirementIds,
    reason,
  ];
}

class ManualPreparationRequirement extends Equatable {
  final String requirementId;
  final CloudProvider provider;
  final String capabilityId;
  final String reason;

  const ManualPreparationRequirement({
    required this.requirementId,
    required this.provider,
    required this.capabilityId,
    required this.reason,
  });

  factory ManualPreparationRequirement.fromJson(
    Map<String, dynamic> json,
    String path,
  ) {
    return ManualPreparationRequirement(
      requirementId: _boundedString(
        json,
        'requirement_id',
        path,
        maxLength: 300,
      ),
      provider: _provider(json['provider'], '$path.provider'),
      capabilityId: _boundedString(json, 'capability_id', path, maxLength: 300),
      reason: _boundedString(json, 'reason', path, maxLength: 2000),
    );
  }

  @override
  List<Object?> get props => [requirementId, provider, capabilityId, reason];
}

class DeploymentPreparationPlan extends Equatable {
  static const schemaVersion = 'graph-account-preparation.v1';

  final String graphDigest;
  final String requirementsDigest;
  final String planDigest;
  final List<AccountPreparationAction> actions;
  final List<ManualPreparationRequirement> manualRequirements;

  const DeploymentPreparationPlan({
    required this.graphDigest,
    required this.requirementsDigest,
    required this.planDigest,
    required this.actions,
    required this.manualRequirements,
  });

  bool get needsReview => actions.isNotEmpty || manualRequirements.isNotEmpty;

  factory DeploymentPreparationPlan.fromJson(
    Map<String, dynamic> json,
    String path,
  ) {
    if (json['schema_version'] != schemaVersion) {
      throw _contractError('$path.schema_version is unsupported.');
    }
    final rawActions = _requiredList(json, 'actions', path);
    final rawManual = _requiredList(json, 'manual_requirements', path);
    if (rawActions.length > 4096 || rawManual.length > 4096) {
      throw _contractError('$path preparation evidence is too large.');
    }
    final actions = rawActions.indexed
        .map(
          (entry) => AccountPreparationAction.fromJson(
            _asMap(entry.$2, '$path.actions[${entry.$1}]'),
            '$path.actions[${entry.$1}]',
          ),
        )
        .toList(growable: false);
    final manual = rawManual.indexed
        .map(
          (entry) => ManualPreparationRequirement.fromJson(
            _asMap(entry.$2, '$path.manual_requirements[${entry.$1}]'),
            '$path.manual_requirements[${entry.$1}]',
          ),
        )
        .toList(growable: false);
    if (!_isSorted(actions.map((item) => item.actionId)) ||
        !_isSorted(manual.map((item) => item.requirementId))) {
      throw _contractError('$path preparation evidence must be sorted.');
    }
    return DeploymentPreparationPlan(
      graphDigest: _contentDigest(json['graph_digest'], '$path.graph_digest'),
      requirementsDigest: _contentDigest(
        json['requirements_digest'],
        '$path.requirements_digest',
      ),
      planDigest: _contentDigest(json['plan_digest'], '$path.plan_digest'),
      actions: List.unmodifiable(actions),
      manualRequirements: List.unmodifiable(manual),
    );
  }

  @override
  List<Object?> get props => [
    graphDigest,
    requirementsDigest,
    planDigest,
    actions,
    manualRequirements,
  ];
}

class DeploymentPreparationRequest extends Equatable {
  final String planDigest;
  final String requirementsDigest;
  final List<String> manualRequirementIds;

  DeploymentPreparationRequest({
    required this.planDigest,
    required this.requirementsDigest,
    Iterable<String> manualRequirementIds = const [],
  }) : manualRequirementIds = List.unmodifiable(
         (manualRequirementIds.toSet().toList()..sort()),
       ) {
    _contentDigest(planDigest, 'plan_digest');
    _contentDigest(requirementsDigest, 'requirements_digest');
  }

  Map<String, dynamic> toJson() => {
    'plan_digest': planDigest,
    'requirements_digest': requirementsDigest,
    'confirmed': true,
    'manual_requirement_ids': manualRequirementIds,
  };

  @override
  List<Object?> get props => [
    planDigest,
    requirementsDigest,
    manualRequirementIds,
  ];
}

enum DeploymentPreparationStatus {
  ready('ready'),
  partial('partial'),
  failed('failed'),
  manualAction('manual_action');

  final String apiValue;

  const DeploymentPreparationStatus(this.apiValue);

  static DeploymentPreparationStatus parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw _contractError('$field contains an unknown status.'),
    );
  }
}

class PreparationActionResult extends Equatable {
  final String actionId;
  final CloudProvider provider;
  final String capabilityId;
  final bool succeeded;
  final String message;

  const PreparationActionResult({
    required this.actionId,
    required this.provider,
    required this.capabilityId,
    required this.succeeded,
    required this.message,
  });

  factory PreparationActionResult.fromJson(
    Map<String, dynamic> json,
    String path, {
    required bool expectedSuccess,
  }) {
    final status = json['status'];
    if (status != (expectedSuccess ? 'ready' : 'failed')) {
      throw _contractError('$path.status is inconsistent.');
    }
    return PreparationActionResult(
      actionId: _boundedString(json, 'action_id', path, maxLength: 500),
      provider: _provider(json['provider'], '$path.provider'),
      capabilityId: _boundedString(json, 'capability_id', path, maxLength: 300),
      succeeded: expectedSuccess,
      message: _boundedString(json, 'message', path, maxLength: 2000),
    );
  }

  @override
  List<Object?> get props => [
    actionId,
    provider,
    capabilityId,
    succeeded,
    message,
  ];
}

class DeploymentPreparationResponse extends Equatable {
  static const schemaVersion = 'deployment-preparation.v1';

  final String twinId;
  final String planDigest;
  final String requirementsDigest;
  final DeploymentPreparationStatus status;
  final List<PreparationActionResult> completedActions;
  final List<PreparationActionResult> failedActions;
  final List<String> remainingActionIds;
  final List<String> acknowledgedManualRequirementIds;
  final List<String> pendingManualRequirementIds;
  final DeploymentReadinessSnapshot readiness;

  const DeploymentPreparationResponse({
    required this.twinId,
    required this.planDigest,
    required this.requirementsDigest,
    required this.status,
    required this.completedActions,
    required this.failedActions,
    required this.remainingActionIds,
    required this.acknowledgedManualRequirementIds,
    required this.pendingManualRequirementIds,
    required this.readiness,
  });

  factory DeploymentPreparationResponse.fromJson(
    Map<String, dynamic> json, {
    required String expectedTwinId,
    required DeploymentPreparationRequest expectedRequest,
  }) {
    if (json['schema_version'] != schemaVersion) {
      throw _contractError(
        'Unsupported deployment preparation schema version.',
      );
    }
    final twinId = _boundedString(json, 'twin_id', 'root', maxLength: 160);
    if (twinId != expectedTwinId) {
      throw _contractError('Deployment preparation belongs to another twin.');
    }
    final planDigest = _contentDigest(json['plan_digest'], 'root.plan_digest');
    final requirementsDigest = _contentDigest(
      json['requirements_digest'],
      'root.requirements_digest',
    );
    if (planDigest != expectedRequest.planDigest ||
        requirementsDigest != expectedRequest.requirementsDigest) {
      throw _contractError('Deployment preparation evidence is stale.');
    }
    if (json['retry_safe'] != true) {
      throw _contractError('Deployment preparation is not retry-safe.');
    }
    final completed = _preparationResults(
      json,
      'completed_actions',
      expectedSuccess: true,
    );
    final failed = _preparationResults(
      json,
      'failed_actions',
      expectedSuccess: false,
    );
    final completedIds = completed.map((item) => item.actionId).toSet();
    final failedIds = failed.map((item) => item.actionId).toSet();
    if (completedIds.intersection(failedIds).isNotEmpty) {
      throw _contractError('Deployment preparation evidence is contradictory.');
    }
    final remaining = _boundedUniqueStringList(
      json,
      'remaining_action_ids',
      'root',
      maxItems: 4096,
      maxLength: 500,
    );
    if (remaining.toSet().difference(failedIds).isNotEmpty ||
        failedIds.difference(remaining.toSet()).isNotEmpty) {
      throw _contractError('Remaining preparation actions are inconsistent.');
    }
    final acknowledged = _boundedUniqueStringList(
      json,
      'acknowledged_manual_requirement_ids',
      'root',
      maxItems: 4096,
      maxLength: 300,
    );
    final pending = _boundedUniqueStringList(
      json,
      'pending_manual_requirement_ids',
      'root',
      maxItems: 4096,
      maxLength: 300,
    );
    if (acknowledged.toSet().intersection(pending.toSet()).isNotEmpty) {
      throw _contractError('Manual preparation evidence is contradictory.');
    }
    final readiness = DeploymentReadinessSnapshot.fromPreflightJson(
      _asMap(json['readiness'], 'root.readiness'),
      expectedTwinId: twinId,
    );
    if (readiness.requirementsDigest != requirementsDigest) {
      throw _contractError(
        'Prepared readiness is bound to different requirements.',
      );
    }
    return DeploymentPreparationResponse(
      twinId: twinId,
      planDigest: planDigest,
      requirementsDigest: requirementsDigest,
      status: DeploymentPreparationStatus.parse(json['status'], 'root.status'),
      completedActions: List.unmodifiable(completed),
      failedActions: List.unmodifiable(failed),
      remainingActionIds: remaining,
      acknowledgedManualRequirementIds: acknowledged,
      pendingManualRequirementIds: pending,
      readiness: readiness,
    );
  }

  String get summary => switch (status) {
    DeploymentPreparationStatus.ready =>
      'Provider preparation completed and readiness passed.',
    DeploymentPreparationStatus.partial =>
      'Preparation needs review before deployment.',
    DeploymentPreparationStatus.failed =>
      'Provider preparation failed; review the failed actions and retry.',
    DeploymentPreparationStatus.manualAction =>
      'External provider steps remain before deployment.',
  };

  @override
  List<Object?> get props => [
    twinId,
    planDigest,
    requirementsDigest,
    status,
    completedActions,
    failedActions,
    remainingActionIds,
    acknowledgedManualRequirementIds,
    pendingManualRequirementIds,
    readiness,
  ];
}

class DeploymentReadinessCheck extends Equatable {
  final String component;
  final DeploymentReadinessCheckStatus status;
  final String code;
  final String message;
  final String action;
  final List<String> permissions;

  const DeploymentReadinessCheck({
    required this.component,
    required this.status,
    required this.code,
    required this.message,
    required this.action,
    required this.permissions,
  });

  factory DeploymentReadinessCheck.fromJson(
    Map<String, dynamic> json,
    String path,
  ) {
    final permissions = _requiredList(json, 'permissions', path);
    if (permissions.length > 250) {
      throw _contractError('$path.permissions must not exceed 250 entries.');
    }
    return DeploymentReadinessCheck(
      component: _boundedString(json, 'component', path, maxLength: 80),
      status: DeploymentReadinessCheckStatus.parse(
        json['status'],
        '$path.status',
      ),
      code: _boundedString(json, 'code', path, maxLength: 120),
      message: _boundedString(json, 'message', path, maxLength: 2000),
      action: _boundedString(json, 'action', path, maxLength: 2000),
      permissions: List.unmodifiable(
        permissions.indexed.map(
          (entry) => _boundedValueString(
            entry.$2,
            '$path.permissions[${entry.$1}]',
            maxLength: 300,
          ),
        ),
      ),
    );
  }

  @override
  List<Object?> get props => [
    component,
    status,
    code,
    message,
    action,
    permissions,
  ];
}

class ProviderDeploymentReadiness extends Equatable {
  final CloudProvider provider;
  final String? connectionId;
  final String? connectionDisplayName;
  final bool ready;
  final ProviderDeploymentReadinessStatus status;
  final String summary;
  final DateTime? checkedAt;
  final String? graphDigest;
  final String? requirementsDigest;
  final List<DeploymentReadinessCheck> checks;
  final List<DeploymentRequirementReadiness> requirements;

  const ProviderDeploymentReadiness({
    required this.provider,
    this.connectionId,
    this.connectionDisplayName,
    required this.ready,
    required this.status,
    required this.summary,
    this.checkedAt,
    this.graphDigest,
    this.requirementsDigest,
    required this.checks,
    this.requirements = const [],
  });

  factory ProviderDeploymentReadiness.fromJson(
    Map<String, dynamic> json,
    String path,
  ) {
    final provider = _provider(json['provider'], '$path.provider');
    final ready = _requiredBool(json, 'ready', path);
    final status = ProviderDeploymentReadinessStatus.parse(
      json['status'],
      '$path.status',
    );
    if (ready != (status == ProviderDeploymentReadinessStatus.ready)) {
      throw _contractError('$path.ready and status are inconsistent.');
    }
    final checks = _requiredList(json, 'checks', path);
    if (checks.isEmpty || checks.length > 32) {
      throw _contractError(
        '$path.checks must contain between 1 and 32 entries.',
      );
    }
    final parsedChecks = checks.indexed
        .map(
          (entry) => DeploymentReadinessCheck.fromJson(
            _asMap(entry.$2, '$path.checks[${entry.$1}]'),
            '$path.checks[${entry.$1}]',
          ),
        )
        .toList(growable: false);
    final requirementValues = _requiredList(json, 'requirements', path);
    if (requirementValues.length > 4096) {
      throw _contractError('$path.requirements must not exceed 4096 entries.');
    }
    final requirements = requirementValues.indexed
        .map(
          (entry) => DeploymentRequirementReadiness.fromJson(
            _asMap(entry.$2, '$path.requirements[${entry.$1}]'),
            '$path.requirements[${entry.$1}]',
          ),
        )
        .toList(growable: false);
    if (requirements.any((item) => item.provider != provider)) {
      throw _contractError('$path.requirements have inconsistent ownership.');
    }
    final connectionId = _optionalBoundedString(
      json,
      'connection_id',
      path,
      maxLength: 160,
    );
    final checkedAt = _optionalDate(json, 'checked_at', path);
    final graphDigest = _optionalContentDigest(
      json['graph_digest'],
      '$path.graph_digest',
    );
    final requirementsDigest = _optionalContentDigest(
      json['requirements_digest'],
      '$path.requirements_digest',
    );
    final expectedReady =
        parsedChecks.every(
          (check) => check.status == DeploymentReadinessCheckStatus.passed,
        ) &&
        requirements.isNotEmpty &&
        requirements.every(
          (item) => item.status == DeploymentRequirementReadinessStatus.ready,
        );
    if (ready != expectedReady) {
      throw _contractError('$path.ready and evidence are inconsistent.');
    }
    if (ready &&
        (connectionId == null ||
            checkedAt == null ||
            graphDigest == null ||
            requirementsDigest == null)) {
      throw _contractError('$path.ready requires graph-bound evidence.');
    }
    return ProviderDeploymentReadiness(
      provider: provider,
      connectionId: connectionId,
      connectionDisplayName: _optionalBoundedString(
        json,
        'connection_display_name',
        path,
        maxLength: 120,
      ),
      ready: ready,
      status: status,
      summary: _boundedString(json, 'summary', path, maxLength: 2000),
      checkedAt: checkedAt,
      graphDigest: graphDigest,
      requirementsDigest: requirementsDigest,
      checks: List.unmodifiable(parsedChecks),
      requirements: List.unmodifiable(requirements),
    );
  }

  @override
  List<Object?> get props => [
    provider,
    connectionId,
    connectionDisplayName,
    ready,
    status,
    summary,
    checkedAt,
    graphDigest,
    requirementsDigest,
    checks,
    requirements,
  ];
}

class DeploymentReadinessSnapshot extends Equatable {
  static const cachedSchemaVersion = 'deployment-readiness.v1';
  static const preflightSchemaVersion = 'deployment-preflight.v1';

  final String schemaVersion;
  final DeploymentReadinessSource source;
  final String twinId;
  final bool ready;
  final String summary;
  final List<CloudProvider> requiredProviders;
  final List<ProviderDeploymentReadiness> providers;
  final DateTime? checkedAt;
  final String? graphDigest;
  final String? requirementsDigest;
  final DeploymentPreparationPlan? preparationPlan;
  final List<DeploymentReadinessCheck> issues;

  const DeploymentReadinessSnapshot({
    required this.schemaVersion,
    required this.source,
    required this.twinId,
    required this.ready,
    required this.summary,
    required this.requiredProviders,
    required this.providers,
    this.checkedAt,
    this.graphDigest,
    this.requirementsDigest,
    this.preparationPlan,
    required this.issues,
  });

  factory DeploymentReadinessSnapshot.fromCachedJson(
    Map<String, dynamic> json, {
    String? expectedTwinId,
  }) {
    final snapshot = DeploymentReadinessSnapshot._fromJson(
      json,
      expectedSchema: cachedSchemaVersion,
      source: DeploymentReadinessSource.cached,
    );
    _verifyTwinId(snapshot, expectedTwinId);
    return snapshot;
  }

  factory DeploymentReadinessSnapshot.fromPreflightJson(
    Map<String, dynamic> json, {
    String? expectedTwinId,
  }) {
    final snapshot = DeploymentReadinessSnapshot._fromJson(
      json,
      expectedSchema: preflightSchemaVersion,
      source: DeploymentReadinessSource.preflight,
    );
    _verifyTwinId(snapshot, expectedTwinId);
    return snapshot;
  }

  factory DeploymentReadinessSnapshot._fromJson(
    Map<String, dynamic> json, {
    required String expectedSchema,
    required DeploymentReadinessSource source,
  }) {
    if (json['schema_version'] != expectedSchema) {
      throw _contractError('Unsupported deployment readiness schema version.');
    }
    final requiredValues = _requiredList(json, 'required_providers', 'root');
    if (requiredValues.length > 3) {
      throw _contractError('required_providers must not exceed three entries.');
    }
    final requiredProviders = requiredValues.indexed
        .map((entry) => _provider(entry.$2, 'required_providers[${entry.$1}]'))
        .toList(growable: false);
    if (requiredProviders.toSet().length != requiredProviders.length) {
      throw _contractError('required_providers must not contain duplicates.');
    }

    final providerValues = _requiredList(json, 'providers', 'root');
    if (providerValues.length != requiredProviders.length) {
      throw _contractError('providers must match required_providers.');
    }
    final providers = providerValues.indexed
        .map(
          (entry) => ProviderDeploymentReadiness.fromJson(
            _asMap(entry.$2, 'providers[${entry.$1}]'),
            'providers[${entry.$1}]',
          ),
        )
        .toList(growable: false);
    for (var index = 0; index < providers.length; index += 1) {
      if (providers[index].provider != requiredProviders[index]) {
        throw _contractError('providers must follow required_providers order.');
      }
    }

    final issueValues = _requiredList(json, 'issues', 'root');
    if (issueValues.length > 16) {
      throw _contractError('issues must not exceed 16 entries.');
    }
    final issues = issueValues.indexed
        .map(
          (entry) => DeploymentReadinessCheck.fromJson(
            _asMap(entry.$2, 'issues[${entry.$1}]'),
            'issues[${entry.$1}]',
          ),
        )
        .toList(growable: false);
    final ready = _requiredBool(json, 'ready', 'root');
    final aggregateReady =
        requiredProviders.isNotEmpty &&
        issues.isEmpty &&
        providers.every((provider) => provider.ready);
    if (ready != aggregateReady) {
      throw _contractError('Aggregate readiness is inconsistent.');
    }
    final checkedAt = _optionalDate(json, 'checked_at', 'root');
    if (ready && checkedAt == null) {
      throw _contractError('Ready deployment evidence requires checked_at.');
    }
    final graphDigest = _optionalContentDigest(
      json['graph_digest'],
      'root.graph_digest',
    );
    final requirementsDigest = _optionalContentDigest(
      json['requirements_digest'],
      'root.requirements_digest',
    );
    final providerGraphDigests = providers
        .map((provider) => provider.graphDigest)
        .whereType<String>()
        .toSet();
    final providerRequirementsDigests = providers
        .map((provider) => provider.requirementsDigest)
        .whereType<String>()
        .toSet();
    if (providerGraphDigests.length > 1 ||
        providerRequirementsDigests.length > 1) {
      throw _contractError('Providers do not share one graph inspection.');
    }
    final providerGraphDigest = providerGraphDigests.isEmpty
        ? null
        : providerGraphDigests.single;
    final providerRequirementsDigest = providerRequirementsDigests.isEmpty
        ? null
        : providerRequirementsDigests.single;
    if (graphDigest != providerGraphDigest ||
        requirementsDigest != providerRequirementsDigest) {
      throw _contractError('Aggregate graph evidence is inconsistent.');
    }
    if (ready && (graphDigest == null || requirementsDigest == null)) {
      throw _contractError('Ready deployment evidence must be graph-bound.');
    }
    final rawPlan = json['preparation_plan'];
    final preparationPlan = rawPlan == null
        ? null
        : DeploymentPreparationPlan.fromJson(
            _asMap(rawPlan, 'root.preparation_plan'),
            'root.preparation_plan',
          );
    if (preparationPlan != null &&
        (preparationPlan.graphDigest != graphDigest ||
            preparationPlan.requirementsDigest != requirementsDigest)) {
      throw _contractError('Preparation plan is not bound to this graph.');
    }

    return DeploymentReadinessSnapshot(
      schemaVersion: expectedSchema,
      source: source,
      twinId: _boundedString(json, 'twin_id', 'root', maxLength: 160),
      ready: ready,
      summary: _boundedString(json, 'summary', 'root', maxLength: 2000),
      requiredProviders: List.unmodifiable(requiredProviders),
      providers: List.unmodifiable(providers),
      checkedAt: checkedAt,
      graphDigest: graphDigest,
      requirementsDigest: requirementsDigest,
      preparationPlan: preparationPlan,
      issues: List.unmodifiable(issues),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    source,
    twinId,
    ready,
    summary,
    requiredProviders,
    providers,
    checkedAt,
    graphDigest,
    requirementsDigest,
    preparationPlan,
    issues,
  ];
}

void _verifyTwinId(
  DeploymentReadinessSnapshot snapshot,
  String? expectedTwinId,
) {
  if (expectedTwinId != null && snapshot.twinId != expectedTwinId) {
    throw _contractError('Deployment readiness belongs to another twin.');
  }
}

CloudProvider _provider(Object? value, String field) {
  if (value is! String) {
    throw _contractError('$field must be a provider string.');
  }
  try {
    return CloudProvider.fromApiValue(value);
  } on ArgumentError {
    throw _contractError('$field contains an unknown provider.');
  }
}

List<dynamic> _requiredList(
  Map<String, dynamic> json,
  String field,
  String path,
) {
  final value = json[field];
  if (value is! List) {
    throw _contractError('$path.$field must be a list.');
  }
  return value;
}

List<String> _boundedStringList(
  Map<String, dynamic> json,
  String field,
  String path, {
  required int maxItems,
  required int maxLength,
}) {
  final values = _requiredList(json, field, path);
  if (values.length > maxItems) {
    throw _contractError('$path.$field must not exceed $maxItems entries.');
  }
  return List.unmodifiable(
    values.indexed.map(
      (entry) => _boundedValueString(
        entry.$2,
        '$path.$field[${entry.$1}]',
        maxLength: maxLength,
      ),
    ),
  );
}

List<String> _boundedUniqueStringList(
  Map<String, dynamic> json,
  String field,
  String path, {
  required int maxItems,
  required int maxLength,
}) {
  final values = _boundedStringList(
    json,
    field,
    path,
    maxItems: maxItems,
    maxLength: maxLength,
  );
  if (values.toSet().length != values.length) {
    throw _contractError('$path.$field must not contain duplicates.');
  }
  return values;
}

List<PreparationActionResult> _preparationResults(
  Map<String, dynamic> json,
  String field, {
  required bool expectedSuccess,
}) {
  final values = _requiredList(json, field, 'root');
  if (values.length > 4096) {
    throw _contractError('root.$field must not exceed 4096 entries.');
  }
  final results = values.indexed
      .map(
        (entry) => PreparationActionResult.fromJson(
          _asMap(entry.$2, 'root.$field[${entry.$1}]'),
          'root.$field[${entry.$1}]',
          expectedSuccess: expectedSuccess,
        ),
      )
      .toList(growable: false);
  if (results.map((item) => item.actionId).toSet().length != results.length) {
    throw _contractError('root.$field contains duplicate actions.');
  }
  return results;
}

bool _isSorted(Iterable<String> values) {
  String? previous;
  for (final value in values) {
    if (previous != null && previous.compareTo(value) > 0) return false;
    previous = value;
  }
  return true;
}

final RegExp _contentDigestPattern = RegExp(r'^sha256:[0-9a-f]{64}$');

String _contentDigest(Object? value, String field) {
  if (value is! String || !_contentDigestPattern.hasMatch(value)) {
    throw _contractError('$field must be a sha256 content digest.');
  }
  return value;
}

String? _optionalContentDigest(Object? value, String field) {
  if (value == null) return null;
  return _contentDigest(value, field);
}

Map<String, dynamic> _asMap(Object? value, String field) {
  if (value is! Map) {
    throw _contractError('$field must be an object.');
  }
  return Map<String, dynamic>.from(value);
}

bool _requiredBool(Map<String, dynamic> json, String field, String path) {
  final value = json[field];
  if (value is! bool) {
    throw _contractError('$path.$field must be a boolean.');
  }
  return value;
}

String _boundedString(
  Map<String, dynamic> json,
  String field,
  String path, {
  required int maxLength,
}) {
  return _boundedValueString(json[field], '$path.$field', maxLength: maxLength);
}

String _boundedValueString(
  Object? value,
  String field, {
  required int maxLength,
}) {
  if (value is! String || value.trim().isEmpty || value.length > maxLength) {
    throw _contractError('$field must be a non-empty bounded string.');
  }
  return value;
}

String? _optionalBoundedString(
  Map<String, dynamic> json,
  String field,
  String path, {
  required int maxLength,
}) {
  final value = json[field];
  if (value == null) return null;
  return _boundedValueString(value, '$path.$field', maxLength: maxLength);
}

DateTime? _optionalDate(Map<String, dynamic> json, String field, String path) {
  final value = json[field];
  if (value == null) return null;
  if (value is! String) {
    throw _contractError('$path.$field must be an ISO-8601 timestamp or null.');
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null) {
    throw _contractError('$path.$field must be an ISO-8601 timestamp or null.');
  }
  return parsed;
}

AppException _contractError(String message) {
  return AppException(message, code: 'DEPLOYMENT_CONTRACT_INVALID');
}
