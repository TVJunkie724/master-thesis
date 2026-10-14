import 'dart:convert';

import 'package:equatable/equatable.dart';

class InfrastructureVerificationResult extends Equatable {
  final List<InfrastructureCheck> checks;
  final InfrastructureSummary summary;

  const InfrastructureVerificationResult({
    required this.checks,
    required this.summary,
  });

  factory InfrastructureVerificationResult.fromJson(Map<String, dynamic> json) {
    return InfrastructureVerificationResult(
      checks: (json['checks'] as List? ?? const [])
          .whereType<Map>()
          .map(
            (item) =>
                InfrastructureCheck.fromJson(Map<String, dynamic>.from(item)),
          )
          .toList(),
      summary: InfrastructureSummary.fromJson(
        Map<String, dynamic>.from(json['summary'] as Map? ?? const {}),
      ),
    );
  }

  Map<String, List<InfrastructureCheck>> groupedByLayer() {
    final grouped = <String, List<InfrastructureCheck>>{};
    for (final check in checks) {
      grouped.putIfAbsent(check.layer, () => []).add(check);
    }
    return grouped;
  }

  @override
  List<Object?> get props => [checks, summary];
}

class InfrastructureCheck extends Equatable {
  final String layer;
  final String name;
  final String provider;
  final String status;
  final String detail;

  const InfrastructureCheck({
    required this.layer,
    required this.name,
    required this.provider,
    required this.status,
    required this.detail,
  });

  factory InfrastructureCheck.fromJson(Map<String, dynamic> json) {
    return InfrastructureCheck(
      layer: json['layer']?.toString() ?? 'Unknown',
      name: json['name']?.toString() ?? '',
      provider: json['provider']?.toString() ?? '',
      status: json['status']?.toString() ?? 'fail',
      detail: json['detail']?.toString() ?? '',
    );
  }

  bool get passed => status == 'pass';
  bool get skipped => status == 'skip';

  @override
  List<Object?> get props => [layer, name, provider, status, detail];
}

class InfrastructureSummary extends Equatable {
  final int passCount;
  final int failCount;
  final int skipCount;
  final int total;
  final bool healthy;

  const InfrastructureSummary({
    this.passCount = 0,
    this.failCount = 0,
    this.skipCount = 0,
    this.total = 0,
    this.healthy = false,
  });

  factory InfrastructureSummary.fromJson(Map<String, dynamic> json) {
    return InfrastructureSummary(
      passCount: _readInt(json['pass_count']),
      failCount: _readInt(json['fail_count']),
      skipCount: _readInt(json['skip_count']),
      total: _readInt(json['total']),
      healthy: json['healthy'] == true,
    );
  }

  @override
  List<Object?> get props => [passCount, failCount, skipCount, total, healthy];
}

class DataFlowVerificationSummary extends Equatable {
  final int passCount;
  final int failCount;
  final int skipCount;
  final double totalTime;
  final String? failedPhase;
  final List<String> hints;

  const DataFlowVerificationSummary({
    this.passCount = 0,
    this.failCount = 0,
    this.skipCount = 0,
    this.totalTime = 0,
    this.failedPhase,
    this.hints = const [],
  });

  factory DataFlowVerificationSummary.fromJson(Map<String, dynamic> json) {
    return DataFlowVerificationSummary(
      passCount: _readInt(json['pass_count']),
      failCount: _readInt(json['fail_count']),
      skipCount: _readInt(json['skip_count']),
      totalTime: _readDouble(json['total_time']),
      failedPhase: json['failed_phase']?.toString(),
      hints: (json['hints'] as List? ?? const [])
          .map((item) => item.toString())
          .toList(),
    );
  }

  bool get allPass => failCount == 0;

  @override
  List<Object?> get props => [
    passCount,
    failCount,
    skipCount,
    totalTime,
    failedPhase,
    hints,
  ];
}

class DataFlowLogEntry extends Equatable {
  final String timestamp;
  final String message;
  final String? status;
  final String? detail;

  const DataFlowLogEntry({
    required this.timestamp,
    required this.message,
    this.status,
    this.detail,
  });

  @override
  List<Object?> get props => [timestamp, message, status, detail];
}

enum TelemetryVerificationStatus {
  running('running'),
  pass('pass'),
  fail('fail'),
  notRun('not_run');

  final String apiValue;

  const TelemetryVerificationStatus(this.apiValue);

  static TelemetryVerificationStatus parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw FormatException(
        'Invalid telemetry verification contract: $field is unsupported.',
      ),
    );
  }
}

