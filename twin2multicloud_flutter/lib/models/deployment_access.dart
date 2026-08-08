import 'package:equatable/equatable.dart';

import '../core/result.dart';
import 'cloud_connection.dart';

enum DeploymentLayer {
  l4,
  l5;

  static DeploymentLayer parse(Object? value, String field) => switch (value) {
    'l4' => DeploymentLayer.l4,
    'l5' => DeploymentLayer.l5,
    _ => throw _contractError('$field contains an unknown layer.'),
  };
}

enum DeploymentAccessAuthMode {
  awsIdentityCenter('aws_identity_center'),
  azureEntra('azure_entra'),
  gcpIap('gcp_iap'),
  generatedViewer('generated_viewer');

  final String apiValue;

  const DeploymentAccessAuthMode(this.apiValue);

  static DeploymentAccessAuthMode parse(Object? value, String field) {
    return values.firstWhere(
      (candidate) => candidate.apiValue == value,
      orElse: () => throw _contractError('$field contains an unknown mode.'),
    );
  }
}

enum DeploymentAccessCredentialAction {
  none,
  rotate;

  static DeploymentAccessCredentialAction parse(Object? value, String field) {
    return switch (value) {
      'none' => DeploymentAccessCredentialAction.none,
      'rotate' => DeploymentAccessCredentialAction.rotate,
      _ => throw _contractError('$field contains an unknown action.'),
    };
  }
}

enum DeploymentAccessResourceStatus {
  ready,
  failed,
  pending;

  static DeploymentAccessResourceStatus parse(Object? value, String field) {
    return _parseNamedEnum(values, value, field);
  }
}

enum DeploymentAccessBindingStatus {
  ready,
  blocked,
  pending;

  static DeploymentAccessBindingStatus parse(Object? value, String field) {
    return _parseNamedEnum(values, value, field);
  }
}

enum DeploymentAccessContentStatus {
  ready,
  failed,
  pending;

  static DeploymentAccessContentStatus parse(Object? value, String field) {
    return _parseNamedEnum(values, value, field);
  }
}

enum DeploymentAccessDataProbeStatus {
  ready,
  failed,
  pending;

  static DeploymentAccessDataProbeStatus parse(Object? value, String field) {
    return _parseNamedEnum(values, value, field);
  }
}

enum DeploymentAccessBrowserStatus {
  unverified,
  verified,
  failed;

  static DeploymentAccessBrowserStatus parse(Object? value, String field) {
    return _parseNamedEnum(values, value, field);
  }
}

enum DeploymentAccessAvailability {
  available,
  unsupported;

  static DeploymentAccessAvailability parse(Object? value, String field) {
    return _parseNamedEnum(values, value, field);
  }
}

class LayerAccessReadiness extends Equatable {
  final DeploymentAccessResourceStatus resource;
  final DeploymentAccessBindingStatus accessBinding;
  final DeploymentAccessContentStatus content;
  final DeploymentAccessDataProbeStatus dataProbe;
  final DeploymentAccessBrowserStatus browserSignIn;

  const LayerAccessReadiness({
    required this.resource,
    required this.accessBinding,
    required this.content,
    required this.dataProbe,
    required this.browserSignIn,
  });

  factory LayerAccessReadiness.fromJson(
    Map<String, dynamic> json,
    String path,
  ) {
    _expectKeys(json, const {
      'resource',
      'access_binding',
      'content',
      'data_probe',
      'browser_sign_in',
    }, path);
    return LayerAccessReadiness(
      resource: DeploymentAccessResourceStatus.parse(
        json['resource'],
        '$path.resource',
      ),
      accessBinding: DeploymentAccessBindingStatus.parse(
        json['access_binding'],
        '$path.access_binding',
      ),
      content: DeploymentAccessContentStatus.parse(
        json['content'],
        '$path.content',
      ),
      dataProbe: DeploymentAccessDataProbeStatus.parse(
        json['data_probe'],
        '$path.data_probe',
      ),
      browserSignIn: DeploymentAccessBrowserStatus.parse(
        json['browser_sign_in'],
        '$path.browser_sign_in',
      ),
    );
  }

  bool get canOpen =>
      resource == DeploymentAccessResourceStatus.ready &&
      accessBinding == DeploymentAccessBindingStatus.ready;

  @override
  List<Object?> get props => [
    resource,
    accessBinding,
    content,
    dataProbe,
    browserSignIn,
  ];
}

class LayerAccessAuth extends Equatable {
  final DeploymentAccessAuthMode mode;
  final String principalLabel;
  final DeploymentAccessCredentialAction credentialAction;

