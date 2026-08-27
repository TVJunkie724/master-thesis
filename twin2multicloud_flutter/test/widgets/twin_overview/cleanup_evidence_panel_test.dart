import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cleanup_evidence.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/cleanup_evidence_panel.dart';

void main() {
  testWidgets('shows complete provider proof and retained prerequisites', (
    tester,
  ) async {
    await _pump(
      tester,
      evidence: CleanupEvidence.fromJson(
        _completeEvidence()
          ..['retained_shared_prerequisites'] = [
            {
              'provider': 'azure',
              'requirement_type': 'resource_provider',
              'capability_id': 'Microsoft.DigitalTwins',
              'scope': 'subscription',
              'reason': 'persistent_account_prerequisite',
            },
          ],
      ),
    );

    expect(find.text('COMPLETE'), findsOneWidget);
    expect(find.text('Terraform state'), findsOneWidget);
    expect(find.text('AWS'), findsOneWidget);
    expect(find.text('Retained shared prerequisites'), findsOneWidget);
    expect(
      find.textContaining('account-level capabilities retained'),
      findsOneWidget,
    );
    expect(find.text('Residual failures'), findsNothing);
  });

  testWidgets('expands incomplete residual failure by default', (tester) async {
    final value = _completeEvidence()
      ..['status'] = 'incomplete'
      ..['providers'] = [
        {
          ...(_completeEvidence()['providers'] as List).single as Map,
          'post_destroy_inventory': 'residual',
          'residual_resource_count': 2,
        },
      ]
      ..['residual_failures'] = [
        {
          'scope': 'provider_inventory',
          'provider': 'aws',
          'reason': 'resources_remain',
        },
      ];

    await _pump(tester, evidence: CleanupEvidence.fromJson(value));

    expect(find.text('INCOMPLETE'), findsOneWidget);
    expect(find.text('Residual failures'), findsOneWidget);
    expect(
      find.text('AWS · provider inventory · resources remain'),
      findsOneWidget,
    );
  });

  testWidgets('labels dry-run evidence without claiming completion', (
    tester,
  ) async {
    final value = _completeEvidence()
      ..['status'] = 'dry_run'
      ..['terraform'] = {
        'destroy_status': 'dry_run',
        'observed_before_resource_count': 9,
        'post_destroy_inventory': 'not_run',
        'residual_resource_count': null,
      }
      ..['providers'] = <Object>[];

    await _pump(tester, evidence: CleanupEvidence.fromJson(value));

    expect(find.text('DRY RUN'), findsOneWidget);
    expect(find.text('COMPLETE'), findsNothing);
    expect(find.textContaining('not run'), findsOneWidget);
  });

  testWidgets('shows invalid and unavailable evidence honestly', (
    tester,
  ) async {
    await _pump(
      tester,
      evidence: null,
      errorMessage: 'Invalid cleanup evidence contract.',
    );
    expect(find.text('EVIDENCE INVALID'), findsOneWidget);
    expect(find.text('Invalid cleanup evidence contract.'), findsOneWidget);

    await _pump(tester, evidence: null);
    expect(find.text('UNAVAILABLE'), findsOneWidget);
    expect(
      find.textContaining('No persisted cleanup evidence'),
      findsOneWidget,
    );
  });

  for (final textScale in [1.5, 2.0]) {
    testWidgets(
      'keeps cleanup proof readable at compact ${(textScale * 100).toInt()} percent text',
      (tester) async {
        await _pump(
          tester,
          evidence: CleanupEvidence.fromJson(_completeEvidence()),
          width: 640,
          textScale: textScale,
        );

        expect(find.text('COMPLETE'), findsOneWidget);
        expect(find.text('Terraform state'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}

Future<void> _pump(
  WidgetTester tester, {
  required CleanupEvidence? evidence,
  String? errorMessage,
  double width = 1200,
  double textScale = 1,
}) async {
  tester.view.physicalSize = Size(width, 1200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(
          context,
        ).copyWith(textScaler: TextScaler.linear(textScale)),
        child: child!,
      ),
      home: Scaffold(
        body: SingleChildScrollView(
          child: CleanupEvidencePanel(
            evidence: evidence,
            errorMessage: errorMessage,
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Map<String, dynamic> _completeEvidence() => {
  'schema_version': 'cleanup-evidence.v1',
  'status': 'complete',
  'terraform': {
    'destroy_status': 'completed',
    'observed_before_resource_count': 9,
    'post_destroy_inventory': 'empty',
    'residual_resource_count': 0,
  },
  'providers': [
    {
      'provider': 'aws',
      'cleanup_status': 'completed',
      'discovered_during_cleanup_count': 4,
      'discovered_resource_kinds': ['Cloud Functions'],
      'post_destroy_inventory': 'empty',
      'residual_resource_count': 0,
    },
  ],
  'retained_shared_prerequisites': <Object>[],
  'residual_failures': <Object>[],
};
