import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('optimizer and deployer task screens do not own API adapters', () {
    for (final path in [
      'lib/screens/wizard/step2_optimizer.dart',
      'lib/screens/wizard/step3_deployer.dart',
    ]) {
      final source = File(path).readAsStringSync();

      for (final forbidden in [
        'apiServiceProvider',
        'ApiService',
        'ManagementApi',
        'ProviderScope.containerOf',
      ]) {
        expect(
          source,
          isNot(contains(forbidden)),
          reason:
              '$path must dispatch feature events instead of using $forbidden',
        );
      }
    }
  });

  test(
    'deployment presentation is free of framework state and API adapters',
    () {
      final deploymentDirectory = Directory(
        'lib/features/configuration_workspace/presentation/deployment',
      );
      final files = deploymentDirectory.listSync().whereType<File>().where(
        (file) => file.path.endsWith('.dart'),
      );

      for (final file in files) {
        final source = file.readAsStringSync();
        for (final forbidden in [
          'flutter_bloc',
          'flutter_riverpod',
          'package:dio',
          'context.read<',
          'ManagementApi',
          'ApiService',
        ]) {
          expect(
            source,
            isNot(contains(forbidden)),
            reason: '${file.path} must remain presentation-only',
          );
        }
      }
    },
  );

  test('wizard state never retains transient ZIP bytes', () {
    final source = File('lib/bloc/wizard/wizard_state.dart').readAsStringSync();
    expect(source, isNot(contains('Uint8List')));
    expect(source, isNot(contains('pendingZip')));
  });
}
