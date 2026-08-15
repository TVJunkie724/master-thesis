import 'dart:async';
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
  late Completer<UserFunctionValidationResult> validationResponse;
  late Completer<TwinExtensionBinding> bindingResponse;

  setUpAll(() {
    registerFallbackValue(_slot);
    registerFallbackValue(
      UserFunctionArtifactUpload(
        slot: _slot,
        draft: UserFunctionSourceDraft(
          filename: 'fallback.zip',
          bytes: Uint8List.fromList([1]),
        ),
      ),
    );
  });

  setUp(() {
    api = _MockManagementApi();
    validationResponse = Completer<UserFunctionValidationResult>();
    bindingResponse = Completer<TwinExtensionBinding>();
  });

  blocTest<WizardBloc, WizardState>(
    'moves a selected archive back to draft without retaining validation',
    build: () => WizardBloc(api: api),
    seed: () => WizardState(
      extensionSlots: const [_slot],
      extensionValidationResults: const {'processor.telemetry': _validation},
      extensionPhases: const {
        'processor.telemetry': UserFunctionWorkflowPhase.valid,
      },
    ),
    act: (bloc) => bloc.add(
      WizardExtensionSourceSelected(
        slotId: _slot.slotId,
        fileBytes: Uint8List.fromList([1, 2, 3]),
        fileName: 'processor.zip',
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
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'does not suppress a same-sized replacement archive',
    build: () => WizardBloc(api: api),
    seed: _readyDraft,
    act: (bloc) => bloc.add(
      WizardExtensionSourceSelected(
        slotId: _slot.slotId,
        fileBytes: Uint8List.fromList([9, 8, 7]),
        fileName: 'processor.zip',
      ),
    ),
    expect: () => [
      isA<WizardState>().having(
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
        () => api.validateUserFunctionArtifact(any()),
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
    'ignores a validation response for a replaced draft',
    setUp: () {
      when(
        () => api.validateUserFunctionArtifact(any()),
      ).thenAnswer((_) => validationResponse.future);
    },
    build: () => WizardBloc(api: api),
    seed: _readyDraft,
    act: (bloc) async {
      bloc.add(const WizardExtensionValidationRequested('processor.telemetry'));
      await untilCalled(() => api.validateUserFunctionArtifact(any()));
      bloc.add(
        WizardExtensionSourceSelected(
          slotId: _slot.slotId,
          fileBytes: Uint8List.fromList([9, 8, 7]),
          fileName: 'replacement.zip',
        ),
      );
      await bloc.stream.firstWhere(
        (state) =>
            state.extensionDraft(_slot.slotId)?.filename == 'replacement.zip',
      );
      validationResponse.complete(_validation);
    },
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
            UserFunctionWorkflowPhase.draft,
          )
          .having(
            (state) => state.extensionValidation(_slot.slotId),
            'validation',
            isNull,
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'creates and binds the validated immutable artifact',
    setUp: () {
      when(
        () => api.createUserFunctionArtifact(any()),
      ).thenAnswer((_) async => _artifact);
      when(
        () => api.bindTwinExtensionArtifact(
          any(),
          any(),
          any(),
          expectedRevision: any(named: 'expectedRevision'),
        ),
      ).thenAnswer((_) async => _binding);
    },
    build: () => WizardBloc(api: api),
    seed: () => _readyDraft().copyWith(
      twinId: 'twin-1',
      extensionValidationResults: const {'processor.telemetry': _validation},
      extensionPhases: const {
        'processor.telemetry': UserFunctionWorkflowPhase.valid,
      },
    ),
    act: (bloc) =>
        bloc.add(const WizardExtensionBindRequested('processor.telemetry')),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.extensionPhase(_slot.slotId),
        'phase',
        UserFunctionWorkflowPhase.binding,
      ),
      isA<WizardState>()
          .having(
            (state) => state.extensionPhase(_slot.slotId),
            'phase',
            UserFunctionWorkflowPhase.bound,
          )
          .having(
            (state) => state.extensionBinding(_slot.slotId),
            'binding',
            _binding,
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'marks a completed binding stale when its draft was replaced',
    setUp: () {
      when(
        () => api.createUserFunctionArtifact(any()),
      ).thenAnswer((_) async => _artifact);
      when(
        () => api.bindTwinExtensionArtifact(
          any(),
          any(),
          any(),
          expectedRevision: any(named: 'expectedRevision'),
        ),
      ).thenAnswer((_) => bindingResponse.future);
    },
    build: () => WizardBloc(api: api),
    seed: () => _readyDraft().copyWith(
      twinId: 'twin-1',
      extensionValidationResults: const {'processor.telemetry': _validation},
      extensionPhases: const {
        'processor.telemetry': UserFunctionWorkflowPhase.valid,
      },
    ),
    act: (bloc) async {
      bloc.add(const WizardExtensionBindRequested('processor.telemetry'));
      await untilCalled(
        () => api.bindTwinExtensionArtifact(
          any(),
          any(),
          any(),
          expectedRevision: any(named: 'expectedRevision'),
        ),
      );
      bloc.add(
        WizardExtensionSourceSelected(
          slotId: _slot.slotId,
          fileBytes: Uint8List.fromList([9, 8, 7]),
          fileName: 'replacement.zip',
        ),
      );
      await bloc.stream.firstWhere(
        (state) =>
            state.extensionDraft(_slot.slotId)?.filename == 'replacement.zip',
      );
      bindingResponse.complete(_binding);
    },
    expect: () => [
      isA<WizardState>().having(
        (state) => state.extensionPhase(_slot.slotId),
        'phase',
        UserFunctionWorkflowPhase.binding,
      ),
      isA<WizardState>().having(
        (state) => state.extensionPhase(_slot.slotId),
        'phase',
        UserFunctionWorkflowPhase.draft,
      ),
      isA<WizardState>()
          .having(
            (state) => state.extensionPhase(_slot.slotId),
            'phase',
            UserFunctionWorkflowPhase.stale,
          )
          .having(
            (state) => state.extensionBinding(_slot.slotId),
            'binding',
            _binding,
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'maps validation API failures to invalid without source disclosure',
    setUp: () {
      when(() => api.validateUserFunctionArtifact(any())).thenThrow(
        const AppException(
          'The source archive is invalid.',
          code: 'EXTENSION_ARCHIVE_UNSAFE',
        ),
      );
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
            UserFunctionWorkflowPhase.invalid,
          )
          .having(
            (state) => state.extensionErrors[_slot.slotId],
            'safe error',
            allOf(contains('invalid'), isNot(contains('def process'))),
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'maps a non-stale bind API failure to the error phase',
    setUp: () {
      when(
        () => api.createUserFunctionArtifact(any()),
      ).thenAnswer((_) async => _artifact);
      when(
        () => api.bindTwinExtensionArtifact(
          any(),
          any(),
          any(),
          expectedRevision: any(named: 'expectedRevision'),
        ),
      ).thenThrow(
        const AppException(
          'The binding service is unavailable.',
          code: 'SERVICE_UNAVAILABLE',
        ),
      );
    },
    build: () => WizardBloc(api: api),
    seed: () => _readyDraft().copyWith(
      twinId: 'twin-1',
      extensionValidationResults: const {'processor.telemetry': _validation},
      extensionPhases: const {
        'processor.telemetry': UserFunctionWorkflowPhase.valid,
      },
    ),
    act: (bloc) =>
        bloc.add(const WizardExtensionBindRequested('processor.telemetry')),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.extensionPhase(_slot.slotId),
        'phase',
        UserFunctionWorkflowPhase.binding,
      ),
      isA<WizardState>().having(
        (state) => state.extensionPhase(_slot.slotId),
        'phase',
        UserFunctionWorkflowPhase.error,
      ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'maps stale binding errors without disclosing the source archive',
    setUp: () {
      when(
        () => api.createUserFunctionArtifact(any()),
      ).thenAnswer((_) async => _artifact);
      when(
        () => api.bindTwinExtensionArtifact(
          any(),
          any(),
          any(),
          expectedRevision: any(named: 'expectedRevision'),
        ),
      ).thenThrow(
        const AppException(
          'The extension binding revision is stale.',
          code: 'EXTENSION_BINDING_UNRESOLVED',
        ),
      );
    },
    build: () => WizardBloc(api: api),
    seed: () => _readyDraft().copyWith(
      twinId: 'twin-1',
      extensionValidationResults: const {'processor.telemetry': _validation},
      extensionPhases: const {
        'processor.telemetry': UserFunctionWorkflowPhase.valid,
      },
    ),
    act: (bloc) =>
        bloc.add(const WizardExtensionBindRequested('processor.telemetry')),
    expect: () => [
      isA<WizardState>(),
      isA<WizardState>()
          .having(
            (state) => state.extensionPhase(_slot.slotId),
            'phase',
            UserFunctionWorkflowPhase.stale,
          )
          .having(
            (state) => state.extensionErrors[_slot.slotId],
            'safe error',
            allOf(contains('stale'), isNot(contains('def process'))),
          ),
    ],
  );
}

WizardState _readyDraft() => WizardState(
  extensionSlots: const [_slot],
  extensionDrafts: {
    'processor.telemetry': UserFunctionSourceDraft(
      filename: 'processor.zip',
      bytes: Uint8List.fromList([1, 2, 3]),
      configuration: const {'scale_factor': 1},
    ),
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

final _artifact = UserFunctionArtifact(
  schemaVersion: 'user-function-artifact.v1',
  artifactId: '00000000-0000-4000-8000-000000000001',
  artifactState: 'valid',
  artifactDigest: _validation.artifactDigest,
  slotId: _slot.slotId,
  slotVersion: _slot.slotVersion,
  runtimeId: _slot.runtimeId,
  configuration: const {'scale_factor': 1},
  declaredCapabilities: _slot.permissionCapabilities,
  validatorVersion: 'user-function-validator.v1',
  sourceFiles: _validation.sourceFiles,
  dependencyCount: 0,
  createdAt: DateTime.utc(2026, 7, 19),
);

final _binding = TwinExtensionBinding(
  bindingId: '10000000-0000-4000-8000-000000000001',
  twinId: 'twin-1',
  slotId: _slot.slotId,
  slotVersion: _slot.slotVersion,
  artifactId: _artifact.artifactId,
  artifactDigest: _artifact.artifactDigest,
  bindingDigest:
      'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  active: true,
  revision: 1,
  createdAt: DateTime.utc(2026, 7, 19),
  unboundAt: null,
);
