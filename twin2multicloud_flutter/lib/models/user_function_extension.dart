import 'dart:convert';
import 'dart:typed_data';

import 'package:equatable/equatable.dart';

enum UserFunctionWorkflowPhase {
  draft,
  validating,
  invalid,
  valid,
  saving,
  saved,
  stale,
  error,
}

final class ExtensionConfigurationField extends Equatable {
  final String name;
  final String type;
  final String title;
  final bool required;
  final num? minimum;
  final num? maximum;
  final int? minLength;
  final int? maxLength;
  final String? pattern;
  final List<Object> allowedValues;

  const ExtensionConfigurationField({
    required this.name,
    required this.type,
    required this.title,
    required this.required,
    this.minimum,
    this.maximum,
    this.minLength,
    this.maxLength,
    this.pattern,
    this.allowedValues = const [],
  });

  factory ExtensionConfigurationField.fromJson(
    String name,
    Map<String, dynamic> json, {
    required bool required,
  }) {
    _exactFields(
      json,
      const {
        'type',
        'title',
        'minimum',
        'maximum',
        'minLength',
        'maxLength',
        'pattern',
        'enum',
        'user_editable',
        'secret',
      },
      'configuration.$name',
      optional: const {
        'title',
        'minimum',
        'maximum',
        'minLength',
        'maxLength',
        'pattern',
        'enum',
      },
    );
    if (json['user_editable'] != true || json['secret'] != false) {
      throw FormatException(
        'Invalid extension contract: configuration field "$name" is not '
        'an approved non-secret user-editable field.',
      );
    }
    final type = _string(json['type'], 'configuration.$name.type');
    if (!{'string', 'integer', 'number', 'boolean'}.contains(type)) {
      throw FormatException(
        'Invalid extension contract: configuration field "$name" has an '
        'unsupported UI type.',
      );
    }
    final values = json['enum'];
    if (values != null && values is! List) {
      throw FormatException(
        'Invalid extension contract: configuration.$name.enum must be an array.',
      );
    }
    return ExtensionConfigurationField(
      name: name,
      type: type,
      title: json['title'] is String ? json['title'] as String : name,
      required: required,
      minimum: json['minimum'] as num?,
      maximum: json['maximum'] as num?,
      minLength: json['minLength'] as int?,
      maxLength: json['maxLength'] as int?,
      pattern: json['pattern'] as String?,
      allowedValues: List<Object>.unmodifiable(
        (values as List?)?.whereType<Object>() ?? const [],
      ),
    );
  }

  @override
  List<Object?> get props => [
    name,
    type,
    title,
    required,
    minimum,
    maximum,
    minLength,
    maxLength,
    pattern,
    allowedValues,
  ];
}

final class ExtensionSlot extends Equatable {
  static const supportedSchemaVersion = 'user-function-extension-slot.v1';

  final String slotId;
  final String slotVersion;
  final String displayName;
  final String runtimeId;
  final List<ExtensionConfigurationField> configurationFields;
  final Map<String, int> resourceLimits;
  final List<String> permissionCapabilities;

  const ExtensionSlot({
    required this.slotId,
    required this.slotVersion,
    required this.displayName,
    required this.runtimeId,
    required this.configurationFields,
    required this.resourceLimits,
    required this.permissionCapabilities,
  });

