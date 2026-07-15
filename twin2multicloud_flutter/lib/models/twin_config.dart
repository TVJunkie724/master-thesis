import 'package:equatable/equatable.dart';

import 'calc_params.dart';
import 'cloud_connection.dart';
import 'json_contract.dart';
import 'optimizer_config.dart';
import 'twin.dart';

enum TwinCredentialSource {
  cloudConnection('cloud_connection');

  final String apiValue;

  const TwinCredentialSource(this.apiValue);

  static TwinCredentialSource? optional(Object? value, String field) {
    if (value == null) return null;
    if (value is! String) {
      throw FormatException('Invalid API contract: $field must be a string.');
    }
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw FormatException(
        'Invalid API contract: $field contains an unknown source.',
      ),
    );
  }
}

class BoundCloudConnection extends Equatable {
  final String id;
  final CloudProvider provider;
  final String displayName;
  final String authType;
  final String validationStatus;
  final DateTime? lastValidatedAt;

  const BoundCloudConnection({
    required this.id,
    required this.provider,
    required this.displayName,
    required this.authType,
    required this.validationStatus,
    this.lastValidatedAt,
  });

  factory BoundCloudConnection.fromJson(
    Map<String, dynamic> json, {
    required CloudProvider expectedProvider,
  }) {
    final providerValue = JsonContract.requiredString(json, 'provider');
    final CloudProvider provider;
    try {
      provider = CloudProvider.fromApiValue(providerValue);
    } on ArgumentError {
      throw const FormatException(
        'Invalid API contract: cloud connection provider is unknown.',
      );
    }
    if (provider != expectedProvider) {
      throw FormatException(
        'Invalid API contract: ${expectedProvider.apiValue} cloud connection has a mismatched provider.',
      );
    }
    return BoundCloudConnection(
      id: JsonContract.requiredString(json, 'id'),
      provider: provider,
      displayName: JsonContract.requiredString(json, 'display_name'),
      authType: JsonContract.requiredString(json, 'auth_type'),
      validationStatus: JsonContract.requiredString(json, 'validation_status'),
      lastValidatedAt: JsonContract.optionalDate(json, 'last_validated_at'),
    );
  }

  @override
  List<Object?> get props => [
    id,
    provider,
    displayName,
    authType,
    validationStatus,
    lastValidatedAt,
  ];
}

class TwinProviderConfig extends Equatable {
  final CloudProvider provider;
  final bool configured;
  final bool validated;
  final TwinCredentialSource? credentialSource;
  final String? cloudConnectionId;
  final BoundCloudConnection? cloudConnection;
  final String? region;
  final String? secondaryRegion;
  final String? tertiaryRegion;
  final String? projectId;
  final bool billingAccountConfigured;

  const TwinProviderConfig({
    required this.provider,
    required this.configured,
    required this.validated,
    this.credentialSource,
    this.cloudConnectionId,
    this.cloudConnection,
    this.region,
    this.secondaryRegion,
    this.tertiaryRegion,
    this.projectId,
    this.billingAccountConfigured = false,
  });

  bool get usesCloudConnection =>
      credentialSource == TwinCredentialSource.cloudConnection &&
      cloudConnectionId != null;

  @override
  List<Object?> get props => [
    provider,
    configured,
    validated,
    credentialSource,
    cloudConnectionId,
    cloudConnection,
    region,
    secondaryRegion,
    tertiaryRegion,
    projectId,
    billingAccountConfigured,
  ];
}

class TwinConfigData extends Equatable {
  final String id;
  final String twinId;
  final String? twinState;
  final bool debugMode;
  final Map<CloudProvider, TwinProviderConfig> providers;
  final int highestStepReached;
  final CalcParams? optimizerParams;
  final OptimizationResultData? optimization;
  final DateTime updatedAt;

  const TwinConfigData({
    required this.id,
    required this.twinId,
    this.twinState,
    required this.debugMode,
    required this.providers,
    required this.highestStepReached,
    this.optimizerParams,
    this.optimization,
    required this.updatedAt,
  });

