import 'dart:typed_data';

import 'package:equatable/equatable.dart';

import '../core/result.dart';

enum DeploymentOperationType {
  deploy('deploy'),
  destroy('destroy'),
  test('test');

  final String apiValue;

  const DeploymentOperationType(this.apiValue);

  static DeploymentOperationType parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () =>
          throw _contractError('$field must be one of: deploy, destroy, test.'),
    );
  }
}

enum DeploymentOperationStatus {
  pending('pending'),
  running('running'),
  success('success'),
  failed('failed');

  final String apiValue;

  const DeploymentOperationStatus(this.apiValue);

  static DeploymentOperationStatus parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw _contractError(
        '$field must be one of: pending, running, success, failed.',
      ),
    );
  }
}

enum DeploymentTwinState {
  draft('draft'),
  configured('configured'),
  deploying('deploying'),
  deployed('deployed'),
  destroying('destroying'),
  destroyed('destroyed'),
  error('error'),
  inactive('inactive');

  final String apiValue;

  const DeploymentTwinState(this.apiValue);

  static DeploymentTwinState parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw _contractError('$field contains an unknown state.'),
    );
  }
}

class OperationSession extends Equatable {
  final String sessionId;
  final String sseUrl;

  const OperationSession({required this.sessionId, required this.sseUrl});

  factory OperationSession.fromJson(Map<String, dynamic> json) {
    return OperationSession(
      sessionId: _requiredString(json, 'session_id'),
      sseUrl: _requiredRelativeUrl(json, 'sse_url'),
    );
  }

  @override
  List<Object?> get props => [sessionId, sseUrl];
}

class ActiveDeploymentSession extends OperationSession {
  final DeploymentOperationType operationType;

  const ActiveDeploymentSession({
    required super.sessionId,
    required super.sseUrl,
    required this.operationType,
  });

  factory ActiveDeploymentSession.fromJson(Map<String, dynamic> json) {
    return ActiveDeploymentSession(
      sessionId: _requiredString(json, 'session_id'),
      sseUrl: _requiredRelativeUrl(json, 'sse_url'),
      operationType: DeploymentOperationType.parse(
        json['operation_type'],
        'active_session.operation_type',
      ),
    );
  }

  @override
  List<Object?> get props => [...super.props, operationType];
}

class DeploymentOperationSummary extends Equatable {
  final String id;
  final String sessionId;
  final String? operationId;
  final DeploymentOperationType operationType;
  final DeploymentOperationStatus status;
  final String? errorCode;
  final String? errorMessage;
  final DateTime? startedAt;
  final DateTime? completedAt;

  const DeploymentOperationSummary({
    required this.id,
    required this.sessionId,
    this.operationId,
    required this.operationType,
    required this.status,
    this.errorCode,
    this.errorMessage,
    this.startedAt,
    this.completedAt,
  });

  factory DeploymentOperationSummary.fromJson(Map<String, dynamic> json) {
    final startedAt = _optionalDate(json, 'started_at');
    final completedAt = _optionalDate(json, 'completed_at');
    if (startedAt != null &&
        completedAt != null &&
        completedAt.isBefore(startedAt)) {
      throw _contractError('completed_at cannot be earlier than started_at.');
    }
    return DeploymentOperationSummary(
      id: _requiredString(json, 'id'),
      sessionId: _requiredString(json, 'session_id'),
      operationId: _optionalString(json, 'operation_id'),
      operationType: DeploymentOperationType.parse(
        json['operation_type'],
        'operation_type',
      ),
      status: DeploymentOperationStatus.parse(json['status'], 'status'),
      errorCode: _optionalString(json, 'error_code'),
      errorMessage: _optionalString(json, 'error_message'),
      startedAt: startedAt,
      completedAt: completedAt,
    );
  }

  @override
  List<Object?> get props => [
    id,
    sessionId,
    operationId,
    operationType,
    status,
    errorCode,
    errorMessage,
    startedAt,
    completedAt,
  ];
}

class DeploymentStatusSnapshot extends Equatable {
  static const supportedSchemaVersion = 'deployment-status.v1';

  final String schemaVersion;
  final DeploymentTwinState state;
  final String? lastError;
  final DateTime? deployedAt;
  final DateTime? destroyedAt;
  final ActiveDeploymentSession? activeSession;
  final DeploymentOperationSummary? latestDeployment;

