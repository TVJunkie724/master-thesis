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

class CloudConnection extends Equatable {
  final String id;
  final CloudProvider provider;
  final String displayName;
  final String authType;
  final Map<String, dynamic> cloudScope;
  final String payloadFingerprint;
  final Map<String, dynamic> payloadSummary;
  final String validationStatus;
  final String? validationMessage;
  final DateTime? lastValidatedAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  const CloudConnection({
    required this.id,
    required this.provider,
    required this.displayName,
    required this.authType,
    required this.cloudScope,
    required this.payloadFingerprint,
    required this.payloadSummary,
    required this.validationStatus,
    this.validationMessage,
    this.lastValidatedAt,
    required this.createdAt,
    required this.updatedAt,
  });

  factory CloudConnection.fromJson(Map<String, dynamic> json) {
    return CloudConnection(
      id: json['id'].toString(),
      provider: CloudProvider.fromApiValue(json['provider'].toString()),
      displayName: json['display_name']?.toString() ?? '',
      authType: json['auth_type']?.toString() ?? '',
      cloudScope: _mapFromJson(json['cloud_scope']),
      payloadFingerprint: json['payload_fingerprint']?.toString() ?? '',
      payloadSummary: _mapFromJson(json['payload_summary']),
      validationStatus: json['validation_status']?.toString() ?? 'untested',
      validationMessage: json['validation_message']?.toString(),
      lastValidatedAt: _dateTimeOrNull(json['last_validated_at']),
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
    displayName,
    authType,
    cloudScope,
    payloadFingerprint,
    payloadSummary,
    validationStatus,
    validationMessage,
    lastValidatedAt,
    createdAt,
    updatedAt,
  ];
}

class CloudConnectionCreateRequest extends Equatable {
  final CloudProvider provider;
  final String displayName;
  final String? authType;
  final Map<String, dynamic> cloudScope;
  final Map<String, dynamic> credentials;

  const CloudConnectionCreateRequest({
    required this.provider,
    required this.displayName,
    this.authType,
    this.cloudScope = const {},
    required this.credentials,
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
      'display_name': displayName,
      if (authType != null) 'auth_type': authType,
      'cloud_scope': cloudScope,
      provider.apiValue: credentials,
    };
  }

  @override
  List<Object?> get props => [
    provider,
    displayName,
    authType,
    cloudScope,
    credentials,
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
