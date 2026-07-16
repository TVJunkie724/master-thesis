import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/supported_platforms.dart';

void main() {
  group('resolveSupportedAppPlatform', () {
    test('resolves Web before the host-oriented native platform', () {
      for (final platform in TargetPlatform.values) {
        expect(
          resolveSupportedAppPlatform(isWeb: true, nativePlatform: platform),
          SupportedAppPlatform.web,
        );
      }
    });

    test('supports every desktop target', () {
      const expected = {
        TargetPlatform.macOS: SupportedAppPlatform.macOS,
        TargetPlatform.windows: SupportedAppPlatform.windows,
        TargetPlatform.linux: SupportedAppPlatform.linux,
      };

      for (final entry in expected.entries) {
        expect(
          resolveSupportedAppPlatform(isWeb: false, nativePlatform: entry.key),
          entry.value,
        );
      }
    });

    test('rejects all unsupported native targets', () {
      for (final platform in [
        TargetPlatform.android,
        TargetPlatform.iOS,
        TargetPlatform.fuchsia,
      ]) {
        expect(
          resolveSupportedAppPlatform(isWeb: false, nativePlatform: platform),
          isNull,
        );
      }
    });
  });
}
