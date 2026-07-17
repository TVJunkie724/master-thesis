import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/pricing_catalog.dart';

import '../fixtures/test_fixtures.dart';

void main() {
  group('PricingCatalogContext', () {
    test(
      'parses exact provider references and normalizes timestamps to UTC',
      () {
        final json = TestFixtures.pricingCatalogContextJson;
        final catalogs = Map<String, dynamic>.from(json['catalogs'] as Map);
        json['catalogs'] = catalogs;
        catalogs['azure'] = {
          ...Map<String, dynamic>.from(catalogs['azure'] as Map),
          'fetchedAt': '2026-07-17T12:00:00+02:00',
        };

        final context = PricingCatalogContext.fromJson(json);

        expect(context.catalogs.keys.toSet(), CloudProvider.values.toSet());
        expect(
          context.reference(CloudProvider.azure).fetchedAt,
          DateTime.utc(2026, 7, 17, 10),
        );
        expect(
          context.reference(CloudProvider.aws).shortenedDigest,
          'sha256:aaaaaaaaaaaa...',
        );
        expect(
          context.reference(CloudProvider.aws).snapshotId,
          'pcs_641a2e9f34ad8cd8c1e51b16a96ed83f367a06b794d13aa87f647835cc33c0a6',
        );
        expect(
          context.reference(CloudProvider.aws).sourceSummary,
          'Reviewed baseline',
        );
      },
    );

    test('distinguishes provider provenance from calculation freshness', () {
      final json = TestFixtures.pricingCatalogContextJson;
      final catalogs = Map<String, dynamic>.from(json['catalogs'] as Map);
      json['catalogs'] = catalogs;
      final aws = Map<String, dynamic>.from(catalogs['aws'] as Map)
        ..['source'] = 'provider_api'
        ..['calculationSource'] = 'last_known_good';
      aws['snapshotId'] = buildPricingCatalogSnapshotId(
        provider: aws['provider'] as String,
        pricingRegion: aws['pricingRegion'] as String,
        providerSchemaVersion: aws['providerSchemaVersion'] as String,
        contractVersion: aws['contractVersion'] as String,
        registryVersion: aws['registryVersion'] as String,
        mappingVersions: List<String>.from(aws['mappingVersions'] as List),
        fetchedAt: DateTime.parse(aws['fetchedAt'] as String),
        contentDigest: aws['contentDigest'] as String,
        source: aws['source'] as String,
        reviewStatus: aws['reviewStatus'] as String,
      );
      catalogs['aws'] = aws;

      final reference = PricingCatalogContext.fromJson(
        json,
      ).reference(CloudProvider.aws);

      expect(reference.sourceSummary, 'Provider API · Last known good');
    });

    test('rejects missing, extra, and mismatched providers', () {
      final missing = TestFixtures.pricingCatalogContextJson;
      final missingCatalogs = Map<String, dynamic>.from(
        missing['catalogs'] as Map,
      )..remove('gcp');
      missing['catalogs'] = missingCatalogs;

      final extra = TestFixtures.pricingCatalogContextJson;
      final extraCatalogs = Map<String, dynamic>.from(extra['catalogs'] as Map)
        ..['other'] = Map<String, dynamic>.from(
          (extra['catalogs'] as Map)['aws'] as Map,
        );
      extra['catalogs'] = extraCatalogs;

      final mismatched = TestFixtures.pricingCatalogContextJson;
      final mismatchedCatalogs = Map<String, dynamic>.from(
        mismatched['catalogs'] as Map,
      );
      mismatched['catalogs'] = mismatchedCatalogs;
      mismatchedCatalogs['aws'] = {
        ...Map<String, dynamic>.from(mismatchedCatalogs['aws'] as Map),
        'provider': 'azure',
      };

      for (final malformed in [missing, extra, mismatched]) {
        expect(
          () => PricingCatalogContext.fromJson(malformed),
          throwsA(isA<FormatException>()),
        );
      }
    });

    test(
      'rejects malformed identity, digest, timestamp, and mutable state',
      () {
        final reference = Map<String, dynamic>.from(
          (TestFixtures.pricingCatalogContextJson['catalogs'] as Map)['aws']
              as Map,
        );
        final malformed = [
          {...reference, 'snapshotId': 'mutable'},
          {...reference, 'contentDigest': 'sha256:not-a-digest'},
          {...reference, 'fetchedAt': '2026-07-17T10:00:00'},
          {...reference, 'reviewStatus': 'review_required'},
          {...reference, 'publicationStatus': 'candidate'},
          {
            ...reference,
            'mappingVersions': ['z', 'a'],
          },
          {...reference, 'contractVersion': 'tampered'},
        ];

        for (final value in malformed) {
          expect(
            () => PricingCatalogReference.fromJson(value),
            throwsA(isA<FormatException>()),
          );
        }
      },
    );

    test('rejects unsupported additive fields at the strict boundary', () {
      final reference = Map<String, dynamic>.from(
        (TestFixtures.pricingCatalogContextJson['catalogs'] as Map)['aws']
            as Map,
      )..['futureField'] = true;

      expect(
        () => PricingCatalogReference.fromJson(reference),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
