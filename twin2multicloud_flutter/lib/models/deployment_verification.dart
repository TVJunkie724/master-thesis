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