enum TelemetryPhaseKind {
  messageAccepted('message_accepted'),
  traceCorrelatedHotRecord('trace_correlated_hot_record'),
  twinmakerPropertyProjection('twinmaker_property_projection'),
  azureTwinProjection('azure_twin_projection'),
  gcpTwinProjection('gcp_twin_projection');

  final String apiValue;

  const TelemetryPhaseKind(this.apiValue);

  static TelemetryPhaseKind parse(Object? value) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw const FormatException(
        'Invalid telemetry verification contract: evidence kind is unsupported.',
      ),
    );
  }
}

class TelemetryPhaseEvidence extends Equatable {
  static const _allowedFields = {
    'phase',
    'kind',
    'provider',
    'record_count',
    'correlation',
  };

  final int phase;
  final TelemetryPhaseKind kind;
  final String provider;
  final int? recordCount;
  final String? correlation;

  const TelemetryPhaseEvidence({
    required this.phase,
    required this.kind,
    required this.provider,
    this.recordCount,
    this.correlation,
  });

  factory TelemetryPhaseEvidence.fromJson(Map<String, dynamic> json) {
    _requireAllowedFields(json, _allowedFields, const {
      'phase',
      'kind',
      'provider',
    }, 'phase evidence');
    final phase = _requiredInt(json, 'phase');
    if (phase < 1 || phase > 3) {
      throw const FormatException(
        'Invalid telemetry verification contract: phase is unsupported.',
      );
    }
    final kind = TelemetryPhaseKind.parse(json['kind']);
    final provider = _requiredEnumString(json, 'provider', const {
      'aws',
      'azure',
      'gcp',
    });
    final recordCount = _optionalInt(json, 'record_count');
    final correlation = _optionalString(json, 'correlation');
    final expectedKinds = switch (phase) {
      1 => const {TelemetryPhaseKind.messageAccepted},
      2 => const {TelemetryPhaseKind.traceCorrelatedHotRecord},
      _ => const {
        TelemetryPhaseKind.twinmakerPropertyProjection,
        TelemetryPhaseKind.azureTwinProjection,
        TelemetryPhaseKind.gcpTwinProjection,
      },
    };
    if (!expectedKinds.contains(kind)) {
      throw const FormatException(
        'Invalid telemetry verification contract: phase and kind disagree.',
      );
    }
    if ((phase == 2) != (recordCount != null) ||
        (recordCount != null && (recordCount < 1 || recordCount > 100))) {
      throw const FormatException(
        'Invalid telemetry verification contract: record count is invalid.',
      );
    }
    if ((phase == 3 && correlation != 'source_sequence') ||
        (phase != 3 && correlation != null)) {
      throw const FormatException(
        'Invalid telemetry verification contract: correlation is invalid.',
      );
    }
    final expectedProvider = switch (kind) {
      TelemetryPhaseKind.twinmakerPropertyProjection => 'aws',
      TelemetryPhaseKind.azureTwinProjection => 'azure',
      TelemetryPhaseKind.gcpTwinProjection => 'gcp',
      _ => null,
    };
    if (expectedProvider != null && provider != expectedProvider) {
      throw const FormatException(
        'Invalid telemetry verification contract: L4 provider and kind disagree.',
      );
    }
    return TelemetryPhaseEvidence(
      phase: phase,
      kind: kind,
      provider: provider,
      recordCount: recordCount,
      correlation: correlation,
    );
  }

  @override
  List<Object?> get props => [phase, kind, provider, recordCount, correlation];
}

class TelemetryVerificationEvidence extends Equatable {
  static const supportedSchemaVersion = 'telemetry-verification.v1';
  static const _fields = {
    'schema_version',
    'trace_id',
    'status',
    'pass_count',
    'fail_count',
    'skip_count',
    'total_time',
    'failed_phase',
    'evidence',
  };
  static const failedPhases = {
    'Phase 1 - Message Delivery',
    'Phase 2 - Pipeline to Hot Storage',
    'Phase 3 - Twin Projection',
    'Verification runtime',
  };

  final String schemaVersion;
  final String traceId;
  final TelemetryVerificationStatus status;
  final int passCount;
  final int failCount;
  final int skipCount;
  final double totalTime;
  final String? failedPhase;
  final List<TelemetryPhaseEvidence> evidence;

  const TelemetryVerificationEvidence({
    required this.schemaVersion,
    required this.traceId,
    required this.status,
    required this.passCount,
    required this.failCount,
    required this.skipCount,
    required this.totalTime,
    this.failedPhase,
    required this.evidence,
  });

