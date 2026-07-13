import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/models/cloud_access_inventory.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/models/pricing_refresh_run.dart';
import 'package:twin2multicloud_flutter/providers/twins_provider.dart';
import 'package:twin2multicloud_flutter/screens/pricing_review/pricing_review_screen.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;

  setUp(() {
    api = MockApiService();
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
  });

  testWidgets('removes the Twin selector and confirms the exact account', (
    tester,
  ) async {
    await tester.pumpWidget(_screen(api));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Twin used for provider credentials'),
      findsNothing,
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Refresh'));
    await tester.pumpAndSettle();

    expect(find.text('Refresh AWS pricing?'), findsOneWidget);
    expect(
      find.text('Pricing will be fetched using Account 123456789012.'),
      findsOneWidget,
    );
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    verifyNever(
      () => api.startPricingRefresh(
        any(),
        connectionId: any(named: 'connectionId'),
      ),
    );
  });

  testWidgets('forwards the confirmed account connection exactly once', (
    tester,
  ) async {
    when(
      () => api.startPricingRefresh('aws', connectionId: 'aws-1'),
    ).thenAnswer((_) async => _failedRun());
    await tester.pumpWidget(_screen(api));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilledButton, 'Refresh'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Refresh').last);
    await tester.pumpAndSettle();

    verify(
      () => api.startPricingRefresh('aws', connectionId: 'aws-1'),
    ).called(1);
  });
}

Widget _screen(ApiService api) => ProviderScope(
  overrides: [apiServiceProvider.overrideWithValue(api)],
  child: const MaterialApp(home: PricingReviewScreen()),
);

PricingHealthResponse _health() => PricingHealthResponse.fromJson({
  'providers': {
    'aws': {
      'provider': 'aws',
      'state': 'stale',
      'severity': 'warning',
      'can_calculate': true,
      'pricing_freshness': 'stale',
      'primary_message': 'Pricing data should be refreshed.',
      'credential_summary': {},
    },
  },
});

CloudAccessInventory _access() => CloudAccessInventory.fromJson({
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
        'provider': 'gcp',
        'purpose': 'pricing',
        'scope': 'user',
        'identity_label': 'GCP Pricing',
        'status': 'missing',
      },
    },
  },
});

PricingRefreshRun _failedRun() => PricingRefreshRun.fromJson({
  'refresh_run_id': 'run-failed',
  'provider': 'aws',
  'status': 'failed',
  'credential_summary': {'scope': 'user'},
  'error_message': 'Provider rejected the request.',
  'created_at': '2026-07-11T10:00:00Z',
});
