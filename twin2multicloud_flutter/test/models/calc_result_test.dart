import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';

import '../fixtures/test_fixtures.dart';

void main() {
  test('LayerCost preserves explicit unsupported contract metadata', () {
    final layer = LayerCost.fromJson({
      'cost': 0,
      'components': <String, dynamic>{},
      'supported': false,
      'unsupportedReason': 'Provider path is not implemented.',
    });

    expect(layer.supported, isFalse);
    expect(layer.unsupportedReason, 'Provider path is not implemented.');
  });

  test('LayerCost rejects unsupported results without a reason', () {
    expect(
      () => LayerCost.fromJson({
        'cost': 0,
        'components': <String, dynamic>{},
        'supported': false,
      }),
      throwsFormatException,
    );

    expect(
      () => LayerCost(cost: 0, components: const {}, supported: false),
      throwsArgumentError,
    );
  });

  test('parses detailed pricing field trace records', () {
    final result = CalcResult.fromJson({
      'totalCost': 1,
      'awsCosts': <String, dynamic>{},
      'azureCosts': <String, dynamic>{},
      'gcpCosts': <String, dynamic>{},
      'cheapestPath': <String>[],
      'inputParamsUsed': <String, dynamic>{},
      'resultTraceSchemaVersion': 'intent-to-result-trace.v1',
      'resultTrace': [
        {
          'trace_id': 'aws.iot.message_ingest.L1.v1',
          'provider': 'aws',
          'layer': 'iot',
          'service': 'AWSIoT',
          'intent_id': 'iot.message_ingest',
          'formula_ref': 'tiered_unit_cost',
          'source_type': 'provider_api',
          'selected_evidence_id': 'aws.iot.mapping',
          'selection_status': 'selected',
          'cost_contribution': 1,
          'cost_contribution_scope': 'component_total',
          'cost_contribution_is_additive': false,
          'result_component_key': 'iot_core',
          'output_metric_unit': 'USD/month',
          'verification_status': 'passed',
          'alternative_record_ids': ['azure.iot'],
          'rejected_evidence_ids': <String>[],
        },
      ],
    });

    expect(result.fieldTraceSchemaVersion, 'intent-to-result-trace.v1');
    expect(result.fieldTraceRecords, hasLength(1));
    expect(result.fieldTraceRecords.single.isSelected, isTrue);
    expect(result.fieldTraceRecords.single.costContributionIsAdditive, isFalse);
  });

  test('keeps historical field trace records readable', () {
    final result = CalcResult.fromJson({
      'totalCost': 1,
      'awsCosts': <String, dynamic>{},
      'azureCosts': <String, dynamic>{},
      'gcpCosts': <String, dynamic>{},
      'cheapestPath': <String>[],
      'inputParamsUsed': <String, dynamic>{},
      'resultTraceSchemaVersion': 'intent-to-result-trace.v1',
      'resultTrace': [
        {
          'trace_id': 'aws.iot.message_ingest.L1.v1',
          'provider': 'aws',
          'layer': 'iot',
          'service': 'AWSIoT',
          'intent_id': 'iot.message_ingest',
          'formula_ref': 'tiered_unit_cost',
          'source_type': 'provider_api',
          'cost_contribution': 1,
          'verification_status': 'passed',
        },
      ],
    });

    final record = result.fieldTraceRecords.single;
    expect(record.selectionStatus, 'not_applicable');
    expect(record.costContributionScope, 'legacy_unspecified');
    expect(record.costContributionIsAdditive, isFalse);
  });

  group('CalcResult', () {
    group('exact transfer evidence', () {
      test('parses six exact routes, pools, tiers, and diagnostics', () {
        final result = CalcResult.fromJson(
          TestFixtures.calcResultWithTransferEvidenceJson,
        );

        expect(result.transferPricingContext?.routes, hasLength(6));
        expect(result.transferPricingContext?.pools, hasLength(2));
        expect(
          result.transferPricingContext?.routes
              .where((route) => route.isCrossProvider)
              .length,
          2,
        );
        expect(result.optimizationDiagnostics?.evaluatedPathCount, 972);
        expect(
          result.optimizationDiagnostics?.winningCandidateId,
          'aws|gcp|gcp|gcp|gcp|aws|aws',
        );
      });

      test('keeps historical results without transfer evidence readable', () {
        final result = CalcResult.fromJson(TestFixtures.calcResultJson);

        expect(result.transferPricingContext, isNull);
        expect(result.optimizationDiagnostics, isNull);
      });

      test('requires transfer context and diagnostics together', () {
        final json = _transferResultCopy();
        (json['result'] as Map).remove('optimizationDiagnostics');

        expect(() => CalcResult.fromJson(json), throwsFormatException);
      });

      test('rejects unsupported versions and incomplete route sets', () {
        final wrongVersion = _transferResultCopy();
        ((wrongVersion['result'] as Map)['transferPricingContext']
                as Map)['schemaVersion'] =
            'complete-path-transfer-pricing.v2';
        expect(() => CalcResult.fromJson(wrongVersion), throwsFormatException);

        final missingRoute = _transferResultCopy();
        (((missingRoute['result'] as Map)['transferPricingContext']
                    as Map)['routes']
                as List)
            .removeLast();
        expect(() => CalcResult.fromJson(missingRoute), throwsFormatException);
      });

      test('rejects non-JSON numbers and inconsistent route arithmetic', () {
        final numericString = _transferResultCopy();
        final route = _firstTransferRoute(numericString);
        route['volumeBytes'] = '1000000000';
        expect(() => CalcResult.fromJson(numericString), throwsFormatException);

        final fractionalBytes = _transferResultCopy();
        _firstTransferRoute(fractionalBytes)['volumeBytes'] = 1000000000.5;
        expect(
          () => CalcResult.fromJson(fractionalBytes),
          throwsFormatException,
        );

        final invalidCost = _transferResultCopy();
        _firstTransferRoute(invalidCost)['totalCost'] = 1;
        expect(() => CalcResult.fromJson(invalidCost), throwsFormatException);

        final roundedMismatch = _transferResultCopy();
        ((roundedMismatch['result'] as Map)['optimizationDiagnostics']
                as Map)['winningScore'] =
            55.675;
        expect(
          () => CalcResult.fromJson(roundedMismatch),
          throwsFormatException,
        );
      });

      test('rejects route, pool, catalog, and solver inconsistencies', () {
        final wrongRegion = _transferResultCopy();
        (_firstTransferRoute(wrongRegion)['source'] as Map)['region'] =
            'europe-west1';
        expect(() => CalcResult.fromJson(wrongRegion), throwsFormatException);

        final danglingPool = _transferResultCopy();
        _firstTransferRoute(danglingPool)['poolId'] = 'pool:missing:test';
        expect(() => CalcResult.fromJson(danglingPool), throwsFormatException);

        final invalidCounts = _transferResultCopy();
        ((invalidCounts['result'] as Map)['optimizationDiagnostics']
                as Map)['evaluatedPathCount'] =
            971;
        expect(() => CalcResult.fromJson(invalidCounts), throwsFormatException);
      });

      test('contract errors never echo unknown field names or values', () {
        const secret = 'SHOULD_NOT_LEAK';
        final json = _transferResultCopy();
        ((json['result'] as Map)['transferPricingContext'] as Map)[secret] =
            secret;

        try {
          CalcResult.fromJson(json);
          fail('Expected a strict shape failure.');
        } on FormatException catch (error) {
          expect(error.message, isNot(contains(secret)));
        }
      });
    });

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

Map<String, dynamic> _transferResultCopy() =>
    jsonDecode(jsonEncode(TestFixtures.calcResultWithTransferEvidenceJson))
        as Map<String, dynamic>;

Map<String, dynamic> _firstTransferRoute(Map<String, dynamic> json) =>
    ((((json['result'] as Map)['transferPricingContext'] as Map)['routes']
                    as List)
                .first
            as Map)
        .cast<String, dynamic>();
