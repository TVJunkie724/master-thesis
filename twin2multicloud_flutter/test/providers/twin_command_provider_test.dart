import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/providers/twins_provider.dart';
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
}
