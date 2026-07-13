import 'package:equatable/equatable.dart';

class PricingHealthResponse extends Equatable {
  static const supportedSchemaVersion = 'pricing-health.v1';

  final String schemaVersion;
  final Map<String, ProviderPricingHealth> providers;

  const PricingHealthResponse({
    required this.schemaVersion,
    required this.providers,
  });

  factory PricingHealthResponse.fromJson(Map<String, dynamic> json) {
    final providerJson = _map(json['providers']);
    return PricingHealthResponse(
      schemaVersion: json['schema_version']?.toString() ?? '',
      providers: providerJson.map(
        (key, value) =>
            MapEntry(key, ProviderPricingHealth.fromJson(_map(value))),
      ),
    );
  }

  ProviderPricingHealth? provider(String provider) {
    return providers[provider.toLowerCase()];
  }

  @override
  List<Object?> get props => [schemaVersion, providers];
}

class ProviderPricingHealth extends Equatable {
  final String provider;
  final String state;
  final String severity;
  final bool reviewRequired;
  final bool canCalculate;
  final String calculationSource;
  final String pricingFreshness;
  final String? age;
  final String? lastFetchedAt;
  final String sourceLabel;
  final PricingCredentialSummary credentialSummary;
  final String primaryMessage;
  final List<String> actions;

  const ProviderPricingHealth({
    required this.provider,
    required this.state,
    required this.severity,
    required this.reviewRequired,
    required this.canCalculate,
    required this.calculationSource,
    required this.pricingFreshness,
    this.age,
    this.lastFetchedAt,
    required this.sourceLabel,
    required this.credentialSummary,
    required this.primaryMessage,
    this.actions = const [],
  });

  factory ProviderPricingHealth.fromJson(Map<String, dynamic> json) {
    return ProviderPricingHealth(
      provider: json['provider']?.toString() ?? '',
      state: json['state']?.toString() ?? 'failed',
      severity: json['severity']?.toString() ?? 'error',
      reviewRequired: json['review_required'] == true,
      canCalculate: json['can_calculate'] == true,
      calculationSource:
          json['calculation_source']?.toString() ?? 'unavailable',
      pricingFreshness: json['pricing_freshness']?.toString() ?? 'unavailable',
      age: _string(json['age']),
      lastFetchedAt: _string(json['last_fetched_at']),
      sourceLabel: json['source_label']?.toString() ?? '',
      credentialSummary: PricingCredentialSummary.fromJson(
        _map(json['credential_summary']),
      ),
      primaryMessage: json['primary_message']?.toString() ?? '',
      actions: _strings(json['actions']),
    );
  }

  @override
  List<Object?> get props => [
    provider,
    state,
    severity,
    reviewRequired,
    canCalculate,
    calculationSource,
    pricingFreshness,
    age,
    lastFetchedAt,
    sourceLabel,
    credentialSummary,
    primaryMessage,
    actions,
  ];
}

class PricingCredentialSummary extends Equatable {
  final String? connectionId;
  final String provider;
  final String purpose;
  final String scope;
  final String identityLabel;
  final String status;
  final String? providerAccountId;
  final String? providerProjectId;
  final String? providerSubscriptionId;

  const PricingCredentialSummary({
    this.connectionId,
    required this.provider,
    required this.purpose,
    required this.scope,
    required this.identityLabel,
    required this.status,
    this.providerAccountId,
    this.providerProjectId,
    this.providerSubscriptionId,
  });

  factory PricingCredentialSummary.fromJson(Map<String, dynamic> json) {
    return PricingCredentialSummary(
      connectionId: _string(json['connection_id']),
      provider: json['provider']?.toString() ?? '',
      purpose: json['purpose']?.toString() ?? 'pricing',
      scope: json['scope']?.toString() ?? 'user',
      identityLabel: json['identity_label']?.toString() ?? '',
      status: json['status']?.toString() ?? 'missing',
      providerAccountId: _string(json['provider_account_id']),
      providerProjectId: _string(json['provider_project_id']),
      providerSubscriptionId: _string(json['provider_subscription_id']),
    );
  }

  @override
  List<Object?> get props => [
    connectionId,
    provider,
    purpose,
    scope,
    identityLabel,
    status,
    providerAccountId,
    providerProjectId,
    providerSubscriptionId,
  ];
}

Map<String, dynamic> _map(dynamic value) {
  return value is Map ? Map<String, dynamic>.from(value) : const {};
}

List<String> _strings(dynamic value) {
  return value is List
      ? value.map((item) => item.toString()).toList()
      : const [];
}

String? _string(dynamic value) {
  if (value == null) return null;
  final text = value.toString();
  return text.isEmpty ? null : text;
}
