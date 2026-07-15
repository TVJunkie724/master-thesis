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
          reason: '$path must dispatch feature events instead of using $forbidden',
        );
      }
    }
  });
}
