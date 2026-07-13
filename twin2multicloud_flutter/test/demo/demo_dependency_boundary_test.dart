import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('demo adapters contain no network infrastructure dependency', () {
    final demoDirectory = Directory('lib/demo');
    final sources = demoDirectory
        .listSync()
        .whereType<File>()
        .where((file) => file.path.endsWith('.dart'))
        .map((file) => MapEntry(file.path, file.readAsStringSync()));

    const forbiddenImports = [
      "import 'dart:io'",
      "import 'dart:html'",
      'package:dio/',
      'package:http/',
      '../services/api_service.dart',
      '../services/sse_service.dart',
    ];

    for (final source in sources) {
      for (final forbidden in forbiddenImports) {
        expect(
          source.value,
          isNot(contains(forbidden)),
          reason: '${source.key} must not depend on $forbidden',
        );
      }
    }
  });
}