  factory TwinConfigData.fromJson(Map<String, dynamic> json) {
    final twinState = JsonContract.optionalString(json, 'twin_state');
    if (twinState != null && !Twin.supportedStates.contains(twinState)) {
      throw const FormatException(
        'Invalid API contract: twin_state contains an unknown twin state.',
      );
    }
    final cloudConnections =
        JsonContract.optionalObject(json, 'cloud_connections') ?? const {};
    final paramsJson = JsonContract.optionalObject(json, 'optimizer_params');
    final resultJson = JsonContract.optionalObject(json, 'optimizer_result');
    final providers = <CloudProvider, TwinProviderConfig>{};
    for (final provider in CloudProvider.values) {
      providers[provider] = _providerConfig(json, cloudConnections, provider);
    }
    return TwinConfigData(
      id: JsonContract.requiredString(json, 'id'),
      twinId: JsonContract.requiredString(json, 'twin_id'),
      twinState: twinState,
      debugMode: JsonContract.requiredBool(json, 'debug_mode'),
      providers: Map.unmodifiable(providers),
      highestStepReached: JsonContract.requiredInt(
        json,
        'highest_step_reached',
      ),
      optimizerParams: paramsJson == null
          ? null
          : CalcParams.fromJson(paramsJson),
      optimization: resultJson == null
          ? null
          : OptimizationResultData.fromPayload(resultJson),
      updatedAt: JsonContract.requiredDate(json, 'updated_at'),
    );
  }

  TwinProviderConfig provider(CloudProvider provider) => providers[provider]!;

  Set<CloudProvider> get configuredProviders => Set.unmodifiable(
    providers.entries
        .where((entry) => entry.value.configured)
        .map((entry) => entry.key),
  );

  @override
  List<Object?> get props => [
    id,
    twinId,
    twinState,
    debugMode,
    providers,
    highestStepReached,
    optimizerParams,
    optimization,
    updatedAt,
  ];
}

TwinProviderConfig _providerConfig(
  Map<String, dynamic> json,
  Map<String, dynamic> boundConnections,
  CloudProvider provider,
) {
  final prefix = provider.apiValue;
  final configured = JsonContract.requiredBool(json, '${prefix}_configured');
  final source = TwinCredentialSource.optional(
    json['${prefix}_credential_source'],
    '${prefix}_credential_source',
  );
  final connectionId = JsonContract.optionalString(
    json,
    '${prefix}_cloud_connection_id',
  );
  final boundJson = boundConnections[prefix];
  final BoundCloudConnection? bound;
  if (boundJson == null) {
    bound = null;
  } else if (boundJson is Map) {
    bound = BoundCloudConnection.fromJson(
      Map<String, dynamic>.from(boundJson),
      expectedProvider: provider,
    );
  } else {
    throw FormatException(
      'Invalid API contract: cloud_connections.$prefix must be an object.',
    );
  }
  if (configured != (source != null && connectionId != null)) {
    throw FormatException(
      'Invalid API contract: $prefix credential metadata is inconsistent.',
    );
  }
  if (bound != null && bound.id != connectionId) {
    throw FormatException(
      'Invalid API contract: $prefix bound connection ID is inconsistent.',
    );
  }

  return TwinProviderConfig(
    provider: provider,
    configured: configured,
    validated: JsonContract.requiredBool(json, '${prefix}_validated'),
    credentialSource: source,
    cloudConnectionId: connectionId,
    cloudConnection: bound,
    region: JsonContract.optionalString(json, '${prefix}_region'),
    secondaryRegion: switch (provider) {
      CloudProvider.aws => JsonContract.optionalString(json, 'aws_sso_region'),
      CloudProvider.azure => JsonContract.optionalString(
        json,
        'azure_region_iothub',
      ),
      CloudProvider.gcp => null,
    },
    tertiaryRegion: provider == CloudProvider.azure
        ? JsonContract.optionalString(json, 'azure_region_digital_twin')
        : null,
    projectId: provider == CloudProvider.gcp
        ? JsonContract.optionalString(json, 'gcp_project_id')
        : null,
    billingAccountConfigured: provider == CloudProvider.gcp
        ? JsonContract.requiredBool(json, 'gcp_billing_account_configured')
        : false,
  );
}
