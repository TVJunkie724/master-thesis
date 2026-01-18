// test/bloc/wizard/helpers/calculation_helper_test.dart
// Tests for CalculationHelper utility functions

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/helpers/calculation_helper.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';

// Simple factory for test CalcResults
CalcResult _createCalcResult({
  required List<String> cheapestPath,
  InputParamsUsed? inputParams,
}) {
  return CalcResult(
    awsCosts: ProviderCosts(),
    azureCosts: ProviderCosts(),
    gcpCosts: ProviderCosts(),
    cheapestPath: cheapestPath,
    inputParamsUsed: inputParams ?? const InputParamsUsed(),
  );
}

void main() {
  group('CalculationHelper', () {
    group('listEquals', () {
      test('returns true for identical lists', () {
        expect(CalculationHelper.listEquals([1, 2, 3], [1, 2, 3]), true);
      });
      
      test('returns false for different lengths', () {
        expect(CalculationHelper.listEquals([1, 2], [1, 2, 3]), false);
      });
      
      test('returns false for different elements', () {
        expect(CalculationHelper.listEquals([1, 2, 3], [1, 3, 2]), false);
      });
      
      test('returns true for empty lists', () {
        expect(CalculationHelper.listEquals([], []), true);
      });
      
      test('handles string lists', () {
        expect(CalculationHelper.listEquals(['a', 'b'], ['a', 'b']), true);
        expect(CalculationHelper.listEquals(['a', 'b'], ['a', 'c']), false);
      });
    });
    
    group('extractProvidersFromPath', () {
      test('extracts simple layer providers', () {
        final path = ['L1_AWS', 'L2_AZURE', 'L4_GCP'];
        final providers = CalculationHelper.extractProvidersFromPath(path);
        
        expect(providers.contains('AWS'), true);
        expect(providers.contains('AZURE'), true);
        expect(providers.contains('GCP'), true);
      });
      
      test('extracts L3 storage tier providers', () {
        final path = ['L3_hot_AWS', 'L3_cool_AZURE'];
        final providers = CalculationHelper.extractProvidersFromPath(path);
        
        expect(providers.contains('AWS'), true);
        expect(providers.contains('AZURE'), true);
      });
      
      test('handles empty path', () {
        final providers = CalculationHelper.extractProvidersFromPath([]);
        expect(providers.isEmpty, true);
      });
      
      test('deduplicates providers', () {
        final path = ['L1_AWS', 'L2_AWS', 'L3_hot_AWS'];
        final providers = CalculationHelper.extractProvidersFromPath(path);
        
        expect(providers.length, 1);
        expect(providers.contains('AWS'), true);
      });
    });
    
    group('getUnconfiguredProviders', () {
      test('returns providers not in configured set', () {
        final path = ['L1_AWS', 'L2_AZURE'];
        final configured = {'AWS'};
        final unconfigured = CalculationHelper.getUnconfiguredProviders(path, configured);
        
        expect(unconfigured.contains('AZURE'), true);
        expect(unconfigured.contains('AWS'), false);
      });
      
      test('returns empty when all configured', () {
        final path = ['L1_AWS', 'L2_AZURE'];
        final configured = {'AWS', 'AZURE'};
        final unconfigured = CalculationHelper.getUnconfiguredProviders(path, configured);
        
        expect(unconfigured.isEmpty, true);
      });
      
      test('handles empty path', () {
        final configured = {'AWS'};
        final unconfigured = CalculationHelper.getUnconfiguredProviders([], configured);
        
        expect(unconfigured.isEmpty, true);
      });
    });
    
    group('calculationInvalidatesStep3', () {
      test('returns false for null old result', () {
        final newResult = _createCalcResult(cheapestPath: ['L1_AWS']);
        
        expect(CalculationHelper.calculationInvalidatesStep3(null, newResult), false);
      });
      
      test('returns true when cheapestPath changes', () {
        final oldResult = _createCalcResult(cheapestPath: ['L1_AWS']);
        final newResult = _createCalcResult(cheapestPath: ['L1_AZURE']);
        
        expect(CalculationHelper.calculationInvalidatesStep3(oldResult, newResult), true);
      });
      
      test('returns false when path unchanged', () {
        final params = const InputParamsUsed();
        final oldResult = _createCalcResult(
          cheapestPath: ['L1_AWS', 'L2_AWS'],
          inputParams: params,
        );
        final newResult = _createCalcResult(
          cheapestPath: ['L1_AWS', 'L2_AWS'],
          inputParams: params,
        );
        
        expect(CalculationHelper.calculationInvalidatesStep3(oldResult, newResult), false);
      });
      
      test('returns true when inputParamsUsed differ', () {
        final oldResult = _createCalcResult(
          cheapestPath: ['L1_AWS'],
          inputParams: const InputParamsUsed(useEventChecking: false),
        );
        final newResult = _createCalcResult(
          cheapestPath: ['L1_AWS'],
          inputParams: const InputParamsUsed(useEventChecking: true),
        );
        
        expect(CalculationHelper.calculationInvalidatesStep3(oldResult, newResult), true);
      });
    });
    
    group('extractProviderFromSegment', () {
      test('extracts provider from L1 segment', () {
        expect(CalculationHelper.extractProviderFromSegment('L1_AWS'), 'AWS');
      });
      
      test('extracts provider from L3 segment', () {
        expect(CalculationHelper.extractProviderFromSegment('L3_hot_AZURE'), 'AZURE');
      });
      
      test('returns null for invalid segment', () {
        expect(CalculationHelper.extractProviderFromSegment('invalid'), null);
      });
    });
  });
}
