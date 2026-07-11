import 'package:equatable/equatable.dart';

class CloudAccessInventory extends Equatable {
  final String schemaVersion;
  final Map<String, CloudAccessProviderInventory> providers;

  const CloudAccessInventory({
    required this.schemaVersion,
    required this.providers,
  });

  factory CloudAccessInventory.fromJson(Map<String, dynamic> json) {
    final providerJson = _map(json['providers']);
    return CloudAccessInventory(
      schemaVersion: json['schema_version']?.toString() ?? '',
      providers: providerJson.map(
        (key, value) =>
            MapEntry(key, CloudAccessProviderInventory.fromJson(_map(value))),
      ),
    );
  }

  CloudAccessEntry? pricingFor(String provider) {
    return providers[provider.toLowerCase()]?.pricing;
  }

  @override
  List<Object?> get props => [schemaVersion, providers];
}

class CloudAccessProviderInventory extends Equatable {
  final String provider;
  final CloudAccessEntry pricing;
  final List<CloudAccessEntry> deployment;

  const CloudAccessProviderInventory({
    required this.provider,
    required this.pricing,
    this.deployment = const [],
  });

  factory CloudAccessProviderInventory.fromJson(Map<String, dynamic> json) {
    return CloudAccessProviderInventory(
      provider: json['provider']?.toString() ?? '',
      pricing: CloudAccessEntry.fromJson(_map(json['pricing'])),
      deployment: _list(
        json['deployment'],
      ).map((item) => CloudAccessEntry.fromJson(_map(item))).toList(),
    );
  }

  @override
  List<Object?> get props => [provider, pricing, deployment];
}

class CloudAccessEntry extends Equatable {
  final String? connectionId;
  final String provider;
  final String purpose;
  final String scope;
  final String identityLabel;
  final String status;
  final String? providerAccountId;
  final String? providerProjectId;
  final String? providerSubscriptionId;
  final bool? isDefaultForPricing;
  final DateTime? lastValidatedAt;
  final DateTime? lastUsedAt;
  final String? permissionSetStatus;
  final int boundTwinCount;
  final List<String> boundTwinLabels;
  final List<String> actions;
  final String? primaryMessage;

  const CloudAccessEntry({
    this.connectionId,
    required this.provider,
    required this.purpose,
    required this.scope,
    required this.identityLabel,
    required this.status,
    this.providerAccountId,
    this.providerProjectId,
    this.providerSubscriptionId,
    this.isDefaultForPricing,
    this.lastValidatedAt,
    this.lastUsedAt,
    this.permissionSetStatus,
    this.boundTwinCount = 0,
    this.boundTwinLabels = const [],
    this.actions = const [],
    this.primaryMessage,
  });

  factory CloudAccessEntry.fromJson(Map<String, dynamic> json) {
    return CloudAccessEntry(
      connectionId: _string(json['connection_id']),
      provider: json['provider']?.toString() ?? '',
      purpose: json['purpose']?.toString() ?? '',
      scope: json['scope']?.toString() ?? '',
      identityLabel: json['identity_label']?.toString() ?? '',
      status: json['status']?.toString() ?? 'missing',
      providerAccountId: _string(json['provider_account_id']),
      providerProjectId: _string(json['provider_project_id']),
      providerSubscriptionId: _string(json['provider_subscription_id']),
      isDefaultForPricing: json['is_default_for_pricing'] as bool?,
      lastValidatedAt: _date(json['last_validated_at']),
      lastUsedAt: _date(json['last_used_at']),
      permissionSetStatus: _string(json['permission_set_status']),
      boundTwinCount: _integer(json['bound_twin_count']),
      boundTwinLabels: _strings(json['bound_twin_labels']),
      actions: _strings(json['actions']),
      primaryMessage: _string(json['primary_message']),
    );
  }

  bool get canRefreshPricing {
    if (scope == 'public') return status == 'active';
    return connectionId != null && {'active', 'stale'}.contains(status);
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
    isDefaultForPricing,
    lastValidatedAt,
    lastUsedAt,
    permissionSetStatus,
    boundTwinCount,
    boundTwinLabels,
    actions,
    primaryMessage,
  ];
}

Map<String, dynamic> _map(dynamic value) {
  return value is Map ? Map<String, dynamic>.from(value) : const {};
}

List<dynamic> _list(dynamic value) => value is List ? value : const [];

List<String> _strings(dynamic value) {
  return _list(value).map((item) => item.toString()).toList();
}

String? _string(dynamic value) {
  if (value == null) return null;
  final text = value.toString();
  return text.isEmpty ? null : text;
}

DateTime? _date(dynamic value) {
  return value == null ? null : DateTime.tryParse(value.toString());
}

int _integer(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}