  factory TelemetryVerificationEvidence.fromJson(Map<String, dynamic> json) {
    _requireAllowedFields(
      json,
      _fields,
      _fields.difference(const {'failed_phase'}),
      'terminal evidence',
    );
    if (_requiredString(json, 'schema_version') != supportedSchemaVersion) {
      throw const FormatException(
        'Invalid telemetry verification contract: schema version is unsupported.',
      );
    }
    final traceId = _requiredString(json, 'trace_id');
    if (!RegExp(r'^VERIFY-[0-9A-F]{8}$').hasMatch(traceId)) {
      throw const FormatException(
        'Invalid telemetry verification contract: trace ID is invalid.',
      );
    }
    final status = TelemetryVerificationStatus.parse(json['status'], 'status');
    if (!{
      TelemetryVerificationStatus.pass,
      TelemetryVerificationStatus.fail,
    }.contains(status)) {
      throw const FormatException(
        'Invalid telemetry verification contract: terminal status is invalid.',
      );
    }
    final passCount = _requiredRangeInt(json, 'pass_count', 0, 3);
    final failCount = _requiredRangeInt(json, 'fail_count', 0, 1);
    final skipCount = _requiredRangeInt(json, 'skip_count', 0, 2);
    final totalTime = _requiredDouble(json, 'total_time');
    if (totalTime < 0 || totalTime > 900) {
      throw const FormatException(
        'Invalid telemetry verification contract: total time is invalid.',
      );
    }
    final failedPhase = _optionalString(json, 'failed_phase');
    if (failedPhase != null && !failedPhases.contains(failedPhase)) {
      throw const FormatException(
        'Invalid telemetry verification contract: failed phase is invalid.',
      );
    }
    final evidenceValues = json['evidence'];
    if (evidenceValues is! List || evidenceValues.length > 3) {
      throw const FormatException(
        'Invalid telemetry verification contract: evidence must be bounded.',
      );
    }
    final evidence = evidenceValues
        .map(
          (value) => TelemetryPhaseEvidence.fromJson(
            _requiredMap(value, 'evidence item'),
          ),
        )
        .toList(growable: false);
    final phases = evidence.map((item) => item.phase).toSet();
    if (passCount + failCount + skipCount != 3 ||
        (status == TelemetryVerificationStatus.pass) != (failCount == 0) ||
        (status == TelemetryVerificationStatus.fail) != (failedPhase != null) ||
        phases.length != evidence.length ||
        evidence.length > passCount) {
      throw const FormatException(
        'Invalid telemetry verification contract: terminal evidence is inconsistent.',
      );
    }
    return TelemetryVerificationEvidence(
      schemaVersion: supportedSchemaVersion,
      traceId: traceId,
      status: status,
      passCount: passCount,
      failCount: failCount,
      skipCount: skipCount,
      totalTime: totalTime,
      failedPhase: failedPhase,
      evidence: List.unmodifiable(evidence),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    traceId,
    status,
    passCount,
    failCount,
    skipCount,
    totalTime,
    failedPhase,
    evidence,
  ];
}

class TelemetryVerificationStart extends Equatable {
  static const supportedSchemaVersion = 'telemetry-verification-session.v1';
  static const _fields = {
    'schema_version',
    'verification_id',
    'session_id',
    'sse_url',
    'status_url',
    'status',
  };

  final String schemaVersion;
  final String verificationId;
  final String sessionId;
  final String sseUrl;
  final String statusUrl;
  final TelemetryVerificationStatus status;

  const TelemetryVerificationStart({
    required this.schemaVersion,
    required this.verificationId,
    required this.sessionId,
    required this.sseUrl,
    required this.statusUrl,
    required this.status,
  });

  factory TelemetryVerificationStart.fromJson(Map<String, dynamic> json) {
    _requireAllowedFields(json, _fields, _fields, 'verification session');
    if (_requiredString(json, 'schema_version') != supportedSchemaVersion) {
      throw const FormatException(
        'Invalid telemetry verification contract: session schema is unsupported.',
      );
    }
    return TelemetryVerificationStart(
      schemaVersion: supportedSchemaVersion,
      verificationId: _requiredString(json, 'verification_id'),
      sessionId: _requiredString(json, 'session_id'),
      sseUrl: _requiredRelativePath(json, 'sse_url'),
      statusUrl: _requiredRelativePath(json, 'status_url'),
      status: TelemetryVerificationStatus.parse(json['status'], 'status'),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    verificationId,
    sessionId,
    sseUrl,
    statusUrl,
    status,
  ];
}

class TelemetryVerificationRecord extends Equatable {
  static const _fields = {
    'id',
    'twin_id',
    'deployment_id',
    'session_id',
    'device_id',
    'status',
    'trace_id',
    'result',
    'error_code',
    'error_message',
    'requested_at',
    'completed_at',
  };

