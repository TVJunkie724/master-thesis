import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/user_function_extension.dart';

void main() {
  test('parses the reviewed non-secret extension slot contract', () {
    final slot = ExtensionSlot.fromJson(_slotJson());

    expect(slot.slotId, 'processor.telemetry');
    expect(slot.runtimeId, 'python311');
    expect(slot.configurationFields.single.name, 'scale_factor');
    expect(slot.configurationFields.single.required, isTrue);
  });

  test('rejects unknown versions and secret configuration controls', () {
    expect(
      () => ExtensionSlot.fromJson({
        ..._slotJson(),
        'schema_version': 'user-function-extension-slot.v2',
      }),
      throwsFormatException,
    );
    expect(
      () => ExtensionSlot.fromJson({
        ..._slotJson(),
        'provider_handler': 'lambda_function.lambda_handler',
      }),
      throwsFormatException,
    );
    final configuration = Map<String, dynamic>.from(
      _slotJson()['configuration_schema'] as Map,
    );
    final properties = Map<String, dynamic>.from(
      configuration['properties'] as Map,
    );
    properties['api_token'] = {
      'type': 'string',
      'user_editable': true,
      'secret': true,
    };
    expect(
      () => ExtensionSlot.fromJson({
        ..._slotJson(),
        'configuration_schema': {...configuration, 'properties': properties},
      }),
      throwsFormatException,
    );
  });

  test(
    'parses validation and current Twin function evidence without source',
    () {
      final validation = UserFunctionValidationResult.fromJson({
        'schema_version': 'user-function-validation-result.v1',
        'valid': true,
        'artifact_digest': 'sha256:${List.filled(64, 'a').join()}',
        'slot_id': 'processor.telemetry',
        'slot_version': '1',
        'runtime_id': 'python311',
        'source_files': ['process.py', 'requirements.lock'],
        'dependencies': ['requests'],
        'checks': ['schema_valid'],
      });
      final userFunction = TwinUserFunction.fromJson({
        'schema_version': 'twin-user-function.v1',
        'function_id': '00000000-0000-4000-8000-000000000001',
        'twin_id': '20000000-0000-4000-8000-000000000001',
        'artifact_digest': validation.artifactDigest,
        'slot_id': validation.slotId,
        'slot_version': validation.slotVersion,
        'runtime_id': validation.runtimeId,
        'configuration': {'scale_factor': 1},
        'declared_capabilities': ['capability.telemetry.process'],
        'validator_version': 'user-function-validator.v1',
        'source_files': validation.sourceFiles,
        'dependencies': ['requests'],
        'created_at': '2026-07-19T00:00:00Z',
        'updated_at': '2026-07-19T00:01:00Z',
      });

      expect(userFunction.dependencies, ['requests']);
      expect(userFunction.sourceFiles, ['process.py', 'requirements.lock']);
      expect(userFunction.artifactDigest, validation.artifactDigest);
      expect(userFunction.toString(), isNot(contains('def process')));
    },
  );

  test('same-sized source drafts remain distinct immutable inputs', () {
    final first = UserFunctionSourceDraft(
      filename: 'processor.zip',
      bytes: Uint8List.fromList([1, 2, 3]),
    );
    final replacement = UserFunctionSourceDraft(
      filename: 'processor.zip',
      bytes: Uint8List.fromList([9, 8, 7]),
    );

    expect(first, isNot(replacement));
  });

  test('Twin function reader rejects additional platform fields', () {
    expect(
      () => TwinUserFunction.fromJson({
        ..._userFunctionJson(),
        'source': 'def process(): pass',
      }),
      throwsFormatException,
    );
  });
}

Map<String, dynamic> _userFunctionJson() => {
  'schema_version': 'twin-user-function.v1',
  'function_id': '00000000-0000-4000-8000-000000000001',
  'twin_id': '20000000-0000-4000-8000-000000000001',
  'artifact_digest': 'sha256:${List.filled(64, 'a').join()}',
  'slot_id': 'processor.telemetry',
  'slot_version': '1',
  'runtime_id': 'python311',
  'configuration': {'scale_factor': 1},
  'declared_capabilities': ['capability.telemetry.process'],
  'validator_version': 'user-function-validator.v1',
  'source_files': ['process.py', 'requirements.lock'],
  'dependencies': <String>[],
  'created_at': '2026-07-19T00:00:00Z',
  'updated_at': '2026-07-19T00:00:00Z',
};

Map<String, dynamic> _slotJson() => {
  'schema_version': 'user-function-extension-slot.v1',
  'slot_id': 'processor.telemetry',
  'slot_version': '1',
  'display_name': 'Telemetry processor',
  'entrypoint': 'process',
  'runtime_id': 'python311',
  'configuration_schema': {
    r'$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object',
    'additionalProperties': false,
    'properties': {
      'scale_factor': {
        'type': 'number',
        'title': 'Scale factor',
        'minimum': 0,
        'maximum': 1000,
        'user_editable': true,
        'secret': false,
      },
    },
    'required': ['scale_factor'],
  },
  'resource_limits': {
    'timeout_seconds': 30,
    'memory_mb': 256,
    'artifact_bytes': 10485760,
    'source_bytes': 2097152,
    'response_bytes': 1048576,
    'file_count': 64,
    'dependency_count': 64,
  },
  'permission_capabilities': ['capability.telemetry.process'],
  'secret_policy': 'forbidden',
};
