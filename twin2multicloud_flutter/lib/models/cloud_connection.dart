import 'dart:convert';
import 'dart:typed_data';

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

class CloudConnectionImportRequest extends Equatable {
  static const maxFileBytes = 128 * 1024;

  final CloudProvider provider;
  final String displayName;
  final String region;
  final String? targetScopeId;
  final String? accountId;
  final String? ssoRegion;
  final String? regionIotHub;
  final String? regionDigitalTwin;
  final String filename;
  final Uint8List _bytes;

  CloudConnectionImportRequest({
    required this.provider,
    required String displayName,
    required String region,
    String? targetScopeId,
    String? accountId,
    String? ssoRegion,
    String? regionIotHub,
    String? regionDigitalTwin,
    required String filename,
    required Uint8List bytes,
  }) : displayName = _requiredBounded(displayName, 'displayName', 120),
       region = _requiredBounded(region, 'region', 80),
       targetScopeId = _optionalBounded(targetScopeId, 'targetScopeId', 256),
       accountId = _optionalBounded(accountId, 'accountId', 12),
       ssoRegion = _optionalBounded(ssoRegion, 'ssoRegion', 80),
       regionIotHub = _optionalBounded(regionIotHub, 'regionIotHub', 80),
       regionDigitalTwin = _optionalBounded(
         regionDigitalTwin,
         'regionDigitalTwin',
         80,
       ),
       filename = _importFilename(provider, filename),
       _bytes = _importBytes(bytes) {
    _validateProviderMetadata();
  }

  Uint8List get bytes => Uint8List.fromList(_bytes);

  String get metadataJson => jsonEncode({
    'provider': provider.apiValue,
    'purpose': CloudConnectionPurpose.deployment.apiValue,
    'display_name': displayName,
    'region': region,
    if (targetScopeId != null) 'target_scope_id': targetScopeId,
    if (accountId != null) 'account_id': accountId,
    if (ssoRegion != null) 'sso_region': ssoRegion,
    if (regionIotHub != null) 'region_iothub': regionIotHub,
    if (regionDigitalTwin != null) 'region_digital_twin': regionDigitalTwin,
  });

  void _validateProviderMetadata() {
    if ({CloudProvider.azure, CloudProvider.gcp}.contains(provider) &&
        targetScopeId == null) {
      throw ArgumentError(
        'targetScopeId is required for Azure and GCP imports.',
      );
    }
    if (provider == CloudProvider.aws) {
      if (accountId != null && !RegExp(r'^\d{12}$').hasMatch(accountId!)) {
        throw ArgumentError('accountId must be a twelve-digit AWS account ID.');
      }
      if (targetScopeId != null ||
          regionIotHub != null ||
          regionDigitalTwin != null) {
        throw ArgumentError('AWS import metadata contains foreign fields.');
      }
      return;
    }
    if (accountId != null || ssoRegion != null) {
      throw ArgumentError('AWS metadata is valid only for AWS imports.');
    }
    if (provider != CloudProvider.azure &&
        (regionIotHub != null || regionDigitalTwin != null)) {
      throw ArgumentError('Azure region overrides require Azure.');
    }
  }

  @override
  List<Object?> get props => [
    provider,
    displayName,
    region,
    targetScopeId,
    accountId,
    ssoRegion,
    regionIotHub,
    regionDigitalTwin,
    filename,
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

String _requiredBounded(String value, String field, int maximum) {
  final normalized = value.trim();
  if (normalized.isEmpty || normalized.length > maximum) {
    throw ArgumentError(
      '$field must contain between 1 and $maximum characters.',
    );
  }
  return normalized;
}

String? _optionalBounded(String? value, String field, int maximum) {
  if (value == null) return null;
  return _requiredBounded(value, field, maximum);
}

String _importFilename(CloudProvider provider, String value) {
  final normalized = value.trim();
  final expected = provider == CloudProvider.aws ? '.csv' : '.json';
  final safe = RegExp(r'^[A-Za-z0-9][A-Za-z0-9._-]*$');
  if (normalized.contains('..') ||
      !safe.hasMatch(normalized) ||
      !normalized.toLowerCase().endsWith(expected)) {
    throw ArgumentError(
      '${provider.label} credential import requires a safe $expected filename.',
    );
  }
  return normalized;
}

Uint8List _importBytes(Uint8List value) {
  if (value.isEmpty ||
      value.length > CloudConnectionImportRequest.maxFileBytes) {
    throw ArgumentError(
      'Credential file size is outside the supported boundary.',
    );
  }
  return Uint8List.fromList(value);
}