  const LayerAccessAuth({
    required this.mode,
    required this.principalLabel,
    required this.credentialAction,
  });

  factory LayerAccessAuth.fromJson(Map<String, dynamic> json, String path) {
    _expectKeys(json, const {
      'mode',
      'principal_label',
      'credential_action',
    }, path);
    return LayerAccessAuth(
      mode: DeploymentAccessAuthMode.parse(json['mode'], '$path.mode'),
      principalLabel: _requiredString(
        json,
        'principal_label',
        path,
        maxLength: 320,
      ),
      credentialAction: DeploymentAccessCredentialAction.parse(
        json['credential_action'],
        '$path.credential_action',
      ),
    );
  }

  @override
  List<Object?> get props => [mode, principalLabel, credentialAction];
}

class DeploymentAccessSurface extends Equatable {
  final DeploymentLayer layer;
  final CloudProvider provider;
  final String serviceId;
  final String displayName;
  final Uri url;
  final LayerAccessAuth auth;
  final LayerAccessReadiness readiness;
  final List<String> capabilities;
  final List<String> limitations;

  const DeploymentAccessSurface({
    required this.layer,
    required this.provider,
    required this.serviceId,
    required this.displayName,
    required this.url,
    required this.auth,
    required this.readiness,
    required this.capabilities,
    required this.limitations,
  });

  factory DeploymentAccessSurface.fromJson(
    Map<String, dynamic> json,
    String path,
  ) {
    _rejectSecretKeys(json, path);
    _expectKeys(json, const {
      'layer',
      'provider',
      'service_id',
      'display_name',
      'url',
      'auth',
      'readiness',
      'capabilities',
      'limitations',
    }, path);
    final layer = DeploymentLayer.parse(json['layer'], '$path.layer');
    final provider = _provider(json['provider'], '$path.provider');
    final serviceId = _requiredString(json, 'service_id', path, maxLength: 80);
    final auth = LayerAccessAuth.fromJson(
      _requiredMap(json, 'auth', path),
      '$path.auth',
    );
    _validateSurfaceCombination(layer, provider, serviceId, auth, path);
    return DeploymentAccessSurface(
      layer: layer,
      provider: provider,
      serviceId: serviceId,
      displayName: _requiredString(json, 'display_name', path, maxLength: 160),
      url: _httpsUri(json['url'], '$path.url'),
      auth: auth,
      readiness: LayerAccessReadiness.fromJson(
        _requiredMap(json, 'readiness', path),
        '$path.readiness',
      ),
      capabilities: _stringList(
        json,
        'capabilities',
        path,
        requireNonEmpty: true,
      ),
      limitations: _stringList(json, 'limitations', path),
    );
  }

  @override
  List<Object?> get props => [
    layer,
    provider,
    serviceId,
    displayName,
    url,
    auth,
    readiness,
    capabilities,
    limitations,
  ];
}

class DeploymentAccessSnapshot extends Equatable {
  static const supportedSchemaVersion = 'deployment-access.v1';

  final String twinId;
  final String deploymentId;
  final DateTime generatedAt;
  final DeploymentAccessAvailability availability;
  final String? reasonCode;
  final List<DeploymentAccessSurface> surfaces;

  const DeploymentAccessSnapshot({
    required this.twinId,
    required this.deploymentId,
    required this.generatedAt,
    required this.availability,
    required this.reasonCode,
    required this.surfaces,
  });