  final String id;
  final String twinId;
  final String? deploymentId;
  final String sessionId;
  final String deviceId;
  final TelemetryVerificationStatus status;
  final String? traceId;
  final TelemetryVerificationEvidence? result;
  final String? errorCode;
  final String? errorMessage;
  final DateTime requestedAt;
  final DateTime? completedAt;

  const TelemetryVerificationRecord({
    required this.id,
    required this.twinId,
    this.deploymentId,
    required this.sessionId,
    required this.deviceId,
    required this.status,
    this.traceId,
    this.result,
    this.errorCode,
    this.errorMessage,
    required this.requestedAt,
    this.completedAt,
  });

  factory TelemetryVerificationRecord.fromJson(Map<String, dynamic> json) {
    _requireAllowedFields(json, _fields, _fields, 'verification record');
    final status = TelemetryVerificationStatus.parse(json['status'], 'status');
    final traceId = _optionalString(json, 'trace_id');
    final resultValue = json['result'];
    final result = resultValue == null
        ? null
        : TelemetryVerificationEvidence.fromJson(
            _requiredMap(resultValue, 'result'),
          );
    final errorCode = _optionalString(json, 'error_code');
    final errorMessage = _optionalString(json, 'error_message');
    final requestedAt = _requiredDate(json, 'requested_at');
    final completedAt = _optionalDate(json, 'completed_at');
    if (completedAt != null && completedAt.isBefore(requestedAt)) {
      throw const FormatException(
        'Invalid telemetry verification contract: timestamps are inconsistent.',
      );
    }
    switch (status) {
      case TelemetryVerificationStatus.running:
        if (traceId != null ||
            result != null ||
            errorCode != null ||
            errorMessage != null ||
            completedAt != null) {
          throw const FormatException(
            'Invalid telemetry verification contract: running record is terminal.',
          );
        }
      case TelemetryVerificationStatus.pass:
        if (result?.status != status ||
            traceId != result?.traceId ||
            completedAt == null ||
            errorCode != null ||
            errorMessage != null) {
          throw const FormatException(
            'Invalid telemetry verification contract: pass record is inconsistent.',
          );
        }
      case TelemetryVerificationStatus.fail:
        if (completedAt == null || errorCode == null || errorMessage == null) {
          throw const FormatException(
            'Invalid telemetry verification contract: failed record lacks evidence.',
          );
        }
        if (result != null &&
            (result.status != status || traceId != result.traceId)) {
          throw const FormatException(
            'Invalid telemetry verification contract: failed result is inconsistent.',
          );
        }
        if (result == null && traceId != null) {
          throw const FormatException(
            'Invalid telemetry verification contract: failed trace lacks a result.',
          );
        }
      case TelemetryVerificationStatus.notRun:
        if (traceId != null ||
            result != null ||
            completedAt == null ||
            errorCode == null ||
            errorMessage == null) {
          throw const FormatException(
            'Invalid telemetry verification contract: not-run record is inconsistent.',
          );
        }
    }
    return TelemetryVerificationRecord(
      id: _requiredString(json, 'id'),
      twinId: _requiredString(json, 'twin_id'),
      deploymentId: _optionalString(json, 'deployment_id'),
      sessionId: _requiredString(json, 'session_id'),
      deviceId: _requiredString(json, 'device_id'),
      status: status,
      traceId: traceId,
      result: result,
      errorCode: errorCode,
      errorMessage: errorMessage,
      requestedAt: requestedAt,
      completedAt: completedAt,
    );
  }

  @override
  List<Object?> get props => [
    id,
    twinId,
    deploymentId,
    sessionId,
    deviceId,
    status,
    traceId,
    result,
    errorCode,
    errorMessage,
    requestedAt,
    completedAt,
  ];
}

class TelemetryVerificationHistory extends Equatable {
  static const supportedSchemaVersion = 'telemetry-verification-history.v1';
  static const _fields = {'schema_version', 'verifications'};

  final String schemaVersion;
  final List<TelemetryVerificationRecord> verifications;

  const TelemetryVerificationHistory({
    required this.schemaVersion,
    required this.verifications,
  });

