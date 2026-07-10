import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';

import '../fixtures/test_fixtures.dart';

void main() {
  group('CalcResult', () {
    // ============================================================
    // Happy Path Tests
    // ============================================================

    group('fromJson', () {
      test('parses complete response with all providers', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);

        expect(result.awsCosts.l1, isNotNull);
        expect(result.azureCosts.l1, isNotNull);
        expect(result.gcpCosts.l1, isNotNull);
        expect(result.cheapestPath.length, 7);
      });

      test('parses layer costs correctly', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);

        expect(result.awsCosts.l1?.cost, 10.50);
        expect(result.awsCosts.l2?.cost, 8.25);
        expect(result.awsCosts.l3Hot?.cost, 2.0);
      });

      test('parses component breakdown', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);

        expect(result.awsCosts.l1?.components['IoT Core'], 5.0);
        expect(result.awsCosts.l1?.components['Lambda'], 5.5);
      });

      test('parses cheapest path', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);

        expect(result.cheapestPath.first, 'L1_AWS');
        expect(result.cheapestPath.contains('L2_GCP'), isTrue);
      });

      test('parses transfer costs', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);

        expect(result.transferCosts, isNotNull);
        expect(result.transferCosts?['L1_to_L2'], 0.05);
      });

      test('parses intent-to-result trace metadata', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);

        expect(result.traceSchemaVersion, 'intent-result-trace.v1');
        expect(result.optimizationProfile?.profileId, 'cost_minimization_v1');
        expect(result.intentTrace, isNotNull);
        expect(result.intentTrace?.schemaVersion, 'intent-result-trace.v1');
        expect(
          result.intentTrace?.profile?.scoringStrategyId,
          'min_total_cost_v1',
        );
        expect(result.intentTrace?.summary.recordCount, 1);
        expect(result.intentTrace?.summary.publishable, isTrue);
        expect(result.intentTrace?.records.single.selected, isTrue);
        expect(
          result.intentTrace?.records.single.verification.evidenceReferenceId,
          startsWith('pricing_registry:'),
        );
        expect(result.intentTrace?.selectedPath.single.provider, 'AWS');
        expect(
          result.intentTrace?.transferTrace.single.sourceIntentId,
          'aws.transfer.egress',
        );
      });
    });

    group('totalCost', () {
      test('reads totalCost from backend JSON', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);

        // totalCost is now a stored field from the backend engine
        expect(result.totalCost, closeTo(55.67, 0.01));
      });

      test('includes transfer costs in total', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);

        // Total should be higher than just layer costs
        expect(result.totalCost, greaterThan(50));
      });
    });

    // ============================================================
    // Edge Case Tests
    // ============================================================

    group('null handling', () {
      test('handles empty GCP costs (L4/L5 not implemented)', () {
        final json = <String, dynamic>{
          'result': <String, dynamic>{
            'awsCosts': <String, dynamic>{
              'L1': <String, dynamic>{
                'cost': 10.0,
                'components': <String, dynamic>{},
              },
            },
            'azureCosts': <String, dynamic>{
              'L1': <String, dynamic>{
                'cost': 12.0,
                'components': <String, dynamic>{},
              },
            },
            'gcpCosts': <String, dynamic>{}, // Empty - GCP doesn't have L4/L5
            'cheapestPath': <String>['L1_AWS'],
          },
        };

        final result = CalcResult.fromJson(json);

        expect(result.gcpCosts.l1, isNull);
        expect(result.gcpCosts.l4, isNull);
        expect(result.gcpCosts.l5, isNull);
      });

      test('handles missing transferCosts', () {
        final json = <String, dynamic>{
          'result': <String, dynamic>{
            'awsCosts': <String, dynamic>{
              'L1': <String, dynamic>{
                'cost': 10.0,
                'components': <String, dynamic>{},
              },
            },
            'azureCosts': <String, dynamic>{},
            'gcpCosts': <String, dynamic>{},
            'cheapestPath': <String>['L1_AWS'],
            // No transferCosts field
          },
        };

        final result = CalcResult.fromJson(json);

        expect(result.transferCosts, isNull);
      });

      test('handles empty cheapestPath', () {
        final result = CalcResult.fromJson(TestFixtures.emptyCalcResultJson);

        expect(result.cheapestPath, isEmpty);
        expect(result.totalCost, 0.0);
      });
    });
  });
}
