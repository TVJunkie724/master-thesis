import 'dart:typed_data';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class _MockApiService extends Mock implements ApiService {}

void main() {
  late _MockApiService api;

  setUpAll(() => registerFallbackValue(Uint8List(0)));
  setUp(() => api = _MockApiService());

  blocTest<WizardBloc, WizardState>(
    'uploads a GLB without retaining binary bytes in state',
    build: () {
      when(
        () => api.uploadSceneGlb('twin-1', any(), 'scene.glb'),
      ).thenAnswer((_) async => {'message': 'stored', 'size_mb': 0.1});
      return WizardBloc(api: api);
    },
    seed: () => const WizardState(twinId: 'twin-1'),
    act: (bloc) => bloc.add(
      WizardSceneGlbUploadRequested(
        bytes: Uint8List.fromList([0x67, 0x6c, 0x54, 0x46]),
        filename: 'scene.glb',
      ),
    ),
    expect: () => [
      isA<WizardState>()
          .having(
            (state) => state.sceneGlbCommand.phase,
            'phase',
            SceneGlbCommandPhase.uploading,
          )
          .having((state) => state.sceneGlbUploaded, 'uploaded', false),
      isA<WizardState>()
          .having(
            (state) => state.sceneGlbCommand.phase,
            'phase',
            SceneGlbCommandPhase.idle,
          )
          .having((state) => state.sceneGlbUploaded, 'uploaded', true)
          .having((state) => state.hasUnsavedChanges, 'dirty', true)
          .having(
            (state) => state.sceneGlbCommand.message,
            'message',
            'GLB uploaded successfully.',
          ),
    ],
    verify: (_) {
      final captured =
          verify(
                () => api.uploadSceneGlb('twin-1', captureAny(), 'scene.glb'),
              ).captured.single
              as Uint8List;
      expect(captured, [0x67, 0x6c, 0x54, 0x46]);
    },
  );

  blocTest<WizardBloc, WizardState>(
    'deletes a persisted GLB through the application boundary',
    build: () {
      when(() => api.deleteSceneGlb('twin-1')).thenAnswer((_) async {});
      return WizardBloc(api: api);
    },
    seed: () => const WizardState(twinId: 'twin-1', sceneGlbUploaded: true),
    act: (bloc) => bloc.add(const WizardSceneGlbDeleteRequested()),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.sceneGlbCommand.phase,
        'phase',
        SceneGlbCommandPhase.deleting,
      ),
      isA<WizardState>()
          .having((state) => state.sceneGlbUploaded, 'uploaded', false)
          .having(
            (state) => state.sceneGlbCommand.message,
            'message',
            'GLB deleted successfully.',
          ),
    ],
    verify: (_) => verify(() => api.deleteSceneGlb('twin-1')).called(1),
  );

  blocTest<WizardBloc, WizardState>(
    'fails locally when a GLB command has no persisted twin',
    build: () => WizardBloc(api: api),
    act: (bloc) => bloc.add(
      WizardSceneGlbUploadRequested(
        bytes: Uint8List.fromList([1]),
        filename: 'scene.glb',
      ),
    ),
    expect: () => [
      isA<WizardState>()
          .having(
            (state) => state.errorMessage,
            'error',
            'Save the draft before uploading a GLB file.',
          )
          .having(
            (state) => state.sceneGlbCommand.phase,
            'phase',
            SceneGlbCommandPhase.idle,
          ),
    ],
    verify: (_) => verifyNever(() => api.uploadSceneGlb(any(), any(), any())),
  );

  blocTest<WizardBloc, WizardState>(
    'rejects unsafe filenames and oversized payloads before API I/O',
    build: () => WizardBloc(api: api, maxSceneGlbBytes: 2),
    seed: () => const WizardState(twinId: 'twin-1'),
    act: (bloc) async {
      bloc.add(
        WizardSceneGlbUploadRequested(
          bytes: Uint8List.fromList([1]),
          filename: '../scene.glb',
        ),
      );
      await Future<void>.delayed(Duration.zero);
      bloc.add(
        WizardSceneGlbUploadRequested(
          bytes: Uint8List.fromList([1, 2, 3]),
          filename: 'scene.glb',
        ),
      );
    },
    expect: () => [
      isA<WizardState>().having(
        (state) => state.errorMessage,
        'unsafe filename',
        'Select a non-empty .glb file with a safe filename.',
      ),
      isA<WizardState>().having(
        (state) => state.errorMessage,
        'oversized',
        'The GLB file exceeds the 100 MB upload limit.',
      ),
    ],
    verify: (_) => verifyNever(() => api.uploadSceneGlb(any(), any(), any())),
  );

  blocTest<WizardBloc, WizardState>(
    'recovers to idle with a public error after upload failure',
    build: () {
      when(
        () => api.uploadSceneGlb('twin-1', any(), 'scene.glb'),
      ).thenThrow(Exception('transport unavailable'));
      return WizardBloc(api: api);
    },
    seed: () => const WizardState(twinId: 'twin-1'),
    act: (bloc) => bloc.add(
      WizardSceneGlbUploadRequested(
        bytes: Uint8List.fromList([1]),
        filename: 'scene.glb',
      ),
    ),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.sceneGlbCommand.phase,
        'phase',
        SceneGlbCommandPhase.uploading,
      ),
      isA<WizardState>()
          .having(
            (state) => state.sceneGlbCommand.phase,
            'phase',
            SceneGlbCommandPhase.idle,
          )
          .having(
            (state) => state.errorMessage,
            'error',
            'GLB upload failed: An unexpected error occurred',
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'ignores a duplicate GLB upload while the first command is active',
    build: () {
      when(() => api.uploadSceneGlb('twin-1', any(), 'scene.glb')).thenAnswer((
        _,
      ) async {
        await Future<void>.delayed(const Duration(milliseconds: 20));
        return {'message': 'stored', 'size_mb': 0.1};
      });
      return WizardBloc(api: api);
    },
    seed: () => const WizardState(twinId: 'twin-1'),
    act: (bloc) {
      final event = WizardSceneGlbUploadRequested(
        bytes: Uint8List.fromList([1]),
        filename: 'scene.glb',
      );
      bloc.add(event);
      bloc.add(event);
    },
    wait: const Duration(milliseconds: 40),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.sceneGlbCommand.phase,
        'phase',
        SceneGlbCommandPhase.uploading,
      ),
      isA<WizardState>().having(
        (state) => state.sceneGlbUploaded,
        'uploaded',
        true,
      ),
    ],
    verify: (_) => verify(
      () => api.uploadSceneGlb('twin-1', any(), 'scene.glb'),
    ).called(1),
  );
}
