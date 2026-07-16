import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/utils/file_writer.dart';

void main() {
  late Directory temporaryDirectory;

  setUp(() {
    temporaryDirectory = Directory.systemTemp.createTempSync('file-writer-');
  });

  tearDown(() {
    temporaryDirectory.deleteSync(recursive: true);
  });

  test('writes binary content to an explicitly selected native path', () async {
    final path = '${temporaryDirectory.path}/payload.bin';

    await writeBytesToPath(path, [0, 1, 127, 255]);

    expect(await File(path).readAsBytes(), [0, 1, 127, 255]);
  });

  test('writes text content to an explicitly selected native path', () async {
    final path = '${temporaryDirectory.path}/payload.txt';

    await writeTextToPath(path, 'Twin2MultiCloud');

    expect(await File(path).readAsString(), 'Twin2MultiCloud');
  });
}
