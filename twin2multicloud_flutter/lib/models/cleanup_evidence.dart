import 'package:equatable/equatable.dart';

enum CleanupEvidenceStatus {
  complete('complete'),
  incomplete('incomplete'),
  dryRun('dry_run');

  final String apiValue;

  const CleanupEvidenceStatus(this.apiValue);

  static CleanupEvidenceStatus parse(Object? value, String field) =>
      _parseEnum(values, value, field, (item) => item.apiValue);
}

enum CleanupInventoryStatus {
  empty('empty'),
  residual('residual'),
  inspectionFailed('inspection_failed'),
  notRun('not_run');

  final String apiValue;

  const CleanupInventoryStatus(this.apiValue);

  static CleanupInventoryStatus parse(Object? value, String field) =>
      _parseEnum(values, value, field, (item) => item.apiValue);
}

enum TerraformDestroyStatus {
  completed('completed'),
  failed('failed'),
  dryRun('dry_run');

  final String apiValue;

  const TerraformDestroyStatus(this.apiValue);

  static TerraformDestroyStatus parse(Object? value, String field) =>
      _parseEnum(values, value, field, (item) => item.apiValue);
}

enum ProviderCleanupStatus {
  completed('completed'),
  failed('failed'),
  notRun('not_run');

  final String apiValue;

  const ProviderCleanupStatus(this.apiValue);

  static ProviderCleanupStatus parse(Object? value, String field) =>
      _parseEnum(values, value, field, (item) => item.apiValue);
}

class TerraformCleanupEvidence extends Equatable {
  static const _allowed = {
    'destroy_status',
    'observed_before_resource_count',
    'post_destroy_inventory',
    'residual_resource_count',
  };
  static const _required = {'destroy_status', 'post_destroy_inventory'};

  final TerraformDestroyStatus destroyStatus;
  final int? observedBeforeResourceCount;
  final CleanupInventoryStatus postDestroyInventory;
  final int? residualResourceCount;

  const TerraformCleanupEvidence({
    required this.destroyStatus,
    this.observedBeforeResourceCount,
    required this.postDestroyInventory,
    this.residualResourceCount,
  });

  factory TerraformCleanupEvidence.fromJson(Map<String, dynamic> json) {
    _requireFields(json, _allowed, _required, 'Terraform evidence');
    return TerraformCleanupEvidence(
      destroyStatus: TerraformDestroyStatus.parse(
        json['destroy_status'],
        'terraform.destroy_status',
      ),
      observedBeforeResourceCount: _optionalNonNegativeInt(
        json,
        'observed_before_resource_count',
      ),
      postDestroyInventory: CleanupInventoryStatus.parse(
        json['post_destroy_inventory'],
        'terraform.post_destroy_inventory',
      ),
      residualResourceCount: _optionalNonNegativeInt(
        json,
        'residual_resource_count',
      ),
    );
  }

  @override
  List<Object?> get props => [
    destroyStatus,
    observedBeforeResourceCount,
    postDestroyInventory,
    residualResourceCount,
  ];
}

class ProviderCleanupEvidence extends Equatable {
  static const _allowed = {
    'provider',
    'cleanup_status',
    'discovered_during_cleanup_count',
    'discovered_resource_kinds',
    'post_destroy_inventory',
    'residual_resource_count',
  };
  static const _required = {
    'provider',
    'cleanup_status',
    'post_destroy_inventory',
  };

  final String provider;
  final ProviderCleanupStatus cleanupStatus;
  final int? discoveredDuringCleanupCount;
  final List<String> discoveredResourceKinds;
  final CleanupInventoryStatus postDestroyInventory;
  final int? residualResourceCount;

  const ProviderCleanupEvidence({
    required this.provider,
    required this.cleanupStatus,
    this.discoveredDuringCleanupCount,
    this.discoveredResourceKinds = const [],
    required this.postDestroyInventory,
    this.residualResourceCount,
  });

