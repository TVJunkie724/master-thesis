import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';
import 'package:twin2multicloud_flutter/widgets/results/resolved_deployment_summary.dart';

void main() {
  testWidgets('renders every Six-layer selection and collapsed evidence', (
    tester,
  ) async {
    final run = _run(deploymentReady: true, selected: true);
    final specification =
        run.specification! as ResolvedDeploymentSpecificationV2;

    await _pumpSummary(tester, run: run, width: 1000);

    expect(find.textContaining('8 architecture responsibilities'), findsOne);
    for (final selection in specification.componentSelections) {
      expect(find.text(selection.implementationComponentId), findsOneWidget);
    }
    expect(find.text('Show technical evidence'), findsOneWidget);
    expect(find.text(specification.digest), findsNothing);
    expect(find.textContaining('resource_count'), findsNothing);

    await tester.ensureVisible(find.text('Show technical evidence'));
    await tester.tap(find.text('Show technical evidence'));
    await tester.pumpAndSettle();

    expect(find.text(specification.digest), findsOneWidget);
    expect(find.textContaining('resource_count'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('wraps long resolved values at narrow desktop width', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(480, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await _pumpSummary(tester, run: _run(deploymentReady: false), width: 480);

    expect(find.text('Resolved cloud resources'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('future specification is inspectable but not deployable', (
    tester,
  ) async {
    final specification = _fixture()
      ..['schema_version'] = 'resolved-deployment-specification.v3';
    specification['digest'] =
        ResolvedDeploymentSpecificationData.calculateDigest(specification);
    final run = _runFromSpecification(specification);

    await _pumpSummary(tester, run: run);

    expect(find.text('Specification version unsupported'), findsOneWidget);
    expect(find.text('Recalculate architecture'), findsOneWidget);
    expect(find.text('Live capacity evidence pending'), findsNothing);
  });

  testWidgets('failed deployment-ready selection exposes one bounded retry', (
    tester,
  ) async {
    var retries = 0;
    final run = _run(deploymentReady: true);

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

  testWidgets('renders evaluation evidence and exact blocking gates', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final run = _run(deploymentReady: false);
    final specification =
        run.specification! as ResolvedDeploymentSpecificationV2;

    await _pumpSummary(tester, run: run, width: 1000);

    expect(find.text('Evaluation only — deployment blocked'), findsOneWidget);
    expect(find.text('Live capacity evidence pending'), findsOneWidget);
    for (final gate in specification.readiness.blockingGateIds) {
      expect(find.text('• $gate'), findsOneWidget);
    }
    expect(find.text('Verify'), findsNothing);
    expect(find.text('Retry'), findsNothing);
    expect(find.textContaining('8 architecture responsibilities'), findsOne);
    expect(tester.takeException(), isNull);
  });
}

Future<void> _pumpSummary(
  WidgetTester tester, {
  required OptimizerDeploymentRunData run,
  double width = 800,
}) => tester.pumpWidget(
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

OptimizerDeploymentRunData _run({
  required bool deploymentReady,
  bool selected = false,
}) {
  final specification = _fixture();
  if (deploymentReady) {
    specification['readiness'] = {
      'status': 'deployment_ready',
      'blocking_gate_ids': <String>[],
    };
    specification['digest'] =
        ResolvedDeploymentSpecificationData.calculateDigest(specification);
  }
  return _runFromSpecification(
    specification,
    selected: selected ? '2026-08-25T09:00:00Z' : null,
  );
}

OptimizerDeploymentRunData _runFromSpecification(
  Map<String, dynamic> specification, {
  String? selected,
}) => OptimizerDeploymentRunData.fromDetailJson({
  'id': specification['calculation_run_id'],
  'twin_id': 'twin-six-layer',
  'status': 'succeeded',
  'deployment_compatibility_status': 'ready',
  'deployment_specification_digest': specification['digest'],
  'deployment_specification_version': specification['schema_version'],
  'resolved_deployment_specification': specification,
  'selected_for_deployment_at': selected,
  'created_at': '2026-08-25T08:00:00Z',
});

Map<String, dynamic> _fixture() =>
    jsonDecode(
          File(
            '../contracts/resolved-deployment-specification/v2/fixtures/valid/'
            'six-layer-aws-azure-eventing-small.json',
          ).readAsStringSync(),
        )
        as Map<String, dynamic>;
