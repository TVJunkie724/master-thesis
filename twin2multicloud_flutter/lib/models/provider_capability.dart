import 'package:equatable/equatable.dart';

enum CapabilityAvailability { available, disabled, unsupported }

enum CapabilityRoadmap { none, planned }

enum CapabilityVerificationLevel { notVerified, contractTested, liveVerified }

class CapabilitySource extends Equatable {
  final CapabilityAvailability availability;
  final CapabilityRoadmap roadmap;
  final String? reasonCode;
  final String? reason;
  final CapabilityVerificationLevel verificationLevel;

  const CapabilitySource({
    required this.availability,
    required this.roadmap,
    required this.reasonCode,
    required this.reason,
    required this.verificationLevel,
  });

  factory CapabilitySource.fromJson(Map<String, dynamic> json) {
    _expectKeys(json, const {
      'availability',
      'roadmap',
      'reason_code',
      'reason',
      'verification_level',
    }, 'capability source');
    return CapabilitySource(
      availability: _availability(json['availability']),
      roadmap: _roadmap(json['roadmap']),
      reasonCode: _nullableString(json['reason_code'], 'reason_code'),
      reason: _nullableString(json['reason'], 'reason'),
      verificationLevel: _verification(json['verification_level']),
    );
  }

  @override
  List<Object?> get props => [
    availability,
    roadmap,
    reasonCode,
    reason,
    verificationLevel,
  ];
}

class CapabilitySources extends Equatable {
  final CapabilitySource optimizer;
  final CapabilitySource deployer;

  const CapabilitySources({required this.optimizer, required this.deployer});

  factory CapabilitySources.fromJson(Map<String, dynamic> json) {
    _expectKeys(json, const {'optimizer', 'deployer'}, 'capability sources');
    return CapabilitySources(
      optimizer: CapabilitySource.fromJson(
        _object(json['optimizer'], 'sources.optimizer'),
      ),
      deployer: CapabilitySource.fromJson(
        _object(json['deployer'], 'sources.deployer'),
      ),
    );
  }

  @override
  List<Object?> get props => [optimizer, deployer];
}

class PlatformLayerCapability extends Equatable {
  final String layer;
  final CapabilityAvailability availability;
  final CapabilityRoadmap roadmap;
  final String? reasonCode;
  final String? reason;
  final bool selectable;
  final bool sourcesAgree;
  final String restrictionSource;
  final CapabilityVerificationLevel verificationLevel;
  final CapabilitySources sources;

  const PlatformLayerCapability({
    required this.layer,
    required this.availability,
    required this.roadmap,
    required this.reasonCode,
    required this.reason,
    required this.selectable,
    required this.sourcesAgree,
    required this.restrictionSource,
    required this.verificationLevel,
    required this.sources,
  });

  factory PlatformLayerCapability.fromJson(Map<String, dynamic> json) {
    _expectKeys(json, const {
      'layer',
      'availability',
      'roadmap',
      'reason_code',
      'reason',
      'selectable',
      'sources_agree',
      'restriction_source',
      'verification_level',
      'sources',
    }, 'platform layer capability');
    final layer = _requiredString(json['layer'], 'layer');
    if (!_layerIds.contains(layer)) {
      throw FormatException('Unsupported provider capability layer: $layer');
    }
    final availability = _availability(json['availability']);
    final selectable = _requiredBool(json['selectable'], 'selectable');
    if (selectable != (availability == CapabilityAvailability.available)) {
      throw const FormatException(
        'Provider capability selectable state is inconsistent.',
      );
    }
    final restrictionSource = _requiredString(
      json['restriction_source'],
      'restriction_source',
    );
    if (!_restrictionSources.contains(restrictionSource)) {
      throw FormatException(
        'Unsupported capability restriction source: $restrictionSource',
      );
    }
    return PlatformLayerCapability(
      layer: layer,
      availability: availability,
      roadmap: _roadmap(json['roadmap']),
      reasonCode: _nullableString(json['reason_code'], 'reason_code'),
      reason: _nullableString(json['reason'], 'reason'),
      selectable: selectable,
      sourcesAgree: _requiredBool(json['sources_agree'], 'sources_agree'),
      restrictionSource: restrictionSource,
      verificationLevel: _verification(json['verification_level']),
      sources: CapabilitySources.fromJson(
        _object(json['sources'], 'capability sources'),
      ),
    );
  }

  @override
  List<Object?> get props => [
    layer,
    availability,
    roadmap,
    reasonCode,
    reason,
    selectable,
    sourcesAgree,
    restrictionSource,
    verificationLevel,
    sources,
  ];
}

class PlatformProviderCapability extends Equatable {
  final String provider;
  final List<PlatformLayerCapability> layers;

  const PlatformProviderCapability({
    required this.provider,
    required this.layers,
  });

  factory PlatformProviderCapability.fromJson(Map<String, dynamic> json) {
    _expectKeys(json, const {'provider', 'layers'}, 'provider capability');
    final provider = _requiredString(json['provider'], 'provider');
    if (!_providerIds.contains(provider)) {
      throw FormatException('Unsupported capability provider: $provider');
    }
    final layers = _objectList(
      json['layers'],
      'provider layers',
    ).map(PlatformLayerCapability.fromJson).toList(growable: false);
    if (layers.map((item) => item.layer).toList().join('|') !=
        _layerIds.join('|')) {
      throw FormatException(
        'Capability provider $provider must contain every layer exactly once.',
      );
    }
    return PlatformProviderCapability(provider: provider, layers: layers);
  }