  factory ProviderCleanupEvidence.fromJson(Map<String, dynamic> json) {
    _requireFields(json, _allowed, _required, 'provider evidence');
    final provider = _requiredAllowedString(json, 'provider', const {
      'aws',
      'azure',
      'gcp',
    });
    final cleanupStatus = ProviderCleanupStatus.parse(
      json['cleanup_status'],
      'provider.cleanup_status',
    );
    final discoveredCount = _optionalNonNegativeInt(
      json,
      'discovered_during_cleanup_count',
    );
    final kindsValue = json['discovered_resource_kinds'] ?? const [];
    if (kindsValue is! List || kindsValue.length > 32) {
      throw const FormatException(
        'Invalid cleanup evidence contract: resource kinds must be bounded.',
      );
    }
    final kindPattern = RegExp(r'^[A-Za-z0-9 /._()-]+$');
    final kinds = kindsValue
        .map((value) {
          if (value is! String ||
              value.isEmpty ||
              value.length > 64 ||
              !kindPattern.hasMatch(value)) {
            throw const FormatException(
              'Invalid cleanup evidence contract: resource kind is invalid.',
            );
          }
          return value;
        })
        .toList(growable: false);
    final inventory = CleanupInventoryStatus.parse(
      json['post_destroy_inventory'],
      'provider.post_destroy_inventory',
    );
    final residualCount = _optionalNonNegativeInt(
      json,
      'residual_resource_count',
    );
    if (cleanupStatus == ProviderCleanupStatus.completed &&
        discoveredCount == null) {
      throw const FormatException(
        'Invalid cleanup evidence contract: completed cleanup lacks discovery evidence.',
      );
    }
    if ((inventory == CleanupInventoryStatus.empty && residualCount != 0) ||
        (inventory == CleanupInventoryStatus.residual &&
            (residualCount == null || residualCount <= 0)) ||
        ({
              CleanupInventoryStatus.inspectionFailed,
              CleanupInventoryStatus.notRun,
            }.contains(inventory) &&
            residualCount != null)) {
      throw const FormatException(
        'Invalid cleanup evidence contract: provider inventory is inconsistent.',
      );
    }
    return ProviderCleanupEvidence(
      provider: provider,
      cleanupStatus: cleanupStatus,
      discoveredDuringCleanupCount: discoveredCount,
      discoveredResourceKinds: List.unmodifiable(kinds),
      postDestroyInventory: inventory,
      residualResourceCount: residualCount,
    );
  }

  @override
  List<Object?> get props => [
    provider,
    cleanupStatus,
    discoveredDuringCleanupCount,
    discoveredResourceKinds,
    postDestroyInventory,
    residualResourceCount,
  ];
}

class RetainedSharedPrerequisite extends Equatable {
  static const _fields = {
    'provider',
    'requirement_type',
    'capability_id',
    'scope',
    'reason',
  };

  final String provider;
  final String requirementType;
  final String capabilityId;
  final String scope;
  final String reason;

  const RetainedSharedPrerequisite({
    required this.provider,
    required this.requirementType,
    required this.capabilityId,
    required this.scope,
    required this.reason,
  });

  factory RetainedSharedPrerequisite.fromJson(Map<String, dynamic> json) {
    _requireFields(json, _fields, _fields, 'retained prerequisite');
    final capabilityId = _requiredString(json, 'capability_id');
    if (capabilityId.length > 255 ||
        !RegExp(r'^[A-Za-z0-9._/-]+$').hasMatch(capabilityId)) {
      throw const FormatException(
        'Invalid cleanup evidence contract: capability ID is invalid.',
      );
    }
    return RetainedSharedPrerequisite(
      provider: _requiredAllowedString(json, 'provider', const {
        'azure',
        'gcp',
      }),
      requirementType: _requiredAllowedString(json, 'requirement_type', const {
        'resource_provider',
        'api',
      }),
      capabilityId: capabilityId,
      scope: _requiredAllowedString(json, 'scope', const {
        'subscription',
        'project',
      }),
      reason: _requiredAllowedString(json, 'reason', const {
        'persistent_account_prerequisite',
      }),
    );
  }

  @override
  List<Object?> get props => [
    provider,
    requirementType,
    capabilityId,
    scope,
    reason,
  ];
}

class CleanupResidualFailure extends Equatable {
  static const _allowed = {'scope', 'provider', 'reason'};
  static const _required = {'scope', 'reason'};

  final String scope;
  final String? provider;
  final String reason;

  const CleanupResidualFailure({
    required this.scope,
    this.provider,
    required this.reason,
  });

  factory CleanupResidualFailure.fromJson(Map<String, dynamic> json) {
    _requireFields(json, _allowed, _required, 'residual failure');
    final providerValue = json['provider'];
    return CleanupResidualFailure(
      scope: _requiredAllowedString(json, 'scope', const {
        'terraform_state',
        'provider_cleanup',
        'provider_inventory',
      }),
      provider: providerValue == null
          ? null
          : _requiredAllowedString(json, 'provider', const {
              'aws',
              'azure',
              'gcp',
            }),
      reason: _requiredAllowedString(json, 'reason', const {
        'resources_remain',
        'inspection_failed',
        'cleanup_failed',
        'context_unavailable',
      }),
    );
  }

  @override
  List<Object?> get props => [scope, provider, reason];
}

class CleanupEvidence extends Equatable {
  static const supportedSchemaVersion = 'cleanup-evidence.v1';
  static const _fields = {
    'schema_version',
    'status',
    'terraform',
    'providers',
    'retained_shared_prerequisites',
    'residual_failures',
  };

  final String schemaVersion;
  final CleanupEvidenceStatus status;
  final TerraformCleanupEvidence terraform;
  final List<ProviderCleanupEvidence> providers;
  final List<RetainedSharedPrerequisite> retainedSharedPrerequisites;
  final List<CleanupResidualFailure> residualFailures;

