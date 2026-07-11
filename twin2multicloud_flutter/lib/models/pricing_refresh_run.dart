import 'package:equatable/equatable.dart';

class PricingRefreshRun extends Equatable {
  final String schemaVersion;
  final String refreshRunId;
  final String provider;
  final String status;
  final PricingRefreshCredentialSummary credentialSummary;
  final bool force;
  final String sseUrl;
  final Map<String, dynamic>? resultSummary;
  final String? errorCode;
  final String? errorMessage;
  final DateTime createdAt;
  final DateTime? startedAt;
  final DateTime? completedAt;

  const PricingRefreshRun({
    required this.schemaVersion,
    required this.refreshRunId,
    required this.provider,
    required this.status,
    required this.credentialSummary,
    required this.force,
    required this.sseUrl,
    this.resultSummary,
    this.errorCode,
    this.errorMessage,
    required this.createdAt,
    this.startedAt,
    this.completedAt,
  });

  factory PricingRefreshRun.fromJson(Map<String, dynamic> json) {
    return PricingRefreshRun(
      schemaVersion: json['schema_version']?.toString() ?? '',
      refreshRunId: json['refresh_run_id']?.toString() ?? '',
      provider: json['provider']?.toString() ?? '',
      status: json['status']?.toString() ?? 'failed',
      credentialSummary: PricingRefreshCredentialSummary.fromJson(
        _map(json['credential_summary']),
      ),
      force: json['force'] as bool? ?? true,
      sseUrl: json['sse_url']?.toString() ?? '',
      resultSummary: json['result_summary'] is Map
          ? Map<String, dynamic>.from(json['result_summary'] as Map)
          : null,
      errorCode: _string(json['error_code']),
      errorMessage: _string(json['error_message']),
      createdAt:
          _date(json['created_at']) ?? DateTime.fromMillisecondsSinceEpoch(0),
      startedAt: _date(json['started_at']),
      completedAt: _date(json['completed_at']),
    );
  }

  bool get succeeded => status == 'succeeded';

  @override
  List<Object?> get props => [
    schemaVersion,
    refreshRunId,
    provider,
    status,
    credentialSummary,
    force,
    sseUrl,
    resultSummary,
    errorCode,
    errorMessage,
    createdAt,
    startedAt,
    completedAt,
  ];
}

class PricingRefreshCredentialSummary extends Equatable {
  final String? connectionId;
  final String identityLabel;
  final String scope;
  final String? providerAccountId;
  final String? providerProjectId;
  final String? providerSubscriptionId;

  const PricingRefreshCredentialSummary({
    this.connectionId,
    required this.identityLabel,
    required this.scope,
    this.providerAccountId,
    this.providerProjectId,
    this.providerSubscriptionId,
  });

  factory PricingRefreshCredentialSummary.fromJson(Map<String, dynamic> json) {
    return PricingRefreshCredentialSummary(
      connectionId: _string(json['connection_id']),
      identityLabel: json['identity_label']?.toString() ?? '',
      scope: json['scope']?.toString() ?? 'user',
      providerAccountId: _string(json['provider_account_id']),
      providerProjectId: _string(json['provider_project_id']),
      providerSubscriptionId: _string(json['provider_subscription_id']),
    );
  }

  @override
  List<Object?> get props => [
    connectionId,
    identityLabel,
    scope,
    providerAccountId,
    providerProjectId,
    providerSubscriptionId,
  ];
}

Map<String, dynamic> _map(dynamic value) {
  return value is Map ? Map<String, dynamic>.from(value) : const {};
}

String? _string(dynamic value) {
  if (value == null) return null;
  final text = value.toString();
  return text.isEmpty ? null : text;
}

DateTime? _date(dynamic value) {
  return value == null ? null : DateTime.tryParse(value.toString());
}