  factory ExtensionSlot.fromJson(Map<String, dynamic> json) {
    _exactFields(json, const {
      'schema_version',
      'slot_id',
      'slot_version',
      'display_name',
      'entrypoint',
      'runtime_id',
      'configuration_schema',
      'resource_limits',
      'permission_capabilities',
      'secret_policy',
    }, 'extension slot');
    _version(json, supportedSchemaVersion, 'extension slot');
    if (json['secret_policy'] != 'forbidden' ||
        json['entrypoint'] != 'process' ||
        json['runtime_id'] != 'python311') {
      throw const FormatException(
        'Invalid extension contract: unsupported v1 runtime ownership.',
      );
    }
    final schema = _map(json['configuration_schema'], 'configuration_schema');
    _exactFields(schema, const {
      r'$schema',
      'type',
      'additionalProperties',
      'properties',
      'required',
    }, 'configuration_schema');
    if (schema[r'$schema'] != 'https://json-schema.org/draft/2020-12/schema' ||
        schema['type'] != 'object' ||
        schema['additionalProperties'] != false) {
      throw const FormatException(
        'Invalid extension contract: configuration schema must be closed.',
      );
    }
    final properties = _map(
      schema['properties'],
      'configuration_schema.properties',
    );
    final required = _stringList(
      schema['required'],
      'configuration_schema.required',
    ).toSet();
    final limits = _map(json['resource_limits'], 'resource_limits');
    _exactFields(limits, const {
      'timeout_seconds',
      'memory_mb',
      'artifact_bytes',
      'source_bytes',
      'response_bytes',
      'file_count',
      'dependency_count',
    }, 'resource_limits');
    return ExtensionSlot(
      slotId: _string(json['slot_id'], 'slot_id'),
      slotVersion: _string(json['slot_version'], 'slot_version'),
      displayName: _string(json['display_name'], 'display_name'),
      runtimeId: _string(json['runtime_id'], 'runtime_id'),
      configurationFields: List.unmodifiable(
        properties.entries.map(
          (entry) => ExtensionConfigurationField.fromJson(
            entry.key,
            _map(entry.value, 'configuration_schema.${entry.key}'),
            required: required.contains(entry.key),
          ),
        ),
      ),
      resourceLimits: Map.unmodifiable(
        limits.map(
          (key, value) => MapEntry(
            key,
            value is int && value > 0
                ? value
                : throw FormatException(
                    'Invalid extension contract: resource_limits.$key '
                    'must be an integer.',
                  ),
          ),
        ),
      ),
      permissionCapabilities: _stringList(
        json['permission_capabilities'],
        'permission_capabilities',
      ),
    );
  }

  @override
  List<Object?> get props => [
    slotId,
    slotVersion,
    displayName,
    runtimeId,
    configurationFields,
    resourceLimits,
    permissionCapabilities,
  ];
}

final class UserFunctionValidationResult extends Equatable {
  static const supportedSchemaVersion = 'user-function-validation-result.v1';

  final String artifactDigest;
  final String slotId;
  final String slotVersion;
  final String runtimeId;
  final List<String> sourceFiles;
  final List<String> dependencies;
  final List<String> checks;

  const UserFunctionValidationResult({
    required this.artifactDigest,
    required this.slotId,
    required this.slotVersion,
    required this.runtimeId,
    required this.sourceFiles,
    required this.dependencies,
    required this.checks,
  });

  factory UserFunctionValidationResult.fromJson(Map<String, dynamic> json) {
    _exactFields(json, const {
      'schema_version',
      'valid',
      'artifact_digest',
      'slot_id',
      'slot_version',
      'runtime_id',
      'source_files',
      'dependencies',
      'checks',
    }, 'validation result');
    _version(json, supportedSchemaVersion, 'validation result');
    if (json['valid'] != true) {
      throw const FormatException(
        'Invalid extension contract: validation result is not valid.',
      );
    }
    return UserFunctionValidationResult(
      artifactDigest: _string(json['artifact_digest'], 'artifact_digest'),
      slotId: _string(json['slot_id'], 'slot_id'),
      slotVersion: _string(json['slot_version'], 'slot_version'),
      runtimeId: _string(json['runtime_id'], 'runtime_id'),
      sourceFiles: _stringList(json['source_files'], 'source_files'),
      dependencies: _stringList(json['dependencies'], 'dependencies'),
      checks: _stringList(json['checks'], 'checks'),
    );
  }

  @override
  List<Object?> get props => [
    artifactDigest,
    slotId,
    slotVersion,
    runtimeId,
    sourceFiles,
    dependencies,
    checks,
  ];
}

final class TwinUserFunction extends Equatable {
  static const supportedSchemaVersion = 'twin-user-function.v1';

  final String functionId;
  final String twinId;
  final String artifactDigest;
  final String slotId;
  final String slotVersion;
  final String runtimeId;
  final Map<String, dynamic> configuration;
  final List<String> declaredCapabilities;
  final String validatorVersion;
  final List<String> sourceFiles;
  final List<String> dependencies;
  final DateTime createdAt;
  final DateTime updatedAt;

  const TwinUserFunction({
    required this.functionId,
    required this.twinId,
    required this.artifactDigest,
    required this.slotId,
    required this.slotVersion,
    required this.runtimeId,
    required this.configuration,
    required this.declaredCapabilities,
    required this.validatorVersion,
    required this.sourceFiles,
    required this.dependencies,
    required this.createdAt,
    required this.updatedAt,
  });

