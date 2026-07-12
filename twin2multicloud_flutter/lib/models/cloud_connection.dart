import 'package:equatable/equatable.dart';

enum CloudProvider {
  aws,
  azure,
  gcp;

  String get apiValue => name;

  String get label => switch (this) {
    CloudProvider.aws => 'AWS',
    CloudProvider.azure => 'Azure',
    CloudProvider.gcp => 'GCP',
  };

  static CloudProvider fromApiValue(String value) {
    return switch (value.toLowerCase()) {
      'aws' => CloudProvider.aws,
      'azure' => CloudProvider.azure,
      'gcp' => CloudProvider.gcp,
      _ => throw ArgumentError.value(value, 'value', 'Unknown cloud provider'),
    };
  }
}

enum CloudConnectionPurpose {
  pricing,
  deployment;

  String get apiValue => name;

  String get label => switch (this) {
    CloudConnectionPurpose.pricing => 'Pricing access',
    CloudConnectionPurpose.deployment => 'Deployment access',
  };

  static CloudConnectionPurpose fromApiValue(String value) {
    return switch (value.toLowerCase()) {
      'pricing' => CloudConnectionPurpose.pricing,
      'deployment' => CloudConnectionPurpose.deployment,
      _ => throw ArgumentError.value(
        value,
        'value',
        'Unknown Cloud Connection purpose',
      ),
    };
  }
}

class CloudConnection extends Equatable {
  final String id;
  final CloudProvider provider;
  final CloudConnectionPurpose purpose;
  final String scope;
  final bool isDefaultForPricing;
  final String displayName;
  final String authType;
  final Map<String, dynamic> cloudScope;
  final String payloadFingerprint;
  final Map<String, dynamic> payloadSummary;
  final String validationStatus;
  final String? validationMessage;
  final DateTime? lastValidatedAt;
  final DateTime? lastUsedAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  const CloudConnection({
    required this.id,
    required this.provider,
    this.purpose = CloudConnectionPurpose.deployment,
    this.scope = 'user',
    this.isDefaultForPricing = false,
    required this.displayName,
    required this.authType,
    required this.cloudScope,
    required this.payloadFingerprint,
    required this.payloadSummary,
    required this.validationStatus,
    this.validationMessage,
    this.lastValidatedAt,
    this.lastUsedAt,
    required this.createdAt,
    required this.updatedAt,
  });

  factory CloudConnection.fromJson(Map<String, dynamic> json) {
    return CloudConnection(
      id: json['id'].toString(),
      provider: CloudProvider.fromApiValue(json['provider'].toString()),
      purpose: CloudConnectionPurpose.fromApiValue(
        json['purpose']?.toString() ?? 'deployment',
      ),
      scope: json['scope']?.toString() ?? 'user',
      isDefaultForPricing: json['is_default_for_pricing'] == true,
      displayName: json['display_name']?.toString() ?? '',
      authType: json['auth_type']?.toString() ?? '',
      cloudScope: _mapFromJson(json['cloud_scope']),
      payloadFingerprint: json['payload_fingerprint']?.toString() ?? '',
      payloadSummary: _mapFromJson(json['payload_summary']),
      validationStatus: json['validation_status']?.toString() ?? 'untested',
      validationMessage: json['validation_message']?.toString(),
      lastValidatedAt: _dateTimeOrNull(json['last_validated_at']),
      lastUsedAt: _dateTimeOrNull(json['last_used_at']),
      createdAt:
          _dateTimeOrNull(json['created_at']) ??
          DateTime.fromMillisecondsSinceEpoch(0),
      updatedAt:
          _dateTimeOrNull(json['updated_at']) ??
          DateTime.fromMillisecondsSinceEpoch(0),
    );
  }

  bool get isValid => validationStatus == 'valid';

  @override
  List<Object?> get props => [
    id,
    provider,
    purpose,
    scope,
    isDefaultForPricing,
    displayName,
    authType,
    cloudScope,
    payloadFingerprint,
    payloadSummary,
    validationStatus,
    validationMessage,
    lastValidatedAt,
    lastUsedAt,
    createdAt,
    updatedAt,
  ];
}

class CloudConnectionCreateRequest extends Equatable {
  final CloudProvider provider;
  final CloudConnectionPurpose purpose;
  final String displayName;
  final String? authType;
  final Map<String, dynamic> cloudScope;
  final Map<String, dynamic> credentials;
  final bool isDefaultForPricing;

  const CloudConnectionCreateRequest({
    required this.provider,
    this.purpose = CloudConnectionPurpose.deployment,
    required this.displayName,
    this.authType,
    this.cloudScope = const {},
    required this.credentials,
    this.isDefaultForPricing = false,
  });

  Map<String, dynamic> toJson() {
    if (provider == CloudProvider.gcp &&
        (credentials['service_account_json']?.toString().trim().isEmpty ??
            true)) {
      throw ArgumentError(
        'service_account_json is required for GCP Cloud Connections',
      );
    }

    return {
      'provider': provider.apiValue,
      'purpose': purpose.apiValue,
      'scope': 'user',
      if (isDefaultForPricing) 'is_default_for_pricing': true,
      'display_name': displayName,
      if (authType != null) 'auth_type': authType,
      'cloud_scope': cloudScope,
      provider.apiValue: credentials,
    };
  }

  @override
  List<Object?> get props => [
    provider,
    purpose,
    displayName,
    authType,
    cloudScope,
    credentials,
    isDefaultForPricing,
  ];
}

class CloudConnectionValidationResult extends Equatable {
  final String id;
  final CloudProvider provider;
  final bool valid;
  final String validationStatus;
  final String message;
  final Map<String, dynamic>? optimizer;
  final Map<String, dynamic>? deployer;

  const CloudConnectionValidationResult({
    required this.id,
    required this.provider,
    required this.valid,
    required this.validationStatus,
    required this.message,
    this.optimizer,
    this.deployer,
  });

  factory CloudConnectionValidationResult.fromJson(Map<String, dynamic> json) {
    return CloudConnectionValidationResult(
      id: json['id'].toString(),
      provider: CloudProvider.fromApiValue(json['provider'].toString()),
      valid: json['valid'] == true,
      validationStatus: json['validation_status']?.toString() ?? 'invalid',
      message: json['message']?.toString() ?? 'Validation complete',
      optimizer: _nullableMapFromJson(json['optimizer']),
      deployer: _nullableMapFromJson(json['deployer']),
    );
  }

  @override
  List<Object?> get props => [
    id,
    provider,
    valid,
    validationStatus,
    message,
    optimizer,
    deployer,
  ];
}

Map<String, dynamic> _mapFromJson(dynamic value) {
  if (value is Map) {
    return Map<String, dynamic>.from(value);
  }
  return const {};
}

Map<String, dynamic>? _nullableMapFromJson(dynamic value) {
  if (value is Map) {
    return Map<String, dynamic>.from(value);
  }
  return null;
}

DateTime? _dateTimeOrNull(dynamic value) {
  if (value == null) return null;
  return DateTime.tryParse(value.toString());
}
