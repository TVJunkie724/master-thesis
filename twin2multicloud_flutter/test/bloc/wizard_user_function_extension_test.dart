import 'dart:typed_data';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/user_function_extension.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  late _MockManagementApi api;

  setUpAll(() {
    registerFallbackValue(_slot);
    registerFallbackValue(
      UserFunctionSourceUpload(
        slot: _slot,
        draft: UserFunctionSourceDraft(
          filename: 'fallback.zip',
          bytes: Uint8List.fromList([1]),
        ),
      ),
    );
  });

  setUp(() => api = _MockManagementApi());

  blocTest<WizardBloc, WizardState>(
    'moves a selected archive back to draft without retaining validation',
    build: () => WizardBloc(api: api),
    seed: () => _readyDraft().copyWith(
      extensionValidationResults: const {'processor.telemetry': _validation},
      extensionPhases: const {
        'processor.telemetry': UserFunctionWorkflowPhase.valid,
      },
    ),
    act: (bloc) => bloc.add(
      WizardExtensionSourceSelected(
        slotId: _slot.slotId,
        fileBytes: Uint8List.fromList([9, 8, 7]),
        fileName: 'replacement.zip',
      ),
    ),
    expect: () => [
      isA<WizardState>()
          .having(
            (state) => state.extensionPhase(_slot.slotId),
            'phase',
            UserFunctionWorkflowPhase.draft,
          )
          .having(
            (state) => state.extensionValidation(_slot.slotId),
            'validation',
            isNull,
          )
          .having(
            (state) => state.extensionDraft(_slot.slotId)?.bytes,
            'replacement bytes',
            orderedEquals([9, 8, 7]),
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'rejects an invalid archive selection before an API call',
    build: () => WizardBloc(api: api),
    seed: _readyDraft,
    act: (bloc) => bloc.add(
      WizardExtensionSourceSelected(
        slotId: _slot.slotId,
        fileBytes: Uint8List(0),
        fileName: 'processor.txt',
      ),
    ),
    expect: () => [
      isA<WizardState>()
          .having(
            (state) => state.extensionPhase(_slot.slotId),
            'phase',
            UserFunctionWorkflowPhase.invalid,
          )
          .having(
            (state) => state.extensionErrors[_slot.slotId],
            'safe error',
            contains('source ZIP'),
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'transitions from draft through validating to valid',
    setUp: () {
      when(
        () => api.validateTwinUserFunction(any(), any()),
      ).thenAnswer((_) async => _validation);
    },
    build: () => WizardBloc(api: api),
    seed: _readyDraft,
    act: (bloc) => bloc.add(
      const WizardExtensionValidationRequested('processor.telemetry'),
    ),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.extensionPhase(_slot.slotId),
        'phase',
        UserFunctionWorkflowPhase.validating,
      ),
      isA<WizardState>()
          .having(
            (state) => state.extensionPhase(_slot.slotId),
            'phase',
            UserFunctionWorkflowPhase.valid,
          )
          .having(
            (state) => state.extensionValidation(_slot.slotId),
            'validation',
            _validation,
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'saves the validated source directly on the Twin',
    setUp: () {
      when(
        () => api.saveTwinUserFunction(any(), any()),
      ).thenAnswer((_) async => _userFunction);
    },
    build: () => WizardBloc(api: api),
    seed: _validatedDraft,
    act: (bloc) =>
        bloc.add(const WizardExtensionSaveRequested('processor.telemetry')),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.extensionPhase(_slot.slotId),
        'phase',
        UserFunctionWorkflowPhase.saving,
      ),
      isA<WizardState>()
          .having(
            (state) => state.extensionPhase(_slot.slotId),
            'phase',
            UserFunctionWorkflowPhase.saved,
          )
          .having(
            (state) => state.twinUserFunction(_slot.slotId),
            'Twin function',
            _userFunction,
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'maps save failures to an error without source disclosure',
    setUp: () {
      when(() => api.saveTwinUserFunction(any(), any())).thenThrow(
        const AppException(
          'The function source could not be saved.',
          code: 'SERVICE_UNAVAILABLE',
        ),
      );
    },
    build: () => WizardBloc(api: api),
    seed: _validatedDraft,
    act: (bloc) =>
        bloc.add(const WizardExtensionSaveRequested('processor.telemetry')),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.extensionPhase(_slot.slotId),
        'phase',
        UserFunctionWorkflowPhase.saving,
      ),
      isA<WizardState>()
          .having(
            (state) => state.extensionPhase(_slot.slotId),
            'phase',
            UserFunctionWorkflowPhase.error,
          )
          .having(
            (state) => state.extensionErrors[_slot.slotId],
            'safe error',
            contains('could not be saved'),
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'removes the current Twin function',
    setUp: () {
      when(
        () => api.deleteTwinUserFunction(any(), any()),
      ).thenAnswer((_) async {});
    },
    build: () => WizardBloc(api: api),
    seed: () => _readyDraft().copyWith(
      twinUserFunctions: [_userFunction],
      extensionPhases: const {
        'processor.telemetry': UserFunctionWorkflowPhase.saved,
      },
    ),
    act: (bloc) =>
        bloc.add(const WizardExtensionDeleteRequested('processor.telemetry')),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.extensionPhase(_slot.slotId),
        'phase',
        UserFunctionWorkflowPhase.saving,
      ),
      isA<WizardState>()
          .having(
            (state) => state.extensionPhase(_slot.slotId),
            'phase',
            UserFunctionWorkflowPhase.draft,
          )
          .having(
            (state) => state.twinUserFunction(_slot.slotId),
            'Twin function',
            isNull,
          ),
    ],
  );
}

WizardState _readyDraft() => WizardState(
  twinId: 'twin-1',
  extensionSlots: const [_slot],
  extensionDrafts: {
    'processor.telemetry': UserFunctionSourceDraft(
      filename: 'processor.zip',
      bytes: Uint8List.fromList([1, 2, 3]),
      configuration: const {'scale_factor': 1},
    ),
  },
);

WizardState _validatedDraft() => _readyDraft().copyWith(
  extensionValidationResults: const {'processor.telemetry': _validation},
  extensionPhases: const {
    'processor.telemetry': UserFunctionWorkflowPhase.valid,
  },
);

const _slot = ExtensionSlot(
  slotId: 'processor.telemetry',
  slotVersion: '1',
  displayName: 'Telemetry processor',
  runtimeId: 'python311',
  configurationFields: [
    ExtensionConfigurationField(
      name: 'scale_factor',
      type: 'number',
      title: 'Scale factor',
      required: true,
      minimum: 0,
      maximum: 1000,
    ),
  ],
  resourceLimits: {'timeout_seconds': 30, 'memory_mb': 256},
  permissionCapabilities: ['capability.telemetry.process'],
);

const _validation = UserFunctionValidationResult(
  artifactDigest:
      'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  slotId: 'processor.telemetry',
  slotVersion: '1',
  runtimeId: 'python311',
  sourceFiles: ['process.py', 'requirements.lock'],
  dependencies: [],
  checks: ['schema_valid', 'secret_scan_passed'],
);

final _userFunction = TwinUserFunction(
  functionId: '00000000-0000-4000-8000-000000000001',
  twinId: 'twin-1',
  artifactDigest: _validation.artifactDigest,
  slotId: _slot.slotId,
  slotVersion: _slot.slotVersion,
  runtimeId: _slot.runtimeId,
  configuration: const {'scale_factor': 1},
  declaredCapabilities: _slot.permissionCapabilities,
  validatorVersion: 'user-function-validator.v1',
  sourceFiles: _validation.sourceFiles,
  dependencies: _validation.dependencies,
  createdAt: DateTime.utc(2026, 7, 19),
  updatedAt: DateTime.utc(2026, 7, 19),
);