  const CleanupEvidence({
    required this.schemaVersion,
    required this.status,
    required this.terraform,
    required this.providers,
    required this.retainedSharedPrerequisites,
    required this.residualFailures,
  });

  factory CleanupEvidence.fromJson(Map<String, dynamic> json) {
    _requireFields(json, _fields, _fields, 'cleanup evidence');
    if (_requiredString(json, 'schema_version') != supportedSchemaVersion) {
      throw const FormatException(
        'Invalid cleanup evidence contract: schema version is unsupported.',
      );
    }
    final status = CleanupEvidenceStatus.parse(json['status'], 'status');
    final terraform = TerraformCleanupEvidence.fromJson(
      _requiredMap(json['terraform'], 'terraform'),
    );
    final providers = _requiredList(json, 'providers', maximum: 3)
        .map(
          (value) => ProviderCleanupEvidence.fromJson(
            _requiredMap(value, 'provider evidence'),
          ),
        )
        .toList(growable: false);
    final providerIds = providers.map((item) => item.provider).toSet();
    if (providerIds.length != providers.length) {
      throw const FormatException(
        'Invalid cleanup evidence contract: providers must be unique.',
      );
    }
    final retained =
        _requiredList(json, 'retained_shared_prerequisites', maximum: 100)
            .map(
              (value) => RetainedSharedPrerequisite.fromJson(
                _requiredMap(value, 'retained prerequisite'),
              ),
            )
            .toList(growable: false);
    final residual = _requiredList(json, 'residual_failures', maximum: 8)
        .map(
          (value) => CleanupResidualFailure.fromJson(
            _requiredMap(value, 'residual failure'),
          ),
        )
        .toList(growable: false);
    if (status == CleanupEvidenceStatus.complete &&
        (residual.isNotEmpty ||
            providers.isEmpty ||
            terraform.destroyStatus != TerraformDestroyStatus.completed ||
            terraform.postDestroyInventory != CleanupInventoryStatus.empty ||
            terraform.residualResourceCount != 0 ||
            providers.any(
              (item) =>
                  item.cleanupStatus != ProviderCleanupStatus.completed ||
                  item.postDestroyInventory != CleanupInventoryStatus.empty ||
                  item.residualResourceCount != 0,
            ))) {
      throw const FormatException(
        'Invalid cleanup evidence contract: complete cleanup is inconsistent.',
      );
    }
    if (status == CleanupEvidenceStatus.incomplete && residual.isEmpty) {
      throw const FormatException(
        'Invalid cleanup evidence contract: incomplete cleanup lacks residual evidence.',
      );
    }
    return CleanupEvidence(
      schemaVersion: supportedSchemaVersion,
      status: status,
      terraform: terraform,
      providers: List.unmodifiable(providers),
      retainedSharedPrerequisites: List.unmodifiable(retained),
      residualFailures: List.unmodifiable(residual),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    status,
    terraform,
    providers,
    retainedSharedPrerequisites,
    residualFailures,
  ];
}

T _parseEnum<T>(
  List<T> values,
  Object? value,
  String field,
  String Function(T) apiValue,
) {
  for (final candidate in values) {
    if (apiValue(candidate) == value) return candidate;
  }
  throw FormatException(
    'Invalid cleanup evidence contract: $field is unsupported.',
  );
}

void _requireFields(
  Map<String, dynamic> json,
  Set<String> allowed,
  Set<String> required,
  String contract,
) {
  if (json.keys.toSet().difference(allowed).isNotEmpty ||
      required.difference(json.keys.toSet()).isNotEmpty) {
    throw FormatException(
      'Invalid cleanup evidence contract: $contract fields do not match v1.',
    );
  }
}

Map<String, dynamic> _requiredMap(Object? value, String field) {
  if (value is! Map) {
    throw FormatException(
      'Invalid cleanup evidence contract: $field must be an object.',
    );
  }
  return Map<String, dynamic>.from(value);
}

List<dynamic> _requiredList(
  Map<String, dynamic> json,
  String field, {
  required int maximum,
}) {
  final value = json[field];
  if (value is! List || value.length > maximum) {
    throw FormatException(
      'Invalid cleanup evidence contract: $field must be a bounded list.',
    );
  }
  return value;
}

String _requiredString(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException(
      'Invalid cleanup evidence contract: $field must be a string.',
    );
  }
  return value.trim();
}

String _requiredAllowedString(
  Map<String, dynamic> json,
  String field,
  Set<String> allowed,
) {
  final value = _requiredString(json, field);
  if (!allowed.contains(value)) {
    throw FormatException(
      'Invalid cleanup evidence contract: $field is unsupported.',
    );
  }
  return value;
}

int? _optionalNonNegativeInt(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value == null) return null;
  if (value is! int || value < 0) {
    throw FormatException(
      'Invalid cleanup evidence contract: $field must be non-negative or null.',
    );
  }
  return value;
}