  const DeploymentStatusSnapshot({
    required this.schemaVersion,
    required this.state,
    this.lastError,
    this.deployedAt,
    this.destroyedAt,
    this.activeSession,
    this.latestDeployment,
  });

  factory DeploymentStatusSnapshot.fromJson(Map<String, dynamic> json) {
    _requireSchema(json, supportedSchemaVersion);
    return DeploymentStatusSnapshot(
      schemaVersion: supportedSchemaVersion,
      state: DeploymentTwinState.parse(json['state'], 'state'),
      lastError: _optionalString(json, 'last_error'),
      deployedAt: _optionalDate(json, 'deployed_at'),
      destroyedAt: _optionalDate(json, 'destroyed_at'),
      activeSession: _optionalObject(
        json,
        'active_session',
        ActiveDeploymentSession.fromJson,
      ),
      latestDeployment: _optionalObject(
        json,
        'latest_deployment',
        DeploymentOperationSummary.fromJson,
      ),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    state,
    lastError,
    deployedAt,
    destroyedAt,
    activeSession,
    latestDeployment,
  ];
}

class DeploymentOutputsSnapshot extends Equatable {
  static const supportedSchemaVersion = 'deployment-outputs.v1';

  final String schemaVersion;
  final Map<String, dynamic>? outputs;
  final DateTime? deployedAt;
  final DeploymentOperationSummary? sourceDeployment;
  final bool redacted;

  const DeploymentOutputsSnapshot({
    required this.schemaVersion,
    this.outputs,
    this.deployedAt,
    this.sourceDeployment,
    required this.redacted,
  });

  factory DeploymentOutputsSnapshot.fromJson(Map<String, dynamic> json) {
    _requireSchema(json, supportedSchemaVersion);
    final rawOutputs = json['outputs'];
    if (rawOutputs != null && rawOutputs is! Map) {
      throw _contractError('outputs must be an object or null.');
    }
    final redacted = json['redacted'];
    if (redacted is! bool) {
      throw _contractError('redacted must be a boolean.');
    }
    return DeploymentOutputsSnapshot(
      schemaVersion: supportedSchemaVersion,
      outputs: rawOutputs == null ? null : _immutableJsonMap(rawOutputs),
      deployedAt: _optionalDate(json, 'deployed_at'),
      sourceDeployment: _optionalObject(
        json,
        'source_deployment',
        DeploymentOperationSummary.fromJson,
      ),
      redacted: redacted,
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    outputs,
    deployedAt,
    sourceDeployment,
    redacted,
  ];
}

class DeploymentHistory extends Equatable {
  static const supportedSchemaVersion = 'deployment-history.v1';

  final String schemaVersion;
  final List<DeploymentOperationSummary> deployments;

  const DeploymentHistory({
    required this.schemaVersion,
    required this.deployments,
  });

  factory DeploymentHistory.fromJson(Map<String, dynamic> json) {
    _requireSchema(json, supportedSchemaVersion);
    final values = _requiredList(json, 'deployments')
        .map(
          (value) => DeploymentOperationSummary.fromJson(
            _asMap(value, 'deployments[]'),
          ),
        )
        .toList(growable: false);
    return DeploymentHistory(
      schemaVersion: supportedSchemaVersion,
      deployments: List.unmodifiable(values),
    );
  }

  @override
  List<Object?> get props => [schemaVersion, deployments];
}

class DeploymentLogEntry extends Equatable {
  final int eventId;
  final String sessionId;
  final DateTime timestamp;
  final String level;
  final String message;
  final String operationType;

  const DeploymentLogEntry({
    required this.eventId,
    required this.sessionId,
    required this.timestamp,
    required this.level,
    required this.message,
    required this.operationType,
  });

  factory DeploymentLogEntry.fromJson(Map<String, dynamic> json) {
    return DeploymentLogEntry(
      eventId: _requiredPositiveInt(json, 'event_id'),
      sessionId: _requiredString(json, 'session_id'),
      timestamp: _requiredDate(json, 'timestamp'),
      level: _requiredString(json, 'level'),
      message: _requiredString(json, 'message'),
      operationType: _requiredString(json, 'operation_type'),
    );
  }

  @override
  List<Object?> get props => [
    eventId,
    sessionId,
    timestamp,
    level,
    message,
    operationType,
  ];
}

class DeploymentLogPage extends Equatable {
  static const supportedSchemaVersion = 'deployment-log-page.v1';