  factory TwinUserFunction.fromJson(Map<String, dynamic> json) {
    _exactFields(json, const {
      'schema_version',
      'function_id',
      'twin_id',
      'artifact_digest',
      'slot_id',
      'slot_version',
      'runtime_id',
      'configuration',
      'declared_capabilities',
      'validator_version',
      'source_files',
      'dependencies',
      'created_at',
      'updated_at',
    }, 'Twin user function');
    _version(json, supportedSchemaVersion, 'Twin user function');
    return TwinUserFunction(
      functionId: _string(json['function_id'], 'function_id'),
      twinId: _string(json['twin_id'], 'twin_id'),
      artifactDigest: _string(json['artifact_digest'], 'artifact_digest'),
      slotId: _string(json['slot_id'], 'slot_id'),
      slotVersion: _string(json['slot_version'], 'slot_version'),
      runtimeId: _string(json['runtime_id'], 'runtime_id'),
      configuration: Map.unmodifiable(
        _map(json['configuration'], 'configuration'),
      ),
      declaredCapabilities: _stringList(
        json['declared_capabilities'],
        'declared_capabilities',
      ),
      validatorVersion: _string(json['validator_version'], 'validator_version'),
      sourceFiles: _stringList(json['source_files'], 'source_files'),
      dependencies: _stringList(json['dependencies'], 'dependencies'),
      createdAt: DateTime.parse(_string(json['created_at'], 'created_at')),
      updatedAt: DateTime.parse(_string(json['updated_at'], 'updated_at')),
    );
  }

  @override
  List<Object?> get props => [
    functionId,
    twinId,
    artifactDigest,
    slotId,
    slotVersion,
    runtimeId,
    configuration,
    declaredCapabilities,
    validatorVersion,
    sourceFiles,
    dependencies,
    createdAt,
    updatedAt,
  ];
}

final class UserFunctionSourceDraft extends Equatable {
  final String filename;
  final Uint8List bytes;
  final Map<String, dynamic> configuration;

  UserFunctionSourceDraft({
    required this.filename,
    required Uint8List bytes,
    Map<String, dynamic> configuration = const {},
  }) : bytes = Uint8List.fromList(bytes),
       configuration = Map.unmodifiable(configuration);

  UserFunctionSourceDraft copyWith({
    String? filename,
    Uint8List? bytes,
    Map<String, dynamic>? configuration,
  }) => UserFunctionSourceDraft(
    filename: filename ?? this.filename,
    bytes: bytes ?? this.bytes,
    configuration: configuration ?? this.configuration,
  );

  @override
  List<Object?> get props => [filename, bytes, configuration];
}

final class UserFunctionSourceUpload {
  final ExtensionSlot slot;
  final UserFunctionSourceDraft draft;

  const UserFunctionSourceUpload({required this.slot, required this.draft});

  Uint8List get metadataBytes => Uint8List.fromList(
    utf8.encode(
      jsonEncode({
        'slot_id': slot.slotId,
        'slot_version': slot.slotVersion,
        'runtime_id': slot.runtimeId,
        'configuration': draft.configuration,
        'declared_capabilities': slot.permissionCapabilities,
      }),
    ),
  );
}

void _version(Map<String, dynamic> json, String expected, String contract) {
  final actual = _string(json['schema_version'], 'schema_version');
  if (actual != expected) {
    throw FormatException('Unsupported $contract schema version "$actual".');
  }
}

Map<String, dynamic> _map(Object? value, String field) {
  if (value is! Map) {
    throw FormatException(
      'Invalid extension contract: $field must be an object.',
    );
  }
  return Map<String, dynamic>.from(value);
}

String _string(Object? value, String field) {
  if (value is! String || value.isEmpty) {
    throw FormatException(
      'Invalid extension contract: $field must be a non-empty string.',
    );
  }
  return value;
}

void _exactFields(
  Map<String, dynamic> json,
  Set<String> allowed,
  String contract, {
  Set<String> optional = const {},
}) {
  final actual = json.keys.toSet();
  final required = allowed.difference(optional);
  if (!actual.containsAll(required) || !allowed.containsAll(actual)) {
    throw FormatException(
      'Invalid extension contract: $contract fields do not match v1.',
    );
  }
}

List<String> _stringList(Object? value, String field) {
  if (value is! List || value.any((item) => item is! String)) {
    throw FormatException(
      'Invalid extension contract: $field must be a string array.',
    );
  }
  return List<String>.unmodifiable(value.cast<String>());
}