  factory TelemetryVerificationHistory.fromJson(Map<String, dynamic> json) {
    _requireAllowedFields(json, _fields, _fields, 'verification history');
    if (_requiredString(json, 'schema_version') != supportedSchemaVersion) {
      throw const FormatException(
        'Invalid telemetry verification contract: history schema is unsupported.',
      );
    }
    final values = json['verifications'];
    if (values is! List || values.length > 25) {
      throw const FormatException(
        'Invalid telemetry verification contract: history must be bounded.',
      );
    }
    final records = values
        .map(
          (value) => TelemetryVerificationRecord.fromJson(
            _requiredMap(value, 'verification history item'),
          ),
        )
        .toList(growable: false);
    final ids = <String>{};
    DateTime? previous;
    for (final record in records) {
      if (!ids.add(record.id) ||
          (previous != null && record.requestedAt.isAfter(previous))) {
        throw const FormatException(
          'Invalid telemetry verification contract: history ordering is invalid.',
        );
      }
      previous = record.requestedAt;
    }
    return TelemetryVerificationHistory(
      schemaVersion: supportedSchemaVersion,
      verifications: List.unmodifiable(records),
    );
  }

  @override
  List<Object?> get props => [schemaVersion, verifications];
}

class DeploymentVerificationPayload {
  static const fallback =
      '{\n  "iotDeviceId": "temperature-sensor-1",\n  "temperature": 42.5,\n  "type": "verification_test"\n}';

  static String initialPayload(String? payloadsJson) {
    if (payloadsJson == null || payloadsJson.isEmpty) return fallback;
    try {
      final decoded = json.decode(payloadsJson);
      if (decoded is List && decoded.isNotEmpty) {
        return const JsonEncoder.withIndent('  ').convert(decoded.first);
      }
      if (decoded is Map) {
        return const JsonEncoder.withIndent('  ').convert(decoded);
      }
    } catch (_) {
      return fallback;
    }
    return fallback;
  }
}

int _readInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

double _readDouble(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}

void _requireAllowedFields(
  Map<String, dynamic> json,
  Set<String> allowed,
  Set<String> required,
  String contract,
) {
  if (json.keys.toSet().difference(allowed).isNotEmpty ||
      required.difference(json.keys.toSet()).isNotEmpty) {
    throw FormatException(
      'Invalid telemetry verification contract: $contract fields do not match v1.',
    );
  }
}

Map<String, dynamic> _requiredMap(Object? value, String field) {
  if (value is! Map) {
    throw FormatException(
      'Invalid telemetry verification contract: $field must be an object.',
    );
  }
  return Map<String, dynamic>.from(value);
}

String _requiredString(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException(
      'Invalid telemetry verification contract: $field must be a string.',
    );
  }
  return value.trim();
}

String? _optionalString(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value == null) return null;
  if (value is! String || value.trim().isEmpty) {
    throw FormatException(
      'Invalid telemetry verification contract: $field must be a string or null.',
    );
  }
  return value.trim();
}

String _requiredEnumString(
  Map<String, dynamic> json,
  String field,
  Set<String> allowed,
) {
  final value = _requiredString(json, field);
  if (!allowed.contains(value)) {
    throw FormatException(
      'Invalid telemetry verification contract: $field is unsupported.',
    );
  }
  return value;
}

int _requiredInt(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! int) {
    throw FormatException(
      'Invalid telemetry verification contract: $field must be an integer.',
    );
  }
  return value;
}

int? _optionalInt(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value == null) return null;
  if (value is! int) {
    throw FormatException(
      'Invalid telemetry verification contract: $field must be an integer or null.',
    );
  }
  return value;
}

int _requiredRangeInt(
  Map<String, dynamic> json,
  String field,
  int minimum,
  int maximum,
) {
  final value = _requiredInt(json, field);
  if (value < minimum || value > maximum) {
    throw FormatException(
      'Invalid telemetry verification contract: $field is outside its range.',
    );
  }
  return value;
}

double _requiredDouble(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! num) {
    throw FormatException(
      'Invalid telemetry verification contract: $field must be numeric.',
    );
  }
  return value.toDouble();
}

DateTime _requiredDate(Map<String, dynamic> json, String field) {
  final parsed = DateTime.tryParse(_requiredString(json, field));
  if (parsed == null) {
    throw FormatException(
      'Invalid telemetry verification contract: $field must be a timestamp.',
    );
  }
  return parsed.toUtc();
}

DateTime? _optionalDate(Map<String, dynamic> json, String field) {
  if (json[field] == null) return null;
  return _requiredDate(json, field);
}

String _requiredRelativePath(Map<String, dynamic> json, String field) {
  final value = _requiredString(json, field);
  if (!value.startsWith('/') || value.startsWith('//')) {
    throw FormatException(
      'Invalid telemetry verification contract: $field must be a relative Management path.',
    );
  }
  return value;
}
