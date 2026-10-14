import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/twin_transfer.dart';

void main() {
  group('portable Twin requests', () {
    test(
      'normalizes bounded names and excludes archive bytes from equality',
      () {
        final first = TwinImportRequest(
          newName: '  Copied Twin  ',
          filename: 'source.twin.zip',
          bytes: Uint8List.fromList([1, 2, 3]),
        );
        final second = TwinImportRequest(
          newName: 'Copied Twin',
          filename: 'source.twin.zip',
          bytes: Uint8List.fromList([9, 8, 7]),
        );

        expect(first.newName, 'Copied Twin');
        expect(first, second);
        expect(first.toString(), isNot(contains('[1, 2, 3]')));
      },
    );

    test('returns defensive byte copies', () {
      final source = Uint8List.fromList([1, 2, 3]);
      final request = TwinImportRequest(
        newName: 'Imported',
        filename: 'source.twin.zip',
        bytes: source,
      );
      source[0] = 9;
      final exposed = request.bytes..[1] = 8;

      expect(request.bytes, [1, 2, 3]);
      expect(exposed, [1, 8, 3]);
    });

    test('rejects unsafe archive names and unsupported downloads', () {
      expect(
        () => TwinImportRequest(
          newName: 'Imported',
          filename: '../source.twin.zip',
          bytes: Uint8List.fromList([1]),
        ),
        throwsFormatException,
      );
      expect(
        () => PortableTwinDownload(
          filename: 'source.twin.zip',
          mediaType: 'text/plain',
          bytes: Uint8List.fromList([1]),
        ),
        throwsFormatException,
      );
    });
  });
}
