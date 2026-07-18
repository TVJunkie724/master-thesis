import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';
import 'package:twin2multicloud_flutter/widgets/results/resolved_deployment_summary.dart';

void main() {
  testWidgets('renders every resolved component and keeps evidence collapsed', (
    tester,
  ) async {
    final run = _selectedRun();
    final specification =
        run.specification! as ResolvedDeploymentSpecificationV1;

    await _pumpSummary(tester, run: run);

    for (final slot in ResolvedDeploymentSlot.values.where(
      (item) => item.isArchitectureSlot,
    )) {
      final componentCount = specification.components
          .where((component) => component.slot == slot)
          .length;
      expect(find.text(slot.label), findsNWidgets(componentCount));
    }
    expect(find.text('Supporting runtime'), findsOneWidget);
    expect(find.text('Show technical evidence'), findsOneWidget);
    expect(find.text(run.specification!.digest), findsNothing);
    expect(find.textContaining('throughput'), findsNothing);

    await tester.ensureVisible(find.text('Show technical evidence'));
    await tester.tap(find.text('Show technical evidence'));
    await tester.pumpAndSettle();

    expect(find.text(run.specification!.digest), findsOneWidget);
    expect(find.textContaining('throughput'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('wraps long resolved values at narrow desktop width', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(480, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await _pumpSummary(tester, run: _selectedRun(), width: 480);

    expect(find.text('Resolved cloud resources'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('legacy state offers recalculation without component rows', (
    tester,
  ) async {
    final legacy = OptimizerDeploymentRunData.fromDetailJson({
      'id': 'legacy-run',
      'twin_id': 'twin-1',
      'status': 'succeeded',
      'deployment_compatibility_status': 'legacy_not_deployable',
      'deployment_specification_digest': null,
      'deployment_specification_version': null,
      'resolved_deployment_specification': null,
      'selected_for_deployment_at': null,
      'created_at': '2026-07-17T08:00:00Z',
    });
    var recalculations = 0;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ResolvedDeploymentSummary(
            review: ResolvedDeploymentReview.fromRun(legacy),
            isSelecting: false,
            onRetrySelection: null,
            onRecalculateArchitecture: () => recalculations += 1,
          ),
        ),
      ),
    );

    expect(find.text('Architecture recalculation required'), findsOneWidget);
    expect(find.text('Recalculate architecture'), findsOneWidget);
    await tester.tap(find.text('Recalculate architecture'));
    expect(recalculations, 1);
  });

  testWidgets('future specification is inspectable but not deployable', (
    tester,
  ) async {
    final specification = _fixture()
      ..['schema_version'] = 'resolved-deployment-specification.v2';
    specification['digest'] =
        ResolvedDeploymentSpecificationData.calculateDigest(specification);
    final run = OptimizerDeploymentRunData.fromDetailJson({
      'id': specification['calculation_run_id'],
      'twin_id': 'twin-1',
      'status': 'succeeded',
      'deployment_compatibility_status': 'ready',
      'deployment_specification_digest': specification['digest'],
      'deployment_specification_version': specification['schema_version'],
      'resolved_deployment_specification': specification,
      'selected_for_deployment_at': null,
      'created_at': '2026-07-17T08:00:00Z',
    });

    await _pumpSummary(tester, run: run);

    expect(find.text('Specification version unsupported'), findsOneWidget);
    expect(find.text('Recalculate architecture'), findsOneWidget);
    expect(find.text('Supporting runtime'), findsNothing);
  });

  testWidgets('failed selection exposes exactly one bounded retry', (
    tester,
  ) async {
    var retries = 0;
    final run = _selectedRun(selected: false);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: ResolvedDeploymentSummary(
              review: ResolvedDeploymentReview.fromRun(
                run,
                selectionFailed: true,
              ),
              isSelecting: false,
              onRetrySelection: () => retries += 1,
              onRecalculateArchitecture: () {},
            ),
          ),
        ),
      ),
    );

    expect(find.text('Retry'), findsOneWidget);
    await tester.tap(find.text('Retry'));
    expect(retries, 1);
  });
}

Future<void> _pumpSummary(
  WidgetTester tester, {
  required OptimizerDeploymentRunData run,
  double width = 800,
}) {
  return tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: SizedBox(
            width: width,
            child: ResolvedDeploymentSummary(
              review: ResolvedDeploymentReview.fromRun(run),
              isSelecting: false,
              onRetrySelection: null,
              onRecalculateArchitecture: () {},
            ),
          ),
        ),
      ),
    ),
  );
}

OptimizerDeploymentRunData _selectedRun({bool selected = true}) {
  final specification = _fixture();
  return OptimizerDeploymentRunData.fromDetailJson({
    'id': specification['calculation_run_id'],
    'twin_id': 'twin-1',
    'status': 'succeeded',
    'deployment_compatibility_status': 'ready',
    'deployment_specification_digest': specification['digest'],
    'deployment_specification_version': specification['schema_version'],
    'resolved_deployment_specification': specification,
    'selected_for_deployment_at': selected ? '2026-07-17T09:00:00Z' : null,
    'created_at': '2026-07-17T08:00:00Z',
  });
}

Map<String, dynamic> _fixture() {
  final file = File(
    '../twin2multicloud_backend/src/contracts/generated/'
    'resolved-deployment-specification/v1/fixtures/valid/mixed-providers.json',
  );
  return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
}
