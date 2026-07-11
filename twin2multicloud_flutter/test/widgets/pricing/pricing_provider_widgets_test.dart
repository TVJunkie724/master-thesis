import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_access_inventory.dart';
import 'package:twin2multicloud_flutter/models/pricing_candidate_review.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/widgets/pricing/pricing_candidate_review_panel.dart';
import 'package:twin2multicloud_flutter/widgets/pricing/pricing_provider_selector.dart';
import 'package:twin2multicloud_flutter/widgets/pricing/pricing_provider_workspace.dart';

void main() {
  testWidgets('wide provider selector shows status and changes provider', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    String? selected;

    await tester.pumpWidget(
      _app(
        PricingProviderSelector(
          selectedProvider: 'aws',
          pricingHealth: PricingHealthResponse.fromJson({
            'providers': {
              'aws': {'state': 'review_required', 'credential_summary': {}},
              'azure': {'state': 'fresh', 'credential_summary': {}},
              'gcp': {'state': 'missing', 'credential_summary': {}},
            },
          }),
          onSelected: (provider) => selected = provider,
        ),
      ),
    );

    expect(find.text('AWS, Review'), findsOneWidget);
    await tester.tap(find.text('AZURE, Fresh'));
    expect(selected, 'azure');
    expect(tester.takeException(), isNull);
  });

  testWidgets('compact provider selector remains within the viewport', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(420, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      _app(
        PricingProviderSelector(
          selectedProvider: 'aws',
          pricingHealth: PricingHealthResponse.fromJson({
            'providers': {
              'aws': {'state': 'review_required', 'credential_summary': {}},
              'azure': {'state': 'fresh', 'credential_summary': {}},
              'gcp': {'state': 'missing', 'credential_summary': {}},
            },
          }),
          onSelected: (_) {},
        ),
      ),
    );

    expect(tester.takeException(), isNull);
  });

  testWidgets('compact workspace stacks its action without overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(420, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      _app(
        PricingProviderWorkspace(
          provider: 'aws',
          health: null,
          access: _access().pricingFor('aws'),
          isLoading: false,
          isRefreshing: false,
          canRefresh: true,
          error: null,
          reportError: null,
          onRefresh: () {},
          onRetry: () {},
        ),
      ),
    );

    expect(find.text('Refresh'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('missing account access disables refresh with guidance', (
    tester,
  ) async {
    await tester.pumpWidget(
      _app(
        PricingProviderWorkspace(
          provider: 'gcp',
          health: null,
          access: _access(gcpMissing: true).pricingFor('gcp'),
          isLoading: false,
          isRefreshing: false,
          canRefresh: false,
          error: null,
          reportError: null,
          onRefresh: () {},
          onRetry: () {},
        ),
      ),
    );

    expect(
      find.text('Configure pricing access in Profile to refresh.'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Refresh'))
          .onPressed,
      isNull,
    );
  });

  testWidgets('Azure identifies its public pricing source', (tester) async {
    await tester.pumpWidget(
      _app(
        PricingProviderWorkspace(
          provider: 'azure',
          health: null,
          access: _access().pricingFor('azure'),
          isLoading: false,
          isRefreshing: false,
          canRefresh: true,
          error: null,
          reportError: null,
          onRefresh: () {},
          onRetry: () {},
        ),
      ),
    );

    expect(find.textContaining('Azure Retail Prices API'), findsOneWidget);
  });

  testWidgets('candidate and trace details are progressively disclosed', (
    tester,
  ) async {
    var traceRequests = 0;
    await tester.pumpWidget(
      _app(
        PricingCandidateReviewPanel(
          reports: [_report()],
          selectedCandidateIds: const {'report-1': 'candidate-1'},
          tracesByReportId: const {},
          traceErrorsByReportId: const {},
          loadingTraceReportIds: const {},
          savingDecisionReportIds: const {},
          decisionsByReportId: const {},
          onCandidateSelected: (_, _) {},
          onTraceRequested: (_) => traceRequests++,
          onDecisionRequested: (_, _) {},
        ),
      ),
    );

    expect(find.text('iot.message_ingest'), findsNothing);
    await tester.tap(find.text('Review results (1)'));
    await tester.pumpAndSettle();
    expect(find.text('iot.message_ingest'), findsOneWidget);

    await tester.tap(find.text('iot.message_ingest'));
    await tester.pumpAndSettle();
    expect(find.text('Intent and matching trace'), findsOneWidget);
    expect(find.textContaining('0.01 USD message'), findsOneWidget);

    await tester.tap(find.text('Intent and matching trace'));
    await tester.pumpAndSettle();
    expect(traceRequests, 1);
  });
}

Widget _app(Widget child) => MaterialApp(
  home: Scaffold(
    body: SingleChildScrollView(
      child: Padding(padding: const EdgeInsets.all(16), child: child),
    ),
  ),
);

CloudAccessInventory _access({bool gcpMissing = false}) =>
    CloudAccessInventory.fromJson({
      'providers': {
        'aws': {
          'provider': 'aws',
          'pricing': {
            'connection_id': 'aws-1',
            'provider': 'aws',
            'purpose': 'pricing',
            'scope': 'user',
            'identity_label': 'AWS Pricing',
            'status': 'active',
            'provider_account_id': '123456789012',
          },
        },
        'azure': {
          'provider': 'azure',
          'pricing': {
            'provider': 'azure',
            'purpose': 'pricing',
            'scope': 'public',
            'identity_label': 'Azure Retail Prices API',
            'status': 'active',
          },
        },
        'gcp': {
          'provider': 'gcp',
          'pricing': {
            'connection_id': gcpMissing ? null : 'gcp-1',
            'provider': 'gcp',
            'purpose': 'pricing',
            'scope': 'user',
            'identity_label': 'GCP Pricing',
            'status': gcpMissing ? 'missing' : 'active',
          },
        },
      },
    });

PricingCandidateReport _report() => PricingCandidateReport.fromJson({
  'report_id': 'report-1',
  'provider': 'aws',
  'refresh_run_id': 'run-1',
  'intent_id': 'iot.message_ingest',
  'deterministic_selection': {
    'candidate_id': 'candidate-1',
    'selectable': true,
  },
  'ai_suggestion': {'enabled': false},
  'candidates': [
    {
      'candidate_id': 'candidate-1',
      'source_type': 'provider_api',
      'field_path': 'pricing.message',
      'value': 0.01,
      'currency': 'USD',
      'unit': 'message',
      'source_label': 'Provider API',
    },
  ],
  'review_state': 'ready',
  'created_at': '2026-07-11T10:00:00Z',
});