  PlatformLayerCapability layer(String layerId) => layers.firstWhere(
    (item) => item.layer == layerId,
    orElse: () => throw StateError('Capability layer $layerId is unavailable.'),
  );

  @override
  List<Object?> get props => [provider, layers];
}

class PlatformProviderCapabilities extends Equatable {
  static const supportedSchemaVersion = 'platform-provider-capabilities.v1';

  final String schemaVersion;
  final bool complete;
  final List<PlatformProviderCapability> providers;

  const PlatformProviderCapabilities({
    required this.schemaVersion,
    required this.complete,
    required this.providers,
  });

  factory PlatformProviderCapabilities.fromJson(Map<String, dynamic> json) {
    _expectKeys(json, const {
      'schema_version',
      'complete',
      'sources',
      'providers',
    }, 'platform provider capabilities');
    final schemaVersion = _requiredString(
      json['schema_version'],
      'schema_version',
    );
    if (schemaVersion != supportedSchemaVersion) {
      throw FormatException(
        'Unsupported provider capability schema: $schemaVersion',
      );
    }
    final complete = _requiredBool(json['complete'], 'complete');
    if (!complete) {
      throw const FormatException(
        'Incomplete provider capability contracts are not supported.',
      );
    }
    _validateSourceHealth(_object(json['sources'], 'capability source health'));
    final providers = _objectList(
      json['providers'],
      'providers',
    ).map(PlatformProviderCapability.fromJson).toList(growable: false);
    if (providers.map((item) => item.provider).toList().join('|') !=
        _providerIds.join('|')) {
      throw const FormatException(
        'Provider capability contract must contain AWS, Azure, and GCP.',
      );
    }
    return PlatformProviderCapabilities(
      schemaVersion: schemaVersion,
      complete: complete,
      providers: providers,
    );
  }

  PlatformLayerCapability capability(String provider, String layer) {
    final normalized = provider.toLowerCase() == 'google'
        ? 'gcp'
        : provider.toLowerCase();
    return providers
        .firstWhere(
          (item) => item.provider == normalized,
          orElse: () => throw StateError(
            'Capability provider $normalized is unavailable.',
          ),
        )
        .layer(layer.toLowerCase());
  }

  @override
  List<Object?> get props => [schemaVersion, complete, providers];
}

const _providerIds = ['aws', 'azure', 'gcp'];
const _layerIds = ['l1', 'l2', 'l3_hot', 'l3_cool', 'l3_archive', 'l4', 'l5'];
const _restrictionSources = {
  'none',
  'restricted_by_optimizer',
  'restricted_by_deployer',
  'restricted_by_both',
};

void _validateSourceHealth(Map<String, dynamic> json) {
  _expectKeys(json, const {
    'optimizer',
    'deployer',
  }, 'capability source health');
  for (final service in const ['optimizer', 'deployer']) {
    final source = _object(json[service], 'capability source health.$service');
    _expectKeys(source, const {
      'status',
      'schema_version',
    }, 'capability source health.$service');
    if (source['status'] != 'available' ||
        source['schema_version'] != 'provider-service-capabilities.v1') {
      throw FormatException('Capability source $service is not available.');
    }
  }
}

CapabilityAvailability _availability(dynamic value) => switch (value) {
  'available' => CapabilityAvailability.available,
  'disabled' => CapabilityAvailability.disabled,
  'unsupported' => CapabilityAvailability.unsupported,
  _ => throw FormatException('Unsupported capability availability: $value'),
};

CapabilityRoadmap _roadmap(dynamic value) => switch (value) {
  'none' => CapabilityRoadmap.none,
  'planned' => CapabilityRoadmap.planned,
  _ => throw FormatException('Unsupported capability roadmap state: $value'),
};

CapabilityVerificationLevel _verification(dynamic value) => switch (value) {
  'not_verified' => CapabilityVerificationLevel.notVerified,
  'contract_tested' => CapabilityVerificationLevel.contractTested,
  'live_verified' => CapabilityVerificationLevel.liveVerified,
  _ => throw FormatException(
    'Unsupported capability verification level: $value',
  ),
};

Map<String, dynamic> _object(dynamic value, String field) {
  if (value is! Map) throw FormatException('$field must be an object.');
  return Map<String, dynamic>.from(value);
}

List<Map<String, dynamic>> _objectList(dynamic value, String field) {
  if (value is! List) throw FormatException('$field must be an array.');
  return value.indexed
      .map((entry) => _object(entry.$2, '$field[${entry.$1}]'))
      .toList(growable: false);
}

String _requiredString(dynamic value, String field) {
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('$field must be a non-empty string.');
  }
  return value;
}

String? _nullableString(dynamic value, String field) {
  if (value == null) return null;
  return _requiredString(value, field);
}

bool _requiredBool(dynamic value, String field) {
  if (value is! bool) throw FormatException('$field must be a boolean.');
  return value;
}

void _expectKeys(Map<String, dynamic> json, Set<String> keys, String label) {
  final actual = json.keys.toSet();
  if (actual.length != keys.length || !actual.containsAll(keys)) {
    throw FormatException('$label contains missing or unexpected fields.');
  }
}