  factory DeploymentAccessSnapshot.fromJson(
    Map<String, dynamic> json, {
    String? expectedTwinId,
  }) {
    _rejectSecretKeys(json, 'deployment_access');
    _expectKeys(json, const {
      'schema_version',
      'twin_id',
      'deployment_id',
      'generated_at',
      'availability',
      'reason_code',
      'surfaces',
    }, 'deployment_access');
    if (json['schema_version'] != supportedSchemaVersion) {
      throw _contractError('Unsupported deployment access schema version.');
    }
    final twinId = _requiredString(
      json,
      'twin_id',
      'deployment_access',
      maxLength: 160,
    );
    if (expectedTwinId != null && twinId != expectedTwinId) {
      throw _contractError('Deployment access belongs to another twin.');
    }
    final availability = DeploymentAccessAvailability.parse(
      json['availability'],
      'deployment_access.availability',
    );
    final rawSurfaces = json['surfaces'];
    if (rawSurfaces is! List) {
      throw _contractError('deployment_access.surfaces must be a list.');
    }
    final surfaces = rawSurfaces.indexed
        .map(
          (entry) => DeploymentAccessSurface.fromJson(
            _asMap(entry.$2, 'deployment_access.surfaces[${entry.$1}]'),
            'deployment_access.surfaces[${entry.$1}]',
          ),
        )
        .toList(growable: false);
    final reason = json['reason_code'];
    if (availability == DeploymentAccessAvailability.available) {
      if (reason != null || surfaces.length != 2) {
        throw _contractError(
          'Available deployment access requires exactly L4 and L5 surfaces.',
        );
      }
      final layers = surfaces.map((surface) => surface.layer).toSet();
      if (layers.length != 2 || !layers.containsAll(DeploymentLayer.values)) {
        throw _contractError(
          'Available deployment access requires unique L4 and L5 surfaces.',
        );
      }
    } else if (reason != 'unsupported_historical_profile' ||
        surfaces.isNotEmpty) {
      throw _contractError(
        'Unsupported deployment access requires its historical reason only.',
      );
    }
    return DeploymentAccessSnapshot(
      twinId: twinId,
      deploymentId: _requiredString(
        json,
        'deployment_id',
        'deployment_access',
        maxLength: 160,
      ),
      generatedAt: _requiredDate(json, 'generated_at', 'deployment_access'),
      availability: availability,
      reasonCode: reason as String?,
      surfaces: List.unmodifiable(surfaces),
    );
  }

  DeploymentAccessSurface? surfaceFor(DeploymentLayer layer) {
    for (final surface in surfaces) {
      if (surface.layer == layer) return surface;
    }
    return null;
  }

  @override
  List<Object?> get props => [
    twinId,
    deploymentId,
    generatedAt,
    availability,
    reasonCode,
    surfaces,
  ];
}

class DeploymentAccessCredential extends Equatable {
  static const supportedSchemaVersion = 'deployment-access-credential.v1';

  final String username;
  final String password;
  final DateTime issuedAt;

  const DeploymentAccessCredential._({
    required this.username,
    required this.password,
    required this.issuedAt,
  });

  factory DeploymentAccessCredential.fromJson(Map<String, dynamic> json) {
    _expectKeys(json, const {
      'schema_version',
      'layer',
      'provider',
      'username',
      'password',
      'issued_at',
    }, 'deployment_access_credential');
    if (json['schema_version'] != supportedSchemaVersion ||
        json['layer'] != 'l5' ||
        json['provider'] != 'gcp') {
      throw _contractError('Unsupported deployment access credential.');
    }
    return DeploymentAccessCredential._(
      username: _requiredString(
        json,
        'username',
        'deployment_access_credential',
        maxLength: 320,
      ),
      password: _requiredString(
        json,
        'password',
        'deployment_access_credential',
        maxLength: 4096,
      ),
      issuedAt: _requiredDate(
        json,
        'issued_at',
        'deployment_access_credential',
      ),
    );
  }

  @override
  List<Object?> get props => [username, issuedAt];

  @override
  String toString() =>
      'DeploymentAccessCredential(username: $username, issuedAt: $issuedAt)';
}

T _parseNamedEnum<T extends Enum>(List<T> values, Object? value, String field) {
  for (final candidate in values) {
    if (candidate.name == value) return candidate;
  }
  throw _contractError('$field contains an unknown status.');
}

void _validateSurfaceCombination(
  DeploymentLayer layer,
  CloudProvider provider,
  String serviceId,
  LayerAccessAuth auth,
  String path,
) {
  final valid = switch ((layer, provider)) {
    (DeploymentLayer.l4, CloudProvider.aws) =>
      serviceId == 'aws_iot_twinmaker' &&
          auth.mode == DeploymentAccessAuthMode.awsIdentityCenter &&
          auth.credentialAction == DeploymentAccessCredentialAction.none,
    (DeploymentLayer.l4, CloudProvider.azure) =>
      serviceId == 'azure_digital_twins' &&
          auth.mode == DeploymentAccessAuthMode.azureEntra &&
          auth.credentialAction == DeploymentAccessCredentialAction.none,
    (DeploymentLayer.l4, CloudProvider.gcp) =>
      serviceId == 'gcp_twin_explorer' &&
          auth.mode == DeploymentAccessAuthMode.gcpIap &&
          auth.credentialAction == DeploymentAccessCredentialAction.none,
    (DeploymentLayer.l5, CloudProvider.aws) =>
      serviceId == 'aws_managed_grafana' &&
          auth.mode == DeploymentAccessAuthMode.awsIdentityCenter &&
          auth.credentialAction == DeploymentAccessCredentialAction.none,
    (DeploymentLayer.l5, CloudProvider.azure) =>
      serviceId == 'azure_managed_grafana' &&
          auth.mode == DeploymentAccessAuthMode.azureEntra &&
          auth.credentialAction == DeploymentAccessCredentialAction.none,
    (DeploymentLayer.l5, CloudProvider.gcp) =>
      serviceId == 'gcp_grafana_oss' &&
          auth.mode == DeploymentAccessAuthMode.generatedViewer &&
          auth.credentialAction == DeploymentAccessCredentialAction.rotate,
  };
  if (!valid) {
    throw _contractError('$path has an unsupported provider surface.');
  }
}

