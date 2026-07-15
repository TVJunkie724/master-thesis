import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';

import '../fixtures/test_fixtures.dart';

void main() {
  group('Twin', () {
    // ============================================================
    // Happy Path Tests
    // ============================================================

    group('fromJson', () {
      test('parses all fields correctly', () {
        final twin = Twin.fromJson(TestFixtures.draftTwinJson);

        expect(twin.id, 'twin-001');
        expect(twin.name, 'Test Twin');
        expect(twin.state, 'draft');
        expect(twin.providers, ['AWS', 'Azure']);
        expect(twin.createdAt, isNotNull);
        expect(twin.updatedAt, isNotNull);
        expect(twin.lastDeployedAt, isNull);
      });

      test('parses deployed twin with lastDeployedAt', () {
        final twin = Twin.fromJson(TestFixtures.deployedTwinJson);

        expect(twin.state, 'deployed');
        expect(twin.lastDeployedAt, isNotNull);
        expect(twin.providers.length, 3);
      });
    });

    group('state helpers', () {
      test('isDraft returns true for draft state', () {
        final twin = Twin.fromJson(TestFixtures.draftTwinJson);

        expect(twin.isDraft, isTrue);
        expect(twin.isDeployed, isFalse);
        expect(twin.isError, isFalse);
      });

      test('isDeployed returns true for deployed state', () {
        final twin = Twin.fromJson(TestFixtures.deployedTwinJson);

        expect(twin.isDraft, isFalse);
        expect(twin.isDeployed, isTrue);
        expect(twin.isError, isFalse);
      });

      test('isError returns true for error state', () {
        final twin = Twin.fromJson(TestFixtures.errorTwinJson);

        expect(twin.isDraft, isFalse);
        expect(twin.isDeployed, isFalse);
        expect(twin.isError, isTrue);
      });

      test('isConfigured returns true for configured state', () {
        final json = {...TestFixtures.draftTwinJson, 'state': 'configured'};
        final twin = Twin.fromJson(json);

        expect(twin.isConfigured, isTrue);
      });
    });

    // ============================================================
    // Edge Case Tests
    // ============================================================

    group('contract validation', () {
      test('rejects null required fields', () {
        expect(
          () => Twin.fromJson(TestFixtures.minimalTwinJson),
          throwsA(isA<FormatException>()),
        );
      });

      test('rejects unknown lifecycle state without leaking its value', () {
        final json = {...TestFixtures.draftTwinJson, 'state': 'secret-state'};

        expect(
          () => Twin.fromJson(json),
          throwsA(
            isA<FormatException>().having(
              (error) => error.message,
              'message',
              allOf(contains('state'), isNot(contains('secret-state'))),
            ),
          ),
        );
      });

      test('ignores unknown additive response fields', () {
        final twin = Twin.fromJson({
          ...TestFixtures.draftTwinJson,
          'future_metadata': {'version': 2},
        });

        expect(twin.id, 'twin-001');
      });

      test('rejects non-string provider entries', () {
        expect(
          () => Twin.fromJson({
            ...TestFixtures.draftTwinJson,
            'providers': ['AWS', 7],
          }),
          throwsA(isA<FormatException>()),
        );
      });
    });

    group('date parsing', () {
      test('parses ISO 8601 dates correctly', () {
        final twin = Twin.fromJson(TestFixtures.draftTwinJson);

        expect(twin.createdAt.year, 2025);
        expect(twin.createdAt.month, 12);
        expect(twin.createdAt.day, 27);
      });

      test('normalizes timestamp offsets to the same UTC instant', () {
        final twin = Twin.fromJson({
          ...TestFixtures.draftTwinJson,
          'created_at': '2025-12-27T11:00:00+01:00',
        });

        expect(twin.createdAt, DateTime.utc(2025, 12, 27, 10));
      });
    });
  });
}
