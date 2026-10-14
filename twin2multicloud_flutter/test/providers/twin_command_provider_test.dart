import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/providers/twins_provider.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';
import 'package:twin2multicloud_flutter/models/twin_transfer.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  late _MockManagementApi api;
  late ProviderContainer container;

  setUp(() {
    api = _MockManagementApi();
    container = ProviderContainer(
      overrides: [apiServiceProvider.overrideWithValue(api)],
    );
  });

  tearDown(() => container.dispose());

  test('deletes through the command boundary and returns to idle', () async {
    when(() => api.deleteTwin('twin-1')).thenAnswer((_) async {});

    await container.read(twinCommandProvider.notifier).deleteTwin('twin-1');

    verify(() => api.deleteTwin('twin-1')).called(1);
    expect(container.read(twinCommandProvider), const AsyncData<void>(null));
  });

  test('exposes failure state and preserves the original exception', () async {
    final failure = Exception('delete unavailable');
    when(() => api.deleteTwin('twin-1')).thenThrow(failure);

    await expectLater(
      container.read(twinCommandProvider.notifier).deleteTwin('twin-1'),
      throwsA(same(failure)),
    );

    expect(
      container.read(twinCommandProvider),
      isA<AsyncError<void>>().having(
        (value) => value.error,
        'error',
        same(failure),
      ),
    );
  });

  test('coalesces duplicate delete commands while one is active', () async {
    final completion = Completer<void>();
    when(() => api.deleteTwin('twin-1')).thenAnswer((_) => completion.future);

    final controller = container.read(twinCommandProvider.notifier);
    final first = controller.deleteTwin('twin-1');
    final duplicate = controller.deleteTwin('twin-1');

    await duplicate;
    verify(() => api.deleteTwin('twin-1')).called(1);

    completion.complete();
    await first;
  });

  test('duplicates a Twin and invalidates the inventory', () async {
    final request = TwinDuplicateRequest(name: 'Twin copy');
    when(
      () => api.duplicateTwin('twin-1', request),
    ).thenAnswer((_) async => _twin(id: 'twin-copy', name: 'Twin copy'));
    final listener = container.listen(twinsProvider, (_, _) {});

    final result = await container
        .read(twinCommandProvider.notifier)
        .duplicateTwin('twin-1', request);

    expect(result?.id, 'twin-copy');
    verify(() => api.duplicateTwin('twin-1', request)).called(1);
    expect(container.read(twinCommandProvider), const AsyncData<void>(null));
    listener.close();
  });

  test('coalesces duplicate Twin requests while the first is active', () async {
    final request = TwinDuplicateRequest(name: 'Twin copy');
    final completion = Completer<Twin>();
    when(
      () => api.duplicateTwin('twin-1', request),
    ).thenAnswer((_) => completion.future);

    final controller = container.read(twinCommandProvider.notifier);
    final first = controller.duplicateTwin('twin-1', request);
    final duplicate = await controller.duplicateTwin('twin-1', request);

    expect(duplicate, isNull);
    verify(() => api.duplicateTwin('twin-1', request)).called(1);
    completion.complete(_twin(id: 'twin-copy', name: 'Twin copy'));
    expect((await first)?.id, 'twin-copy');
  });

  test('imports a typed portable archive once while busy', () async {
    final request = TwinImportRequest(
      newName: 'Imported Twin',
      filename: 'research.twin.zip',
      bytes: Uint8List.fromList([1, 2, 3]),
    );
    final completion = Completer<Twin>();
    when(() => api.importTwin(request)).thenAnswer((_) => completion.future);

    final controller = container.read(twinCommandProvider.notifier);
    final first = controller.importTwin(request);
    final duplicate = await controller.importTwin(request);

    expect(duplicate, isNull);
    verify(() => api.importTwin(request)).called(1);
    completion.complete(_twin(id: 'imported', name: 'Imported Twin'));
    expect((await first)?.id, 'imported');
  });

  test('exports without invalidating or mutating the inventory', () async {
    final download = PortableTwinDownload(
      filename: 'research.twin.zip',
      mediaType: PortableTwinDownload.mediaTypeZip,
      bytes: Uint8List.fromList([1, 2, 3]),
    );
    when(() => api.exportTwin('twin-1')).thenAnswer((_) async => download);

    final result = await container
        .read(twinCommandProvider.notifier)
        .exportTwin('twin-1');

    expect(result, download);
    verify(() => api.exportTwin('twin-1')).called(1);
    expect(container.read(twinCommandProvider), const AsyncData<void>(null));
  });
}

Twin _twin({required String id, required String name}) => Twin(
  id: id,
  name: name,
  state: 'draft',
  createdAt: DateTime.utc(2026, 8, 27),
  updatedAt: DateTime.utc(2026, 8, 27),
);
