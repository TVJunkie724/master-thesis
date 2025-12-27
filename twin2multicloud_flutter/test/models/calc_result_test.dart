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
    });

    group('totalCost', () {
      test('sums costs from cheapest path correctly', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);
        final total = result.totalCost;
        
        // L1_AWS (10.50) + L2_GCP (7.00) + L3 GCP tiers (1.8+0.9+0.4) + 
        // L4_AWS (15.0) + L5_AWS (20.0) + transfers (0.05+0.02)
        // = 10.5 + 7 + 3.1 + 15 + 20 + 0.07 = 55.67
        expect(total, closeTo(55.67, 0.1));
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
            'awsCosts': <String, dynamic>{'L1': <String, dynamic>{'cost': 10.0, 'components': <String, dynamic>{}}},
            'azureCosts': <String, dynamic>{'L1': <String, dynamic>{'cost': 12.0, 'components': <String, dynamic>{}}},
            'gcpCosts': <String, dynamic>{}, // Empty - GCP doesn't have L4/L5
            'cheapestPath': <String>['L1_AWS'],
          }
        };
        
        final result = CalcResult.fromJson(json);
        
        expect(result.gcpCosts.l1, isNull);
        expect(result.gcpCosts.l4, isNull);
        expect(result.gcpCosts.l5, isNull);
      });

      test('handles missing transferCosts', () {
        final json = <String, dynamic>{
          'result': <String, dynamic>{
            'awsCosts': <String, dynamic>{'L1': <String, dynamic>{'cost': 10.0, 'components': <String, dynamic>{}}},
            'azureCosts': <String, dynamic>{},
            'gcpCosts': <String, dynamic>{},
            'cheapestPath': <String>['L1_AWS'],
            // No transferCosts field
          }
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

    group('ProviderCosts.getLayer', () {
      test('returns correct layer by key', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);
        
        expect(result.awsCosts.getLayer('L1')?.cost, 10.50);
        expect(result.awsCosts.getLayer('L2')?.cost, 8.25);
        expect(result.awsCosts.getLayer('L3_HOT')?.cost, 2.0);
        expect(result.awsCosts.getLayer('L3_COOL')?.cost, 1.0);
        expect(result.awsCosts.getLayer('L3_ARCHIVE')?.cost, 0.5);
      });

      test('returns null for unknown layer', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);
        
        expect(result.awsCosts.getLayer('L99'), isNull);
      });

      test('handles case insensitive keys', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);
        
        expect(result.awsCosts.getLayer('l1'), isNotNull);
        expect(result.awsCosts.getLayer('L1'), isNotNull);
      });
    });
  });
}
