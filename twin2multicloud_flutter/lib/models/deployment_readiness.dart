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

enum PermissionSetReadinessStatus {
  matched('matched'),
  missing('missing'),
  outdated('outdated');

  final String apiValue;

  const PermissionSetReadinessStatus(this.apiValue);

  static PermissionSetReadinessStatus parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw _contractError('$field contains an unknown status.'),
    );
  }
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
  final String expectedPermissionSetVersion;
  final String? suppliedPermissionSetVersion;
  final PermissionSetReadinessStatus permissionSetStatus;
  final DateTime? checkedAt;
  final List<DeploymentReadinessCheck> checks;

  const ProviderDeploymentReadiness({
    required this.provider,
    this.connectionId,
    this.connectionDisplayName,
    required this.ready,
    required this.status,
    required this.summary,
    required this.expectedPermissionSetVersion,
    this.suppliedPermissionSetVersion,
    required this.permissionSetStatus,
    this.checkedAt,
    required this.checks,
  });

  factory ProviderDeploymentReadiness.fromJson(
    Map<String, dynamic> json,
    String path,
  ) {
    final ready = _requiredBool(json, 'ready', path);
    final status = ProviderDeploymentReadinessStatus.parse(
      json['status'],
      '$path.status',
    );
    final permissionStatus = PermissionSetReadinessStatus.parse(
      json['permission_set_status'],
      '$path.permission_set_status',
    );
    if (ready != (status == ProviderDeploymentReadinessStatus.ready)) {
      throw _contractError('$path.ready and status are inconsistent.');
    }
    if (ready && permissionStatus != PermissionSetReadinessStatus.matched) {
      throw _contractError(
        '$path cannot be ready with an unmatched permission set.',
      );
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
    if (ready !=
        parsedChecks.every(
          (check) => check.status == DeploymentReadinessCheckStatus.passed,
        )) {
      throw _contractError('$path.ready and checks are inconsistent.');
    }
    final connectionId = _optionalBoundedString(
      json,
      'connection_id',
      path,
      maxLength: 160,
    );
    final checkedAt = _optionalDate(json, 'checked_at', path);
    if (ready && (connectionId == null || checkedAt == null)) {
      throw _contractError('$path.ready requires a connection and timestamp.');
    }
    return ProviderDeploymentReadiness(
      provider: _provider(json['provider'], '$path.provider'),
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
      expectedPermissionSetVersion: _boundedString(
        json,
        'expected_permission_set_version',
        path,
        maxLength: 80,
      ),
      suppliedPermissionSetVersion: _optionalBoundedString(
        json,
        'supplied_permission_set_version',
        path,
        maxLength: 80,
      ),
      permissionSetStatus: permissionStatus,
      checkedAt: checkedAt,
      checks: List.unmodifiable(parsedChecks),
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
    expectedPermissionSetVersion,
    suppliedPermissionSetVersion,
    permissionSetStatus,
    checkedAt,
    checks,
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

    return DeploymentReadinessSnapshot(
      schemaVersion: expectedSchema,
      source: source,
      twinId: _boundedString(json, 'twin_id', 'root', maxLength: 160),
      ready: ready,
      summary: _boundedString(json, 'summary', 'root', maxLength: 2000),
      requiredProviders: List.unmodifiable(requiredProviders),
      providers: List.unmodifiable(providers),
      checkedAt: checkedAt,
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
