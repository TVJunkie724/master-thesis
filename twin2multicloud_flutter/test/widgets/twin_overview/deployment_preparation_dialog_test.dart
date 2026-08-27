import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_readiness.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/deployment_preparation_dialog.dart';

void main() {
  testWidgets('requires explicit acknowledgement for an external-only plan', (
    tester,
  ) async {
    DeploymentPreparationRequest? result;
    await tester.pumpWidget(
      _dialogHost(
        plan: _plan(manualOnly: true),
        onResult: (value) => result = value,
      ),
    );

    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    final confirm = tester.widget<FilledButton>(
      find.byKey(const Key('confirm-deployment-preparation')),
    );
    expect(confirm.onPressed, isNull);

    await tester.tap(
      find.byKey(const ValueKey('manual-preparation-manual:marketplace')),
    );
    await tester.pump();
    await tester.tap(find.text('Confirm preparation'));
    await tester.pumpAndSettle();

    expect(result?.planDigest, _planDigest);
    expect(result?.manualRequirementIds, ['manual:marketplace']);
  });

  testWidgets('describes persistent automatic changes before confirmation', (
    tester,
  ) async {
    await tester.pumpWidget(_dialogHost(plan: _plan(), onResult: (_) {}));

    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();

    expect(find.text('Automatic changes'), findsOneWidget);
    expect(
      find.textContaining('persist after this Twin is destroyed'),
      findsOneWidget,
    );
    expect(
      find.textContaining('Enable Google Cloud project API'),
      findsOneWidget,
    );
    final confirm = tester.widget<FilledButton>(
      find.byKey(const Key('confirm-deployment-preparation')),
    );
    expect(confirm.onPressed, isNotNull);
  });
}

Widget _dialogHost({
  required DeploymentPreparationPlan plan,
  required ValueChanged<DeploymentPreparationRequest?> onResult,
}) {
  return MaterialApp(
    home: Scaffold(
      body: Builder(
        builder: (context) => FilledButton(
          onPressed: () async {
            onResult(
              await showDialog<DeploymentPreparationRequest>(
                context: context,
                builder: (_) => DeploymentPreparationDialog(plan: plan),
              ),
            );
          },
          child: const Text('Open'),
        ),
      ),
    ),
  );
}

DeploymentPreparationPlan _plan({bool manualOnly = false}) {
  return DeploymentPreparationPlan(
    graphDigest: _graphDigest,
    requirementsDigest: _requirementsDigest,
    planDigest: _planDigest,
    actions: manualOnly
        ? const []
        : const [
            AccountPreparationAction(
              actionId: 'gcp:enable:serviceusage.googleapis.com',
              provider: CloudProvider.gcp,
              actionType: 'enable_project_api',
              capabilityId: 'serviceusage.googleapis.com',
              scope: 'project',
              requirementIds: ['gcp:serviceusage.googleapis.com'],
              reason: 'Required by the resolved deployment graph.',
            ),
          ],
    manualRequirements: const [
      ManualPreparationRequirement(
        requirementId: 'manual:marketplace',
        provider: CloudProvider.azure,
        capabilityId: 'marketplace_terms',
        reason: 'Accept the external marketplace terms.',
      ),
    ],
  );
}

const _graphDigest =
    'sha256:1111111111111111111111111111111111111111111111111111111111111111';
const _requirementsDigest =
    'sha256:2222222222222222222222222222222222222222222222222222222222222222';
const _planDigest =
    'sha256:3333333333333333333333333333333333333333333333333333333333333333';
