import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_access_inventory.dart';
import 'package:twin2multicloud_flutter/models/pricing_candidate_review.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/models/pricing_refresh_run.dart';

void main() {
  group('CloudAccessInventory', () {
    test('parses account identity and refresh capability', () {
      final inventory = CloudAccessInventory.fromJson({
        'schema_version': 'cloud-access-inventory.v1',
        'providers': {
          'aws': {
            'provider': 'aws',
            'pricing': {
              'connection_id': 'connection-1',
              'provider': 'aws',
              'purpose': 'pricing',
              'scope': 'user',
              'identity_label': 'AWS Pricing',
              'status': 'active',
              'provider_account_id': '123456789012',
              'bound_twin_count': 2,
              'bound_twin_labels': ['Factory', 'Office'],
              'actions': ['validate', 'delete'],
            },
            'pricing_options': [
              {
                'connection_id': 'connection-2',
                'provider': 'aws',
                'purpose': 'pricing',
                'scope': 'user',
                'identity_label': 'AWS Pricing Alternative',
                'status': 'needs_validation',
                'is_default_for_pricing': false,
              },
            ],
            'deployment': [],
          },
        },
      });

      final pricing = inventory.pricingFor('AWS')!;
      expect(inventory.schemaVersion, 'cloud-access-inventory.v1');
      expect(pricing.connectionId, 'connection-1');
      expect(pricing.providerAccountId, '123456789012');
      expect(pricing.canRefreshPricing, isTrue);
      expect(pricing.boundTwinCount, 2);
      expect(pricing.boundTwinLabels, ['Factory', 'Office']);
      expect(
        inventory.providers['aws']!.pricingOptions.single.connectionId,
        'connection-2',
      );
    });

    test('handles missing and public access defensively', () {
      final missing = CloudAccessEntry.fromJson({
        'provider': 'gcp',
        'purpose': 'pricing',
        'scope': 'user',
        'identity_label': 'GCP access missing',
        'status': 'missing',
      });
      final public = CloudAccessEntry.fromJson({
        'provider': 'azure',
        'purpose': 'pricing',
        'scope': 'public',
        'identity_label': 'Azure Retail Prices API',
        'status': 'active',
      });

      expect(missing.canRefreshPricing, isFalse);
      expect(missing.boundTwinLabels, isEmpty);
      expect(public.canRefreshPricing, isTrue);
      expect(public.identityLabel, 'Azure Retail Prices API');
    });
  });

  group('PricingHealthResponse', () {
    test('parses provider health and credential summary', () {
      final response = PricingHealthResponse.fromJson({
        'schema_version': 'pricing-health.v1',
        'providers': {
          'gcp': {
            'provider': 'gcp',
            'state': 'review_required',
            'severity': 'warning',
            'review_required': true,
            'can_calculate': true,
            'calculation_source': 'last_known_good',
            'pricing_freshness': 'stale',
            'age': '9 days',
            'source_label': 'Project thesis-demo',
            'credential_summary': {
              'connection_id': 'gcp-1',
              'provider': 'gcp',
              'purpose': 'pricing',
              'scope': 'user',
              'identity_label': 'GCP Pricing',
              'status': 'active',
              'provider_project_id': 'thesis-demo',
            },
            'primary_message': 'Review pricing evidence.',
            'actions': ['open_pricing_review'],
          },
        },
      });

      final health = response.provider('GCP')!;
      expect(health.state, 'review_required');
      expect(health.credentialSummary.connectionId, 'gcp-1');
      expect(health.credentialSummary.providerProjectId, 'thesis-demo');
      expect(health.actions, ['open_pricing_review']);
    });

    test('uses safe defaults for unknown and empty payloads', () {
      final response = PricingHealthResponse.fromJson({
        'providers': {
          'aws': {
            'state': 'new_state',
            'credential_summary': <String, dynamic>{},
          },
        },
      });

      expect(response.provider('aws')!.state, 'new_state');
      expect(response.provider('aws')!.severity, 'error');
      expect(response.provider('azure'), isNull);
    });
  });

  group('PricingRefreshRun', () {
    test(
      'parses terminal run metadata without exposing credential payloads',
      () {
        final run = PricingRefreshRun.fromJson({
          'schema_version': 'pricing-refresh-run.v1',
          'refresh_run_id': 'run-1',
          'provider': 'aws',
          'status': 'succeeded',
          'credential_summary': {
            'connection_id': 'aws-1',
            'identity_label': 'AWS Pricing',
            'scope': 'user',
            'provider_account_id': '123456789012',
          },
          'force': true,
          'sse_url': '/optimizer/pricing-refresh/runs/run-1/stream',
          'result_summary': {'status': 'ok'},
          'created_at': '2026-07-11T10:00:00Z',
          'completed_at': '2026-07-11T10:03:00Z',
        });

        expect(run.succeeded, isTrue);
        expect(run.credentialSummary.providerAccountId, '123456789012');
        expect(run.completedAt, DateTime.parse('2026-07-11T10:03:00Z'));
        expect(run.resultSummary, {'status': 'ok'});
      },
    );

    test('parses immutable AWS TwinMaker account pricing context', () {
      final run = PricingRefreshRun.fromJson(
        _awsRefreshRunJson(
          currentPlan: {
            'mode': 'TIERED_BUNDLE',
            'billable_entity_count': 1001,
            'effective_at': '2026-07-17T10:00:00+02:00',
            'updated_at': '2026-07-17T08:00:00Z',
            'update_reason': 'Account plan update',
            'bundle': {
              'tier': 'TIER_2',
              'names': ['factory', 'warehouse'],
            },
          },
          pendingPlan: {
            'mode': 'STANDARD',
            'billable_entity_count': 1001,
            'effective_at': '2026-07-20T08:00:00Z',
            'updated_at': null,
            'update_reason': null,
            'bundle': null,
          },
        ),
      );

      final context = run.awsTwinMakerContext!;
      expect(
        context.schemaVersion,
        AwsTwinMakerPricingContext.supportedSchemaVersion,
      );
      expect(context.provider, 'aws');
      expect(context.service, 'iot_twinmaker');
      expect(context.region, 'eu-central-1');
      expect(context.verifiedAccountId, '123456789012');
      expect(context.observedAt, DateTime.parse('2026-07-17T08:00:00Z'));
      expect(
        context.currentPlan.mode,
        AwsTwinMakerPricingPlanMode.tieredBundle,
      );
      expect(context.currentPlan.billableEntityCount, 1001);
      expect(context.currentPlan.bundle!.tier, AwsTwinMakerBundleTier.tier2);
      expect(context.currentPlan.bundle!.names, ['factory', 'warehouse']);
      expect(context.pendingPlan!.mode, AwsTwinMakerPricingPlanMode.standard);
      expect(context.connectionId, 'aws-1');
      expect(
        () => context.currentPlan.bundle!.names.add('mutable'),
        throwsUnsupportedError,
      );
    });

    test('omits malformed optional AWS context without losing the run', () {
      final malformedContexts = [
        {'schema_version': 'unknown'},
        {..._awsAccountContext(), 'provider': 'azure'},
        {..._awsAccountContext(), 'observed_at': '2026-07-17T08:00:00'},
        {
          ..._awsAccountContext(),
          'current_plan': {..._standardPlan(), 'billable_entity_count': -1},
        },
        {
          ..._awsAccountContext(),
          'current_plan': {..._standardPlan(), 'mode': 'UNKNOWN'},
        },
        {
          ..._awsAccountContext(),
          'current_plan': {
            ..._standardPlan(),
            'bundle': {
              'tier': 'TIER_1',
              'names': ['invalid for standard'],
            },
          },
        },
        {
          ..._awsAccountContext(),
          'management_binding': {
            ..._managementBinding(),
            'pricing_connection_id': 'other-connection',
          },
        },
        {..._awsAccountContext(), 'verified_account_id': 123456789012},
        {
          ..._awsAccountContext(),
          'management_binding': {
            ..._managementBinding(),
            'pricing_connection_id': 123,
          },
        },
        {
          ..._awsAccountContext(),
          'current_plan': {..._standardPlan(), 'update_reason': 123},
        },
      ];

      for (final malformed in malformedContexts) {
        final json = _awsRefreshRunJson();
        (json['result_summary']
                as Map<String, dynamic>)['__account_pricing_context__'] =
            malformed;
        final run = PricingRefreshRun.fromJson(json);

        expect(run.refreshRunId, 'run-aws');
        expect(run.succeeded, isTrue);
        expect(run.awsTwinMakerContext, isNull);
        expect(run.resultSummary, isNotNull);
      }
    });

    test('rejects account context embedded in the wrong outer run', () {
      final wrongProvider = _awsRefreshRunJson()..['provider'] = 'azure';
      final wrongAccount = _awsRefreshRunJson();
      (wrongAccount['credential_summary']
              as Map<String, dynamic>)['provider_account_id'] =
          '999999999999';

      expect(
        PricingRefreshRun.fromJson(wrongProvider).awsTwinMakerContext,
        isNull,
      );
      expect(
        PricingRefreshRun.fromJson(wrongAccount).awsTwinMakerContext,
        isNull,
      );
    });

    test('parses failed run with defensive date fallback', () {
      final run = PricingRefreshRun.fromJson({
        'refresh_run_id': 'run-2',
        'provider': 'gcp',
        'status': 'failed',
        'credential_summary': {
          'identity_label': 'GCP Pricing',
          'scope': 'user',
        },
        'sse_url': '',
        'created_at': 'invalid',
        'error_code': 'OPTIMIZER_UNAVAILABLE',
        'error_message': 'Optimizer service is unavailable.',
      });

      expect(run.succeeded, isFalse);
      expect(run.createdAt.millisecondsSinceEpoch, 0);
      expect(run.errorCode, 'OPTIMIZER_UNAVAILABLE');
    });
  });

  group('Pricing candidate review contracts', () {
    test('parses reports, candidate values and AI suggestion', () {
      final list = PricingCandidateReportList.fromJson({
        'schema_version': 'pricing-candidate-report-list.v1',
        'provider': 'aws',
        'refresh_run_id': 'run-1',
        'reports': [
          {
            'schema_version': 'pricing-candidate-report.v1',
            'report_id': 'report-1',
            'provider': 'aws',
            'refresh_run_id': 'run-1',
            'intent_id': 'iot.message_ingest',
            'expected_model': 'tiered',
            'expected_unit': 'message',
            'deterministic_selection': {
              'candidate_id': 'candidate-1',
              'selectable': true,
              'confidence_label': 'exact',
            },
            'ai_suggestion': {
              'enabled': true,
              'candidate_id': 'candidate-2',
              'rationale': 'Semantic match',
            },
            'candidates': [
              {
                'candidate_id': 'candidate-1',
                'source_type': 'provider_api',
                'field_path': 'iot.price',
                'value': 0.000001,
                'currency': 'USD',
                'unit': 'message',
                'source_label': 'AWS Price List',
                'evidence_status': 'selected',
              },
            ],
            'rejected_candidates': [
              {
                'candidate_id': 'candidate-x',
                'reasons': ['unit mismatch'],
              },
            ],
            'review_state': 'ready',
            'source_status': 'quality_metadata',
            'created_at': '2026-07-11T10:00:00Z',
          },
        ],
      });

      final report = list.reports.single;
      expect(report.deterministicSelection.candidateId, 'candidate-1');
      expect(report.aiSuggestion.candidateId, 'candidate-2');
      expect(report.candidates.single.value, 0.000001);
      expect(report.candidates.single.value, 0.000001);
      expect(report.rejectedCandidates.single.reasons, ['unit mismatch']);
    });

    test('parses bounded sanitized trace and decision', () {
      final trace = PricingTrace.fromJson({
        'schema_version': 'pricing-trace.v1',
        'report_id': 'report-1',
        'provider': 'aws',
        'intent': {'intent_id': 'iot.message_ingest'},
        'query_scope': {'region': 'eu-central-1'},
        'selected_candidate': {'candidate_id': 'candidate-1'},
        'close_candidates': [
          {'candidate_id': 'candidate-2'},
        ],
        'rejected_candidates': [],
        'hard_checks': [
          {'check': 'unit', 'status': 'passed'},
        ],
        'normalization': {'factor': 1000000},
        'formula_ref': 'tiered_unit_cost',
        'sanitization': {
          'bounded': true,
          'secret_free': true,
          'omitted_raw_rows': 7,
        },
      });
      final decision = PricingReviewDecision.fromJson({
        'schema_version': 'pricing-review-decision.v1',
        'decision_id': 'decision-1',
        'report_id': 'report-1',
        'provider': 'aws',
        'intent_id': 'iot.message_ingest',
        'decision': 'approve',
        'selected_candidate_id': 'candidate-1',
        'created_at': '2026-07-11T10:05:00Z',
      });

      expect(trace.sanitization.bounded, isTrue);
      expect(trace.sanitization.secretFree, isTrue);
      expect(trace.sanitization.omittedRawRows, 7);
      expect(trace.closeCandidates.single['candidate_id'], 'candidate-2');
      expect(decision.selectedCandidateId, 'candidate-1');
      expect(decision.schemaVersion, 'pricing-review-decision.v1');
      expect(decision.createdAt, DateTime.parse('2026-07-11T10:05:00Z'));
    });

    test('handles empty reports and trace collections', () {
      final list = PricingCandidateReportList.fromJson({});
      final trace = PricingTrace.fromJson({
        'sanitization': <String, dynamic>{},
      });

      expect(list.reports, isEmpty);
      expect(trace.hardChecks, isEmpty);
      expect(trace.closeCandidates, isEmpty);
      expect(trace.sanitization.omittedRawRows, 0);
    });
  });
}

