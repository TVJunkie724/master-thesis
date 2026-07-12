import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/architecture_path.dart';

void main() {
  group('ArchitecturePath', () {
    test('parses canonical and legacy storage segment order', () {
      expect(ArchitecturePath.providerForSegment('L3_hot_AWS'), 'AWS');
      expect(ArchitecturePath.providerForSegment('L3_AWS_HOT'), 'AWS');
      expect(ArchitecturePath.storageTierForSegment('L3_AWS_HOT'), 'hot');
    });

    test('rejects unknown provider tokens', () {
      expect(ArchitecturePath.providerForSegment('L3_hot_UNKNOWN'), isNull);
    });

    test('builds provider map without treating storage tier as provider', () {
      expect(
        ArchitecturePath.layerProviders([
          'L1_AWS',
          'L2_AZURE',
          'L3_AWS_HOT',
          'L4_GCP',
        ]),
        {'L1': 'AWS', 'L2': 'AZURE', 'L3': 'AWS', 'L4': 'GCP'},
      );
    });
  });
}
