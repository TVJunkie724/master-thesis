// test/utils/twin_state_utils_test.dart
// Tests for TwinStateUtils.canEdit() covering all states and edge cases

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/utils/twin_state_utils.dart';

void main() {
  group('TwinStateUtils.canEdit', () {
    // ============================================
    // Happy Path - Editable States
    // ============================================

    test('canEdit_draft returns true', () {
      expect(TwinStateUtils.canEdit('draft'), isTrue);
    });

    test('canEdit_configured returns true', () {
      expect(TwinStateUtils.canEdit('configured'), isTrue);
    });

    test('canEdit_error returns true', () {
      expect(TwinStateUtils.canEdit('error'), isTrue);
    });

    test('canEdit_destroyed returns true', () {
      expect(TwinStateUtils.canEdit('destroyed'), isTrue);
    });

    // ============================================
    // Blocked States
    // ============================================

    test('canEdit_deployed returns false', () {
      expect(TwinStateUtils.canEdit('deployed'), isFalse);
    });

    test('canEdit_deploying returns false', () {
      expect(TwinStateUtils.canEdit('deploying'), isFalse);
    });

    test('canEdit_destroying returns false', () {
      expect(TwinStateUtils.canEdit('destroying'), isFalse);
    });

    // ============================================
    // Edge Cases
    // ============================================

    test('canEdit_null returns true (new twins)', () {
      // New twins have null state, should be editable
      expect(TwinStateUtils.canEdit(null), isTrue);
    });

    test('canEdit_unknown fails closed', () {
      expect(TwinStateUtils.canEdit('unknown'), isFalse);
    });

    test('canEdit_caseInsensitive returns false for DEPLOYED', () {
      expect(TwinStateUtils.canEdit('DEPLOYED'), isFalse);
    });
  });
}