  final String schemaVersion;
  final String twinId;
  final String? sessionId;
  final int afterEventId;
  final int limit;
  final List<DeploymentLogEntry> logs;
  final bool hasMore;
  final int? nextAfterEventId;
  final int? latestEventId;

  const DeploymentLogPage({
    required this.schemaVersion,
    required this.twinId,
    this.sessionId,
    required this.afterEventId,
    required this.limit,
    required this.logs,
    required this.hasMore,
    this.nextAfterEventId,
    this.latestEventId,
  });

  factory DeploymentLogPage.fromJson(Map<String, dynamic> json) {
    _requireSchema(json, supportedSchemaVersion);
    final afterEventId = _requiredNonNegativeInt(json, 'after_event_id');
    final limit = _requiredPositiveInt(json, 'limit');
    if (limit > 500) {
      throw _contractError('limit must not exceed 500.');
    }
    final logs = _requiredList(json, 'logs')
        .map((value) => DeploymentLogEntry.fromJson(_asMap(value, 'logs[]')))
        .toList(growable: false);
    var previousEventId = afterEventId;
    for (final log in logs) {
      if (log.eventId <= previousEventId) {
        throw _contractError(
          'logs must contain strictly ascending event IDs after the cursor.',
        );
      }
      previousEventId = log.eventId;
    }
    final hasMore = json['has_more'];
    if (hasMore is! bool) {
      throw _contractError('has_more must be a boolean.');
    }
    final nextAfterEventId = _optionalNonNegativeInt(
      json,
      'next_after_event_id',
    );
    final latestEventId = _optionalNonNegativeInt(json, 'latest_event_id');
    if (nextAfterEventId != null && nextAfterEventId < afterEventId) {
      throw _contractError('next_after_event_id cannot regress.');
    }
    if (logs.isNotEmpty && nextAfterEventId != logs.last.eventId) {
      throw _contractError(
        'next_after_event_id must match the final returned event.',
      );
    }
    if (latestEventId != null && latestEventId < previousEventId) {
      throw _contractError('latest_event_id cannot precede returned events.');
    }
    return DeploymentLogPage(
      schemaVersion: supportedSchemaVersion,
      twinId: _requiredString(json, 'twin_id'),
      sessionId: _optionalString(json, 'session_id'),
      afterEventId: afterEventId,
      limit: limit,
      logs: List.unmodifiable(logs),
      hasMore: hasMore,
      nextAfterEventId: nextAfterEventId,
      latestEventId: latestEventId,
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    twinId,
    sessionId,
    afterEventId,
    limit,
    logs,
    hasMore,
    nextAfterEventId,
    latestEventId,
  ];
}

class LogTraceStartResult extends Equatable {
  final String traceId;
  final DateTime sentAt;
  final String l1Provider;
  final List<String> providers;
  final String message;
  final String? sessionId;
  final String? sseUrl;

  const LogTraceStartResult({
    required this.traceId,
    required this.sentAt,
    required this.l1Provider,
    required this.providers,
    required this.message,
    this.sessionId,
    this.sseUrl,
  });

  factory LogTraceStartResult.fromJson(Map<String, dynamic> json) {
    final providers = _requiredList(json, 'providers')
        .map((value) {
          if (value is! String || value.trim().isEmpty) {
            throw _contractError(
              'providers must contain only non-empty strings.',
            );
          }
          return value.trim();
        })
        .toList(growable: false);
    if (providers.isEmpty || providers.toSet().length != providers.length) {
      throw _contractError('providers must be a non-empty unique list.');
    }
    final l1Provider = _requiredString(json, 'l1_provider');
    if (!providers.contains(l1Provider)) {
      throw _contractError('l1_provider must be included in providers.');
    }
    final sessionId = _optionalString(json, 'session_id');
    final sseUrl = _optionalRelativeUrl(json, 'sse_url');
    if ((sessionId == null) != (sseUrl == null)) {
      throw _contractError(
        'session_id and sse_url must either both be present or both be null.',
      );
    }
    return LogTraceStartResult(
      traceId: _requiredString(json, 'trace_id'),
      sentAt: _requiredDate(json, 'sent_at'),
      l1Provider: l1Provider,
      providers: List.unmodifiable(providers),
      message: _requiredString(json, 'message'),
      sessionId: sessionId,
      sseUrl: sseUrl,
    );
  }

  @override
  List<Object?> get props => [
    traceId,
    sentAt,
    l1Provider,
    providers,
    message,
    sessionId,
    sseUrl,
  ];
}

class BinaryDownload {
  final Uint8List _bytes;
  final String filename;
  final String mediaType;
  final bool containsSensitiveRuntimeCredentials;