Map<String, dynamic> _awsRefreshRunJson({
  Map<String, dynamic>? currentPlan,
  Map<String, dynamic>? pendingPlan,
}) {
  return {
    'schema_version': 'pricing-refresh-run.v1',
    'refresh_run_id': 'run-aws',
    'provider': 'aws',
    'status': 'succeeded',
    'credential_summary': {
      'connection_id': 'aws-1',
      'identity_label': 'AWS Pricing',
      'scope': 'user',
      'provider_account_id': '123456789012',
    },
    'force': true,
    'sse_url': '/optimizer/pricing-refresh/runs/run-aws/stream',
    'result_summary': {
      'status': 'ok',
      '__account_pricing_context__': _awsAccountContext(
        currentPlan: currentPlan,
        pendingPlan: pendingPlan,
      ),
    },
    'created_at': '2026-07-17T08:00:00Z',
    'completed_at': '2026-07-17T08:03:00Z',
  };
}

Map<String, dynamic> _awsAccountContext({
  Map<String, dynamic>? currentPlan,
  Map<String, dynamic>? pendingPlan,
}) {
  return {
    'schema_version': 'aws-twinmaker-account-pricing-context.v1',
    'provider': 'aws',
    'service': 'iot_twinmaker',
    'region': 'eu-central-1',
    'verified_account_id': '123456789012',
    'catalog_snapshot_digest':
        'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'observed_at': '2026-07-17T08:00:00Z',
    'current_plan': currentPlan ?? _standardPlan(),
    'pending_plan': pendingPlan,
    'management_binding': _managementBinding(),
  };
}

Map<String, dynamic> _standardPlan() => {
  'mode': 'STANDARD',
  'billable_entity_count': 42,
  'effective_at': null,
  'updated_at': '2026-07-17T08:00:00Z',
  'update_reason': null,
  'bundle': null,
};

Map<String, dynamic> _managementBinding() => {
  'schema_version': 'aws-twinmaker-management-binding.v1',
  'pricing_connection_id': 'aws-1',
  'connection_fingerprint':
      'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  'verified_account_id': '123456789012',
  'configured_account_id': '123456789012',
};
