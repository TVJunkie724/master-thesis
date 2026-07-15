import 'dart:async';
import 'dart:typed_data';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

final class _MockApiService extends Mock implements ApiService {}

void main() {
  late _MockApiService api;

  setUpAll(() => registerFallbackValue(Uint8List(0)));
  setUp(() => api = _MockApiService());

  blocTest<WizardBloc, WizardState>(
    'uploads transient ZIP bytes without retaining them in WizardState',
    build: () {
      when(
        () => api.uploadProjectZip('twin-1', any(), 'project.zip'),
      ).thenAnswer(
        (_) async => {
          'success': true,
          'files': <String, dynamic>{},
          'functions': <String, dynamic>{},
          'assets': <String, dynamic>{},
        },
      );
      return WizardBloc(api: api);
    },
    seed: () => const WizardState(twinId: 'twin-1'),
    act: (bloc) => bloc.add(
      WizardZipUploadRequested(
        fileBytes: Uint8List.fromList([0x50, 0x4b, 0x03, 0x04]),
        fileName: 'project.zip',
      ),
    ),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.zipUploadInProgress,
        'uploading',
        true,
      ),
      isA<WizardState>()
          .having((state) => state.zipUploadInProgress, 'uploading', false)
          .having(
            (state) => state.successMessage,
            'success',
            startsWith('Zip extracted!'),
          ),
    ],
    verify: (_) {
      final bytes =
          verify(
                () =>
                    api.uploadProjectZip('twin-1', captureAny(), 'project.zip'),
              ).captured.single
              as Uint8List;
      expect(bytes, [0x50, 0x4b, 0x03, 0x04]);
    },
  );

  test('coalesces concurrent ZIP upload requests', () async {
    final completion = Completer<Map<String, dynamic>>();
    when(
      () => api.uploadProjectZip('twin-1', any(), 'project.zip'),
    ).thenAnswer((_) => completion.future);
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    bloc.emit(const WizardState(twinId: 'twin-1'));
    final request = WizardZipUploadRequested(
      fileBytes: Uint8List.fromList([0x50, 0x4b, 0x03, 0x04]),
      fileName: 'project.zip',
    );

    bloc.add(request);
    bloc.add(request);
    await Future<void>.delayed(const Duration(milliseconds: 20));

    verify(
      () => api.uploadProjectZip('twin-1', any(), 'project.zip'),
    ).called(1);
    completion.complete({
      'success': true,
      'files': <String, dynamic>{},
      'functions': <String, dynamic>{},
      'assets': <String, dynamic>{},
    });
    await bloc.stream.firstWhere((state) => !state.zipUploadInProgress);
  });

  blocTest<WizardBloc, WizardState>(
    'rejects ZIP upload before API I/O when the twin is not persisted',
    build: () => WizardBloc(api: api),
    act: (bloc) => bloc.add(
      WizardZipUploadRequested(
        fileBytes: Uint8List.fromList([0x50, 0x4b]),
        fileName: 'project.zip',
      ),
    ),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.errorMessage,
        'error',
        'Save twin first before uploading zip',
      ),
    ],
    verify: (_) {
      verifyNever(() => api.uploadProjectZip(any(), any(), any()));
    },
  );

  blocTest<WizardBloc, WizardState>(
    'rejects unsafe and oversized ZIP payloads before API I/O',
    build: () => WizardBloc(api: api, maxProjectZipBytes: 2),
    seed: () => const WizardState(twinId: 'twin-1'),
    act: (bloc) async {
      bloc.add(
        WizardZipUploadRequested(
          fileBytes: Uint8List.fromList([1]),
          fileName: '../project.zip',
        ),
      );
      await Future<void>.delayed(Duration.zero);
      bloc.add(
        WizardZipUploadRequested(
          fileBytes: Uint8List.fromList([1, 2, 3]),
          fileName: 'project.zip',
        ),
      );
    },
    expect: () => [
      isA<WizardState>().having(
        (state) => state.errorMessage,
        'unsafe filename',
        'Select a non-empty .zip file with a safe filename.',
      ),
      isA<WizardState>().having(
        (state) => state.errorMessage,
        'oversized payload',
        'The project ZIP exceeds the 100 MB upload limit.',
      ),
    ],
    verify: (_) {
      verifyNever(() => api.uploadProjectZip(any(), any(), any()));
    },
  );
}