  BinaryDownload({
    required Uint8List bytes,
    required String filename,
    required this.mediaType,
    this.containsSensitiveRuntimeCredentials = true,
  }) : _bytes = Uint8List.fromList(bytes),
       filename = _safeZipFilename(filename);

  Uint8List get bytes => Uint8List.fromList(_bytes);
}

AppException _contractError(String message) {
  return AppException(message, code: 'DEPLOYMENT_CONTRACT_INVALID');
}

void _requireSchema(Map<String, dynamic> json, String supported) {
  final actual = _requiredString(json, 'schema_version');
  if (actual != supported) {
    throw _contractError(
      'Unsupported deployment contract version "$actual"; expected "$supported".',
    );
  }
}

Map<String, dynamic> _asMap(Object? value, String field) {
  if (value is! Map) {
    throw _contractError('$field must be an object.');
  }
  final result = <String, dynamic>{};
  for (final entry in value.entries) {
    if (entry.key is! String) {
      throw _contractError('$field must contain string keys.');
    }
    result[entry.key as String] = entry.value;
  }
  return result;
}

Map<String, dynamic> _immutableJsonMap(Map<dynamic, dynamic> value) {
  final result = <String, dynamic>{};
  for (final entry in value.entries) {
    if (entry.key is! String) {
      throw _contractError('outputs must contain string keys.');
    }
    result[entry.key as String] = _immutableJsonValue(entry.value);
  }
  return Map.unmodifiable(result);
}

dynamic _immutableJsonValue(Object? value) {
  if (value is Map) return _immutableJsonMap(value);
  if (value is List) {
    return List<dynamic>.unmodifiable(value.map(_immutableJsonValue));
  }
  return value;
}

List<dynamic> _requiredList(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! List) {
    throw _contractError('$field must be a list.');
  }
  return value;
}

String _requiredString(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! String || value.trim().isEmpty) {
    throw _contractError('$field must be a non-empty string.');
  }
  return value.trim();
}

String _requiredRelativeUrl(Map<String, dynamic> json, String field) {
  final value = _requiredString(json, field);
  if (!value.startsWith('/') || value.startsWith('//')) {
    throw _contractError('$field must be a relative Management API path.');
  }
  return value;
}

String? _optionalRelativeUrl(Map<String, dynamic> json, String field) {
  final value = _optionalString(json, field);
  if (value == null) return null;
  if (!value.startsWith('/') || value.startsWith('//')) {
    throw _contractError('$field must be a relative Management API path.');
  }
  return value;
}

String? _optionalString(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value == null) return null;
  if (value is! String) {
    throw _contractError('$field must be a string or null.');
  }
  final normalized = value.trim();
  return normalized.isEmpty ? null : normalized;
}

DateTime _requiredDate(Map<String, dynamic> json, String field) {
  final value = _requiredString(json, field);
  final parsed = DateTime.tryParse(value);
  if (parsed == null) {
    throw _contractError('$field must be an ISO-8601 timestamp.');
  }
  return parsed;
}

DateTime? _optionalDate(Map<String, dynamic> json, String field) {
  final value = _optionalString(json, field);
  if (value == null) return null;
  final parsed = DateTime.tryParse(value);
  if (parsed == null) {
    throw _contractError('$field must be an ISO-8601 timestamp or null.');
  }
  return parsed;
}

int _requiredPositiveInt(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! int || value <= 0) {
    throw _contractError('$field must be a positive integer.');
  }
  return value;
}

int _requiredNonNegativeInt(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! int || value < 0) {
    throw _contractError('$field must be a non-negative integer.');
  }
  return value;
}

int? _optionalNonNegativeInt(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value == null) return null;
  if (value is! int || value < 0) {
    throw _contractError('$field must be a non-negative integer or null.');
  }
  return value;
}

T? _optionalObject<T>(
  Map<String, dynamic> json,
  String field,
  T Function(Map<String, dynamic>) parser,
) {
  final value = json[field];
  return value == null ? null : parser(_asMap(value, field));
}

String _safeZipFilename(String value) {
  final normalized = value.trim();
  final safePattern = RegExp(r'^[A-Za-z0-9][A-Za-z0-9._-]*\.zip$');
  if (normalized.contains('..') || !safePattern.hasMatch(normalized)) {
    throw _contractError('Simulator filename is unsafe.');
  }
  return normalized;
}