CloudProvider _provider(Object? value, String field) {
  if (value is! String) {
    throw _contractError('$field must be a provider string.');
  }
  try {
    return CloudProvider.fromApiValue(value);
  } on ArgumentError {
    throw _contractError('$field contains an unknown provider.');
  }
}

Uri _httpsUri(Object? value, String field) {
  if (value is! String || value.trim() != value || value.isEmpty) {
    throw _contractError('$field must be an HTTPS URL.');
  }
  final uri = Uri.tryParse(value);
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.host.isEmpty ||
      uri.userInfo.isNotEmpty) {
    throw _contractError('$field must be an HTTPS URL without user info.');
  }
  return uri;
}

Map<String, dynamic> _requiredMap(
  Map<String, dynamic> json,
  String field,
  String path,
) {
  return _asMap(json[field], '$path.$field');
}

Map<String, dynamic> _asMap(Object? value, String field) {
  if (value is! Map || value.keys.any((key) => key is! String)) {
    throw _contractError('$field must be an object with string keys.');
  }
  return Map<String, dynamic>.unmodifiable(value.cast<String, dynamic>());
}

String _requiredString(
  Map<String, dynamic> json,
  String field,
  String path, {
  required int maxLength,
}) {
  final value = json[field];
  if (value is! String ||
      value.trim().isEmpty ||
      value.trim() != value ||
      value.length > maxLength) {
    throw _contractError('$path.$field must be a non-empty bounded string.');
  }
  return value;
}

DateTime _requiredDate(Map<String, dynamic> json, String field, String path) {
  final value = json[field];
  final parsed = value is String ? DateTime.tryParse(value) : null;
  if (parsed == null) {
    throw _contractError('$path.$field must be an ISO-8601 timestamp.');
  }
  return parsed.toUtc();
}

List<String> _stringList(
  Map<String, dynamic> json,
  String field,
  String path, {
  bool requireNonEmpty = false,
}) {
  final value = json[field];
  if (value is! List ||
      (requireNonEmpty && value.isEmpty) ||
      value.length > 32) {
    throw _contractError('$path.$field must be a bounded list.');
  }
  final parsed = <String>[];
  for (final entry in value.indexed) {
    final item = entry.$2;
    if (item is! String ||
        item.trim().isEmpty ||
        item.trim() != item ||
        item.length > 500) {
      throw _contractError('$path.$field[${entry.$1}] must be a string.');
    }
    parsed.add(item);
  }
  if (parsed.toSet().length != parsed.length) {
    throw _contractError('$path.$field must not contain duplicates.');
  }
  return List.unmodifiable(parsed);
}

void _expectKeys(Map<String, dynamic> json, Set<String> keys, String path) {
  if (json.keys.toSet().difference(keys).isNotEmpty ||
      keys.difference(json.keys.toSet()).isNotEmpty) {
    throw _contractError('$path has missing or unknown fields.');
  }
}

void _rejectSecretKeys(Object? value, String path) {
  const denied = {
    'password',
    'secret',
    'secret_access_key',
    'client_secret',
    'private_key',
    'session_token',
    'access_token',
    'refresh_token',
    'api_key',
    'service_account_json',
  };
  if (value is Map) {
    for (final entry in value.entries) {
      final key = entry.key.toString().toLowerCase();
      if (denied.contains(key) || key.endsWith('_password')) {
        throw _contractError('$path contains a secret field.');
      }
      _rejectSecretKeys(entry.value, '$path.$key');
    }
  } else if (value is List) {
    for (final entry in value.indexed) {
      _rejectSecretKeys(entry.$2, '$path[${entry.$1}]');
    }
  }
}

AppException _contractError(String message) {
  return AppException(message, code: 'DEPLOYMENT_ACCESS_CONTRACT_INVALID');
}
